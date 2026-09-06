# NOTSIP Platform 0.7

Standalone NOTSIP platform for the user's Windows 11 laptop and Android phone. This repository is intentionally separate from `Notsip-995/NOTSIPAI`.

## Install on Windows 11

```powershell
git clone https://github.com/Notsip-995/NOTSIP-Platform.git
cd NOTSIP-Platform
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\install_windows.ps1
notepad .env
.\scripts\start_windows.ps1
```

Open `http://127.0.0.1:8765`.

## Runtime

Persistent identity/context, FTS memory with provenance, world entities/relations, fact/evidence records, model routing, structured tool calling, risk/autonomy enforcement, persistent jobs, audit history, live web retrieval, Playwright browser extraction, Windows PowerShell and desktop screenshot tools, isolated workspace, SMTP/IMAP email, ICS calendar, OAuth scaffolding, signed events, Android pairing, device command/result transport, and browser voice input/output.

External capabilities require the real endpoint/account/permission. NOTSIP never fabricates external success.

## Target hardware

Windows 11 Pro, Intel Core i5-1335U, 16 GB RAM, Intel Iris Xe. No CUDA dependency. Android companion is the phone node.

## Deferred

Robotics, satellites/remote sensing, vehicles and building automation are disabled until real systems are connected.
