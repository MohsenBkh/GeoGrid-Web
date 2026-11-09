FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

WORKDIR /app

# gcc is only needed if a dependency has to be built from source; it costs
# a few MB of image size and avoids obscure build failures on some platforms.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p storage/uploads storage/outputs storage/db

EXPOSE 8000

# WEB_CONCURRENCY defaults to 1: a single uvicorn worker already serves all
# requests concurrently (conversions run in app/worker.py's thread pool), and
# on Render's free 512 MB instance a second worker only doubles memory use.
# On a bigger box set WEB_CONCURRENCY=2.
CMD gunicorn app.main:app \
    --workers "${WEB_CONCURRENCY:-1}" \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:"${PORT:-8000}" \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
