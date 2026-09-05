Slack draft

I was able to create and run a safe test workflow directly in the Databricks UI, including a 2-step dependency flow, without touching any existing tables or volumes.

I also prepared test-only Databricks workflow and Airflow YAMLs locally for the same orchestration pattern, so the jobs-as-code pieces are ready.

So for the current goal, the UI workflow validation is done and the YAMLs are ready.

Separate from that, I also tested local CLI-based bundle deployment from VS Code. CLI install and PAT auth are set up, but API access from my machine is failing with `Unauthorized network access to workspace: 7474648066331722` for `https://gevernova-ai-dev-dbr.cloud.databricks.com`.

Can you confirm whether local CLI access from my machine/network is expected for this workspace, and if so what network allowlisting, proxy, or other setup is required for bundle deployment from VS Code?

Shorter draft

I created the Databricks workflow YAML and the Airflow YAML for this job.

Next I need to trigger it through Airflow. Can you confirm:

1. Which AWS account / MWAA environment should I be connected to for Airflow job creation?
2. Which Airflow repo/path should I use for adding the YAML for this job?
3. Is there a specific FSSO, secret, or connection config I should use for the Databricks Airflow trigger?