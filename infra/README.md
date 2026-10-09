# Deploying Midflight to AWS

Team Yoga deploys Midflight **once**; every team then uses the same connector URL
(decision D16). This folder has everything the deploy needs:

| File | What it is |
| --- | --- |
| `template.yaml` | Every AWS resource, as an AWS SAM template |
| `package.py` | Builds `build/lambda.zip`: the code plus its dependencies for Lambda |
| `put_secrets.py` | Copies the GitHub App's secrets from your `.env` into Secrets Manager |

## What gets created

| Resource | Why |
| --- | --- |
| **Web Lambda + Function URL** | Serves the REST API, the MCP connector at `/mcp`, Sign in with GitHub, and the GitHub webhook. Runs the same server as `uv run midflight-server`, through Lambda Web Adapter. A Function URL instead of API Gateway because `submit_claim` waits up to 60 s (API Gateway stops at 30 s). |
| **Worker Lambda** | Reviews claims and verifies pushes. DynamoDB's stream hands it each new job; it retries twice, then gives up to the dead-letter queue. It may call Anthropic models on Bedrock, for the AI reviewer. |
| **DynamoDB table** | Everything Midflight stores. Encrypted, point-in-time recovery on, expired sign-in records deleted automatically. |
| **Secrets Manager secret** | The GitHub App's client secret, private key, and webhook secret. Never in code or environment variables. |
| **SQS dead-letter queue** | Jobs that failed every retry, kept 14 days for inspection. |
| **Log groups** | 14 days of logs. Tokens and secrets are never logged. |

Each Lambda can only touch this table, this secret, and (the worker) this queue.

## One-time setup (Somesh)

