# Hardware reconciliation

Target node: Lenovo ThinkPad-class laptop, Windows 11 Pro 64-bit, Intel Core i5-1335U, 16 GB RAM, Intel Iris Xe iGPU, 256 GB NVMe with limited free space.

The platform is therefore configured around CPU-friendly services and external/model-provider boundaries. NVIDIA/CUDA inference is not assumed. Docker, local PostgreSQL/Redis, Ollama/vLLM/llama.cpp and ffmpeg are optional dependencies rather than prerequisites of the core.

An Android companion is included for the user's Android phone. No Raspberry Pi, ESP32, Arduino, robotics, vehicle, satellite or smart-building hardware is assumed present.

The Windows node exposes a controlled execution boundary; destructive/high-risk actions remain gated by policy. The Android companion is paired with a device-scoped token and never receives provider API keys.
