#!/usr/bin/env bash
set -euo pipefail

# Sync only selected local 1-TILs folders <-> Databricks Workspace without Git.
#
# Examples:
#   ./sync_workspace.sh up
#   ./sync_workspace.sh down
#   ./sync_workspace.sh up --profile DEFAULT
#   ./sync_workspace.sh down --remote /Workspace/Users/madhurima.saxena@gevernova.com/TILs
#
# Environment variables (optional):
#   DBX_PROFILE     Databricks CLI profile name
#   DBX_REMOTE_DIR  Databricks Workspace base path for TILs

usage() {
  cat <<'EOF'
Usage:
  sync_workspace.sh <up|down> [--profile <name>] [--remote <workspace-path>] [--local-base <local-path>]

Options:
  up                Push only:
                    1) analysis/notebooks
                    2) ai_parse_extraction_results
  down              Pull only the same two folders from Workspace
  --profile NAME    Databricks CLI profile (default: DBX_PROFILE env or DEFAULT)
  --remote PATH     Workspace folder path (default: DBX_REMOTE_DIR env or /Workspace/Users/madhurima.saxena@gevernova.com/TILs)
  --local-base PATH Local TILs base path (default: this script directory)
  -h, --help        Show this help

Notes:
  - This is copy-based sync, not real-time merge.
  - The script ensures the five sample subfolders exist under ai_parse_extraction_results:
    1937, 1945, 2284, 1502, 1603
  - Databricks notebook objects are exported/imported as source files (.py/.sql/.scala/.r/.ipynb).
EOF
}

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

ACTION="$1"
shift

PROFILE="${DBX_PROFILE:-DEFAULT}"
REMOTE_DIR="${DBX_REMOTE_DIR:-/Workspace/Users/madhurima.saxena@gevernova.com/TILs}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCAL_BASE="$SCRIPT_DIR"
SAMPLE_IDS=(1937 1945 2284 1502 1603)

while [[ $# -gt 0 ]]; do
  case "$1" in
    --profile)
      PROFILE="$2"
      shift 2
      ;;
    --remote)
      REMOTE_DIR="$2"
      shift 2
      ;;
    --local-base)
      LOCAL_BASE="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1"
      usage
      exit 1
      ;;
  esac
done

if ! command -v databricks >/dev/null 2>&1; then
  echo "Error: databricks CLI not found in PATH"
  exit 1
fi

# Validate profile early with a lightweight auth check.
if ! databricks auth env --profile "$PROFILE" >/dev/null 2>&1; then
  echo "Error: Databricks profile '$PROFILE' is not configured or not valid."
  echo "Run: databricks auth profiles"
  exit 1
fi

LOCAL_NOTEBOOKS="$LOCAL_BASE/analysis/notebooks"
LOCAL_RESULTS="$LOCAL_BASE/ai_parse_extraction_results"

REMOTE_NOTEBOOKS="$REMOTE_DIR/analysis/notebooks"
REMOTE_RESULTS="$REMOTE_DIR/ai_parse_extraction_results"

mkdir -p "$LOCAL_NOTEBOOKS" "$LOCAL_RESULTS"
for id in "${SAMPLE_IDS[@]}"; do
  mkdir -p "$LOCAL_RESULTS/$id"
done

remote_exists() {
  databricks workspace get-status "$1" --profile "$PROFILE" >/dev/null 2>&1
}

echo "Profile   : $PROFILE"
echo "Local base: $LOCAL_BASE"
echo "Remote dir: $REMOTE_DIR"
echo "Sync set  : analysis/notebooks, ai_parse_extraction_results"

case "$ACTION" in
  up)
    databricks workspace mkdirs "$REMOTE_DIR" --profile "$PROFILE"
    databricks workspace mkdirs "$REMOTE_NOTEBOOKS" --profile "$PROFILE"
    databricks workspace mkdirs "$REMOTE_RESULTS" --profile "$PROFILE"
    for id in "${SAMPLE_IDS[@]}"; do
      databricks workspace mkdirs "$REMOTE_RESULTS/$id" --profile "$PROFILE"
    done

    databricks workspace import-dir "$LOCAL_NOTEBOOKS" "$REMOTE_NOTEBOOKS" --overwrite --profile "$PROFILE"
    databricks workspace import-dir "$LOCAL_RESULTS" "$REMOTE_RESULTS" --overwrite --profile "$PROFILE"
    echo "Push complete."
    ;;
  down)
    if remote_exists "$REMOTE_NOTEBOOKS"; then
      databricks workspace export-dir "$REMOTE_NOTEBOOKS" "$LOCAL_NOTEBOOKS" --overwrite --profile "$PROFILE"
    else
      echo "Skip pull: $REMOTE_NOTEBOOKS does not exist"
    fi

    if remote_exists "$REMOTE_RESULTS"; then
      databricks workspace export-dir "$REMOTE_RESULTS" "$LOCAL_RESULTS" --overwrite --profile "$PROFILE"
    else
      echo "Skip pull: $REMOTE_RESULTS does not exist"
    fi

    for id in "${SAMPLE_IDS[@]}"; do
      mkdir -p "$LOCAL_RESULTS/$id"
    done
    echo "Pull complete."
    ;;
  *)
    echo "Error: action must be 'up' or 'down'."
    usage
    exit 1
    ;;
esac
