# Izabela Engines

A local "Custom" TTS engine server for [Izabela](https://github.com/nature-heart-software/izabela/) - an open-source speech assistant that enables communication through text-to-speech in games, Discord, and other applications.

## Features

- Simple, reliable setup with Docker
- Supports CPU, modern NVIDIA GPUs (GTX 16-series through RTX 50-series), and older NVIDIA GPUs (GTX 900 / GTX 10-series)
- Automatically caches downloaded models in a persistent Docker volume
- Easily extensible with new engines
- Runs locally, for free!

## Available Engines

Currently implemented engines:

- **[Kokoro](https://github.com/hexgrad/kokoro)** - A high-quality 82M-parameter TTS engine with natural-sounding speech. Works well for longer sentences and sometimes struggles on shorter ones.
  **Supported languages:** English (US & GB), French, Spanish, Hindi, Italian, Brazilian Portuguese, Japanese, and Mandarin Chinese (non-English quality varies).
  Models and voices are downloaded automatically on first use and persisted in the `izabela-hf-cache` Docker volume.

More local engines are planned in the future - contributions are welcome!

## System Requirements

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows / macOS) or Docker Engine + Compose (Linux)
- **Optional (for NVIDIA GPU acceleration):**
  - **Windows:** Up-to-date NVIDIA Game Ready or Studio driver (WSL2 GPU support is built into Docker Desktop)
  - **Linux:** NVIDIA driver + [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)

## Getting Started

### 1. Download the Project

Download and extract the [latest release](https://github.com/its5Q/izabela-engines/releases/latest), or clone the repository:

```sh
git clone https://github.com/its5Q/izabela-engines.git
cd izabela-engines
```

### 2. Start the Server

Make sure Docker Desktop (or Docker Engine) is running, open a terminal in the project folder, and run **one** of the following commands based on your hardware:

- **Modern NVIDIA GPU (GTX 16-series, RTX 20 / 30 / 40 / 50-series):**
  ```sh
  docker compose --profile cuda up -d --build
  ```

- **Older NVIDIA GPU (GTX 900 / GTX 10-series, e.g. GTX 1060, 1070, 1080 Ti):**
  ```sh
  docker compose --profile cuda-legacy up -d --build
  ```

- **CPU-only (no NVIDIA GPU, or AMD/Intel GPU):**
  ```sh
  docker compose --profile cpu up -d --build
  ```

> **First-run note:** The initial build downloads dependencies, and the first startup downloads the Kokoro voice model (~330 MB) into a Docker volume so subsequent startups are fast. You can watch startup progress with:
> ```sh
> docker compose logs -f
> ```
> Once you see `Uvicorn running on http://0.0.0.0:6556`, the server is ready at `http://127.0.0.1:6556`.

### Stopping or Updating

- **Stop the server:**
  ```sh
  docker compose --profile cuda down
  ```
  *(Replace `cuda` with `cuda-legacy` or `cpu` depending on the profile you started — or manage the container directly in the Docker Desktop GUI.)*

- **Change the port (default `6556`):**
  Copy `.env.example` to `.env` and edit `IZABELA_PORT`, then restart the container.

## Connecting to Izabela

1. Open Izabela
2. Go to **Settings > Speech Engine**
3. Select the **Custom** engine
4. Enter `http://127.0.0.1:6556` (or your custom port) in the **API Endpoint** field. Leave the **API Key** field empty.
5. Select any voice from the list.
6. Enjoy your local and free TTS!

---

If you encounter any issues or have suggestions, please open an issue on this repository.