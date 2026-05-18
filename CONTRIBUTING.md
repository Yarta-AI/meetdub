# Contributing to meetdub

Thanks for considering a contribution!

## Quick start

```bash
git clone https://github.com/Yarta-AI/meetdub
cd meetdub
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
ruff check meetdub tests
```

## Before opening a PR

1. **Open an issue first** for anything bigger than a typo fix. Saves both of us
   from a "thanks but we won't merge this" conversation after you've done the work.
2. **Tests pass** — `pytest`.
3. **Lint clean** — `ruff check meetdub tests && ruff format --check meetdub tests`.
4. **No new dependencies** without justification in the PR description.

## What we want

- Bug fixes with a reproducer (paste a minimal command + what you saw).
- Linux audio routing (PulseAudio / PipeWire `null-sink`).
- Windows audio routing (VB-CABLE).
- Additional translation backends (local Whisper, on-prem providers).
- Tests for `runner.py` / `audio.py` (currently under-tested).
- Documentation improvements, especially a demo GIF.

## What we'll likely reject

- Frameworks-for-the-sake-of-it (DI containers, plugin abstractions before we have plugins).
- Renames of public APIs without a deprecation path.
- Dependencies on heavyweight ML stacks pulled in unconditionally.

## Code style

- Type hints on new code. We're not running mypy strict yet, but try to make it possible.
- Comments explain *why*, not *what*. If the code reads obvious, skip the comment.
- One short docstring per module is enough; verbose Sphinx-style docstrings are noise.

## Releasing (maintainers only)

1. Update `CHANGELOG.md` under a new version heading.
2. Bump `version` in `pyproject.toml` and `meetdub/__init__.py`.
3. Tag: `git tag v0.x.y && git push --tags`.
4. CI builds and publishes to PyPI on tagged pushes.

## Code of Conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md).
