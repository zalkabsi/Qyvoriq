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

The public web page loads without credentials; processing and results require the shared token. Retrieve the token in **Secrets Manager → qyvoriq/demo/api-token → Retrieve secret value**. Supply it through the competition's private judge instructions. Keep it out of the video, public README, and source.

Running resources are billed: Fargate, ALB/LCUs, public IPv4, logs, ECR, and Secrets Manager. A small continuously available demo is roughly a few US dollars per day; the exact cost depends on region and traffic. One-task scaling is not a hard billing cap. Set an AWS Budget alert and choose how long the judges need the endpoint before enabling the workflow. Retain access through the published judging window rather than deleting it immediately after recording.

To revoke future deployment access, remove the trust from `qyvoriq-github-deploy` or delete that role after disabling the workflow. To stop application costs after judging, delete the `qyvoriq-demo` CloudFormation stack and check for Express Mode managed resources. The bootstrap's ECR repository is retained deliberately; remove unused images/repository separately if appropriate. An existing shared GitHub OIDC provider is not owned by this project.

## Sources checked on 2026-10-25

- [GitHub OIDC with AWS](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws).
- [AWS ECS Express Mode setup and managed endpoint](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/express-service-getting-started.html).
- [ECS Express CloudFormation resource](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-ecs-expressgatewayservice.html).
- [Fargate pricing](https://aws.amazon.com/fargate/pricing/) and [ALB pricing](https://aws.amazon.com/elasticloadbalancing/pricing/).

The older `deploy/service.yaml` template remains an advanced ARM64 deployment design with owner-supplied DNS, certificate, and networking. It is not the new judge-demo path. Standard OpenCV is used; COOL is not claimed.
