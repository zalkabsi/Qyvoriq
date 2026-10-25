#!/usr/bin/env bash
set -euo pipefail

# Run by the account owner in AWS CloudShell after reviewing deploy/bootstrap.yaml.
: "${AWS_REGION:=us-west-2}"
export AWS_REGION
subject_file=deploy/oidc-subject.txt
if [[ ! -s "$subject_file" ]]; then
  echo 'The verified GitHub OIDC subject is not published yet. Complete the identity-check workflow first.' >&2
  exit 1
fi
subject="$(cat "$subject_file")"
aws sts get-caller-identity --query Account --output text >/dev/null
if aws cloudformation describe-stacks --stack-name qyvoriq-access >/dev/null 2>&1; then
  existing_provider="$(aws cloudformation describe-stacks --stack-name qyvoriq-access --query "Stacks[0].Parameters[?ParameterKey=='ExistingOidcProviderArn'].ParameterValue | [0]" --output text)"
  [[ "$existing_provider" == None ]] && existing_provider=''
else
  existing_provider="$(aws iam list-open-id-connect-providers --query "OpenIDConnectProviderList[?ends_with(Arn, 'oidc-provider/token.actions.githubusercontent.com')].Arn | [0]" --output text)"
  [[ "$existing_provider" == None ]] && existing_provider=''
fi
aws cloudformation deploy --template-file deploy/bootstrap.yaml --stack-name qyvoriq-access \
  --capabilities CAPABILITY_NAMED_IAM --no-fail-on-empty-changeset \
  --parameter-overrides "GitHubSubject=$subject" "ExistingOidcProviderArn=$existing_provider"
aws cloudformation describe-stacks --stack-name qyvoriq-access \
  --query 'Stacks[0].Outputs[?OutputKey==`DeploymentRoleArn`]' --output table
printf 'Region: %s\n' "$AWS_REGION"
printf 'Send the DeploymentRoleArn and region to Codex. Do not send keys or the judge token.\n'
