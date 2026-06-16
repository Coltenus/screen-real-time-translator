#!/usr/bin/env python3
"""
Screen Translator — Pure Wayland real-time screen translation tool.
Uses grim and slurp for native Wayland region selection and screen capture.
"""

import sys
import os
import json
import time
import threading
import subprocess
import io
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QComboBox, QSpinBox, QGroupBox,
    QSystemTrayIcon, QMenu, QDialog, QFormLayout, QSlider,
    QCheckBox, QTextEdit, QMessageBox, QColorDialog, QTabWidget
)
from PyQt6.QtCore import (
    Qt, QThread, pyqtSignal, QRect, QPoint, QSettings, pyqtSlot
)
from PyQt6.QtGui import (
    QPainter, QBrush, QColor, QFont, QPixmap, QIcon, QAction
)

try:
    import pytesseract
    from PIL import Image, ImageFilter, ImageEnhance, ImageOps
    from deep_translator import GoogleTranslator
    DEPS_OK = True
except ImportError as e:
    DEPS_OK = False
    MISSING_DEP = str(e)

# ─── Config ──────────────────────────────────────────────────────────────────

CONFIG_PATH = Path.home() / ".config" / "screen_translator" / "config.json"

LANGUAGES = {
    "Auto-detect": "auto",
    "English": "en",
    "Ukrainian": "uk",
    "Russian": "ru",
    "German": "de",
    "French": "fr",
    "Spanish": "es",
    "Italian": "it",
    "Polish": "pl",
    "Portuguese": "pt",
    "Chinese (Simplified)": "zh-CN",
    "Chinese (Traditional)": "zh-TW",
    "Japanese": "ja",
    "Korean": "ko",
    "Arabic": "ar",
    "Turkish": "tr",
    "Dutch": "nl",
    "Swedish": "sv",
    "Norwegian": "no",
    "Finnish": "fi",
    "Czech": "cs",
    "Slovak": "sk",
    "Hungarian": "hu",
    "Romanian": "ro",
    "Bulgarian": "bg",
    "Greek": "el",
    "Hebrew": "iw",
    "Hindi": "hi",
    "Thai": "th",
    "Vietnamese": "vi",
    "Indonesian": "id",
}

DEFAULT_CONFIG = {
    "source_lang": "auto",
    "target_lang": "en",
    "interval_ms": 2000,
    "font_size": 14,
    "overlay_opacity": 220,
    "overlay_bg": "#1a1a2e",
    "overlay_fg": "#e0e0ff",
    "tesseract_cmd": "",
    "always_on_top": True,
    "show_original": False,
    "region_str": "",         # Slurp geometry string: "x,y wxh"
}


def load_config() -> dict:
    try:
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH) as f:
                cfg = json.load(f)
            for k, v in DEFAULT_CONFIG.items():
                cfg.setdefault(k, v)
            return cfg
    except Exception:
        pass
    return dict(DEFAULT_CONFIG)


def save_config(cfg: dict):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)


# ─── Worker thread ────────────────────────────────────────────────────────────

