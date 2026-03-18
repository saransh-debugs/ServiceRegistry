FROM python:3.11-slim

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY service_registry_improved.py .
COPY example_service.py .
COPY microservice.py .
COPY client_demo.py .

# Expose port
EXPOSE 5001

# Run the registry by default
CMD ["python", "service_registry_improved.py"]