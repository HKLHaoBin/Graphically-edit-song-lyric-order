# syntax=docker/dockerfile:1
FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps (optional, can be removed if not needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
 && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt ./
RUN pip install -r requirements.txt

# Copy app source
COPY app.py index.html ./

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
