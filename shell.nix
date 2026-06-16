{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  name = "screen-translator-env";
  
  buildInputs = with pkgs; [
    grim
    slurp
    tesseract
    
    # Declarative Python environment with native library paths patched
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
    echo "Dependencies sourced declaratively via the Nix store."
    echo "Run the application: python3 screen_translator.py"
  '';
}