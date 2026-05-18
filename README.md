<div align="center">

# 🎙️ meetdub

### Speak any language with your own voice — in any meeting.

**Real-time speech-to-speech translation that lives between your mic and Teams/Zoom/Meet.**

[![CI](https://github.com/Yarta-AI/meetdub/actions/workflows/ci.yml/badge.svg)](https://github.com/Yarta-AI/meetdub/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/meetdub?color=blue)](https://pypi.org/project/meetdub/)
[![Python](https://img.shields.io/pypi/pyversions/meetdub)](https://pypi.org/project/meetdub/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/Yarta-AI/meetdub?style=social)](https://github.com/Yarta-AI/meetdub/stargazers)

**English** · [日本語](README.ja.md)

<sub>built on OpenAI's <code>gpt-realtime-translate</code> · runs locally · BYO API key · MIT</sub>

</div>

---

<!-- HERO: replace with a real demo GIF before launching. ffmpeg one-liner:
     ffmpeg -i demo.mov -vf "fps=15,scale=900:-1" -loop 0 docs/demo.gif -->

> **📹 Demo GIF goes here** — `docs/demo.gif` (Teams call with live JA→EN translation in the meetdub TUI)

## Why meetdub?

|                         | meetdub | Microsoft Teams<br>Live Translation | Krisp / Noise tools | Heygen<br>(avatar dubbing) |
| ----------------------- | :-----: | :---------------------------------: | :-----------------: | :------------------------: |
| Works in **any** app    |    ✅    |             ❌ Teams only            |          ✅          |             ❌              |
| **Your own voice**      |    ✅    |    ❌ Synth voice / text captions    |         N/A         |             ✅              |
| Bring your own key      |    ✅    |                  ❌                  |          ❌          |             ❌              |
| Open source             |    ✅    |                  ❌                  |          ❌          |             ❌              |
| Cost                    | ~$2/hr  |          Per-seat license           |     Subscription    |        Subscription        |
| Self-hostable           |    ✅    |                  ❌                  |          ❌          |             ❌              |

## Quick start

```bash
curl -fsSL https://raw.githubusercontent.com/Yarta-AI/meetdub/main/install.sh | bash

meetdub auth openai                                   # paste your sk-… (hidden input)
meetdub run --to ja --output BlackHole --monitor AirPods --input MacBook
```

In Teams / Zoom / Meet, set **microphone → BlackHole 2ch**. That's it.

## How it works

```
                     ┌───────────────┐    24kHz PCM16    ┌──────────────────────┐
   you speak ──────▶ │     mic       │ ─────────────────▶│ gpt-realtime-translate│
       │             └───────────────┘                   └──────────────────────┘
       │                                                            │
       │                                                            │ translated audio
       │                                                            │ (your voice, target language)
       │                                                            ▼
       │                                                  ┌───────────────────┐
       │                                                  │   BlackHole 2ch   │ ──▶ Teams hears it
       │                                                  └───────────────────┘
       │                                                            │
       │                                                            ▼ (--monitor)
       │                                                  ┌───────────────────┐
       └─────── live bilingual captions in your terminal  │   your headphones │
                                                          └───────────────────┘
```

* **Capture** — `sounddevice` reads 24 kHz mono PCM16 in 20 ms frames.
* **VAD** — RMS energy gate skips silence so you only pay for speech. No native deps.
* **Translate** — WebSocket to `wss://api.openai.com/v1/realtime/translations?model=gpt-realtime-translate` (or your Azure deployment).
* **Play** — translated audio writes straight to BlackHole 2ch. Teams reads BlackHole as its microphone.
* **TUI** — `rich.Live` renders bilingual source / target captions plus a running cost meter.
* **Hotkeys** — `pynput` listens for F2–F12 (language hot-swap), Space (push-to-translate), Esc (quit).

## Features

* 🎭 **Voice preservation** — `gpt-realtime-translate` keeps your tone, pitch, and cadence. People hear *you*, just in another language.
* 🪄 **Universal** — Teams · Zoom · Google Meet · Slack huddles · Discord · OBS · QuickTime · FaceTime. If it picks a mic, meetdub works.
* ⚡ **One-command install** — Homebrew, BlackHole 2ch, pipx, and the audio walkthrough handled by `install.sh`.
* 🌐 **11 output languages** — English, 日本語, Español, Français, Deutsch, 中文, 한국어, Português, Italiano, हिन्दी, Русский. Plus Indonesian and Vietnamese.
* ⌨️ **Hot-swap mid-call** — tap F2–F12 to change target language without restarting.
* 🔇 **Push-to-translate** — hold Space (with `--ptt`) so meetdub only listens while you're speaking. Perfect for multilingual calls where you want to hear the other side untranslated.
* 💸 **Live cost meter** — your TUI shows actual API spend so you never get a surprise invoice.
* 📝 **Bilingual transcripts** — every session auto-saves a Markdown transcript to `~/.meetdub/transcripts/`.
* 🔐 **Local secrets** — credentials in `~/.meetdub/secrets.env` (chmod 600), never in shell rc.
* ☁️ **Two backends** — OpenAI direct or Azure OpenAI (api-key or Microsoft Entra ID).
* 🐍 **MIT, no telemetry** — single Python package, no servers we control, no analytics.

## Install

**Requirements:** macOS, an `OPENAI_API_KEY` (or Azure OpenAI deployment).

### One-liner

```bash
curl -fsSL https://raw.githubusercontent.com/Yarta-AI/meetdub/main/install.sh | bash
```

The installer runs through 5 visible steps:

1. **Homebrew** — installs if missing
2. **pipx** — `brew install pipx && pipx ensurepath`
3. **BlackHole 2ch** — `brew install --cask blackhole-2ch` (sudo for system extension)
4. **meetdub** — `pipx install meetdub`
5. **Audio setup** — walks you through creating a Multi-Output Device so you can hear yourself while Teams hears the translation

### Audit before running

```bash
git clone https://github.com/Yarta-AI/meetdub && cd meetdub
less install.sh
./install.sh
```

Or use the Python bootstrap: `python3 scripts/bootstrap.py`.

### After install

If you see `meetdub: command not found`, your shell hasn't picked up `~/.local/bin` yet:

```bash
exec zsh   # or: source ~/.zshrc
```

## Configure credentials

Credentials live in `~/.meetdub/secrets.env` (chmod 600) — never in your shell rc.

### OpenAI

```bash
meetdub auth openai                # interactive, hides input
meetdub auth openai --key sk-…     # non-interactive
```

### Azure OpenAI

Three auth modes are supported:

```bash
# 1. API key
meetdub auth azure
  # prompts: endpoint, deployment, key

meetdub auth azure --endpoint my-resource.openai.azure.com \
                   --deployment my-realtime-translate \
                   --key …

# 2. Static Microsoft Entra Bearer token
meetdub auth azure --aad-token "$(az account get-access-token --resource https://cognitiveservices.azure.com --query accessToken -o tsv)"

# 3. Interactive browser login (no `az` CLI needed)
meetdub auth login
  # opens your browser, signs you into Azure, caches the token for auto-refresh
```

**Use case for `auth login`:** when your Azure OpenAI resource is configured for **Microsoft Entra ID only** (api-key disabled). It's the smoothest path and survives token expiry automatically.

### Inspect / clear

```bash
meetdub auth show                  # masked summary
meetdub auth clear --openai        # remove specific backend
meetdub auth clear --azure
meetdub auth clear --all
meetdub auth path                  # print file path
```

**Precedence:** shell env vars > `~/.meetdub/secrets.env`. So `OPENAI_API_KEY=other-key meetdub run …` still overrides cleanly for one-off testing.

## Run

```bash
meetdub run --to ja                                     # translate to Japanese
meetdub run --to es --ptt                               # Spanish, push-to-translate
meetdub run --to fr --monitor "MacBook Pro Speakers"    # also hear it yourself
meetdub run --to ja --azure                             # use Azure (after `meetdub auth azure`)
```

### Recommended setup for Teams / Zoom

```bash
meetdub run --to en \
  --input  "MacBook" \
  --output "BlackHole" \
  --monitor "AirPods"
```

| Flag | Effect |
| --- | --- |
| `--input "MacBook"` | Capture from the built-in mic. AirPods mic pickup is often too soft. |
| `--output "BlackHole"` | Send translated audio to BlackHole 2ch — Teams reads this as its microphone. |
| `--monitor "AirPods"` | Also play the translation to your AirPods so you hear yourself. |

In Teams / Zoom / Meet:
- **Microphone:** `BlackHole 2ch`
- **Speaker:** your real headphones (so you hear the other party)
- **Noise suppression:** ⚠ **Low or Off** — Teams' default "auto" filters out synthesized voices.

### Hotkeys

| Key | Action |
| --- | --- |
| `F2` `F3` `F4` `F5` `F6` `F7` `F8` `F9` `F10` `F11` `F12` | EN · JA · ES · FR · DE · ZH · KO · PT · IT · HI · RU |
| `Space` (hold, with `--ptt`) | push-to-translate |
| `Esc` | quit |

> ⚠ macOS reserves the F-key row for media controls by default. Either hold `fn` while pressing F2, or enable **System Settings → Keyboard → Use F1, F2, etc. keys as standard function keys**.

## CLI reference

```text
meetdub install                      Install BlackHole + audio walkthrough
meetdub run [options]                Start translating
meetdub auth openai | azure | login  Save credentials
meetdub auth show | clear | path     Manage credentials
meetdub doctor                       Verify environment
meetdub devices                      List audio devices
meetdub languages                    Supported output languages
meetdub config                       Print current config
meetdub keys-test                    Verify keyboard permission (Input Monitoring)
meetdub mic-test                     Verify microphone permission + level
meetdub --version
```

### `meetdub run` options

| Option | Default | Notes |
| --- | --- | --- |
| `--to / -t` | from config | Target language code (en, ja, es, fr, de, zh, ko, pt, it, hi, ru, id, vi) |
| `--input` | system default | Substring match on input device name |
| `--output` | `BlackHole 2ch` | Substring match on output device name |
| `--monitor` | none | Also play translation to this output (for hearing yourself) |
| `--ptt` | off | Translate only while Space is held |
| `--no-vad` | off | Always send audio (more accurate, more cost) |
| `--no-transcript` | off | Skip the Markdown transcript |
| `--azure` | off | Use Azure backend |
| `--azure-endpoint` | from auth | `my-resource.openai.azure.com` |
| `--azure-deployment` | from auth | Deployment name |
| `--azure-api-version` | GA | Set for preview API (deprecated 2026-04-30) |
| `--azure-path` | `/openai/v1/realtime/translations` | Override if your region 404s |
| `--debug` | off | Verbose log to `~/.meetdub/debug.log` |

## Troubleshooting

Run **`meetdub doctor`** first — it checks Homebrew, BlackHole, secrets, and Azure config.

| Symptom | Cause / fix |
| --- | --- |
| `meetdub: command not found` | Run `exec zsh` to refresh `PATH` after pipx install. |
| `meetdub doctor` shows BlackHole as ✗ even after `brew install` | Run `sudo killall coreaudiod` to make CoreAudio re-scan plugins. |
| **No audio captured** — `mic-test` shows < -100 dBFS | macOS Microphone permission missing. Settings → Privacy & Security → Microphone → enable your terminal. **Cmd+Q the terminal**, then reopen. |
| **F-keys / Esc / Space do nothing** — `keys-test` receives nothing | macOS Input Monitoring permission missing. Settings → Privacy & Security → Input Monitoring **and** Accessibility → enable your terminal. Cmd+Q, reopen. |
| Translation runs but Teams stays silent | Set Teams microphone to BlackHole 2ch. Also: noise suppression → **Low** or **Off**. |
| Teams sounds robotic / chopped | Teams' noise suppression is filtering meetdub's output. Set it to **Off**. |
| `Endpoint configured for Microsoft Entra ID authentication, key is not needed` | Your Azure resource disabled api-key auth. Run `meetdub auth login` for browser login. |
| Audio is choppy / "ぷつぷつ" | Check your monitor device — Bluetooth headphones (AirPods) add 150-300ms latency. Try a wired output. |
| Persistent transcription errors mid-call | Speak in complete sentences (3+ seconds). Very short utterances or whispers fail to transcribe. Try `--no-vad`. |

## Roadmap

- [ ] Demo GIF
- [ ] PyPI publish
- [ ] Homebrew tap (`brew install Yarta-AI/meetdub/meetdub`)
- [ ] Linux support (PulseAudio / PipeWire null-sink)
- [ ] Windows support (VB-CABLE)
- [ ] Two-way mode — pipe the other side's audio through translation back to your headphones
- [ ] Glossary plugin hooks — rewrite jargon / product names before TTS
- [ ] Local model backend — `whisper.cpp` + open TTS for offline / privacy mode
- [ ] Keychain storage backend (macOS) as alternative to `secrets.env`

## Contributing

PRs welcome — please open an issue first for anything bigger than a typo. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Acknowledgements

- [OpenAI](https://openai.com) — `gpt-realtime-translate` model and Realtime API
- [Existential Audio](https://existential.audio/blackhole/) — the BlackHole virtual audio driver
- [sounddevice](https://python-sounddevice.readthedocs.io/) · [websockets](https://websockets.readthedocs.io/) · [rich](https://rich.readthedocs.io/) · [typer](https://typer.tiangolo.com/) · [pynput](https://pynput.readthedocs.io/) · [azure-identity](https://learn.microsoft.com/en-us/python/api/overview/azure/identity-readme)

## License

[MIT](LICENSE) — do whatever you want, just don't blame us.
