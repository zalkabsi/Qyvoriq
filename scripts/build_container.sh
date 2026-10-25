#!/usr/bin/env bash
set -euo pipefail

docker_args=(buildx build --load --tag qyvoriq:local)
has_proxy=0
for proxy_var in HTTP_PROXY HTTPS_PROXY NO_PROXY http_proxy https_proxy no_proxy; do
  proxy_value="${!proxy_var:-}"
  if [[ -n "${proxy_value}" ]]; then
    has_proxy=1
    docker_args+=(--build-arg "${proxy_var}=${proxy_value}")
  fi
done
if [[ "${has_proxy}" == 1 ]]; then
  proxy_host="$(python3 -c 'import os; from urllib.parse import urlsplit; print(urlsplit(os.getenv("HTTPS_PROXY") or os.getenv("https_proxy") or os.getenv("HTTP_PROXY") or os.getenv("http_proxy") or "").hostname or "")')"
  if [[ -n "${proxy_host}" ]]; then
    proxy_ip="$(python3 -c 'import socket, sys; print(socket.gethostbyname(sys.argv[1]))' "${proxy_host}")"
    docker_args+=(--network=host --allow network.host --add-host "${proxy_host}:${proxy_ip}")
  fi
fi
if [[ -n "${CODEX_PROXY_CERT:-}" && -r "${CODEX_PROXY_CERT}" ]]; then
  docker_args+=(--secret "id=proxy_ca,src=${CODEX_PROXY_CERT}")
  if [[ -r /etc/ssl/certs/ca-certificates.crt ]]; then
    docker_args+=(--secret id=system_ca,src=/etc/ssl/certs/ca-certificates.crt)
  fi
fi
docker "${docker_args[@]}" .
