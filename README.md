# Screen Translator

Screen Translator is a real-time optical character recognition (OCR) and translation tool designed for Wayland desktop environments. The application allows users to select a specific screen area, automatically extracts text, and displays the translation as an overlay near the captured region.

This software was developed with the assistance of artificial intelligence (AI-generated software).

---

## Key Features

* **Wayland Native Compatibility:** Uses `grim` and `slurp` for screen capture and region selection, completely bypassing XWayland security or black-screen limitations.
* **Dynamic Overlay Window:** The translation overlay dynamically adjusts its bounds based on text size and positions itself near the captured region.
* **Multilingual Support:** Powered by Tesseract OCR and Google Translator to recognize and process text across dozens of languages, including Ukrainian.
* **Universal Automation Script:** Automatically detects the underlying Linux distribution and configures dependencies accordingly (including declarative support for NixOS).

---

## Dependencies

To run this application, the following components must be present on your system:

* `grim` and `slurp` (for native screen selection and capture under Wayland)
* `tesseract` along with required language packs (e.g., `tesseract-data-ukr`)
* Python 3 and the following modules: `PyQt6`, `pytesseract`, `pillow`, `deep-translator`

---

## Installation and Setup

An automation script is provided to set up the environment. It detects your distribution, installs the necessary system binaries, and isolates Python packages.

1. Make the installation script executable:
```bash
chmod +x install_deps.py

```


2. Execute the configuration script:
```bash
./install_deps.py

```



### NixOS Target

The script automatically generates a `shell.nix` file and drops you into a managed environment via `nix-shell`. Python virtual environment (`venv`) generation is bypassed to maintain proper shared library linkages for Qt graphics drivers inside the Nix store. Once inside the shell, launch the application using:

```bash
python3 screen_translator.py

```

### Arch / Fedora / Ubuntu Targets

The script provisions system packages using your native package manager, sets up a local virtual environment in the `.venv` directory, and fetches the required Python modules. Run the translator using the isolated environment interpreter:

```bash
./.venv/bin/python screen_translator.py

```

---

## Usage

1. Launch the primary application window.
2. Select your target source and destination languages.
3. Click the region selection button to invoke `slurp` and drag a bounding box over your screen.
4. Click "Start Translation" to begin the real-time processing loop.