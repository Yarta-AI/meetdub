"""Secrets storage at ~/.meetdub/secrets.env.

Why a dotenv file instead of macOS Keychain?
- Single file, easy to back up, rsync, or move between machines.
- No platform-specific code paths (Keychain on macOS, Secret Service on Linux, …).
- chmod 600 is sufficient for a single-user dev machine.

If you'd rather use Keychain, swap this module — the rest of meetdub only calls
`load_into_env()` and `set_value()`.

Precedence at runtime (highest wins):
  1. process env vars (e.g. exported in shell)
  2. ~/.meetdub/secrets.env
  3. nothing (will error in backend resolution)
"""

from __future__ import annotations

import os
import re
import stat

from meetdub.config import CONFIG_DIR

SECRETS_PATH = CONFIG_DIR / "secrets.env"

# Keys we know about — used by `meetdub auth show` and tab completion.
KNOWN_KEYS: tuple[str, ...] = (
    "OPENAI_API_KEY",
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_DEPLOYMENT",
    "AZURE_OPENAI_API_KEY",
    "AZURE_OPENAI_AAD_TOKEN",
)

_LINE_RE = re.compile(r"^\s*([A-Z][A-Z0-9_]*)\s*=\s*(.*?)\s*$")


def _ensure_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def _ensure_mode_600() -> None:
    if SECRETS_PATH.exists():
        os.chmod(SECRETS_PATH, stat.S_IRUSR | stat.S_IWUSR)


def read_all() -> dict[str, str]:
    if not SECRETS_PATH.exists():
        return {}
    out: dict[str, str] = {}
    with SECRETS_PATH.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n")
            if not line or line.lstrip().startswith("#"):
                continue
            m = _LINE_RE.match(line)
            if not m:
                continue
            key, val = m.group(1), m.group(2)
            # Strip surrounding quotes if present
            if (val.startswith('"') and val.endswith('"')) or (
                val.startswith("'") and val.endswith("'")
            ):
                val = val[1:-1]
            out[key] = val
    return out


def write_all(values: dict[str, str]) -> None:
    _ensure_dir()
    body = ["# meetdub secrets — managed by `meetdub auth`. Do not commit.\n"]
    for k in sorted(values):
        v = values[k]
        # Quote if value contains whitespace or special chars
        needs_quote = bool(re.search(r"[\s#'\"]", v))
        body.append(f'{k}="{v}"\n' if needs_quote else f"{k}={v}\n")
    SECRETS_PATH.write_text("".join(body), encoding="utf-8")
    _ensure_mode_600()


def set_value(key: str, value: str) -> None:
    values = read_all()
    values[key] = value
    write_all(values)


def clear_keys(keys: list[str] | None = None) -> None:
    if keys is None:
        if SECRETS_PATH.exists():
            SECRETS_PATH.unlink()
        return
    values = read_all()
    for k in keys:
        values.pop(k, None)
    write_all(values)


def load_into_env(*, override: bool = False) -> dict[str, str]:
    """Merge secrets file into os.environ.

    By default, real env vars win — this lets users `export OPENAI_API_KEY=…`
    for a one-off override without editing the file. Pass override=True to
    forcibly replace.
    """
    loaded: dict[str, str] = {}
    for k, v in read_all().items():
        if override or k not in os.environ:
            os.environ[k] = v
            loaded[k] = v
    return loaded


def mask(value: str) -> str:
    if not value:
        return "(empty)"
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}…{value[-4:]} ({len(value)} chars)"