class TranslationWorker(QThread):
    result_ready = pyqtSignal(str, str)   # original, translated
    error_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._region_str: str = ""
        self._cfg: dict = {}
        self._running = False
        self._paused = True
        self._lock = threading.Lock()

    def configure(self, cfg: dict, region_str: str):
        with self._lock:
            self._cfg = dict(cfg)
            self._region_str = region_str

    def set_paused(self, paused: bool):
        self._paused = paused

    def stop(self):
        self._running = False

    def run(self):
        self._running = True
        while self._running:
            with self._lock:
                cfg = dict(self._cfg)
                region_str = self._region_str

            interval = cfg.get("interval_ms", 2000) / 1000.0

            if not self._paused and region_str:
                try:
                    text, translated = self._capture_and_translate(cfg, region_str)
                    if text.strip():
                        self.result_ready.emit(text, translated)
                except Exception as e:
                    self.error_signal.emit(str(e))

            slept = 0.0
            while slept < interval and self._running:
                time.sleep(0.1)
                slept += 0.1

    @staticmethod
    def _preprocess(img):
        scale = 2.0
        img = img.resize(
            (int(img.width * scale), int(img.height * scale)),
            Image.LANCZOS,
        )
        img = img.convert("L")
        img = ImageOps.autocontrast(img)
        img = ImageEnhance.Contrast(img).enhance(1.5)
        img = ImageEnhance.Sharpness(img).enhance(1.5)
        return img

    # Replace the worker capture method with a multi-backend approach
    def _capture_and_translate(self, cfg, region_str):
        if cfg.get("tesseract_cmd"):
            pytesseract.pytesseract.tesseract_cmd = cfg["tesseract_cmd"]

        # Parse slurp coordinates: "x,y wxh"
        try:
            coords, dims = region_str.split(" ")
            rx, ry = map(int, coords.split(","))
            rw, rh = map(int, dims.split("x"))
        except ValueError:
            raise RuntimeError("Malformed region string.")

        img = None

        # Backend Method 1: Try grim (Efficient fallback for wlroots/Hyprland/Sway)
        try:
            cmd = ["grim", "-g", region_str, "-"]
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=2)
            if proc.returncode == 0 and proc.stdout:
                img = Image.open(io.BytesIO(proc.stdout))
        except Exception:
            pass

        # Backend Method 2: Universal Fallback if grim fails (GNOME/Mutter/KDE)
        if img is None:
            try:
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    tmp_path = tmp.name
                
                # Перенаправляємо stdout ТА stderr у DEVNULL, щоб прибрати спам від kf.iconthemes та spectacle
                if os.path.exists("/usr/bin/gnome-screenshot"):
                    subprocess.run(
                        ["gnome-screenshot", "-f", tmp_path], 
                        stdout=subprocess.DEVNULL, 
                        stderr=subprocess.DEVNULL
                    )
                elif os.path.exists("/usr/bin/spectacle"):
                    subprocess.run(
                        ["spectacle", "-b", "-n", "-o", tmp_path], 
                        stdout=subprocess.DEVNULL, 
                        stderr=subprocess.DEVNULL
                    )
                else:
                    subprocess.run(
                        ["grim", tmp_path], 
                        stdout=subprocess.DEVNULL, 
                        stderr=subprocess.DEVNULL
                    )

                full_img = Image.open(tmp_path)
                img = full_img.crop((rx, ry, rx + rw, ry + rh))
                
                # Обов'язково закриваємо дескриптор файлу перед видаленням, щоб не було lock-ів
                full_img.close() 
                os.unlink(tmp_path)
            except Exception as e:
                raise RuntimeError(f"All capture backends exhausted: {e}")

        # -- 2. Preprocess for OCR --
        img = self._preprocess(img)

        src = cfg.get("source_lang", "auto")
        tgt = cfg.get("target_lang", "en")

        # -- 3. Map language code to Tesseract lang string --
        TESS_MAP = {
            "en": "eng", "uk": "ukr", "ru": "rus", "de": "deu",
            "fr": "fra", "es": "spa", "it": "ita", "pl": "pol",
            "pt": "por", "zh-CN": "chi_sim", "zh-TW": "chi_tra",
            "ja": "jpn", "ko": "kor", "ar": "ara", "tr": "tur",
            "nl": "nld", "sv": "swe", "no": "nor", "fi": "fin",
            "cs": "ces", "sk": "slk", "hu": "hun", "ro": "ron",
            "bg": "bul", "el": "ell", "iw": "heb", "hi": "hin",
            "th": "tha", "vi": "vie", "id": "ind",
        }
        tess_lang = TESS_MAP.get(src, "eng")

        try:
            available = pytesseract.get_languages(config='')
        except Exception:
            available = []

        if tess_lang not in available:
            tess_lang = "eng"

        # -- 4. OCR --
        tess_config = "--oem 3 --psm 4"
        try:
            original = pytesseract.image_to_string(
                img, lang=tess_lang, config=tess_config
            ).strip()
        except pytesseract.TesseractError as e:
            err = str(e)
            if "Failed loading language" in err:
                original = pytesseract.image_to_string(
                    img, lang="eng", config=tess_config
                ).strip()
            else:
                raise RuntimeError(f"Tesseract OCR error: {err}") from e

        if not original:
            return "[no text detected]", ""

        # -- 5. Translate --
        translator = GoogleTranslator(source=src, target=tgt)
        translated = translator.translate(original)
        return original, translated or ""


