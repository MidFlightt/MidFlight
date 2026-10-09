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
| **Web Lambda + Function URL** | Serves the REST API, the MCP connector at `/mcp`, and Sign in with GitHub. Runs the same server as `uv run midflight-server`, through Lambda Web Adapter. A Function URL instead of API Gateway because `submit_claim` waits up to 60 s (API Gateway stops at 30 s). |
| **Worker Lambda** | Reviews claims. DynamoDB's stream hands it each new job; it retries twice, then gives up to the dead-letter queue. |
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

```bash
uv run python infra/package.py
sam deploy --guided --template-file infra/template.yaml --stack-name midflight --capabilities CAPABILITY_IAM
```

`--guided` asks a few questions the first time; accept the defaults (region
`us-east-1`), say **yes** to "WebFunction Function Url has no authentication" (Midflight
does its own sign-in), and **yes** to saving the answers in `samconfig.toml`. The stack
prints its outputs, including `FunctionUrl`.

Then:

```bash
uv run python infra/put_secrets.py
sam deploy --template-file infra/template.yaml --parameter-overrides PublicUrl=<FunctionUrl without the trailing slash>
```

The second deploy tells the server its own address, which sign-in needs.

Finally, in the GitHub App's settings:

- **Callback URL:** add the `GitHubCallbackUrl` output.
- **Webhook URL:** `<FunctionUrl>github/webhook` (used once verification lands, M-6).

## Check it works

```bash
curl <FunctionUrl>healthz
claude mcp add --transport http midflight <ConnectorUrl>
```

`curl` should print `{"status":"ok"}`. In Claude Code, run `/mcp`, choose **midflight**,
and sign in with GitHub in the browser that opens. Then ask: "list my Midflight
projects".

## Updating

Run `uv run python infra/package.py` and `sam deploy` again. Data in DynamoDB is kept.

## If something goes wrong

| Symptom | Likely cause |
| --- | --- |
| The Function URL answers 403 Forbidden | The function's public-access policy is missing. Re-run `sam deploy`; an older SAM CLI may only add `lambda:InvokeFunctionUrl`, and Function URLs created since October 2025 also need `lambda:InvokeFunction` (update SAM CLI). |
| `/healthz` answers 502, logs say "configure Sign in with GitHub" | The secrets are still placeholders: run `put_secrets.py`. |
| Sign-in redirects to `127.0.0.1` | `PublicUrl` isn't set yet: run the second deploy. |
| A claim stays `pending` | Look at the worker's logs and the dead-letter queue. |
