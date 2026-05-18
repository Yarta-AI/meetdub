#!/usr/bin/env bash
# meetdub one-shot installer.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/Yarta-AI/meetdub/main/install.sh | bash
#
# What this does (in order):
#   1. Ensure Homebrew      (installs if missing — prompts for sudo)
#   2. Ensure pipx          (brew install pipx + ensurepath)
#   3. Ensure BlackHole 2ch (brew install --cask blackhole-2ch)
#   4. Install meetdub      (pipx install meetdub)
#   5. Run meetdub install  (prints the Multi-Output Device walkthrough)

set -euo pipefail

REPO="${MEETDUB_REPO:-Yarta-AI/meetdub}"
BRANCH="${MEETDUB_BRANCH:-main}"

# If we're running from a checkout of the repo, install from the local path.
# This makes ./install.sh work before the repo is published anywhere.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
LOCAL_SOURCE=""
if [[ -f "$SCRIPT_DIR/pyproject.toml" ]] && grep -q '^name = "meetdub"' "$SCRIPT_DIR/pyproject.toml" 2>/dev/null; then
    LOCAL_SOURCE="$SCRIPT_DIR"
fi

bold()   { printf '\033[1m%s\033[0m\n' "$*"; }
green()  { printf '\033[32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[33m%s\033[0m\n' "$*"; }
red()    { printf '\033[31m%s\033[0m\n' "$*"; }
step()   { printf '\n\033[1;36m▶ %s\033[0m\n' "$*"; }

die() { red "error: $*" >&2; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }

[[ "$(uname -s)" == "Darwin" ]] || die "meetdub currently supports macOS only (BlackHole is macOS)."

bold "meetdub installer"
echo  "  repo:   $REPO@$BRANCH"
echo  "  python: $(python3 --version 2>/dev/null || echo 'not found')"
echo  "  arch:   $(uname -m)"

step "1/5 · Homebrew"
if have brew; then
    green "✓ already installed: $(brew --version | head -n1)"
else
    yellow "Homebrew not found. Installing from https://brew.sh …"
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    # add brew to PATH for this script's remainder
    if [[ -x /opt/homebrew/bin/brew ]];   then eval "$(/opt/homebrew/bin/brew shellenv)"; fi
    if [[ -x /usr/local/bin/brew ]];      then eval "$(/usr/local/bin/brew shellenv)"; fi
fi
have brew || die "Homebrew install failed — install manually from https://brew.sh"

step "2/5 · pipx"
if have pipx; then
    green "✓ $(pipx --version)"
else
    brew install pipx
    pipx ensurepath
fi

step "3/5 · BlackHole 2ch"
if system_profiler SPAudioDataType 2>/dev/null | grep -qi blackhole; then
    green "✓ BlackHole already installed"
else
    yellow "Installing BlackHole 2ch (you may be prompted for sudo) …"
    brew install --cask blackhole-2ch
fi

step "4/5 · meetdub"
if [[ -n "$LOCAL_SOURCE" ]]; then
    pipx install --force "$LOCAL_SOURCE"
    green "✓ installed from local checkout: $LOCAL_SOURCE"
elif pipx install --force "git+https://github.com/$REPO.git@$BRANCH" 2>/dev/null; then
    green "✓ installed from github.com/$REPO@$BRANCH"
else
    pipx install --force meetdub
    green "✓ installed from PyPI"
fi

# pipx puts binaries in ~/.local/bin — make them visible to this shell
export PATH="$HOME/.local/bin:$PATH"
have meetdub || die "meetdub binary not on PATH. Run: pipx ensurepath && exec \$SHELL"

step "5/5 · audio setup"
meetdub install

echo
bold "─────────────────────────────────────────────────────────────"
green "  meetdub is installed. To start translating:"
echo  "    export OPENAI_API_KEY=sk-…"
echo  "    meetdub doctor          # verify environment"
echo  "    meetdub run --to ja     # translate to Japanese"
bold "─────────────────────────────────────────────────────────────"
