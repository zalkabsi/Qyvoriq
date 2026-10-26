# Give Qyvoriq deployment access

The preferred route is a dedicated AWS IAM role trusted by this repository's GitHub Actions workflow using OpenID Connect (OIDC). GitHub receives a short-lived session when the deployment runs. AWS account keys are not stored in the repository or passed through this chat.

## Account owner setup

1. Sign in to your AWS console with an authorized account identity, choose the deployment region, and open **CloudShell**. The default configuration is `us-west-2` (Oregon).
2. Clone the public project and review `deploy/bootstrap.yaml`. It creates a project ECR repository, ECS cluster, seven-day log group, generated API-token secret, container execution role, ECS infrastructure role, and GitHub deployment role. It reuses an existing GitHub OIDC provider when present. The infrastructure role uses AWS's managed Express Mode policy to provision the ALB, network rules, and scaling resources. The deployment role can pass only the two project roles; it cannot edit IAM policies or read other application secrets.
3. Run:

   ```bash
   git clone https://github.com/zalkabsi/Qyvoriq.git
   cd Qyvoriq
   export AWS_REGION=us-west-2
   bash scripts/bootstrap_access.sh
   ```

   The setup requires permission to create the named IAM roles, an OIDC provider if absent, ECR, ECS cluster, CloudWatch log group, and Secrets Manager secret. It does not start the application or ALB. Metadata storage may have small charges.
4. Send only the printed **DeploymentRoleArn** and **Region** in this chat. Neither is a password. Codex can then enable `deploy/aws-config.json` and monitor the deployment through the connected GitHub account. No access key or AWS console password is needed.

The bootstrap uses the exact subject from the repository's `AWS identity setup check` workflow. GitHub may use immutable owner/repository IDs in that subject; it must be observed rather than guessed. The trust is restricted to this repository's `main` branch and the `sts.amazonaws.com` audience.

The subject in `deploy/oidc-subject.txt` was verified in the [successful identity check](https://github.com/zalkabsi/Qyvoriq/actions/runs/40202662188). The job printed the subject and public repository IDs; it did not print the OIDC token.

## What runs after access is configured

`Deploy AWS judge demo` builds the tested `linux/amd64` image, pins its ECR digest, and deploys `deploy/express.yaml`. ECS Express Mode provides a managed HTTPS endpoint without requiring a custom domain or your own ACM certificate. It uses the account's default VPC and public subnets; if these are absent, preflight stops before creating the service and reports the missing networking.

The application runs one 1-vCPU, 2-GiB Fargate task in steady state. Scale-out is fixed to one because inspection records are process-local. Deployment transitions can temporarily run replacement tasks and reset sessions. Do not update the service during a judge's active inspection.

After deployment, the workflow tests actual health, token protection, clear/glare/follow-up/ambiguous/unsupported images, evidence PNGs, and benchmark data. It saves non-secret deployment evidence as a GitHub Actions artifact. Only a passing live check can be used for the final AWS demo recording and report.

## Judge access and cost

The public web page and health routes load without credentials. Uploads, processing, inspection results and benchmark API requests require the shared bearer token. Retrieve it in **Secrets Manager → qyvoriq/demo/api-token → Retrieve secret value** and supply it through the competition's private judge instructions. Keep it out of the video, public README, and source.

This is shared-code access, not a verified judge identity check. Anyone who receives the token can use it and access retained inspection records; the app has no individual judge accounts, email allowlist, or per-user record isolation. Give the code only to the owner and judges, and use demonstration images rather than confidential uploads. Strictly limiting access to named people would require an invitation-based authentication layer.

For the default Oregon region (`us-west-2`), plan for approximately **US$2–3 per day**, or **US$30–45 for two weeks**, with one continuously running 1-vCPU/2-GiB x86 task and light judge traffic. This is a planning estimate, not an AWS quote or spending limit. It includes an allowance for Fargate, the ALB and LCUs, public IPv4, logs, ECR, and Secrets Manager. Taxes, credits and account-specific Free Tier eligibility are not assumed; actual network configuration, public addresses and traffic can change the bill.

The task and load balancer incur base charges even when nobody is using the app. One-task scaling bounds steady-state compute capacity but is not a hard billing cap; deployment transitions can temporarily add replacement tasks. AWS Budget alerts send notifications rather than automatically stopping all charges. Choose the judging access period before enabling deployment and retain the endpoint through the published judging window rather than deleting it immediately after recording.

To revoke future deployment access, remove the trust from `qyvoriq-github-deploy` or delete that role after disabling the workflow. To stop application costs after judging, delete the `qyvoriq-demo` CloudFormation stack and check for Express Mode managed resources. The bootstrap's ECR repository is retained deliberately; remove unused images/repository separately if appropriate. An existing shared GitHub OIDC provider is not owned by this project.

## Sources

Pricing references were rechecked on 2026-10-26; setup references were checked during the 2026-10-25 deployment review.

- [GitHub OIDC with AWS](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws).
- [AWS ECS Express Mode setup and managed endpoint](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/express-service-getting-started.html).
- [ECS Express CloudFormation resource](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-ecs-expressgatewayservice.html).
- [Fargate pricing](https://aws.amazon.com/fargate/pricing/), [ALB pricing](https://aws.amazon.com/elasticloadbalancing/pricing/), and [public IPv4 pricing](https://aws.amazon.com/vpc/pricing/).

The older `deploy/service.yaml` template remains an advanced ARM64 deployment design with owner-supplied DNS, certificate, and networking. It is not the new judge-demo path. Standard OpenCV is used; COOL is not claimed.