# ─── Translation overlay window ───────────────────────────────────────────────

class TranslationOverlay(QWidget):
    """Floating window that shows the translated text near the selected region."""

    def __init__(self):
        super().__init__()
        self._cfg: dict = {}
        self._region_str = ""

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        self._label = QLabel(self)
        self._label.setWordWrap(True)
        self._label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.addWidget(self._label)

    def apply_config(self, cfg: dict):
        self._cfg = cfg
        alpha = cfg.get("overlay_opacity", 220)
        fg = cfg.get("overlay_fg", "#e0e0ff")
        bg = cfg.get("overlay_bg", "#1a1a2e")
        fs = cfg.get("font_size", 14)

        r = int(bg[1:3], 16)
        g = int(bg[3:5], 16)
        b = int(bg[5:7], 16)

        self._label.setStyleSheet(
            f"color: {fg}; font-size: {fs}pt; font-family: 'Segoe UI', 'Noto Sans', sans-serif;"
        )
        self.setStyleSheet(
            f"QWidget {{ background-color: rgba({r},{g},{b},{alpha}); "
            f"border-radius: 8px; border: 1px solid rgba(100,120,200,150); }}"
        )

        flags = self.windowFlags()
        if cfg.get("always_on_top", True):
            flags |= Qt.WindowType.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)

    def set_region(self, region_str: str):
        self._region_str = region_str
        self._reposition()

    def update_text(self, original: str, translated: str):
        show_orig = self._cfg.get("show_original", False)

        if show_orig and original:
            text = f"<b>Original:</b><br>{original}<hr><b>Translation:</b><br>{translated}"
        else:
            text = translated or ""

        self._label.setText(text)
        self.adjustSize()
        self._reposition()

        if text.strip():
            self.show()
            self.raise_()
        else:
            self.hide()

    def _reposition(self):
        if not self._region_str:
            return

        try:
            # Parse slurp format "x,y wxh"
            coords, dims = self._region_str.split(" ")
            rx, ry = map(int, coords.split(","))
            rw, rh = map(int, dims.split("x"))
        except ValueError:
            return

        screen = QApplication.primaryScreen()
        screen_geo = screen.geometry()

        x = rx
        y = ry - self.height() - 6
        if y < screen_geo.y():
            y = ry + rh + 6

        max_x = screen_geo.x() + screen_geo.width() - self.width() - 4
        x = max(screen_geo.x() + 4, min(x, max_x))

        self.setFixedWidth(max(rw, 200))
        self.adjustSize()
        self.move(x, y)


# ─── Settings dialog ──────────────────────────────────────────────────────────

