# Izabela Engines

A small implementation of a "Custom" TTS engine for [Izabela](https://github.com/nature-heart-software/izabela/) - an open-source speech assistant that enables communication through text-to-speech in games, Discord, and other applications.

## Features

- Easy automated setup with a single script
- Supports both CPU and CUDA acceleration
- Easily extensible with new engines
- Runs locally, for free!

## System Requirements

- Windows 10+
- NVIDIA GPU (optional, for faster processing)

## Getting Started

### Installation

1. Download the [latest release](https://github.com/its5Q/izabela-engines/releases/latest), or clone the repository for the bleeding-edge version.
   **Make sure that the path doesn't contain spaces or letters other than latin (ASCII), or the installation will not work!**
   ```
   git clone https://github.com/its5Q/izabela-engines.git
   ```
   

2. Run the PowerShell script `install_environment.ps1` to install all the necessary dependencies by right-clicking it and selecting "Run with PowerShell"
   Follow the prompts to choose between CUDA acceleration (if you have a compatible GPU) or CPU-only mode.

### Running the Server

After installation, start the server using one of the following scripts:

- For CUDA acceleration (GPU):
  ```
  run_cuda.cmd
  ```

- For CPU-only mode:
  ```
  run_cpu.cmd
  ```

The server will start on `http://127.0.0.1:8000`. It must always be running when you want to use it in Izabela

## Connecting to Izabela

1. Open Izabela
2. Go to Settings > Speech Engine
3. Select the "Custom" engine
4. Enter `http://127.0.0.1:8000` in the "API Endpoint" field. The API Key field can be left empty.
5. Select any voice from the list.
6. Enjoy your local and free TTS!

## Available Engines

Currently implemented engines:

- **[Kokoro](https://github.com/hexgrad/kokoro)** - A high-quality TTS engine with natural-sounding speech. Works well for longer sentences and sometimes struggles on shorter ones.  
  **Supported languages**: English, French, Spanish, Hindi, Italian, Brazilian Portugese, Japanese and Chinese, but languages other than English vary wildly in quality.  
  Doesn't require any additional setup, the model with all voices is downloaded automatically on first startup.

More local engines are planned in the future, contributions are welcome!

## Notes

- If you want to move this application somewhere else on your computer, you have to reinstall the environment by deleting the `conda_install` and `conda_env` folders and running the install script again.

---

If you encounter any issues or have suggestions, please open an issue on this repository.