1. **AWS account:** verified, root MFA on, a $25/month budget alert, and a deploy
   identity (IAM Identity Center user or an IAM user with MFA). See
   [the development plan's human steps](../docs/development-plan.md#human-steps).
2. **Install the tools:** AWS CLI v2 and SAM CLI. Sign in with `aws configure sso` (or
   `aws configure`), region `us-east-1`.
3. **Your `.env`** (copy `.env.example`) has the client secret, the `.pem` path, and the
   webhook secret.

## Deploy

The commands below use the `midflight` CLI profile from `aws configure sso`. Each
deploy first **previews** the changes (a CloudFormation change set) and applies them
only after you've read the list.

```bash
uv run python infra/package.py
sam deploy --template-file infra/template.yaml --stack-name midflight --capabilities CAPABILITY_IAM --resolve-s3 --region us-east-1 --profile midflight --no-execute-changeset
```

Read the change set it prints (the first time: 13 resources added), then apply it with
the ARN it ends with:

```bash
aws cloudformation execute-change-set --profile midflight --region us-east-1 --change-set-name <change set ARN>
aws cloudformation wait stack-create-complete --stack-name midflight --profile midflight --region us-east-1
aws cloudformation describe-stacks --stack-name midflight --profile midflight --region us-east-1 --query "Stacks[0].Outputs"
```

The outputs include `FunctionUrl`. Then store the secrets and tell the server its own
address, which sign-in needs:

```bash
AWS_PROFILE=midflight AWS_REGION=us-east-1 uv run python infra/put_secrets.py
sam deploy --template-file infra/template.yaml --stack-name midflight --capabilities CAPABILITY_IAM --resolve-s3 --region us-east-1 --profile midflight --no-execute-changeset --parameter-overrides PublicUrl=<FunctionUrl without the trailing slash>
```

Apply that change set the same way (only the two functions change; wait with
`stack-update-complete`).

Finally, in the GitHub App's settings:

- **Callback URL:** add the `GitHubCallbackUrl` output.
- **Webhook:** Active, URL = the `GitHubWebhookUrl` output, secret = the webhook secret
  from your `.env`.
- **Permissions:** Checks read and write; Actions, Contents, Pull requests, Metadata
  read. **Events:** Workflow run.

## Check it works

```bash
curl <FunctionUrl>healthz
claude mcp add --transport http midflight <ConnectorUrl>
```

`curl` should print `{"status":"ok"}`. In Claude Code, run `/mcp`, choose **midflight**,
and sign in with GitHub in the browser that opens. Then ask: "list my Midflight
projects".

## Updating

Run `uv run python infra/package.py` and the `sam deploy ... --no-execute-changeset`
command again, keeping `--parameter-overrides PublicUrl=...`; then apply the change set.
Data in DynamoDB is kept.

## Turning on the AI reviewer

The deploy runs **rules only** until you set `ReviewerModel`. Turn it on only once a
message in the Bedrock playground (`us-east-1`) gets an answer: while Bedrock refuses
calls, every complete claim would wait in `pending`. Then add it to the redeploy:

```bash
sam deploy ... --parameter-overrides PublicUrl=<FunctionUrl without the slash> ReviewerModel=us.anthropic.claude-sonnet-5-5
```

As of October 9, Bedrock answers "Operation not allowed" for every model on this
account; see the [human steps](../docs/development-plan.md#human-steps).

### Bedrock through another account

If this account can't call Bedrock but another one can, the reviewer can borrow a role
there. Everything else stays here. In the other account, open **CloudShell** (us-east-1)
and paste:

```bash
cat > trust.json <<'EOF'
{"Version": "2012-10-17", "Statement": [{
  "Effect": "Allow",
  "Principal": {"AWS": "arn:aws:iam::376564125271:root"},
  "Action": "sts:AssumeRole",
  "Condition": {"ArnLike": {"aws:PrincipalArn": [
    "arn:aws:iam::376564125271:role/midflight-WorkerFunctionRole-*",
    "arn:aws:iam::376564125271:role/aws-reserved/sso.amazonaws.com/*AWSReservedSSO_AdministratorAccess_*"
  ]}}
}]}
EOF
aws iam create-role --role-name midflight-bedrock-reviewer --assume-role-policy-document file://trust.json --query Role.Arn --output text
aws iam put-role-policy --role-name midflight-bedrock-reviewer --policy-name invoke-models-only --policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":"bedrock:InvokeModel","Resource":["arn:aws:bedrock:*::foundation-model/*","arn:aws:bedrock:*:*:inference-profile/*"]}]}'
```

The role can only call Bedrock models, and only Midflight's worker Lambda and this
account's administrators can use it. The first command prints the role's ARN; deploy
with it:

```bash
sam deploy ... --parameter-overrides PublicUrl=<FunctionUrl without the slash> ReviewerModel=us.amazon.nova-pro-v1:0 ReviewerRoleArn=<that ARN>
```

The live deploy uses `us.amazon.nova-pro-v1:0` through the role
`arn:aws:iam::825125930394:role/midflight-bedrock-reviewer` (October 9): that account
hasn't submitted Anthropic's use-case form, so Claude isn't available there yet.

Bedrock usage is billed to the other account (cents for a demo). To stop, delete the
role there and deploy again without `ReviewerRoleArn`.

## The live deployment

Deployed October 9, 2026: stack `midflight`, `us-east-1`.

- Connector URL: `https://5hwub7vaxiyz6oezhxrs3qivaa0cvjvy.lambda-url.us-east-1.on.aws/mcp`
- GitHub callback URL: `https://5hwub7vaxiyz6oezhxrs3qivaa0cvjvy.lambda-url.us-east-1.on.aws/oauth/github/callback`
- GitHub webhook URL: `https://5hwub7vaxiyz6oezhxrs3qivaa0cvjvy.lambda-url.us-east-1.on.aws/github/webhook`

## If something goes wrong

| Symptom | Likely cause |
| --- | --- |
| The Function URL answers 403 Forbidden | The function's public-access policy is missing. Re-run `sam deploy`; an older SAM CLI may only add `lambda:InvokeFunctionUrl`, and Function URLs created since October 2025 also need `lambda:InvokeFunction` (update SAM CLI). |
| `/healthz` answers 502, logs say "configure Sign in with GitHub" | The secrets are still placeholders: run `put_secrets.py`. |
| Sign-in redirects to `127.0.0.1` | `PublicUrl` isn't set yet: run the second deploy. |
| A claim stays `pending` | Look at the worker's logs and the dead-letter queue. With `ReviewerModel` set, check that Bedrock answers for this account. |
| No `midflight/verify` on a pull request | The App's Recent Deliveries: is the webhook active, and did a `workflow_run` arrive with a 202? Does the repo's workflow file end in `contract.yml`, and does the pull request's branch belong to an approved claim? |
| Project shows as stale | GitHub errored or the lead turned the fault switch on (`simulate_github_outage` with `on: false` turns it off). |
