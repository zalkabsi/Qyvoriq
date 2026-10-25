#!/usr/bin/env bash
set -euo pipefail

: "${AWS_REGION:?Set AWS_REGION}"
: "${AWS_ACCOUNT_ID:?Set AWS_ACCOUNT_ID}"
: "${ECR_REPOSITORY:?Set ECR_REPOSITORY to the full ECR URI}"
: "${IMAGE_TAG:?Set IMAGE_TAG to an immutable source revision}"

registry="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
image_uri="${ECR_REPOSITORY}:${IMAGE_TAG}"
aws sts get-caller-identity >/dev/null
aws ecr get-login-password --region "${AWS_REGION}" | docker login --username AWS --password-stdin "${registry}"
docker_args=(buildx build --platform linux/arm64 --tag "${image_uri}" --push)
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
printf 'Published %s\n' "${image_uri}"
