<div align="center">

# 🎙️ meetdub

### あなたの声のまま、どの言語でも、どの会議でも。

**マイクと Teams/Zoom/Meet の間に挟まる、リアルタイム音声翻訳ツール。**

[![CI](https://github.com/Yarta-AI/meetdub/actions/workflows/ci.yml/badge.svg)](https://github.com/Yarta-AI/meetdub/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/meetdub?color=blue)](https://pypi.org/project/meetdub/)
[![Python](https://img.shields.io/pypi/pyversions/meetdub)](https://pypi.org/project/meetdub/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/Yarta-AI/meetdub?style=social)](https://github.com/Yarta-AI/meetdub/stargazers)

[English](README.md) · **日本語**

<sub>OpenAI <code>gpt-realtime-translate</code> ベース · ローカル動作 · BYOK · MIT</sub>

</div>

---

> **📹 デモ GIF はここに** — `docs/demo.gif`（Teams 通話を日本語↔英語にリアルタイム翻訳しているところ）

## なぜ meetdub？

|                            | meetdub | Teams ライブ翻訳 | Krisp 等 | Heygen 等<br>(アバター吹替) |
| -------------------------- | :-----: | :--------------: | :------: | :------------------------: |
| **どの会議アプリでも動く** |    ✅    |   ❌ Teams のみ   |     ✅    |             ❌              |
| **自分の声のまま**         |    ✅    |   ❌ 合成音/字幕  |    N/A   |             ✅              |
| 自分の API キーを使える    |    ✅    |         ❌        |     ❌    |             ❌              |
| オープンソース             |    ✅    |         ❌        |     ❌    |             ❌              |
| 料金                       | 〜$2/時 |   席ライセンス    |   月額    |            月額             |
| 自前ホスティング可         |    ✅    |         ❌        |     ❌    |             ❌              |

## クイックスタート

```bash
curl -fsSL https://raw.githubusercontent.com/Yarta-AI/meetdub/main/install.sh | bash

meetdub auth openai          # sk-… を貼り付け（非表示入力）
meetdub setup                # 一回だけ: 言語・デバイス・パススルーをウィザード設定
meetdub run                  # ▶ 翻訳開始
```

Teams / Zoom / Meet で **マイク → BlackHole 2ch** を選ぶだけ。

以降の日常運用は `meetdub run`（または言語を切替えたい時だけ `meetdub run --to en`）。

## 仕組み

```
                     ┌───────────────┐    24kHz PCM16    ┌──────────────────────┐
   発話 ───────────▶ │     マイク     │ ─────────────────▶│ gpt-realtime-translate│
       │             └───────────────┘                   └──────────────────────┘
       │                                                            │
       │                                                            │ 翻訳音声
       │                                                            │ (あなたの声色のまま、訳語で)
       │                                                            ▼
       │                                                  ┌───────────────────┐
       │                                                  │   BlackHole 2ch   │ ──▶ Teams が拾う
       │                                                  └───────────────────┘
       │                                                            │
       │                                                            ▼ (--monitor)
       │                                                  ┌───────────────────┐
       └──── ターミナルにバイリンガル字幕                 │  自分のイヤホン    │
                                                          └───────────────────┘
```

* **取得** — `sounddevice` が 24 kHz モノ PCM16 を 20 ms フレームで読み取る
* **VAD** — RMS（音量）しきい値で無音をスキップして API コスト節約。ネイティブ依存なし
* **翻訳** — WebSocket で `wss://api.openai.com/v1/realtime/translations?model=gpt-realtime-translate` へ（Azure デプロイにも対応）
* **再生** — 翻訳音声を BlackHole 2ch に書き込む → Teams がそれをマイク入力として認識
* **UI** — `rich.Live` で元言語と訳語の二段ライブ字幕＋使用料金リアルタイム表示
* **ホットキー** — `pynput` で F2-F12（言語切替）/ Space（push-to-translate）/ Esc（終了）

## 機能

* 🎭 **声色保持** — `gpt-realtime-translate` がトーン・ピッチ・話速をそのまま訳語に転写。相手には **あなたの声で別言語が届く**
* 🪄 **どこでも動く** — Teams · Zoom · Google Meet · Slack ハドル · Discord · OBS · QuickTime · FaceTime。マイク選択できるアプリなら全て対応
* ⚡ **ワンコマンド導入 + setup ウィザード** — `install.sh` が BlackHole / pipx / brew をまとめて入れる。残りは `meetdub setup` 一回で書き込み、以降は `meetdub run` だけ
* 🌐 **11 言語出力** — English · 日本語 · Español · Français · Deutsch · 中文 · 한국어 · Português · Italiano · हिन्दी · Русский（+ Indonesian / Vietnamese）
* ⌨️ **会議中に言語ホットスワップ** — F2-F12 で再起動なしに翻訳先言語を切替
* 🎚️ **パススルー音量ライブ調整** — `+ / - / 0` で元音声のミックス量を調整。多言語会議で相手が自分の母語で話す時の無音回避（cookbook 推奨）
* 🔇 **Push-to-translate** — `--ptt` モードで Space 押下中のみ翻訳。多言語ミーティングで相手の話す番は翻訳しないユースケース向け
* 💸 **コストメーター** — TUI に API 使用料がリアルタイム表示。請求の不意打ちなし
* 📝 **バイリンガル議事録** — セッション毎に `~/.meetdub/transcripts/` へ Markdown 自動保存
* 🔐 **ローカル鍵管理** — 認証情報は `~/.meetdub/secrets.env` (chmod 600) に保存。シェル rc を汚さない
* ☁️ **2 バックエンド** — OpenAI 直 / Azure OpenAI（API キー or Microsoft Entra ID）
* 🐍 **MIT・テレメトリなし** — Python パッケージ 1 個。私たちが運営するサーバーも分析もゼロ

## インストール

**前提:** macOS、`OPENAI_API_KEY`（または Azure OpenAI デプロイメント）

### ワンライナー

```bash
curl -fsSL https://raw.githubusercontent.com/Yarta-AI/meetdub/main/install.sh | bash
```

5 ステップが順に表示されます:

1. **Homebrew** — 未インストールなら入れる
2. **pipx** — `brew install pipx && pipx ensurepath`
3. **BlackHole 2ch** — `brew install --cask blackhole-2ch`（システム機能拡張承認で sudo 要求あり）
4. **meetdub** — `pipx install meetdub`
5. **オーディオ設定** — Multi-Output Device 作成手順（自分も翻訳音声を聞けるように）

### 中身を確認してから実行

```bash
git clone https://github.com/Yarta-AI/meetdub && cd meetdub
less install.sh
./install.sh
```

または Python ブートストラップ: `python3 scripts/bootstrap.py`

### インストール後

`meetdub: command not found` が出る場合は `PATH` がまだ更新されていません:

```bash
exec zsh
```

## 認証情報の設定

認証情報は `~/.meetdub/secrets.env` (chmod 600) に保存されます。シェル rc を汚しません。

### OpenAI

```bash
meetdub auth openai                # 対話モード（入力非表示）
meetdub auth openai --key sk-…     # 非対話
```

### Azure OpenAI

3 つの認証モードに対応:

```bash
# 1. API キー
meetdub auth azure
  # endpoint, deployment, key を聞かれる

meetdub auth azure --endpoint my-resource.openai.azure.com \
                   --deployment my-realtime-translate \
                   --key …

# 2. 取得済み Microsoft Entra Bearer トークン
meetdub auth azure --aad-token "$(az account get-access-token --resource https://cognitiveservices.azure.com --query accessToken -o tsv)"

# 3. ブラウザ対話ログイン（`az` CLI 不要）
meetdub auth login
  # ブラウザが開いて Microsoft アカウントでサインイン → トークンキャッシュ
```

**`auth login` を使う場面:** Azure リソースが「Microsoft Entra ID 認証のみ（API キー無効化）」設定の時。`az` CLI を入れずにブラウザだけで完結し、トークン期限切れも自動でハンドリングされます。

### 確認・削除

```bash
meetdub auth show                  # マスク表示
meetdub auth clear --openai
meetdub auth clear --azure
meetdub auth clear --all
meetdub auth path                  # ファイルパス表示
```

**優先順位:** シェル環境変数 > `~/.meetdub/secrets.env`。`OPENAI_API_KEY=other-key meetdub run …` で一時上書きできます。

## 起動

`meetdub setup` 済みなら通常のコマンドはこれだけ:

```bash
meetdub run
```

一時的な上書き:

```bash
meetdub run --to en                  # このセッションだけ翻訳先を変更
meetdub run --ptt                    # Push-to-translate モード
meetdub run --passthrough            # 元音声を 15% でミックス（+/- で調整）
meetdub run --azure                  # Azure バックエンドを使用
```

`meetdub setup` を飛ばしてもデフォルト値で動きます:
- **Output** → `BlackHole 2ch`（Teams/Zoom がマイクとして読む仮想デバイス）
- **Input** → MacBook 内蔵マイクを自動選択（AirPods マイクは翻訳精度が出にくいため）
- **Monitor** → なし（自分の翻訳音声は聞こえない。聞きたい時は `--monitor "AirPods"` 等を追加）

Teams / Zoom / Meet 側の設定:
- **マイク:** `BlackHole 2ch`
- **スピーカー:** あなたの普通のヘッドホン（相手の声を聞く用）
- **ノイズ抑制:** ⚠ **「低」または「オフ」** — デフォルトの「自動」は合成音声をフィルタリングしてしまう

### ホットキー

| キー | 動作 |
| --- | --- |
| `F2` `F3` `F4` `F5` `F6` `F7` `F8` `F9` `F10` `F11` `F12` | EN · JA · ES · FR · DE · ZH · KO · PT · IT · HI · RU |
| `+` / `-` | パススルー音量 ±5% |
| `0` | パススルー ミュート |
| `Space` (長押し、`--ptt` 時) | push-to-translate |
| `Esc` | 終了 |

キー入力には 2 経路あります:
1. **グローバル**（Teams 前面でも動く）— `pynput` ベース。macOS の **入力監視** + **アクセシビリティ** 権限をターミナルに付与する必要あり
2. **TTY フォールバック**（meetdub のターミナルが前面の時だけ動くが、権限不要）— `/dev/tty` を cbreak モードで直接読む

> ⚠ Mac の最上段はデフォルトでメディアキーなので、`fn + F2` で押すか、**システム設定 → キーボード → F1, F2 等のキーを標準のファンクションキーとして使用** を ON にしてください。

## CLI リファレンス

```text
meetdub install                      BlackHole 導入＋オーディオ設定ガイド
meetdub setup                        対話ウィザード（言語・デバイス・パススルー）
meetdub run [options]                翻訳開始
meetdub auth openai | azure | login  認証情報設定
meetdub auth show | clear | path     認証情報管理
meetdub doctor                       環境診断
meetdub devices                      オーディオデバイス一覧
meetdub languages                    対応出力言語一覧
meetdub config                       現在の設定表示
meetdub keys-test                    キーボード権限確認（入力監視）
meetdub mic-test                     マイク権限・レベル確認
meetdub --version
```

### `meetdub run` のオプション

| オプション | デフォルト | 説明 |
| --- | --- | --- |
| `--to / -t` | 設定ファイル | 翻訳先言語コード (en, ja, es, fr, de, zh, ko, pt, it, hi, ru, id, vi) |
| `--input` | MacBook 内蔵を自動選択。なければシステム既定 | 入力デバイス名の部分一致 |
| `--output` | `BlackHole 2ch` | 出力デバイス名の部分一致 |
| `--monitor` | なし（config に値があればそれ） | 翻訳音声を別デバイスにも流す（自分でモニタ用） |
| `--ptt` | off | Space 押下中のみ翻訳 |
| `--passthrough` | off | 元音声を 15% で BlackHole にミックス（`+/-` で調整） |
| `--passthrough-gain` | — | 線形ゲイン 0.0〜1.0 を明示指定（`--passthrough` を上書き） |
| `--no-vad` | off | 音量に関わらず常時送信（精度↑コスト↑） |
| `--no-transcript` | off | Markdown 議事録を保存しない |
| `--azure` | off | Azure バックエンドを使用 |
| `--azure-endpoint` | auth から | `my-resource.openai.azure.com` |
| `--azure-deployment` | auth から | デプロイメント名 |
| `--azure-api-version` | GA | preview API 利用時のみ（2026-04-30 廃止予定） |
| `--azure-path` | `/openai/v1/realtime/translations` | リージョン依存で 404 出る時の上書き用 |
| `--debug` | off | 詳細ログを `~/.meetdub/debug.log` に出力 |

## トラブルシューティング

まずは **`meetdub doctor`** を実行してください。Homebrew・BlackHole・認証情報・Azure 設定をまとめて検査します。

| 症状 | 原因と対処 |
| --- | --- |
| `meetdub: command not found` | `exec zsh` で `PATH` を再読み込み |
| `meetdub doctor` で BlackHole が ✗（`brew install` 済みなのに） | `sudo killall coreaudiod` で CoreAudio に再スキャンさせる |
| **マイクが取れていない** — `mic-test` が -100 dBFS 未満 | マイク権限なし。設定 → プライバシーとセキュリティ → マイク → ターミナルを ON。**ターミナルを Cmd+Q で完全終了**して再起動 |
| **F キー / Esc / Space が無反応** — `keys-test` で何も出ない | 入力監視権限なし。設定 → プライバシーとセキュリティ → 入力監視 **と** アクセシビリティ → ターミナルを ON。Cmd+Q → 再起動 |
| 翻訳は動いてるのに Teams が無音 | Teams のマイクが BlackHole 2ch になっているか確認。ノイズ抑制を **低 or オフ** に |
| Teams から機械的・途切れる音 | Teams のノイズ抑制が合成音声をフィルタしてる。**オフ** にする |
| `エンドポイントが Microsoft Entra ID 認証で構成されているため、キーは必要ありません` | Azure リソースが API キー認証を無効化している。`meetdub auth login` でブラウザログイン |
| 音声がぷつぷつ | モニタデバイスを確認。AirPods 等の Bluetooth は 150-300ms 遅延がある。有線出力で試す |
| 通話中に転写エラーが頻発 | 文単位で続けて話す（3 秒以上）。短い発話・小声は転写が失敗しやすい。`--no-vad` も試す |

## ロードマップ

- [ ] デモ GIF
- [ ] PyPI 公開
- [ ] Homebrew tap (`brew install Yarta-AI/meetdub/meetdub`)
- [ ] Linux 対応 (PulseAudio / PipeWire null-sink)
- [ ] Windows 対応 (VB-CABLE)
- [ ] 双方向翻訳 — 相手の声も meetdub 経由で翻訳して自分の耳へ
- [ ] 用語集プラグイン — 専門用語・固有名詞を TTS 前に書き換え
- [ ] ローカルモデルバックエンド — `whisper.cpp` + OSS TTS でオフライン/プライバシーモード
- [ ] macOS Keychain ストレージ（`secrets.env` の代替）

## コントリビュート

PR 歓迎、ただし軽微な typo 以上の変更は先に Issue を立ててください。[CONTRIBUTING.md](CONTRIBUTING.md) 参照。

## 謝辞

- [OpenAI](https://openai.com) — `gpt-realtime-translate` モデルと Realtime API
- [Existential Audio](https://existential.audio/blackhole/) — BlackHole 仮想オーディオドライバ
- [sounddevice](https://python-sounddevice.readthedocs.io/) · [websockets](https://websockets.readthedocs.io/) · [rich](https://rich.readthedocs.io/) · [typer](https://typer.tiangolo.com/) · [pynput](https://pynput.readthedocs.io/) · [azure-identity](https://learn.microsoft.com/en-us/python/api/overview/azure/identity-readme)

## ライセンス

[MIT](LICENSE) — ご自由にどうぞ。
