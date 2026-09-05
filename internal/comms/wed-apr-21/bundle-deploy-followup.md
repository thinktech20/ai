# Bundle Deploy Follow-up

For the new manual validation workflow change, use the Databricks bundle from:

`/home/u560060992/dbx/implementation/sdg-pipelines/workflows`

Exact deploy command:

```bash
cd /home/u560060992/dbx/implementation/sdg-pipelines/workflows
databricks bundle deploy -t dev
```

Recommended pre-check:

```bash
cd /home/u560060992/dbx/implementation/sdg-pipelines/workflows
databricks bundle validate -t dev
```

What this should deploy:

- `PW SDG FSR Ingestion Pipeline`
- `PW SDG FSR Manual Validation`

Current blocker noted on Apr 21:

- Local CLI install and PAT auth were set up.
- Bundle deployment from VS Code was blocked by `Unauthorized network access to workspace: 7474648066331722` against `https://gevernova-ai-dev-dbr.cloud.databricks.com`.
- If that blocker is still present, confirm network allowlisting or proxy requirements before retrying the deploy command.