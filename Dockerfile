# Elastique CRM Backend - Cloud Run Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (build-essential sometimes needed for python libs)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download Spacy model (required by conversation_manager.py)
RUN python -m spacy download en_core_web_sm

# Copy application code
COPY server.py .
COPY services/ services/
COPY api/ api/
COPY data/ data/

# Ensure data directory is writable (SQLite and logs)
RUN chmod -R 777 /app/data

# Expose port
EXPOSE 8080

# Cloud Run uses PORT env variable - use shell to expand it properly or use python to read it
CMD ["python", "-c", "import os, uvicorn; from server import app; uvicorn.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))"]
