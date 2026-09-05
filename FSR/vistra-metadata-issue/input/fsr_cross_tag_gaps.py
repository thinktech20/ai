"""Workspace-local launcher for the repo FSR cross-tag gap workflow."""

from __future__ import annotations

import os
import runpy
from pathlib import Path


THIS_FILE = Path(__file__).resolve()
REPO_ROOT = THIS_FILE.parents[2]
TARGET_SCRIPT = REPO_ROOT / 'fsr_cross_tag_gaps.py'


def main():
    if not TARGET_SCRIPT.exists():
        raise SystemExit(f'Unable to locate source script: {TARGET_SCRIPT}')

    os.chdir(REPO_ROOT)
    runpy.run_path(str(TARGET_SCRIPT), run_name='__main__')


if __name__ == '__main__':
    main()