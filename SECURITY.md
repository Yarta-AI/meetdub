# Security Policy

## Reporting a vulnerability

Please **do not open a public issue** for security vulnerabilities.

Instead, use GitHub's [Private Vulnerability Reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
feature on this repository, or email the maintainers privately (see the
repository's GitHub profile for contact).

We aim to acknowledge within 72 hours and to publish a fix or mitigation within
14 days of a confirmed report.

## Scope

In scope:
- Code in this repository
- Default install / configuration paths (`install.sh`, `scripts/bootstrap.py`)
- Secret handling (`meetdub/secrets.py`, `meetdub/auth_cli.py`)

Out of scope:
- Vulnerabilities in upstream dependencies (report to that project)
- BlackHole / Homebrew / Azure OpenAI / OpenAI itself
- Social engineering, physical attacks
- Issues only reproducible on unsupported Python/OS versions

## Known threat model

`meetdub` runs locally on a developer's machine and connects to OpenAI / Azure
OpenAI over TLS using user-provided credentials. We do not operate any server
component, do not collect telemetry, and do not transmit audio to any
third-party service other than the configured OpenAI/Azure endpoint.

Credentials are stored at `~/.meetdub/secrets.env` with mode `0600`. If you
share your machine or use a less restrictive umask, prefer the `keyring`-based
storage backend (planned, not yet implemented — contributions welcome).
