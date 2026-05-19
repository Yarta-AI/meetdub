# meetdub 0.1.0 — first public release 🎙️

**Speak any language. Stay sounding like you.**

https://github.com/user-attachments/assets/969b3ede-e13a-49e4-b07b-ef125f651452

meetdub sits between your mic and Teams/Zoom/Meet/Discord/OBS, pipes your
voice through OpenAI's `gpt-realtime-translate`, and routes the translated
audio — adapted to your tone and pacing — into a virtual mic the meeting
app reads as its input.

## ✨ Highlights

- **Speaker-adaptive voice.** The model uses *dynamic voice adaptation* —
  the translated speech follows your general tone, pitch, and pacing.
  It is **not** a voice clone; listeners hear a model voice that
  approximates how you sound rather than a pixel-perfect copy.
- **Universal.** Teams, Zoom, Meet, Discord, OBS, QuickTime, FaceTime — if
  it can pick a mic, meetdub works.
- **One command to install.** `curl … install.sh | bash` handles Homebrew,
  pipx, BlackHole, and walks you through the audio setup.
- **One-time wizard.** After `meetdub setup`, you just run `meetdub run`.
- **Two backends.** OpenAI direct or Azure OpenAI — including api-key,
  static Entra Bearer, and an in-app browser login (`meetdub auth login`)
  for resources locked to Entra ID.
- **13 output languages** (English, 日本語, Español, Français, Deutsch, 中文, 한국어, Português, Italiano, हिन्दी, Русский, Bahasa Indonesia, Tiếng Việt). Hot-swap mid-call with `F2`–`F12` for the first eleven.
- **Cookbook-honest passthrough mix.** Original mic at adjustable gain so
  the other side keeps hearing you when the model emits same-language
  silence. `+ / - / 0` to dial it live.
- **Near-real-time playback.** Default output buffer is the device
  minimum (`--latency-ms 0`). Bump up only if you hear stutter.
- **Local secrets.** Credentials in `~/.meetdub/secrets.env` (chmod 600),
  never in shell rc.
- **MIT, no telemetry.** Single Python package, no servers we operate.

## 🚀 Install

```bash
curl -fsSL https://raw.githubusercontent.com/Yarta-AI/meetdub/main/install.sh | bash

meetdub auth openai          # paste your sk-… (hidden input)
meetdub setup                # pick language, devices, passthrough
meetdub run                  # ▶
```

In Teams / Zoom / Meet, set the **microphone to BlackHole 2ch**.

Already have pipx + BlackHole? `pipx install meetdub && meetdub install`.

## 🧠 How it works

```
mic → meetdub → gpt-realtime-translate → BlackHole 2ch → Teams hears you
                                              ↓
                                         your headphones (optional)
```

`sounddevice` captures 24 kHz PCM16, a WebSocket streams it to
`gpt-realtime-translate`, translated 200 ms chunks come back, and a
threaded audio sink writes them to BlackHole without blocking the
asyncio loop. RMS-based VAD skips silence to keep cost down. The Rich
TUI shows bilingual captions and the live API spend.

## 🧭 What's next

- Demo GIF in the README (next).
- Linux audio routing (PipeWire / PulseAudio null-sink).
- Two-way mode — translate the *other* side back into your headphones.
- Glossary / local-model backends.
- Web version for mobile browsers (the WebRTC translations endpoint).
- See [README → Roadmap](https://github.com/Yarta-AI/meetdub#roadmap).

## 🙏 Credits

- OpenAI — `gpt-realtime-translate` and the Realtime API
- Existential Audio — the BlackHole virtual audio driver
- `sounddevice`, `websockets`, `rich`, `typer`, `pynput`, `azure-identity`

## 📦 Install from PyPI

```bash
pipx install meetdub
```

Full docs: https://github.com/Yarta-AI/meetdub
Japanese readme: https://github.com/Yarta-AI/meetdub/blob/main/README.ja.md
