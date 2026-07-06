# FastAPI engine. Chromium serves two jobs: kaleido chart PNGs and
# headless print-to-pdf for exports. Build from the PROJECT ROOT:
#   docker build -f backend/Dockerfile -t datavisual-backend .
FROM python:3.12-slim

# Chromium + fonts (charts/PDF), plus WeasyPrint's native libs as the
# preferred PDF engine when available.
RUN apt-get update && apt-get install -y --no-install-recommends \
        chromium fonts-liberation \
        libpango-1.0-0 libpangocairo-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    BROWSER_PATH=/usr/bin/chromium

WORKDIR /app
COPY pyproject.toml ./
RUN pip install --no-cache-dir uv && uv pip install --system -r pyproject.toml
COPY backend ./backend

# All state lives here — mount a volume so it survives redeploys.
VOLUME /app/data
EXPOSE 8001
CMD ["python", "-m", "backend.main"]
