set -euo pipefail

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

step() { echo -e "${BLUE}$1${NC}"; }
ok()   { echo -e "   ${GREEN}✓${NC} $1"; }
warn() { echo -e "   ${YELLOW}⚠${NC}  $1"; }
die()  { echo -e "${RED}ERROR: $1${NC}"; exit 1; }

echo "============================================"
echo " ServiceRegistry — Istio Mesh Deployment"
echo "============================================"
echo

# ---- Prerequisites -------------------------------------------------------
step "1. Checking prerequisites..."
command -v minikube &>/dev/null || die "minikube not found. https://minikube.sigs.k8s.io/docs/start/"
command -v kubectl  &>/dev/null || die "kubectl not found. https://kubernetes.io/docs/tasks/tools/"
command -v docker   &>/dev/null || die "docker not found."
ok "All tools present"
echo

# ---- Minikube ------------------------------------------------------------
step "2. Starting Minikube (if not running)..."
if ! minikube status &>/dev/null 2>&1; then
    minikube start --memory=4096 --cpus=2
    ok "Minikube started"
else
    ok "Minikube already running"
fi
echo

# ---- Istio addon ---------------------------------------------------------
step "3. Enabling Istio addon..."
minikube addons enable istio-provisioner
minikube addons enable istio
ok "Istio addon enabled"
echo

# Wait for Istio control plane pods
step "4. Waiting for Istio control plane to be ready..."
kubectl wait --for=condition=ready pod \
    -l app=istiod \
    -n istio-system \
    --timeout=120s || warn "istiod not ready yet — continuing anyway"
ok "Istio control plane ready"
echo

# ---- Docker image --------------------------------------------------------
step "5. Building Docker image inside Minikube..."
eval "$(minikube docker-env)"
docker build -t service-registry:latest .
ok "Image built: service-registry:latest"
echo

# ---- Namespace -----------------------------------------------------------
step "6. Creating namespace with sidecar injection..."
kubectl apply -f k8s/istio/namespace.yaml
ok "Namespace 'service-mesh' ready (istio-injection=enabled)"
echo

# ---- Registry (plain k8s, no sidecar needed for registry itself) ---------
step "7. Deploying Service Registry into service-mesh namespace..."
# Patch the existing manifest to target the new namespace inline
kubectl apply -f k8s/registry-deployment.yaml -n service-mesh
ok "Registry deployed"
echo

step "8. Waiting for Registry to be ready..."
kubectl wait --for=condition=ready pod \
    -l app=service-registry \
    -n service-mesh \
    --timeout=60s
ok "Registry ready"
echo

# ---- Microservices -------------------------------------------------------
step "9. Deploying user-service (2 replicas) and payment-service..."
kubectl apply -f k8s/example-service-deployment.yaml -n service-mesh
ok "Services deployed"
echo

step "10. Waiting for user-service pods..."
kubectl wait --for=condition=ready pod \
    -l app=user-service \
    -n service-mesh \
    --timeout=90s
ok "user-service pods ready"
echo

# ---- Istio configs -------------------------------------------------------
step "11. Applying Istio Gateway, VirtualService, DestinationRule..."
kubectl apply -f k8s/istio/gateway.yaml
kubectl apply -f k8s/istio/virtual-service.yaml
kubectl apply -f k8s/istio/destination-rule.yaml
ok "Istio traffic policies applied"
echo

# ---- Summary -------------------------------------------------------------
MINIKUBE_IP=$(minikube ip)
INGRESS_PORT=$(kubectl -n istio-system get service istio-ingressgateway \
    -o jsonpath='{.spec.ports[?(@.name=="http2")].nodePort}' 2>/dev/null || echo "80")

echo "============================================"
echo -e "${GREEN}Deployment complete!${NC}"
echo "============================================"
echo
echo "Cluster pods (service-mesh namespace):"
kubectl get pods -n service-mesh
echo
echo "Istio resources:"
kubectl get gateway,virtualservice,destinationrule -n service-mesh
echo
echo "Access points:"
echo "  Registry (NodePort)  : http://$MINIKUBE_IP:30001"
echo "  Istio ingress        : http://$MINIKUBE_IP:$INGRESS_PORT"
echo
echo "Quick tests:"
echo "  curl http://$MINIKUBE_IP:30001/health"
echo "  curl http://$MINIKUBE_IP:30001/discover/user-service"
echo "  curl -H 'Host: user-service.local' http://$MINIKUBE_IP:$INGRESS_PORT/ping"
echo
echo "Watch Istio traffic (requires kiali addon):"
echo "  minikube addons enable kiali"
echo "  minikube service kiali -n istio-system"
echo
echo "Cleanup:"
echo "  kubectl delete namespace service-mesh"
echo "  minikube stop"
