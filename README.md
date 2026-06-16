# Screen Translator

Screen Translator is a real-time optical character recognition (OCR) and translation tool designed for Wayland desktop environments. The application allows users to select a specific screen area, automatically extracts text, and displays the translation as an overlay near the captured region.

This software was developed with the assistance of artificial intelligence (AI-generated software).

---

## Key Features

* **Wayland Native Compatibility:** Uses `grim` and `slurp` for screen capture and region selection, completely bypassing XWayland security or black-screen limitations.
* **Dynamic Overlay Window:** The translation overlay dynamically adjusts its bounds based on text size and positions itself near the captured region.
* **Multilingual Support:** Powered by Tesseract OCR and Google Translator to recognize and process text across dozens of languages, including Ukrainian.
* **Universal Automation Script:** Automatically detects traditional Linux distributions to configure dependencies and virtual environments while safely redirecting NixOS users.

---

## Dependencies

To run this application, the following components must be present on your system:

* `grim` and `slurp` (for native screen selection and capture under Wayland)
* `tesseract` along with required language packs (e.g., `tesseract-data-ukr`)
* Python 3 and the following modules: `PyQt6`, `pytesseract`, `pillow`, `deep-translator`

---

## Installation and Setup

### NixOS Environment

If you are running NixOS, a standalone configuration is available. Do not run the automated installation script. Instead, drop straight into the managed environment using the native package manager:

```bash
nix-shell

```

The declarative configuration automatically provisions the system utilities and isolated Python bindings. Once the shell finishes evaluating, launch the application:

```bash
python3 screen_translator.py

```

### Arch / Fedora / Ubuntu Environments

For traditional FHS distributions, an automation script is provided to handle system binaries via your native package manager and isolate application modules inside a local virtual environment (`.venv`).

1. Make the installation script executable:
```bash
chmod +x install_deps.py
```

2. Execute the configuration script:
```bash
./install_deps.py
```

3. Run the translator using the isolated environment interpreter:
```bash
./.venv/bin/python screen_translator.py
```

---

## Usage

1. Launch the primary application window.
2. Select your target source and destination languages.
3. Click the region selection button to invoke `slurp` and drag a bounding box over your screen.
4. Click "Start Translation" to begin the real-time processing loop.