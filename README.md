# meetdub 🎙️

> Real-time speech-to-speech translation for **any** meeting app — your voice, every language.

**meetdub** routes your microphone through OpenAI's `gpt-realtime-translate`
model and pipes the translated audio into [BlackHole](https://github.com/ExistentialAudio/BlackHole),
a virtual audio device. Pick BlackHole as your microphone in Teams / Zoom / Meet /
Discord / OBS, and the other side hears you — in their language — **in your own voice**.

```
   you speak EN ─►  gpt-realtime-translate  ─►  BlackHole  ─►  Teams hears JA
        │                  (voice preserved)         │
        └── live bilingual captions in the terminal ─┘
```

## Why it's different

- 🎭 **Your voice, not a TTS voice.** `gpt-realtime-translate` preserves the
  speaker's tone, pitch, and cadence. People hear *you*, just in another language.
- 🪄 **Works in every meeting app** — Teams, Zoom, Google Meet, Slack huddles,
  Discord, OBS, FaceTime. If it can pick a mic, meetdub works.
- ⚡ **One command to install.** No 12-tab Stack Overflow safari to set up
  CoreAudio aggregate devices.
- 🌐 **11 languages, hot-swappable mid-call** — tap `F2`–`F12` to switch target.
- 🔇 **Push-to-translate** mode (hold `Space`) for privacy in mixed-language calls.
- 💸 **Cost meter** in the TUI so you always know what the call is costing.
- 📝 **Bilingual transcripts** auto-saved as Markdown to `~/.meetdub/transcripts/`.
- 🧱 **MIT licensed**, single Python package, ~1,200 lines.

## Install

**Requirements:** macOS, an `OPENAI_API_KEY`. Everything else (Homebrew, pipx,
BlackHole, Python deps) is handled by the installer.

```bash
curl -fsSL https://raw.githubusercontent.com/Yarta-AI/meetdub/main/install.sh | bash
```

The one-liner runs through 5 steps, printing each one:

1. **Homebrew** — installs if missing.
2. **pipx** — `brew install pipx && pipx ensurepath`.
3. **BlackHole 2ch** — `brew install --cask blackhole-2ch`.
4. **meetdub** — `pipx install meetdub` (or from this repo if you set
   `MEETDUB_REPO` / `MEETDUB_BRANCH`).
5. **Audio setup** — walks you through the one manual macOS step (creating a
   Multi-Output Device so *you* can also hear yourself while Teams hears the
   translation).

Don't trust pipes-to-shell? Same thing, audited:

```bash
git clone https://github.com/Yarta-AI/meetdub && cd meetdub
less install.sh        # read it
./install.sh           # then run it
```

Or use the Python bootstrap: `python3 scripts/bootstrap.py`.

## Configure credentials

Don't want to pollute your shell rc with `export OPENAI_API_KEY=…`?
Store credentials in `~/.meetdub/secrets.env` (chmod 600) via the `auth`
subcommand:

```bash
meetdub auth openai                                 # prompts for key (hidden input)
meetdub auth openai --key sk-…                      # non-interactive

meetdub auth azure                                  # prompts for endpoint, deployment, key
meetdub auth azure --endpoint my-resource.openai.azure.com \
                   --deployment my-realtime-translate \
                   --key …
meetdub auth azure --aad-token "$(az account get-access-token …)"

meetdub auth show                                   # masked summary
meetdub auth clear --azure                          # remove specific backend
meetdub auth path                                   # print file path
```

**Precedence:** shell env vars > `~/.meetdub/secrets.env`. So a one-off
`OPENAI_API_KEY=other-key meetdub run …` still overrides cleanly.

## Run

```bash
meetdub run --to ja           # translate to Japanese
meetdub run --to es --ptt     # translate to Spanish, push-to-translate
meetdub run --to fr --monitor "MacBook Pro Speakers"   # also hear it yourself
meetdub run --to ja --azure   # use Azure deployment from `meetdub auth azure`
```

In your meeting app, set **microphone → BlackHole 2ch**. That's it.

### Azure OpenAI

meetdub also supports Azure OpenAI deployments. Auth is `api-key` header (or
Microsoft Entra Bearer token).

```bash
meetdub auth azure   # walk-through prompt — see "Configure credentials" above
meetdub run --to ja --azure
```

CLI flags override stored secrets:

```bash
meetdub run --azure \
  --azure-endpoint my-resource.openai.azure.com \
  --azure-deployment my-realtime-translate \
  --to ja
```

**URL paths.** meetdub defaults to the GA path
`/openai/v1/realtime/translations?model=<deployment>`. If your region hasn't
shipped the translate-specific sub-path yet and you get a 404, drop the
`/translations` suffix:

```bash
meetdub run --azure --azure-path /openai/v1/realtime --to ja
```

If you're stuck on the deprecated preview API (sunset 2026-04-30), pass the
api-version — meetdub will switch to the preview URL shape automatically:

```bash
meetdub run --azure --azure-api-version 2025-04-01-preview --to ja
```

### Hotkeys

| key            | action                                  |
| -------------- | --------------------------------------- |
| `F2`–`F12`     | hot-swap target language (no restart)   |
| `Space` (hold) | push-to-translate (when `--ptt`)        |
| `Esc`          | quit                                    |

### Useful commands

```bash
meetdub doctor       # verify install
meetdub devices      # list audio devices
meetdub languages    # supported output languages
meetdub config       # print config path / contents
```

## How it works

```
┌──────────┐  20ms PCM16  ┌────────────┐  WSS  ┌──────────────────────┐
│   mic    │ ───────────► │  VAD gate  │ ────► │ gpt-realtime-translate│
└──────────┘     24kHz    └────────────┘       └──────────────────────┘
                                                          │ 200ms chunks
                                                          ▼
                                                  ┌───────────────┐
                                                  │   BlackHole   │ ─► Teams
                                                  └───────────────┘
                                                          │
                                                          ▼ (optional)
                                                  ┌───────────────┐
                                                  │ your speakers │
                                                  └───────────────┘
```

- **Capture:** `sounddevice` reads 24 kHz mono PCM16 in 20 ms frames.
- **VAD:** `webrtcvad` gates silence so you only pay for speech.
- **Translate:** `wss://api.openai.com/v1/realtime/translations?model=gpt-realtime-translate`
  with `audio.output.language` set to your target.
- **Play:** translated audio is written straight to the BlackHole 2ch device.
- **UI:** `rich.Live` renders bilingual captions, status, and cost.
- **Hotkeys:** `pynput` global keyboard listener for F-keys / Space / Esc.

## Roadmap

- [ ] Linux support (PulseAudio / PipeWire null-sink instead of BlackHole)
- [ ] Windows support (VB-CABLE)
- [ ] Glossary plugin hooks — rewrite jargon/names before TTS
- [ ] Two-way mode — pipe the *other side's* audio back through translation
      and into your headphones
- [ ] Hugging Face / local model backend for offline / privacy mode

## Contributing

PRs welcome. Open an issue first for anything non-trivial.

## License

MIT
