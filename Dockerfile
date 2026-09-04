FROM python:3.11-slim

WORKDIR /app

# Install dependencies first for better layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code.
COPY . .

# Create the uploads directory used for local image storage.
RUN mkdir -p /app/uploads

ENV PYTHONUNBUFFERED=1
ENV ENVIRONMENT=production
ENV DB_ENGINE=mysql

EXPOSE 5000

# Production entrypoint. Override with `python app.py` for local dev if needed.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "app:app"]
