FROM python:3.11-slim

WORKDIR /app

# Dépendances système
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Code + frontend
COPY app.py .
COPY index.html .

# Port Hugging Face Spaces
EXPOSE 7860

CMD ["python", "app.py"]
