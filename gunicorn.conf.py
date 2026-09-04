"""
Gunicorn configuration for FarmBridge production deploys.

Used automatically when Gunicorn runs with:
    gunicorn -c gunicorn.conf.py app:app
"""

import multiprocessing
import os

# Render injects PORT. Gunicorn must bind to it (default 5000 for local/docker).
PORT = os.environ.get('PORT', '5000')

# Keep small for a student/startup deployment.
workers = int(os.environ.get('GUNICORN_WORKERS', max(1, multiprocessing.cpu_count())))
threads = int(os.environ.get('GUNICORN_THREADS', 4))
bind = '0.0.0.0:%s' % PORT
timeout = int(os.environ.get('GUNICORN_TIMEOUT', 60))
graceful_timeout = int(os.environ.get('GUNICORN_GRACEFUL_TIMEOUT', 30))

# Logs for Render / container runtime.
accesslog = '-'
errorlog = '-'
loglevel = os.environ.get('LOG_LEVEL', 'info')

# Do not run gunicorn as root on bare-metal unless necessary.
user = os.environ.get('GUNICORN_USER')
if user:
    globals()['user'] = user
