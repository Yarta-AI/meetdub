"""User configuration stored at ~/.meetdub/config.yaml."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

import yaml

CONFIG_DIR = Path.home() / ".meetdub"
CONFIG_PATH = CONFIG_DIR / "config.yaml"
TRANSCRIPTS_DIR = CONFIG_DIR / "transcripts"


@dataclass
class Config:
    target_language: str = "en"
    input_device: str | None = None
    output_device: str = "BlackHole 2ch"
    monitor_device: str | None = None
    monitor_sync: bool = False
    push_to_translate: bool = False
    vad_enabled: bool = True
    save_transcripts: bool = True
    noise_reduction: str = "near_field"

    # Linear gain (0.0–1.0) for mixing the original mic into the BlackHole
    # output alongside translated audio. The cookbook recommends NOT fully
    # muting the original — when the other side speaks your target language
    # the model emits silence, and the passthrough fills the gap.
    passthrough_gain: float = 0.0

    # Output device latency. 0 = "low" (device minimum, closest to real-time
    # but may stutter under jitter). Otherwise milliseconds — higher = smoother
    # playback at the cost of perceived lag.
    output_latency_ms: int = 0
    virtual_jitter_ms: int = 100

    # Backend selection: "openai" (default) or "azure"
    backend: str = "openai"

    # OpenAI direct
    api_key_env: str = "OPENAI_API_KEY"

    # Azure OpenAI
    azure_endpoint: str = ""  # e.g. "my-resource.openai.azure.com"
    azure_deployment: str = ""  # e.g. "my-realtime-translate"
    azure_api_key_env: str = "AZURE_OPENAI_API_KEY"
    azure_api_version: str = ""  # empty = GA path (recommended)
    azure_path: str = ""  # override path if /translations 404s
    azure_auth_mode: str = "auto"  # "auto" | "key" | "aad"

    glossary: dict[str, str] = field(default_factory=dict)

    @classmethod
    def load(cls) -> Config:
        if not CONFIG_PATH.exists():
            return cls()
        with CONFIG_PATH.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
        with CONFIG_PATH.open("w", encoding="utf-8") as f:
            yaml.safe_dump(asdict(self), f, allow_unicode=True, sort_keys=False)

    def api_key(self) -> str | None:
        return os.environ.get(self.api_key_env)
