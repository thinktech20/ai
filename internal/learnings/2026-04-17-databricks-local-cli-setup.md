Databricks local CLI setup learnings

Context

- Goal was to validate local Databricks Asset Bundle deployment for the safe FSR workflow test under `implementation/fsr-processing/workflows`.
- The Databricks workflow and Airflow test YAMLs were created locally.
- UI-based workflow creation and execution in Databricks succeeded.

What worked

1. Databricks CLI was not preinstalled on the machine.
2. Standard installer to `/usr/local/bin` failed because the directory was not writable without `sudo`.
3. The installer also ran into corporate TLS issues when downloading from GitHub releases.
4. Manual user-local install worked:

```bash
mkdir -p "$HOME/bin"

cd /tmp
curl -k -fL -o databricks_cli_0.297.1_linux_amd64.zip \
  https://github.com/databricks/cli/releases/download/v0.297.1/databricks_cli_0.297.1_linux_amd64.zip

unzip -o databricks_cli_0.297.1_linux_amd64.zip
chmod +x databricks
cp databricks "$HOME/bin/databricks"

export PATH="$HOME/bin:$PATH"
databricks version
```

5. Verified CLI version:

```bash
Databricks CLI v0.297.1
```

6. Bundle root for this POC is:

```bash
cd /home/u560060992/dbx/implementation/fsr-processing/workflows
```

Why OAuth login did not work

- `databricks auth login --host https://gevernova-ai-dev-dbr.cloud.databricks.com` failed.
- Failure reason was TLS verification against the workspace metadata and OAuth endpoints.
- Conclusion: browser/OAuth flow from local CLI is blocked by the current corporate certificate/network path.

PAT-based local profile that worked

- A PAT-based CLI profile could be created in `~/.databrickscfg`.
- Needed `skip_verify = true` because of the certificate chain issue.

Profile used:

```ini
[ai-dev-fsr-test]
host = https://gevernova-ai-dev-dbr.cloud.databricks.com
token = <PAT>
skip_verify = true
```

Commands used:

```bash
export PATH="$HOME/bin:$PATH"

echo "Paste your Databricks PAT and press Enter:"
read DATABRICKS_TOKEN

cat > ~/.databrickscfg <<EOF
[ai-dev-fsr-test]
host = https://gevernova-ai-dev-dbr.cloud.databricks.com
token = $DATABRICKS_TOKEN
skip_verify = true
EOF

chmod 600 ~/.databrickscfg
unset DATABRICKS_TOKEN
```

Validation command

```bash
export PATH="$HOME/bin:$PATH"
databricks current-user me --profile ai-dev-fsr-test
```

Final blocker

- PAT auth was recognized successfully.
- Final error was:

```text
Unauthorized network access to workspace: 7474648066331722
```

- This indicates the remaining issue is not CLI install and not PAT auth.
- It points to workspace network restrictions, IP allowlisting, proxy path, or other network access policy on the Databricks side.

Practical takeaway

- Local CLI setup from this machine is possible.
- PAT-based profile setup is possible.
- Local API access to the AI dev workspace is still blocked by network policy.
- Next action is to confirm with the Databricks team whether local CLI access is expected from this network, and what allowlisting or proxy setup is required.

Notes

- Do not store PATs in repo files.
- Keep tokens only in `~/.databrickscfg` or another local private secret store.
- For new terminals, `PATH` must include the local install path:

```bash
export PATH="$HOME/bin:$PATH"
```