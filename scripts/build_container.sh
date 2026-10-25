#!/usr/bin/env bash
set -euo pipefail

docker_args=(buildx build --load --tag qyvoriq:local)
# Docker's configured client proxy settings supply the reachable build proxy.
# Preserve DOCKER_CONFIG so its proxy mapping and registry credentials are used.
if [[ -n "${CODEX_PROXY_CERT:-}" && -r "${CODEX_PROXY_CERT}" ]]; then
  docker_args+=(--secret "id=proxy_ca,src=${CODEX_PROXY_CERT}")
  if [[ -r /etc/ssl/certs/ca-certificates.crt ]]; then
    docker_args+=(--secret id=system_ca,src=/etc/ssl/certs/ca-certificates.crt)
  fi
fi
docker "${docker_args[@]}" .
