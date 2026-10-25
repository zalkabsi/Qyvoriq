# AWS deployment

## Status

The template is prepared, but no AWS deployment was attempted. The managed environment reports no AWS secret, runtime variable, or outbound identity, and the AWS CLI is not installed. No AWS resources or costs were created. The current API keeps inspections in process memory; the template deliberately fixes the service to one Fargate task.

## Prerequisites

- An AWS account and an authorized deployment role with permissions for ECR, ECS, EC2 security groups, ELBv2, IAM, CloudWatch Logs, and Secrets Manager.
- A Docker Buildx builder that supports `linux/arm64` (an Arm host or a builder configured for cross-architecture execution). The workspace builder used for the local container check advertises only `linux/amd64`.
- A VPC with at least two public subnets in different availability zones and routes through an Internet Gateway. This template assigns public IPs to Fargate tasks; the task security group only accepts API traffic from the ALB.
- A domain/DNS record and ACM certificate for that domain in the same region as the ALB.
- AWS CLI v2, Docker Buildx, Python 3 (to resolve a configured host proxy during image builds), and a Secrets Manager secret whose `SecretString` is the API bearer token.
- A deliberate budget review before provisioning. The ALB, Fargate task, logs, and data transfer may incur charges.

## Sequence

1. In the chosen region, create the private repository stack:

   ```bash
   aws cloudformation deploy --template-file deploy/ecr.yaml --stack-name qyvoriq-ecr
   ```

2. Read the `RepositoryUri` output and build/push an immutable commit tag for ARM64:

   ```bash
   export AWS_REGION=us-west-2
   export AWS_ACCOUNT_ID=123456789012
   export ECR_REPOSITORY=123456789012.dkr.ecr.us-west-2.amazonaws.com/qyvoriq
   export IMAGE_TAG=<commit-sha>
   ./scripts/publish_arm64.sh
   ```

3. Deploy the service using existing networking, a matching ACM certificate, and the token secret ARN:

   ```bash
   aws cloudformation deploy \
     --template-file deploy/service.yaml \
     --stack-name qyvoriq-service \
     --capabilities CAPABILITY_IAM \
     --parameter-overrides \
       ImageUri="$ECR_REPOSITORY:$IMAGE_TAG" \
       VpcId=<vpc-id> \
       VpcCidr=<vpc-cidr> \
       PublicSubnetIds=<subnet-a>,<subnet-b> \
       CertificateArn=<acm-certificate-arn> \
       ApiTokenSecretArn=<secrets-manager-secret-arn>
   ```

4. Point the certificate's DNS name to the ALB output. Open the web app through that HTTPS name and enter the bearer token in the UI. Verify `/api/health/ready`, upload a real supported image, submit a follow-up when requested, and check CloudWatch logs. Record the exact URL, region, image digest, task architecture, OpenCV version, and date in the technical report.

The ALB target group uses stickiness to keep a follow-up with the task that created its ephemeral record. Task replacement or scale-out still loses in-memory inspections. Do not increase desired task count above one without moving state into a private durable store and revising retention/deletion behavior. A public endpoint should be protected with AWS WAF/rate controls and monitored before judges use it.

## COOL

The image is built from the standard `opencv-python-headless` PyPI wheel. ARM64 Fargate is not evidence of COOL integration. Do not claim the Best Use of COOL Award unless COOL is installed and the claimed workload is measured on the qualifying Graviton/Arm path against a reproducible standard OpenCV baseline.