class SettingsDialog(QDialog):
    config_changed = pyqtSignal(dict)

    def __init__(self, cfg: dict, parent=None):
        super().__init__(parent)
        self._cfg = dict(cfg)
        self.setWindowTitle("Settings — Screen Translator")
        self.setMinimumWidth(460)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        layout.addWidget(tabs)

        # Languages
        lang_tab = QWidget()
        form = QFormLayout(lang_tab)
        self._src_combo = QComboBox()
        self._tgt_combo = QComboBox()
        for name, code in LANGUAGES.items():
            self._src_combo.addItem(name, code)
            if code != "auto":
                self._tgt_combo.addItem(name, code)
        self._set_combo(self._src_combo, self._cfg.get("source_lang", "auto"))
        self._set_combo(self._tgt_combo, self._cfg.get("target_lang", "en"))
        form.addRow("Source language:", self._src_combo)
        form.addRow("Target language:", self._tgt_combo)
        tabs.addTab(lang_tab, "🌐 Languages")

        # Capture
        cap_tab = QWidget()
        form2 = QFormLayout(cap_tab)
        self._interval_spin = QSpinBox()
        self._interval_spin.setRange(500, 30000)
        self._interval_spin.setSuffix(" ms")
        self._interval_spin.setValue(self._cfg.get("interval_ms", 2000))
        form2.addRow("Capture interval:", self._interval_spin)
        self._show_orig = QCheckBox("Show original text above translation")
        self._show_orig.setChecked(self._cfg.get("show_original", False))
        form2.addRow(self._show_orig)
        tabs.addTab(cap_tab, "📷 Capture")

        # Overlay Styles
        ov_tab = QWidget()
        form3 = QFormLayout(ov_tab)
        self._font_spin = QSpinBox()
        self._font_spin.setRange(8, 36)
        self._font_spin.setValue(self._cfg.get("font_size", 14))
        form3.addRow("Font size:", self._font_spin)
        self._opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self._opacity_slider.setRange(60, 255)
        self._opacity_slider.setValue(self._cfg.get("overlay_opacity", 220))
        form3.addRow("Background opacity:", self._opacity_slider)
        self._always_on_top = QCheckBox("Always on top")
        self._always_on_top.setChecked(self._cfg.get("always_on_top", True))
        form3.addRow(self._always_on_top)
        
        bg_btn = QPushButton("Choose background color…")
        self._bg_color = self._cfg.get("overlay_bg", "#1a1a2e")
        bg_btn.clicked.connect(self._pick_bg)
        form3.addRow("Background:", bg_btn)

        fg_btn = QPushButton("Choose text color…")
        self._fg_color = self._cfg.get("overlay_fg", "#e0e0ff")
        fg_btn.clicked.connect(self._pick_fg)
        form3.addRow("Text color:", fg_btn)
        tabs.addTab(ov_tab, "🎨 Overlay")

        # Advanced
        adv_tab = QWidget()
        form4 = QFormLayout(adv_tab)
        self._tess_edit = QTextEdit()
        self._tess_edit.setFixedHeight(40)
        self._tess_edit.setPlainText(self._cfg.get("tesseract_cmd", ""))
        form4.addRow("Tesseract path:", self._tess_edit)
        tabs.addTab(adv_tab, "⚙️ Advanced")

        btns = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._save)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(cancel_btn)
        btns.addWidget(save_btn)
        layout.addLayout(btns)

    def _set_combo(self, combo: QComboBox, code: str):
        for i in range(combo.count()):
            if combo.itemData(i) == code:
                combo.setCurrentIndex(i)
                return

    def _pick_bg(self):
        color = QColorDialog.getColor(QColor(self._bg_color), self, "Background Color")
        if color.isValid():
            self._bg_color = color.name()

    def _pick_fg(self):
        color = QColorDialog.getColor(QColor(self._fg_color), self, "Text Color")
        if color.isValid():
            self._fg_color = color.name()

    def _save(self):
        self._cfg["source_lang"] = self._src_combo.currentData()
        self._cfg["target_lang"] = self._tgt_combo.currentData()
        self._cfg["interval_ms"] = self._interval_spin.value()
        self._cfg["show_original"] = self._show_orig.isChecked()
        self._cfg["font_size"] = self._font_spin.value()
        self._cfg["overlay_opacity"] = self._opacity_slider.value()
        self._cfg["always_on_top"] = self._always_on_top.isChecked()
        self._cfg["overlay_bg"] = self._bg_color
        self._cfg["overlay_fg"] = self._fg_color
        self._cfg["tesseract_cmd"] = self._tess_edit.toPlainText().strip()
        save_config(self._cfg)
        self.config_changed.emit(self._cfg)
        self.accept()


