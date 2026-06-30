# ========== BUILD STAGE ==========
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies (wheels)
COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt


# ========== RUNTIME STAGE ==========
FROM python:3.12-slim AS runtime

WORKDIR /app

# Only runtime deps (no gcc, no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 && \
    rm -rf /var/lib/apt/lists/*

# Copy pre-built wheels and requirements.txt from builder
COPY --from=builder /wheels /wheels
COPY --from=builder /build/requirements.txt .
RUN pip install --no-cache-dir --no-index --find-links /wheels -r requirements.txt && \
    rm -rf /wheels requirements.txt

# Copy application code
COPY . .

# Create data directory for olympiads.json mount
RUN mkdir -p /app/data

EXPOSE 8000

ENV PYTHONUNBUFFERED=1

HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=15s \
    CMD python -c "import urllib.request; exit(0 if urllib.request.urlopen('http://localhost:8000/health').getcode() == 200 else 1)"

CMD ["python", "entrypoint.py"]
