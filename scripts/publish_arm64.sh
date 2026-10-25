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
docker_args=(buildx build --platform linux/arm64 --build-arg "QYVORIQ_REVISION=${IMAGE_TAG}" --tag "${image_uri}" --push)
# Preserve Docker's configured proxy and registry credentials.
if [[ -n "${CODEX_PROXY_CERT:-}" && -r "${CODEX_PROXY_CERT}" ]]; then
  docker_args+=(--secret "id=proxy_ca,src=${CODEX_PROXY_CERT}")
  if [[ -r /etc/ssl/certs/ca-certificates.crt ]]; then
    docker_args+=(--secret id=system_ca,src=/etc/ssl/certs/ca-certificates.crt)
  fi
fi
docker "${docker_args[@]}" .
printf 'Published %s\n' "${image_uri}"
