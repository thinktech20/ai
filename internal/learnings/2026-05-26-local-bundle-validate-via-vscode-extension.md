Local Databricks bundle validate — working setup via VS Code extension

Context

- Goal: test a Databricks Asset Bundle YAML locally against the AI dev workspace before merging.
- Apr 17 note (`2026-04-17-databricks-local-cli-setup.md`) reached PAT auth but was blocked by `Unauthorized network access to workspace: 7474648066331722` on direct CLI calls.
- Today's path works end-to-end using the Databricks VS Code extension (which bundles its own CLI and uses VS Code's network stack).

What worked

1. Install the Databricks VS Code extension from the Marketplace.
2. Proxy / no-proxy setup so the bundled CLI can reach the workspace:
   - VS Code Settings → `http.noProxy` → add `gevernova-ai-dev-dbr.cloud.databricks.com` (and other env hosts as needed).
   - WSL shell env: add the same hosts to `NO_PROXY` and `no_proxy` in `~/.bashrc`.
     Existing shell only had `NO_PROXY=github.apps.gevernova.net`; updated to:
     ```bash
     export NO_PROXY=github.apps.gevernova.net,gevernova-ai-dev-dbr.cloud.databricks.com,gevernova-ai-qa-dbr.cloud.databricks.com,gevernova-ai-stg-dbr.cloud.databricks.com,gevernova-ai-dbr.cloud.databricks.com
     export no_proxy="$NO_PROXY"
     ```
   - `source ~/.bashrc`, then VS Code Command Palette → `Developer: Reload Window` (so the WSL extension host inherits the new env).
3. In the Databricks side-panel:
   - Click **Select a project** → pick `pw_sdg_ai_ser_repo` (the bundle root containing `databricks.yaml`).
   - Auth: pick **PAT Token**, paste a fresh PAT from the dev workspace UI, give the profile a name (e.g. `dev-dbr-profile`).
   - Target: pick `dev` from the dropdown next to the Target row in CONFIGURATION.
4. Bundle resources populate in BUNDLE RESOURCE EXPLORER once auth + parse succeed.

Why earlier attempts failed

- WSL shell exports `HTTP_PROXY`/`HTTPS_PROXY` pointing at the GE Zscaler proxy. The bundled CLI (Go binary) inherits those env vars and routes calls through Zscaler, which MITMs with a GE-issued cert not in WSL's trust store. Error: `tls: failed to verify certificate: x509: certificate signed by unknown authority`.
- VS Code's `http.noProxy` setting alone does not flow into child Go processes — they look at the standard `NO_PROXY` env var. Fix is to update both.
- `openssl s_client -connect host:443` from WSL bypasses proxy env vars, so a direct cert check returns the real DigiCert chain — useful sanity check but does not tell you whether the CLI is also going direct.

Running validate

- The Databricks side-panel does not have an explicit Validate button. The BUNDLE RESOURCE EXPLORER refresh re-parses but can mask errors (uses cached parse on auth failures).
- Run validate from a terminal to see the full error output:
  ```bash
  CLI=~/.vscode-server/extensions/databricks.databricks-*/bin/databricks
  cd ~/dbx/pw_sdg_ai_ser_repo
  $CLI bundle validate -t dev --profile dev-dbr-profile
  ```
- `--profile` flag is required if `~/.databrickscfg` has more than one profile pointing at the same host.

Reproducing the CI error locally

- CI runs `databricks bundle validate -t ${BUNDLETARGET}` for the changed branch.
- To reproduce, check out the PR branch in `pw_sdg_ai_ser_repo` and run the validate command above. Output matches CI byte-for-byte (e.g. `Missing required cluster or environment settings at resources.jobs.<Job>.tasks[0]`).

Notes

- PAT-based profile in `~/.databrickscfg`; do not commit.
- CLI version bundled with extension 2.10.8 is `v0.297.2`. Local install in Apr 17 note was `v0.297.1`. Errors are identical between the two.
- "Databricks Connect disabled" in the status bar is unrelated to bundle validate; ignore.
- No need to install Databricks CLI separately to `~/bin` — the extension's bundled CLI works fine for terminal use too.
