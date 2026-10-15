#!/usr/bin/env python3
"""Changelog fragments for every package in this repository.

    python scripts/changelog.py new backend --kind added --title "..."   # with your change
    python scripts/changelog.py check --base origin/dev                   # what CI runs on a pull request
    python scripts/changelog.py release backend --bump minor              # when cutting a release

Needs nothing installed: the tool is loaded straight from backend/src, so it
works in a bare checkout in CI. See docs/guides/changelog.md.
"""

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TOOL = REPO / "backend" / "src" / "acex" / "changelog" / "tool.py"


def _load():
    spec = importlib.util.spec_from_file_location("acex_changelog_tool", TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses look the module up by name
    spec.loader.exec_module(module)
    return module


if __name__ == "__main__":
    sys.exit(_load().main(repo=REPO))
