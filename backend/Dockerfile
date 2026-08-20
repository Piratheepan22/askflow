# backend/Dockerfile
FROM python:3.12-slim
WORKDIR /code
# Install dependencies first so Docker can cache this layer.
COPY requirements.txt .
# RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir \
    --default-timeout=300 \
    --retries 10 \
    -r requirements.txt
# Copy the application code.
COPY ./app ./app
# Start the API server, listening on all interfaces.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]