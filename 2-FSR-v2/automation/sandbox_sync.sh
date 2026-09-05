#!/usr/bin/env bash
# Push the local working branch to a personal Databricks workspace sandbox so it
# can be run without a bundle deploy or a CI/CD merge (CI/CD only deploys from
# the dev branch, so an unmerged branch has no other way to run).
#
# Do NOT strip the "# Databricks notebook source" marker from common/fsr_v2/config.py:
# all four pipeline notebooks pull it in with `%run`, which requires it to stay a
# NOTEBOOK object. Every common/ module that is genuinely *imported*
# (chunker, enums, mlflow_logger, preprocessor_v2, prompts/*) is already
# marker-free and syncs as a FILE, so imports resolve without any rewriting.
set -euo pipefail

REPO="${REPO:-/home/u560060992/dbx/pw_sdg_ai_ser_repo}"
SANDBOX="${SANDBOX:-/Users/madhurima.saxena@gevernova.com/fsr_v2_sandbox}"
PROFILE="${PROFILE:-dev-dbr-profile}"

# A previous sync can leave an object of the wrong type at a path (FILE where a
# NOTEBOOK belongs), which then fails with "file already exists". Guarded so this
# can only ever remove the sandbox itself.
case "$SANDBOX" in
  */fsr_v2_sandbox) databricks workspace delete "$SANDBOX" --recursive --profile "$PROFILE" 2>/dev/null || true ;;
  *) echo "refusing to delete unexpected sandbox path: $SANDBOX" >&2; exit 1 ;;
esac

databricks sync "$REPO" "$SANDBOX" --profile "$PROFILE" --full \
  --exclude 'certs/**' --exclude 'htmlcov/**' --exclude '**/.pytest_cache/**'

echo "sandbox ready: $SANDBOX"
