#!/usr/bin/env python3
import os
import sys
import subprocess
from pathlib import Path

# Package definitions for traditional Linux distributions
DEPS = {
    "ubuntu_debian": ["grim", "slurp", "tesseract-ocr", "tesseract-ocr-ukr", "tesseract-ocr-eng", "python3-pip", "python3-venv"],
    "fedora": ["grim", "slurp", "tesseract", "tesseract-langpack-ukr", "tesseract-langpack-eng", "python3-pip"],
    "arch": ["grim", "slurp", "tesseract", "tesseract-data-ukr", "tesseract-data-eng", "python-pip"]
}

# Pip requirements
PYTHON_DEPS = ["PyQt6", "pytesseract", "pillow", "deep-translator"]

def get_distro():
    """Identifies the host Linux distribution."""
    os_release = Path("/etc/os-release")
    if not os_release.exists():
        return "unknown"
    
    content = os_release.read_text().lower()
    if "nixos" in content:
        return "nixos"
    elif "arch" in content:
        return "arch"
    elif "fedora" in content:
        return "fedora"
    elif "ubuntu" in content or "debian" in content or "mint" in content:
        return "ubuntu_debian"
    
    return "unknown"

def run_cmd(cmd, sudo=False):
    """Executes system commands cleanly."""
    if sudo and os.geteuid() != 0:
        cmd = ["sudo"] + cmd
    try:
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError:
        print(f"❌ Execution failed for command: {' '.join(cmd)}")
        return False

def main():
    distro = get_distro()
    print(f"🔍 Detected distribution: {distro.upper()}")

    if distro == "nixos":
        print("❄️ NixOS environment detected.")
        print("Please use 'nix-shell' directly to evaluate the local shell.nix configuration.")
        print("Aborting native installation routine to prevent store impurity.")
        sys.exit(0)

    if distro == "unknown":
        print("❌ Unsupported or unrecognized distribution. Install dependencies manually.")
        sys.exit(1)

    print("\n🔄 1. Provisioning system utilities (grim, slurp, tesseract)...")
    if distro == "ubuntu_debian":
        if run_cmd(["apt-get", "update"], sudo=True):
            run_cmd(["apt-get", "install", "-y"] + DEPS["ubuntu_debian"], sudo=True)
    elif distro == "fedora":
        run_cmd(["dnf", "install", "-y"] + DEPS["fedora"], sudo=True)
    elif distro == "arch":
        if run_cmd(["pacman", "-Sy"], sudo=True):
            run_cmd(["pacman", "-S", "--needed", "--noconfirm"] + DEPS["arch"], sudo=True)

    # Isolated environment configuration
    venv_dir = Path("./.venv")
    print(f"\n📦 2. Instantiating virtual environment inside '{venv_dir}'...")
    try:
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
    except subprocess.CalledProcessError:
        print("❌ Virtual environment setup failed. Ensure python3-venv is available.")
        sys.exit(1)

    venv_pip = venv_dir / "bin" / "pip"
    venv_python = venv_dir / "bin" / "python"

    print("\n🐍 3. Propagating Python packages via pip inside venv...")
    subprocess.run([str(venv_python), "-m", "pip", "install", "--upgrade", "pip"], check=True)
    
    try:
        subprocess.run([str(venv_pip), "install"] + PYTHON_DEPS, check=True)
        print("\n" + "=" * 50)
        print("✅ Environment setup completed successfully!")
        print("=" * 50)
        print(f"\nLaunch application using:\n  {venv_python} screen_translator.py")
    except subprocess.CalledProcessError:
        print("\n❌ PIP propagation phase crashed inside the virtual environment.")

if __name__ == "__main__":
    main()