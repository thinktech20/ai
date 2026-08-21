# FSR Agent Test - Next Time Checklist

Use this exact sequence to test the deployed app quickly.

## 1) Sync local changes to Databricks workspace

Run from WSL:

```bash
/home/u560060992/bin/databricks sync --full \
  /home/u560060992/dbx/2-FSR-v2/agents \
  /Workspace/Users/madhurima.saxena@gevernova.com/fsr_v2_agents \
  --profile dev-dbr-profile
```

## 2) Open the notebook in Databricks

Open:

`/Workspace/Users/madhurima.saxena@gevernova.com/fsr_v2_agents/nb_test_fsr_agent`

## 3) Generate OAuth token (not PAT)

Use a dedicated OAuth profile (do not use PAT profile for this):

```bash
databricks auth login --host https://gevernova-ai-dev-dbr.cloud.databricks.com --profile dev-oauth
databricks auth token --profile dev-oauth
```

Copy `access_token` value only.

## 4) Notebook run order

1. Run Cell 5 (creates `APP_OAUTH_TOKEN` widget).
2. Paste OAuth token into widget `APP_OAUTH_TOKEN`.
   - Paste raw token only.
   - Do NOT include `Bearer ` prefix.
3. Run Cell 7 (API test call).

## 5) Expected behavior

- You should see HTTP status and JSON response body.
- If it works, app endpoint and auth are good.

## 6) If it fails

- `APP_OAUTH_TOKEN is empty`: widget value not set.
- `Detected PAT token`: token starts with `dapi`; generate OAuth token from `dev-oauth` profile.
- `Sign-In HTML response`: token expired or invalid for app; regenerate via `databricks auth token --profile dev-oauth`.

## 7) Security

- Never commit tokens in code.
- If a token was pasted in notebook/chat, revoke and regenerate it.