# ─── Main window ──────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._cfg = load_config()
        self._region_str: str = self._cfg.get("region_str", "")
        self._running = False

        self.setWindowTitle("Screen Translator")
        self.setMinimumSize(360, 280)

        self._overlay = TranslationOverlay()
        self._overlay.apply_config(self._cfg)
        self._overlay.set_region(self._region_str)

        self._worker = TranslationWorker()
        self._worker.result_ready.connect(self._on_result)
        self._worker.error_signal.connect(self._on_error)
        self._worker.configure(self._cfg, self._region_str)
        self._worker.start()

        self._build_ui()
        self._build_tray()
        self._update_status_bar()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        title = QLabel("🔤 Screen Translator (Wayland)")
        title.setStyleSheet("font-size: 16pt; font-weight: bold;")
        root.addWidget(title)

        region_grp = QGroupBox("Selected Region")
        rg_layout = QVBoxLayout(region_grp)
        self._region_label = QLabel(self._region_text())
        self._region_label.setStyleSheet("font-family: monospace;")
        rg_layout.addWidget(self._region_label)

        region_btns = QHBoxLayout()
        self._select_btn = QPushButton("🖱 Select Region (Slurp)")
        self._select_btn.clicked.connect(self._start_selection)
        clear_btn = QPushButton("✕ Clear")
        clear_btn.clicked.connect(self._clear_region)
        region_btns.addWidget(self._select_btn)
        region_btns.addWidget(clear_btn)
        rg_layout.addLayout(region_btns)
        root.addWidget(region_grp)

        lang_grp = QGroupBox("Languages")
        lang_layout = QHBoxLayout(lang_grp)
        self._src_combo = QComboBox()
        self._tgt_combo = QComboBox()
        for name, code in LANGUAGES.items():
            self._src_combo.addItem(name, code)
            if code != "auto":
                self._tgt_combo.addItem(name, code)
        self._set_combo(self._src_combo, self._cfg.get("source_lang", "auto"))
        self._set_combo(self._tgt_combo, self._cfg.get("target_lang", "en"))
        self._src_combo.currentIndexChanged.connect(self._quick_lang_changed)
        self._tgt_combo.currentIndexChanged.connect(self._quick_lang_changed)
        lang_layout.addWidget(self._src_combo, 1)
        lang_layout.addWidget(QLabel("→"))
        lang_layout.addWidget(self._tgt_combo, 1)
        root.addWidget(lang_grp)

        self._toggle_btn = QPushButton("▶ Start Translation")
        self._toggle_btn.setMinimumHeight(36)
        self._toggle_btn.clicked.connect(self._toggle_translation)
        self._toggle_btn.setStyleSheet("background: #2a6edd; color: white; border-radius: 6px;")
        root.addWidget(self._toggle_btn)

        btn_row2 = QHBoxLayout()
        settings_btn = QPushButton("⚙️ Settings")
        settings_btn.clicked.connect(self._open_settings)
        diag_btn = QPushButton("🔍 Diagnostics")
        diag_btn.clicked.connect(self._run_diagnostics)
        btn_row2.addWidget(settings_btn)
        btn_row2.addWidget(diag_btn)
        root.addLayout(btn_row2)

        prev_grp = QGroupBox("Last Result")
        prev_layout = QVBoxLayout(prev_grp)
        self._original_label = QLabel("—")
        self._original_label.setWordWrap(True)
        self._translated_label = QLabel("—")
        self._translated_label.setWordWrap(True)
        prev_layout.addWidget(self._original_label)
        prev_layout.addWidget(self._translated_label)
        root.addWidget(prev_grp)

        self._status_label = QLabel()
        root.addWidget(self._status_label)

    def _build_tray(self):
        # Створюємо іконку (біла літера "T" на синьому тлі)
        pixmap = QPixmap(32, 32)
        pixmap.fill(QColor("#2a6edd"))
        painter = QPainter(pixmap)
        painter.setPen(QColor("white"))
        painter.setFont(QFont("sans-serif", 16, QFont.Weight.Bold))
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "T")
        painter.end()
        icon = QIcon(pixmap)
        
        self.setWindowIcon(icon) # Задаємо іконку також і для вікна

        # Створюємо трей додатка
        self._tray = QSystemTrayIcon(icon, self)
        
        menu = QMenu()
        show_act = QAction("👁 Показати вікно", self)
        show_act.triggered.connect(self.show)
        
        toggle_act = QAction("▶/⏹ Старт/Стоп", self)
        toggle_act.triggered.connect(self._toggle_translation)
        
        quit_act = QAction("✕ Вийти", self)
        quit_act.triggered.connect(self._quit)
        
        menu.addAction(show_act)
        menu.addAction(toggle_act)
        menu.addSeparator()
        menu.addAction(quit_act)
        
        self._tray.setContextMenu(menu)
        
        # Обробка кліку по самій іконці трею (відкрити/сховати вікно)
        self._tray.activated.connect(self._on_tray_activated)
        
        self._tray.show() # Показуємо трей обов'язково

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self.show()
                self.raise_()
                self.activateWindow()

    def _region_text(self) -> str:
        return self._region_str if self._region_str else "No region selected"

    def _set_combo(self, combo: QComboBox, code: str):
        for i in range(combo.count()):
            if combo.itemData(i) == code:
                combo.setCurrentIndex(i)
                return

    def _update_status_bar(self):
        interval = self._cfg.get("interval_ms", 2000)
        self._status_label.setText(f"Interval: {interval} ms | {'Running' if self._running else 'Stopped'}")

    def _start_selection(self):
        was_running = self._running
        if self._running:
            self._set_running(False)

        # Hide main window briefly so user can see what's under it
        self.hide()
        time.sleep(0.1) 

        # Call native slurp tool
        proc = subprocess.run(["slurp"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.show()

        if proc.returncode == 0:
            self._region_str = proc.stdout.decode().strip()
            self._cfg["region_str"] = self._region_str
            save_config(self._cfg)
            self._region_label.setText(self._region_text())
            self._overlay.set_region(self._region_str)
            self._worker.configure(self._cfg, self._region_str)
            if was_running:
                self._set_running(True)
        else:
            if was_running:
                self._set_running(True)

    def _clear_region(self):
        self._region_str = ""
        self._cfg["region_str"] = ""
        save_config(self._cfg)
        self._region_label.setText(self._region_text())
        self._overlay.hide()
        self._worker.configure(self._cfg, "")

    def _toggle_translation(self):
        self._set_running(not self._running)

    def _set_running(self, running: bool):
        self._running = running
        self._worker.set_paused(not running)
        if running:
            self._toggle_btn.setText("⏹ Stop Translation")
            self._toggle_btn.setStyleSheet("background: #c0392b; color: white; border-radius: 6px;")
            if not self._region_str:
                self._start_selection()
        else:
            self._toggle_btn.setText("▶ Start Translation")
            self._toggle_btn.setStyleSheet("background: #2a6edd; color: white; border-radius: 6px;")
        self._update_status_bar()

    def _quick_lang_changed(self):
        self._cfg["source_lang"] = self._src_combo.currentData()
        self._cfg["target_lang"] = self._tgt_combo.currentData()
        save_config(self._cfg)
        self._worker.configure(self._cfg, self._region_str)

    def _open_settings(self):
        dlg = SettingsDialog(self._cfg, self)
        dlg.config_changed.connect(self._apply_config)
        dlg.exec()

    def _apply_config(self, cfg: dict):
        self._cfg = cfg
        self._region_str = cfg.get("region_str", self._region_str)
        self._overlay.apply_config(cfg)
        self._worker.configure(cfg, self._region_str)
        self._set_combo(self._src_combo, cfg.get("source_lang", "auto"))
        self._set_combo(self._tgt_combo, cfg.get("target_lang", "en"))
        self._update_status_bar()

    @pyqtSlot(str, str)
    def _on_result(self, original: str, translated: str):
        self._original_label.setText(f"Orig: {original[:60]}")
        self._translated_label.setText(f"Trans: {translated[:60]}")
        self._overlay.update_text(original, translated)

    @pyqtSlot(str)
    def _on_error(self, msg: str):
        self._status_label.setText(f"⚠ Error: {msg[:50]}")

    def _run_diagnostics(self):
        lines = []
        for tool in ["grim", "slurp", "tesseract"]:
            res = subprocess.run(["which", tool], stdout=subprocess.PIPE)
            status = "✅ Found" if res.returncode == 0 else "❌ Missing"
            lines.append(f"{tool}: {status}")

        msg = QMessageBox(self)
        msg.setWindowTitle("Wayland Environment Diagnostics")
        msg.setText("\n".join(lines))
        msg.exec()

    def _quit(self):
        self._worker.stop()
        self._worker.wait(1000)
        self._overlay.close()
        QApplication.quit()

    def closeEvent(self, event):
        # Якщо трей працює і видимий — ховаємо вікно замість закриття
        if hasattr(self, "_tray") and self._tray.isVisible():
            self.hide()
            event.ignore() # Ігноруємо закриття додатка
        else:
            self._quit()
            event.accept()


def main():
    if not DEPS_OK:
        print(f"Missing Python dependencies: {MISSING_DEP}")
        sys.exit(1)

    # Let Qt detect native Wayland vs XWayland automatically 
    app = QApplication(sys.argv)
    app.setApplicationName("WaylandScreenTranslator")
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()