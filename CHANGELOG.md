# Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-05-18

Initial release.

### Added
- Real-time speech-to-speech translation via OpenAI's `gpt-realtime-translate`.
- Azure OpenAI backend (`--azure`) with api-key and Microsoft Entra ID (AAD) auth.
- BlackHole 2ch routing for Teams / Zoom / Meet / Discord / OBS.
- `meetdub install` — one-shot installer (Homebrew + BlackHole + Multi-Output guide).
- `meetdub auth` — credentials stored in `~/.meetdub/secrets.env` (chmod 600).
- `meetdub doctor` — environment diagnostics.
- `meetdub keys-test` / `mic-test` — permission diagnostics for macOS.
- Live bilingual TUI with source/target captions, cost meter, hotkey legend.
- Hotkey language switching (F2–F12), push-to-translate (Space), Esc to quit.
- RMS-based voice activity detection (no native deps).
- Auto-saved bilingual Markdown transcripts.
- `--monitor` flag for hearing yourself translated while Teams hears it.
