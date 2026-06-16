#!/usr/bin/env python3
import os
import sys
import subprocess
from pathlib import Path

# Список системних пакетів для традиційних дистрибутивів
DEPS = {
    "ubuntu_debian": ["grim", "slurp", "tesseract-ocr", "tesseract-ocr-ukr", "python3-pip", "python3-venv"],
    "fedora": ["grim", "slurp", "tesseract", "tesseract-langpack-ukr", "python3-pip"],
    "arch": ["grim", "slurp", "tesseract", "tesseract-data-ukr", "python-pip"]
}

# Python залежності для pip (тільки для non-NixOS)
PYTHON_DEPS = ["PyQt6", "pytesseract", "pillow", "deep-translator"]

SHELL_NIX_CONTENT = """{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  name = "screen-translator-env";
  
  buildInputs = with pkgs; [
    grim
    slurp
    tesseract
    
    # Декларативний Python для NixOS (без жодних venv)
    (python3.withPackages (ps: with ps; [
      pyqt6
      pytesseract
      pillow
      deep-translator
    ]))
  ];

  shellHook = ''
    echo "================================================="
    echo " Welcome to Screen Translator Environment (NixOS)"
    echo "================================================="
    echo "Всі залежності завантажено через Nix store."
    echo "Запуск перекладача: python3 screen_translator.py"
  '';
}
"""

def get_distro():
    """Визначає поточний дистрибутив Linux."""
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
    """Безпечно запускає команду в системі."""
    if sudo and os.geteuid() != 0:
        cmd = ["sudo"] + cmd
    try:
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError:
        print(f"❌ Помилка під час виконання команди: {' '.join(cmd)}")
        return False

def main():
    distro = get_distro()
    print(f"🔍 Виявлено дистрибутив: {distro.upper()}")

    if distro == "unknown":
        print("❌ Не вдалося визначити дистрибутив. Встанови пакети вручну.")
        sys.exit(1)

    # ─── Сценарій 1: Чистий NixOS (Повний skip для venv та pip) ───
    if distro == "nixos":
        nix_file = Path("shell.nix")
        print(f"📦 NixOS режим: Створення {nix_file.absolute()}...")
        nix_file.write_text(SHELL_NIX_CONTENT)
        print("🚀 Запуск nix-shell (оточення буде ізольованим у Nix store)...")
        # os.execvp повністю замінює цей процес на nix-shell, наступні рядки кода НЕ виконуються
        os.execvp("nix-shell", ["nix-shell", str(nix_file)])

    # ─── Сценарій 2: Традиційні дистрибутиви (Зі створення venv) ───
    print("\n🔄 1. Встановлення системних утиліт (grim, slurp, tesseract)...")
    
    if distro == "ubuntu_debian":
        if run_cmd(["apt-get", "update"], sudo=True):
            run_cmd(["apt-get", "install", "-y"] + DEPS["ubuntu_debian"], sudo=True)
    elif distro == "fedora":
        run_cmd(["dnf", "install", "-y"] + DEPS["fedora"], sudo=True)
    elif distro == "arch":
        if run_cmd(["pacman", "-Sy"], sudo=True):
            run_cmd(["pacman", "-S", "--needed", "--noconfirm"] + DEPS["arch"], sudo=True)

    # Створення та налаштування venv (Тільки для Arch/Fedora/Debian)
    venv_dir = Path("./.venv")
    print(f"\n📦 2. Створення віртуального оточення Python у папці '{venv_dir}'...")
    
    try:
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
    except subprocess.CalledProcessError:
        print("❌ Не вдалося створити venv. Перевір, чи встановлено пакет python3-venv.")
        sys.exit(1)

    venv_pip = venv_dir / "bin" / "pip"
    venv_python = venv_dir / "bin" / "python"

    print("\n🐍 3. Встановлення Python залежностей через pip всередині venv...")
    subprocess.run([str(venv_python), "-m", "pip", "install", "--upgrade", "pip"], check=True)
    
    try:
        subprocess.run([str(venv_pip), "install"] + PYTHON_DEPS, check=True)
        print("\n" + "="*50)
        print("✅ Всі залежності для традиційного дистрибутива встановлено!")
        print("="*50)
        print(f"\nЗапуск перекладача:\n  {venv_python} screen_translator.py")
    except subprocess.CalledProcessError:
        print("\n❌ Помилка під час роботи pip всередині venv.")

if __name__ == "__main__":
    main()