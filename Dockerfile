# syntax=docker/dockerfile:1.7
FROM node:24-bookworm-slim AS frontend-build
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN --mount=type=secret,id=proxy_ca,required=false \
    set -eu; \
    if [ -f /run/secrets/proxy_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/proxy_ca; fi; \
    npm ci --strict-ssl=true
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm AS runtime
ARG QYVORIQ_REVISION=unknown
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    QYVORIQ_ENV=production \
    QYVORIQ_REVISION=${QYVORIQ_REVISION}
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt requirements-lock.txt ./
RUN --mount=type=secret,id=proxy_ca,required=false \
    --mount=type=secret,id=system_ca,required=false \
    set -eu; \
    if [ -f /run/secrets/proxy_ca ]; then \
      if [ -f /run/secrets/system_ca ]; then cat /run/secrets/system_ca /run/secrets/proxy_ca > /tmp/qyvoriq-ca.pem; \
      else cat /etc/ssl/certs/ca-certificates.crt /run/secrets/proxy_ca > /tmp/qyvoriq-ca.pem; fi; \
      export PIP_CERT=/tmp/qyvoriq-ca.pem; \
    fi; \
    python -m pip install --no-cache-dir -r requirements.txt; \
    rm -f /tmp/qyvoriq-ca.pem
COPY backend/ ./backend/
COPY benchmarks/ ./benchmarks/
COPY examples/ ./examples/
COPY --from=frontend-build /build/frontend/dist ./frontend/dist
RUN chmod -R a+rX /app/backend /app/benchmarks /app/examples /app/frontend \
    && groupadd --system --gid 10001 qyvoriq \
    && useradd --system --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin qyvoriq
USER 10001:10001
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=60s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/health/ready', timeout=2)" || exit 1
CMD ["uvicorn", "backend.api:app", "--host", "0.0.0.0", "--port", "8080", "--no-proxy-headers"]
