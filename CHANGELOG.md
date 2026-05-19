# Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-05-19

First public release.

### Added — translation core
- Real-time speech-to-speech translation via OpenAI's `gpt-realtime-translate`.
- Azure OpenAI backend (`--azure`) with three auth modes:
  api-key, static Microsoft Entra Bearer token, and interactive browser
  login (`meetdub auth login`, no `az` CLI required).
- BlackHole 2ch routing so any meeting app (Teams, Zoom, Meet, Discord,
  OBS, QuickTime…) can use the translated audio as its microphone.
- Original-mic passthrough: mix your raw voice in at adjustable volume
  so the other side keeps hearing you when the model emits silence
  during same-language stretches (cookbook recommendation).
- Configurable output latency (`--latency-ms`), defaults to device
  minimum for near-real-time playback.

### Added — UX
- `meetdub setup` interactive wizard — pick language, devices, and
  passthrough once; afterwards `meetdub run` works with no arguments.
- `meetdub install` one-shot installer — Homebrew + BlackHole 2ch +
  audio device walkthrough.
- `meetdub auth` — credentials live in `~/.meetdub/secrets.env`
  (chmod 600), never in shell rc.
- `meetdub doctor`, `keys-test`, `mic-test` — environment and
  permission diagnostics.
- Rich TUI with bilingual source/target captions, live cost meter,
  hotkey legend, and passthrough indicator.
- Hotkeys: F2–F12 to hot-swap target language, Space (with `--ptt`)
  for push-to-translate, `+`/`-`/`0` for passthrough volume,
  `Esc` to quit.
- TTY input fallback — F-keys / Space / Esc / volume keys also work
  via direct `/dev/tty` reading, so hotkeys keep working even when
  macOS Input Monitoring permission isn't granted (as long as the
  meetdub terminal is focused).

### Added — operations
- Auto-saved bilingual Markdown transcripts in
  `~/.meetdub/transcripts/`.
- `--monitor` flag to also play translation to a second output device
  (so you hear yourself translated while Teams hears it).
- RMS-based voice activity gate — no native deps, Python 3.10–3.14
  compatible.
- One-line install via `curl … install.sh | bash`.

### Known limitations
- macOS only; Linux (PulseAudio / PipeWire null-sink) and Windows
  (VB-CABLE) are on the roadmap.
- The model is shipped with dynamic voice adaptation — no custom
  voice / prompt / glossary parameters.
- Per-utterance transcription failures are surfaced in the debug log
  but not in the main TUI; long, complete sentences transcribe more
  reliably than short fragments.
