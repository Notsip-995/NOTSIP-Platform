# NOTSIP — Install Quickstart

NOTSIP is a local AI operating layer for your computer. On first run it shows a
graphical setup wizard where you enter your API keys — nothing is configured
before that, and no key is ever written to a plaintext file.

## Option A — Windows Setup (recommended)

1. Install **Python 3.12 or newer** from https://www.python.org/downloads/
   (on the installer screen tick `Add python.exe to PATH`).
2. Unzip `NOTSIP-Platform-0.9.0.zip`.
3. Right-click `scripts\install.ps1` → **Run with PowerShell**
   (or open PowerShell, `cd` into the unzipped folder, run `python scripts\install.py`).
4. The installer creates `.venv`, installs NOTSIP + Windows UI Automation + the
   Chromium engine for browser automation, then starts NOTSIP and opens the setup wizard.
5. Complete the wizard: model/API keys, autonomy level, email, OIDC, pairing.
   **Every save persists immediately** and the same session can keep saving.

## Option B — Raw Python

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev,windows]"   # Windows
.venv/bin/python -m pip install -e ".[dev]"               # Linux/macOS
.venv/bin/python -m notsip
```

The console prints `NOTSIP listening at http://127.0.0.1:8765/`. Open that URL:
the first visit redirects to `/setup` while no configuration exists.

## Building the standalone EXE (optional)

On a Windows machine:

```powershell
.\scripts\build_exe.ps1        # builds dist\NOTSIP.exe
.\scripts\start_windows.ps1    # runs it
```

For a full installer, open `scripts\NOTSIP.iss` with Inno Setup and compile.

## What the wizard configures

- **Primary model / fallback model** — OpenAI, OpenRouter, Gemini, OmniRoute, …
  with separate base URLs and keys.
- **API key** — used to authenticate your browser session and API calls.
- **Autonomy level** — how much NOTSIP may do without asking.
- **STT/TTS, vision, web search, email, OIDC/OAuth, Android pairing, federated
  nodes, HMAC event signing** — all optional, all configuration-gated.

NOTSIP never fakes an external success: integration panels show real status from
the configured providers.