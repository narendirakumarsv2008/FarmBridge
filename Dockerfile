# Farm Bridge — production-grade container image.
#
# Builds the Flask app and serves it with Gunicorn (no debug server).

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies first (better layer caching).
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy application code.
COPY . .

# Uploads are written at runtime (also mounted as a volume in compose).
RUN mkdir -p uploads

EXPOSE 5000

# Gunicorn: 4 workers, sane timeouts, bind to all interfaces.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--timeout", "120", "app:app"]
