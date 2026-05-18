#!/usr/bin/env python3
"""meetdub one-shot bootstrap.

Run from a fresh macOS shell:

    python3 scripts/bootstrap.py

This installs pipx if missing, then installs meetdub into an isolated env,
and runs the post-install setup (BlackHole + audio device walkthrough).

We don't use `curl | bash`. Every step is a discrete Python call so the user
can read it, copy it, and audit it.
"""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from pathlib import Path


def die(msg: str, code: int = 1) -> "Never":  # type: ignore[name-defined]
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)


def run(cmd: list[str]) -> None:
    print(f"$ {' '.join(cmd)}")
    rc = subprocess.call(cmd)
    if rc != 0:
        die(f"command failed with exit {rc}: {cmd[0]}")


def have(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def main() -> int:
    if platform.system() != "Darwin":
        die("meetdub bootstrap currently supports macOS only.")

    # 1. Ensure pipx
    if not have("pipx"):
        if not have("brew"):
            die("Homebrew is required. Install from https://brew.sh and rerun.")
        run(["brew", "install", "pipx"])
        run(["pipx", "ensurepath"])

    # 2. Install meetdub from source if we're inside the repo, else from PyPI
    here = Path(__file__).resolve().parent.parent
    if (here / "pyproject.toml").exists():
        run(["pipx", "install", "--force", str(here)])
    else:
        run(["pipx", "install", "--force", "meetdub"])

    # 3. Post-install — installs BlackHole, prints Multi-Output guide
    run(["meetdub", "install"])

    print()
    print("─" * 60)
    print("Next steps:")
    print("  1. export OPENAI_API_KEY=sk-…")
    print("  2. meetdub doctor          # verify setup")
    print("  3. meetdub run --to ja     # start translating to Japanese")
    print("─" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
