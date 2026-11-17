#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Chivet-kh Download (PyQt6)
------------------
A dark, premium download manager with:
  * multi-connection HTTP/HTTPS downloads with resume
  * video-site downloads through yt-dlp (YouTube, Facebook, TikTok, Instagram ...)
  * optional BitTorrent support through libtorrent (.torrent files and magnet links)
  * categories, queue, scheduler, global speed limit, system tray
  * browser integration: a local API on 127.0.0.1 used by the companion
    Chrome/Edge extension (folder "browser_extension")

Requirements:  pip install PyQt6 requests
Optional:      pip install yt-dlp        (video sites)
               pip install libtorrent    (torrents)
               ffmpeg in PATH            (merge best video+audio, mp3 extraction)
"""
import os
import re
import sys
import json
import time
import uuid
import shutil
import platform
import itertools
import threading
import subprocess
import urllib.parse
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import requests
from PyQt6.QtCore import (Qt, QTimer, QObject, pyqtSignal, QAbstractTableModel, QModelIndex,
                          QSize, QByteArray, QTime, QUrl, QRectF, QItemSelectionModel)
from PyQt6.QtGui import (QIcon, QPixmap, QPainter, QColor, QAction, QDesktopServices, QFont,
                         QLinearGradient, QKeySequence, QGuiApplication, QPainterPath, QPen)
from PyQt6.QtWidgets import (QPlainTextEdit, QTabWidget, QProgressBar, QTableWidget, QTableWidgetItem, QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QGridLayout, QFormLayout, QLabel, QLineEdit, QPushButton, QToolButton,
                             QTableView, QTreeWidget, QTreeWidgetItem, QSplitter, QHeaderView,
                             QAbstractItemView, QStyledItemDelegate, QStyle, QDialog, QDialogButtonBox,
                             QComboBox, QSpinBox, QCheckBox, QFileDialog, QMessageBox, QMenu,
                             QSystemTrayIcon, QStackedWidget, QTimeEdit, QInputDialog, QFrame,
                             QToolBar, QGroupBox, QTextBrowser, QSizePolicy)
from PyQt6.QtSvg import QSvgRenderer

try:
    import yt_dlp
    HAS_YTDLP = True
except Exception:
    yt_dlp = None
    HAS_YTDLP = False

try:
    import libtorrent as lt
    HAS_LT = True
except Exception:
    lt = None
    HAS_LT = False

APP_NAME = "Chivet-kh Download"
APP_SHORT = "ChivetKhDownload"
VERSION = "1.7.0"
DATA_DIR = Path.home() / ".chivet_kh_download"
# carry settings + download list over from the earlier builds (Chivet IDM, Mister DM)
for _old in (Path.home() / ".chivet_idm", Path.home() / ".mister_dm"):
    if not DATA_DIR.exists() and _old.is_dir():
        try:
            shutil.copytree(_old, DATA_DIR)
        except Exception:
            pass
DOWNLOADS_FILE = DATA_DIR / "downloads.json"
SETTINGS_FILE = DATA_DIR / "settings.json"
DEFAULT_PORT = 17890
DEFAULT_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")


def app_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


EXTENSION_DIR = app_base_dir() / "browser_extension"

# ----------------------------------------------------------------------------
# Theme
# ----------------------------------------------------------------------------
C_BG = "#0e1016"
C_PANEL = "#151821"
C_PANEL2 = "#1b1f2b"
C_BORDER = "#262b3a"
C_TEXT = "#e7e9f0"
C_MUTED = "#8a91a6"
C_ACCENT = "#7c5cff"
C_ACCENT2 = "#22d3ee"
C_GREEN = "#34d399"
C_RED = "#f87171"
C_AMBER = "#fbbf24"

STYLE = f"""
* {{ font-family: 'Segoe UI', 'Inter', 'Khmer UI', 'Leelawadee UI', 'Noto Sans Khmer', sans-serif; font-size: 10pt; color: {C_TEXT}; }}
QMainWindow, QDialog {{ background: {C_BG}; }}
QWidget#central {{ background: {C_BG}; }}
QMenuBar {{ background: {C_BG}; border-bottom: 1px solid {C_BORDER}; padding: 2px; }}
QMenuBar::item {{ padding: 5px 10px; border-radius: 6px; background: transparent; }}
QMenuBar::item:selected {{ background: {C_PANEL2}; }}
QMenu {{ background: {C_PANEL}; border: 1px solid {C_BORDER}; border-radius: 8px; padding: 6px; }}
QMenu::item {{ padding: 7px 22px 7px 12px; border-radius: 6px; }}
QMenu::item:selected {{ background: {C_ACCENT}; color: white; }}
QMenu::item:disabled {{ color: #4d5366; }}
QMenu::separator {{ height: 1px; background: {C_BORDER}; margin: 5px 8px; }}
QToolBar {{ background: {C_PANEL}; border: none; border-bottom: 1px solid {C_BORDER}; padding: 6px 8px; spacing: 2px; }}
QToolBar::separator {{ background: {C_BORDER}; width: 1px; margin: 8px 6px; }}
QToolButton {{ background: transparent; border: 1px solid transparent; border-radius: 10px; padding: 6px 8px; color: {C_TEXT}; }}
QToolButton:hover {{ background: {C_PANEL2}; border: 1px solid {C_BORDER}; }}
QToolButton:pressed {{ background: #232838; }}
QToolButton:disabled {{ color: #4d5366; }}
QToolButton::menu-indicator {{ image: none; }}
QToolButton[popupMode="1"] {{ padding-right: 16px; }}
QToolButton::menu-button {{ border: none; width: 14px; }}
QTreeWidget {{ show-decoration-selected: 0; selection-background-color: transparent; background: {C_PANEL}; border: 1px solid {C_BORDER}; border-radius: 12px; padding: 6px; outline: 0; }}
QTreeWidget::item {{ padding: 6px 4px; border-radius: 7px; }}
QTreeWidget::item:hover {{ background: {C_PANEL2}; }}
QTreeWidget::item:selected {{ background: rgba(124,92,255,0.22); color: white; }}
QTreeWidget::branch {{ background: transparent; }}
QTreeWidget::branch:selected {{ background: transparent; }}
QTableView {{ background: {C_PANEL}; alternate-background-color: #171b25; border: 1px solid {C_BORDER};
              border-radius: 12px; gridline-color: transparent; selection-background-color: rgba(124,92,255,0.28);
              selection-color: white; outline: 0; }}
QTableView::item {{ padding: 4px 6px; border: none; }}
QHeaderView::section {{ background: {C_PANEL}; color: {C_MUTED}; border: none; border-bottom: 1px solid {C_BORDER};
                        padding: 8px 6px; font-weight: 600; }}
QHeaderView {{ background: {C_PANEL}; border: none; }}
QTableCornerButton::section {{ background: {C_PANEL}; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 4px; }}
QScrollBar::handle:vertical {{ background: #2c3244; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: #3a4258; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 4px; }}
QScrollBar::handle:horizontal {{ background: #2c3244; border-radius: 4px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QLineEdit, QSpinBox, QComboBox, QTimeEdit {{ background: {C_PANEL2}; border: 1px solid {C_BORDER}; border-radius: 8px;
              padding: 7px 9px; selection-background-color: {C_ACCENT}; }}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QTimeEdit:focus {{ border: 1px solid {C_ACCENT}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{ background: {C_PANEL}; border: 1px solid {C_BORDER}; selection-background-color: {C_ACCENT}; }}
QSpinBox::up-button, QSpinBox::down-button, QTimeEdit::up-button, QTimeEdit::down-button {{ width: 16px; border: none; }}
QPushButton {{ background: {C_PANEL2}; border: 1px solid {C_BORDER}; border-radius: 9px; padding: 8px 16px; font-weight: 600; }}
QPushButton:hover {{ border: 1px solid #3a4258; background: #222839; }}
QPushButton:pressed {{ background: #232838; }}
QPushButton#primary {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {C_ACCENT}, stop:1 #5b8cff); border: none; color: white; }}
QPushButton#primary:hover {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #8b6dff, stop:1 #6d99ff); }}
QPushButton#link {{ background: transparent; border: none; color: {C_ACCENT2}; padding: 4px; font-weight: 600; }}
QPushButton#link:hover {{ text-decoration: underline; }}
QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 5px; border: 1px solid #3a4258; background: {C_PANEL2}; }}
QCheckBox::indicator:checked {{ background: {C_ACCENT}; border: 1px solid {C_ACCENT}; }}
QGroupBox {{ border: 1px solid {C_BORDER}; border-radius: 12px; margin-top: 14px; padding: 14px 12px 10px 12px; background: {C_PANEL}; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 14px; padding: 0 6px; color: {C_MUTED}; font-weight: 600; }}
QStatusBar {{ background: {C_PANEL}; border-top: 1px solid {C_BORDER}; color: {C_MUTED}; }}
QStatusBar QLabel {{ color: {C_MUTED}; padding: 0 8px; }}
QSplitter::handle {{ background: {C_BG}; width: 8px; }}
QToolTip {{ background: {C_PANEL2}; color: {C_TEXT}; border: 1px solid {C_BORDER}; padding: 5px; border-radius: 6px; }}
QTextBrowser {{ background: {C_PANEL}; border: 1px solid {C_BORDER}; border-radius: 10px; padding: 8px; }}
QLabel#muted {{ color: {C_MUTED}; }}
QTabWidget::pane {{ border: 1px solid {C_BORDER}; border-radius: 10px; background: {C_PANEL}; top: -1px; }}
QTabBar::tab {{ background: transparent; color: {C_MUTED}; padding: 8px 14px; margin-right: 2px; border: 1px solid transparent;
                border-top-left-radius: 8px; border-top-right-radius: 8px; font-weight: 600; }}
QTabBar::tab:selected {{ background: {C_PANEL}; color: {C_TEXT}; border: 1px solid {C_BORDER}; border-bottom-color: {C_PANEL}; }}
QTabBar::tab:hover:!selected {{ color: {C_TEXT}; }}
QProgressBar {{ background: #252a39; border: none; border-radius: 7px; height: 16px; text-align: center; color: white; font-weight: 700; }}
QProgressBar::chunk {{ border-radius: 7px; background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {C_ACCENT}, stop:1 {C_ACCENT2}); }}
QProgressBar#done::chunk {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #10b981, stop:1 {C_GREEN}); }}
QProgressBar#paused::chunk {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #d97706, stop:1 {C_AMBER}); }}
QLineEdit#ro {{ background: transparent; border: none; padding: 0; }}
QTableView::indicator {{ width: 16px; height: 16px; border-radius: 5px; border: 1px solid #4a5268; background: {C_PANEL2}; }}
QTableView::indicator:checked {{ border: 1px solid {C_ACCENT}; background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 {C_ACCENT}, stop:1 {C_ACCENT2}); }}
QLabel#title {{ font-size: 15pt; font-weight: 700; }}
"""

# ----------------------------------------------------------------------------
# SVG icons (24x24 line icons, drawn for this app)
# ----------------------------------------------------------------------------
ICONS = {
    "add": '<path d="M12 4.5v15M4.5 12h15"/>',
    "magnet": '<path d="M5 4h4v7.5a3 3 0 0 0 6 0V4h4v7.5a7 7 0 0 1-14 0z"/><path d="M5 8h4M15 8h4"/>',
    "resume": '<circle cx="12" cy="12" r="9"/><path d="M12 7.5v9M8.3 12.8 12 16.5l3.7-3.7"/>',
    "stop": '<circle cx="12" cy="12" r="9"/><rect x="9" y="9" width="6" height="6" rx="1.2"/>',
    "stopall": '<circle cx="12" cy="12" r="9"/><path d="M5.7 5.7l12.6 12.6"/>',
    "delete": '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>',
    "delclean": '<path d="M4 7h16M6 7l1 13h10l1-13M9 7V4h6v3"/><path d="M9.3 13.6l2 2 3.6-3.8"/>',
    "options": '<circle cx="12" cy="12" r="3.2"/><path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3M5.3 5.3l2.1 2.1M16.6 16.6l2.1 2.1M5.3 18.7l2.1-2.1M16.6 7.4l2.1-2.1"/>',
    "scheduler": '<circle cx="12" cy="13" r="8"/><path d="M12 9v4.2l2.8 1.8M5 3.5 2.5 6M19 3.5 21.5 6"/>',
    "qstart": '<rect x="3" y="3.5" width="14" height="14" rx="2.5"/><path d="M8 21h10.5a2.5 2.5 0 0 0 2.5-2.5V8"/><path d="M10 7.5v6M7.6 11.2 10 13.6l2.4-2.4"/>',
    "qstop": '<rect x="3" y="3.5" width="14" height="14" rx="2.5"/><path d="M8 21h10.5a2.5 2.5 0 0 0 2.5-2.5V8"/><rect x="7.5" y="8" width="5" height="5" rx="1"/>',
    "all": '<path d="M12 3v12M7 10l5 5 5-5"/><path d="M4 17v2.5A1.5 1.5 0 0 0 5.5 21h13a1.5 1.5 0 0 0 1.5-1.5V17"/>',
    "compressed": '<rect x="3.5" y="4" width="17" height="5" rx="1.5"/><path d="M5 9v9.5A1.5 1.5 0 0 0 6.5 20h11a1.5 1.5 0 0 0 1.5-1.5V9M10 13h4"/>',
    "documents": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M9 13h6M9 17h6"/>',
    "music": '<path d="M9 18V5l11-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="17" cy="16" r="3"/>',
    "programs": '<rect x="3" y="4" width="18" height="16" rx="2.5"/><path d="M3 9h18M7 6.5h.01M10 6.5h.01"/>',
    "video": '<rect x="3" y="5" width="18" height="14" rx="2.5"/><path d="M10 9.5v5l4.5-2.5z"/>',
    "torrents": '<path d="M5 4h4v7.5a3 3 0 0 0 6 0V4h4v7.5a7 7 0 0 1-14 0z"/>',
    "unfinished": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "finished": '<circle cx="12" cy="12" r="9"/><path d="M8 12.5l2.7 2.7L16.5 9.5"/>',
    "queues": '<path d="M8 6h13M8 12h13M8 18h13M3.5 6h.01M3.5 12h.01M3.5 18h.01"/>',
    "other": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/>',
    "folder": '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    "open": '<path d="M14 4h6v6M20 4l-9 9M18 14v4a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4"/>',
    "copy": '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/>',
    "refresh": '<path d="M20 11a8 8 0 1 0-2.3 5.7M20 4v7h-7"/>',
    "puzzle": '<path d="M10 3.5a2 2 0 0 1 4 0V6h4a1 1 0 0 1 1 1v4h-2.5a2 2 0 0 0 0 4H19v4a1 1 0 0 1-1 1h-4v-2.5a2 2 0 0 0-4 0V20H6a1 1 0 0 1-1-1v-4h2.5a2 2 0 0 0 0-4H5V7a1 1 0 0 1 1-1h4z"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.5h.01"/>',
    "image": '<rect x="3" y="4" width="18" height="16" rx="2.5"/><circle cx="8.5" cy="9.5" r="1.8"/><path d="M21 16l-5-5-9 9"/>',
}

ICON_COLORS = {
    "add": "#34d399", "magnet": "#a78bfa", "resume": "#60a5fa", "stop": "#f59e0b", "stopall": "#f87171",
    "delete": "#f87171", "delclean": "#fb923c", "options": "#a78bfa", "scheduler": "#f472b6",
    "qstart": "#22d3ee", "qstop": "#94a3b8", "all": "#7c5cff", "compressed": "#fbbf24", "documents": "#60a5fa",
    "music": "#f472b6", "programs": "#34d399", "video": "#22d3ee", "torrents": "#a78bfa", "unfinished": "#f59e0b",
    "finished": "#34d399", "queues": "#94a3b8", "other": "#94a3b8", "folder": "#fbbf24", "open": "#60a5fa",
    "copy": "#94a3b8", "refresh": "#22d3ee", "puzzle": "#a78bfa", "info": "#60a5fa", "image": "#fb923c",
}

_icon_cache = {}


def _render_svg(svg: str, size: int) -> QPixmap:
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(p)
    p.end()
    return pm


def icon(name: str, color: str = None) -> QIcon:
    key = (name, color)
    if key in _icon_cache:
        return _icon_cache[key]
    body = ICONS.get(name, ICONS["other"])
    color = color or ICON_COLORS.get(name, C_TEXT)
    ic = QIcon()
    for mode, col in ((QIcon.Mode.Normal, color), (QIcon.Mode.Disabled, "#454b5e"),
                      (QIcon.Mode.Active, color), (QIcon.Mode.Selected, "#ffffff")):
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{col}" '
               f'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">{body}</svg>')
        for s in (16, 20, 24, 32, 48, 64):
            ic.addPixmap(_render_svg(svg, s), mode)
    _icon_cache[key] = ic
    return ic


def app_icon() -> QIcon:
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
           '<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
           '<stop offset="0" stop-color="#7c5cff"/><stop offset="1" stop-color="#22d3ee"/></linearGradient></defs>'
           '<rect x="2" y="2" width="60" height="60" rx="16" fill="url(#g)"/>'
           '<path d="M32 14v26M21 30l11 11 11-11" fill="none" stroke="#fff" stroke-width="6" '
           'stroke-linecap="round" stroke-linejoin="round"/>'
           '<path d="M17 47h30" stroke="#fff" stroke-width="6" stroke-linecap="round"/></svg>')
    ic = QIcon()
    for s in (16, 24, 32, 48, 64, 128, 256):
        ic.addPixmap(_render_svg(svg, s))
    return ic


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
CATEGORIES = ["Compressed", "Documents", "Images", "Music", "Programs", "Video", "Torrents"]
CATEGORY_ICONS = {"Compressed": "compressed", "Documents": "documents", "Images": "image", "Music": "music",
                  "Programs": "programs", "Video": "video", "Torrents": "torrents", "Other": "other"}
EXT_MAP = {
    "Compressed": "zip rar 7z tar gz tgz bz2 xz iso cab arj lzh z zst".split(),
    "Documents": "pdf doc docx xls xlsx ppt pptx txt rtf odt ods odp epub csv md".split(),
    "Music": "mp3 wav flac aac m4a ogg opus wma aiff mid".split(),
    "Programs": "exe msi apk xapk dmg pkg deb rpm appimage bat jar".split(),
    "Images": "jpg jpeg png gif webp bmp svg avif heic tif tiff".split(),
    "Video": "mp4 mkv avi mov wmv flv webm m4v ts 3gp mpg mpeg vob".split(),
}
VIDEO_SITES = ("youtube.com", "youtu.be", "facebook.com", "fb.watch", "tiktok.com", "instagram.com",
               "twitter.com", "x.com", "vimeo.com", "dailymotion.com", "twitch.tv", "bilibili.com",
               "reddit.com", "soundcloud.com", "pinterest.com", "threads.net")


def category_for(name: str, kind: str = "http") -> str:
    if kind == "torrent":
        return "Torrents"
    if kind == "ytdlp":
        return "Video"
    ext = os.path.splitext(name or "")[1].lower().lstrip(".")
    for cat, exts in EXT_MAP.items():
        if ext in exts:
            return cat
    return "Other"


def human_size(n) -> str:
    if n is None or n < 0:
        return "Unknown"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.2f} {unit}"
        n /= 1024.0
    return f"{n:.2f} TB"


def human_speed(bps) -> str:
    if not bps or bps <= 0:
        return ""
    return human_size(bps) + "/s"


def human_eta(sec) -> str:
    if sec is None or sec < 0 or sec == float("inf"):
        return ""
    sec = int(sec)
    if sec < 60:
        return f"{sec} sec"
    m, s = divmod(sec, 60)
    if m < 60:
        return f"{m} min {s:02d} sec"
    h, m = divmod(m, 60)
    if h < 48:
        return f"{h} h {m:02d} min"
    return f"{h // 24} days"


_BAD_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def safe_filename(name: str) -> str:
    name = _BAD_CHARS.sub("_", (name or "").strip()).strip(" .")
    return name[:200] or "download"


def filename_from_url(url: str) -> str:
    try:
        path = urllib.parse.urlparse(url).path
        name = urllib.parse.unquote(os.path.basename(path))
    except Exception:
        name = ""
    return safe_filename(name) if name else "download"


def filename_from_headers(headers, url: str) -> str:
    cd = headers.get("Content-Disposition", "") or ""
    m = re.search(r"filename\*\s*=\s*([^']*)'[^']*'([^;]+)", cd, re.I)
    if m:
        try:
            return safe_filename(urllib.parse.unquote(m.group(2).strip().strip('"'), encoding=m.group(1) or "utf-8"))
        except Exception:
            pass
    m = re.search(r'filename\s*=\s*"([^"]+)"', cd, re.I) or re.search(r"filename\s*=\s*([^;]+)", cd, re.I)
    if m:
        raw = m.group(1).strip()
        try:
            raw = raw.encode("latin-1").decode("utf-8")
        except Exception:
            pass
        return safe_filename(urllib.parse.unquote(raw))
    name = filename_from_url(url)
    if "." not in name:
        ctype = (headers.get("Content-Type", "") or "").split(";")[0].strip().lower()
        guess = {"application/pdf": ".pdf", "application/zip": ".zip", "video/mp4": ".mp4",
                 "audio/mpeg": ".mp3", "application/vnd.android.package-archive": ".apk",
                 "application/x-msdownload": ".exe", "image/jpeg": ".jpg", "image/png": ".png",
                 "video/webm": ".webm", "application/x-rar-compressed": ".rar", "image/webp": ".webp",
                 "image/gif": ".gif", "image/avif": ".avif", "image/svg+xml": ".svg", "image/bmp": ".bmp",
                 "image/heic": ".heic"}.get(ctype)
        if guess:
            name += guess
    return name


def is_video_site(url: str) -> bool:
    try:
        host = urllib.parse.urlparse(url).netloc.lower().split(":")[0]
    except Exception:
        return False
    return any(host == d or host.endswith("." + d) for d in VIDEO_SITES)


_FFMPEG_AUTO = []


def find_ffmpeg(settings: dict = None):
    """ffmpeg chosen in Helpers → ffmpeg in PATH → bundled imageio-ffmpeg binary."""
    p = (settings or {}).get("ffmpeg_path") or ""
    if p and os.path.isfile(p):
        return p
    if not _FFMPEG_AUTO:
        found = shutil.which("ffmpeg")
        if not found:
            try:
                import imageio_ffmpeg
                found = imageio_ffmpeg.get_ffmpeg_exe()
            except Exception:
                found = None
        _FFMPEG_AUTO.append(found)
    return _FFMPEG_AUTO[0]


def looks_like_url(text: str) -> bool:
    t = (text or "").strip()
    return t.startswith(("http://", "https://", "magnet:?")) and " " not in t


def open_path(path: str):
    if path and os.path.exists(path):
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))


def reveal_in_folder(path: str):
    if not path:
        return
    try:
        if platform.system() == "Windows" and os.path.exists(path):
            subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
            return
        if platform.system() == "Darwin" and os.path.exists(path):
            subprocess.Popen(["open", "-R", path])
            return
    except Exception:
        pass
    folder = path if os.path.isdir(path) else os.path.dirname(path)
    if os.path.isdir(folder):
        QDesktopServices.openUrl(QUrl.fromLocalFile(folder))


def load_json(path: Path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = str(path) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


DEFAULT_SETTINGS = {
    "download_dir": str(Path.home() / "Downloads" / "ChivetKhDownload"),
    "category_subfolders": True,
    "connections": 8,
    "max_concurrent": 3,
    "speed_limit_kb": 0,
    "port": DEFAULT_PORT,
    "browser_confirm": True,
    "close_to_tray": True,
    "autostart": True,
    "ytdlp_quality": "best",
    "ffmpeg_path": "",
    "show_progress_dialog": True,
    "show_complete_dialog": True,
    "scheduler": {"start_enabled": False, "start_time": "02:00", "stop_enabled": False,
                  "stop_time": "07:00", "days": [0, 1, 2, 3, 4, 5, 6], "on_finish": "nothing"},
}


def load_settings() -> dict:
    s = json.loads(json.dumps(DEFAULT_SETTINGS))
    data = load_json(SETTINGS_FILE, {})
    if isinstance(data, dict):
        sched = data.pop("scheduler", None)
        s.update(data)
        if isinstance(sched, dict):
            s["scheduler"].update(sched)
    return s


# ----------------------------------------------------------------------------
# Data model
# ----------------------------------------------------------------------------
RUNTIME_FIELDS = ("speed", "eta", "phase")


@dataclass
class DownloadItem:
    url: str
    filename: str
    save_dir: str
    kind: str = "http"                 # http | ytdlp | torrent
    category: str = "Other"
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    size: int = -1
    downloaded: int = 0
    status: str = "Queued"             # Queued | Connecting | Downloading | Processing | Stopped | Finished | Error
    in_queue: bool = False
    added: float = field(default_factory=time.time)
    finished_at: float = 0.0
    resumable: bool = False
    segments: list = field(default_factory=list)
    headers: dict = field(default_factory=dict)
    connections: int = 8
    auto_name: bool = True
    error: str = ""
    quality: str = "best"
    torrent_source: str = ""
    title_hint: str = ""
    ytdlp_format: str = ""
    audio_format: str = ""
    audio_quality: str = ""
    sub_lang: str = ""
    sub_auto: bool = False
    embed_subs: bool = False
    peers: int = 0
    ratio: float = 0.0
    speed_limit_kb: int = 0
    open_when_done: bool = False
    folder_when_done: bool = False
    shutdown_when_done: bool = False
    speed: float = 0.0
    eta: float = -1
    phase: str = ""

    def target_path(self) -> str:
        return os.path.join(self.save_dir, self.filename)

    def temp_path(self) -> str:
        return self.target_path() + ".mdm"

    def progress(self) -> float:
        if self.status == "Finished":
            return 100.0
        if self.size and self.size > 0:
            return max(0.0, min(100.0, self.downloaded * 100.0 / self.size))
        return 0.0

    def to_dict(self) -> dict:
        d = asdict(self)
        for k in RUNTIME_FIELDS:
            d.pop(k, None)
        d["segments"] = [list(s) for s in self.segments]
        return d

    @staticmethod
    def from_dict(d: dict) -> "DownloadItem":
        known = {f for f in DownloadItem.__dataclass_fields__ if f not in RUNTIME_FIELDS}
        it = DownloadItem(**{k: v for k, v in d.items() if k in known})
        if it.status in ("Downloading", "Connecting", "Processing"):
            it.status = "Stopped"
        return it


class Bridge(QObject):
    task_done = pyqtSignal(str, str, str)        # id, result(finished|stopped|error), message
    browser_add = pyqtSignal(dict)
    show_window = pyqtSignal()
    probe_result = pyqtSignal(int, dict)
    lookup_result = pyqtSignal(int, object)
    batch_add = pyqtSignal(dict)
    links_add = pyqtSignal(dict)
    links_result = pyqtSignal(int, int, object)
    thumb_result = pyqtSignal(int, bytes)


class Throttle:
    """Global leaky-bucket speed limiter shared by every connection."""

    def __init__(self):
        self.rate = 0
        self._lock = threading.Lock()
        self._allow = time.monotonic()

    def consume(self, n: int):
        if self.rate <= 0:
            return
        with self._lock:
            now = time.monotonic()
            if self._allow < now:
                self._allow = now
            self._allow += n / float(self.rate)
            wait = self._allow - now
        if wait > 0:
            time.sleep(min(wait, 2.0))


# ----------------------------------------------------------------------------
# Download engines
# ----------------------------------------------------------------------------
class BaseTask:
    reports_speed = False

    def __init__(self, item: DownloadItem, settings: dict, throttle: Throttle, bridge: Bridge):
        self.item = item
        self.settings = settings
        self.throttle = throttle
        self.bridge = bridge
        self.stop_event = threading.Event()
        self.thread = None

    def start(self):
        self.thread = threading.Thread(target=self._safe_run, daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()

    def _safe_run(self):
        try:
            self.run()
        except Exception as e:  # last-resort guard
            if self.stop_event.is_set():
                self.bridge.task_done.emit(self.item.id, "stopped", "")
            else:
                self.bridge.task_done.emit(self.item.id, "error", str(e))

    def run(self):
        raise NotImplementedError


class HttpTask(BaseTask):
    CHUNK = 64 * 1024
    MAX_RETRIES = 8

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.lock = threading.Lock()
        self.errors = []
        self.seg_info = {}
        self.local = Throttle()
        self.local.rate = int(self.item.speed_limit_kb or 0) * 1024

    def _headers(self) -> dict:
        h = {"User-Agent": DEFAULT_UA, "Accept": "*/*"}
        for k, v in (self.item.headers or {}).items():
            if v:
                h[k] = v
        h["Accept-Encoding"] = "identity"
        return h

    def _probe(self):
        it = self.item
        with requests.get(it.url, headers={**self._headers(), "Range": "bytes=0-"}, stream=True,
                          timeout=(15, 30), allow_redirects=True) as r:
            r.raise_for_status()
            size, resumable = -1, False
            if r.status_code == 206:
                m = re.search(r"/(\d+)\s*$", r.headers.get("Content-Range", ""))
                if m:
                    size, resumable = int(m.group(1)), True
            else:
                cl = r.headers.get("Content-Length", "")
                if cl.isdigit():
                    size = int(cl)
                resumable = r.headers.get("Accept-Ranges", "").lower() == "bytes" and size > 0
            if it.auto_name:
                name = filename_from_headers(r.headers, r.url)
                if name and name != it.filename:
                    try:
                        if os.path.exists(it.temp_path()):
                            os.remove(it.temp_path())
                    except OSError:
                        pass
                    it.filename = unique_name(it.save_dir, name, exclude_id=it.id)
                    if it.category != "Images":
                        it.category = category_for(it.filename)
        it.size, it.resumable = size, resumable

    def _init_segments(self):
        it = self.item
        conns = max(1, int(it.connections or 1))
        if it.resumable and it.size > 2 * 1024 * 1024 and conns > 1:
            n = int(min(conns, max(1, it.size // (1024 * 1024))))
            part = it.size // n
            it.segments = [[i * part, (it.size - 1) if i == n - 1 else (i + 1) * part - 1, 0] for i in range(n)]
        else:
            it.segments = [[0, it.size - 1 if it.size > 0 else -1, 0]]
        os.makedirs(it.save_dir, exist_ok=True)
        with open(it.temp_path(), "wb") as f:
            if it.size > 0:
                f.truncate(it.size)
        it.downloaded = 0

    @staticmethod
    def _seg_done(seg) -> bool:
        return seg[1] >= 0 and seg[0] + seg[2] > seg[1]

    def run(self):
        it = self.item
        it.status, it.error = "Connecting", ""
        os.makedirs(it.save_dir, exist_ok=True)
        if not it.segments or not it.resumable or not os.path.exists(it.temp_path()):
            self._probe()
            if self.stop_event.is_set():
                self.bridge.task_done.emit(it.id, "stopped", "")
                return
            self._init_segments()
        it.downloaded = sum(s[2] for s in it.segments)
        it.status = "Downloading"
        threads = [threading.Thread(target=self._seg_worker, args=(i,), daemon=True)
                   for i, s in enumerate(it.segments) if not self._seg_done(s)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        if self.stop_event.is_set():
            self.bridge.task_done.emit(it.id, "stopped", "")
            return
        if self.errors:
            self.bridge.task_done.emit(it.id, "error", self.errors[0])
            return
        if it.size > 0 and it.downloaded < it.size:
            self.bridge.task_done.emit(it.id, "error", "Download incomplete — press Resume to continue")
            return
        if it.size <= 0:
            it.size = it.downloaded
        final = it.target_path()
        if os.path.exists(final):
            it.filename = unique_name(it.save_dir, it.filename, exclude_id=it.id, check_items=False)
            final = it.target_path()
        os.replace(it.temp_path(), final)
        self.bridge.task_done.emit(it.id, "finished", "")

    def _seg_worker(self, idx: int):
        it = self.item
        seg = it.segments[idx]
        tries = 0
        while not self.stop_event.is_set():
            if self._seg_done(seg):
                self.seg_info[idx] = "Finished"
                return
            pos = seg[0] + seg[2]
            h = self._headers()
            if it.resumable:
                h["Range"] = f"bytes={pos}-{seg[1]}"
            self.seg_info[idx] = "Send GET…"
            try:
                with requests.get(it.url, headers=h, stream=True, timeout=(15, 30), allow_redirects=True) as r:
                    r.raise_for_status()
                    self.seg_info[idx] = "Receiving data…"
                    if it.resumable and r.status_code != 206 and not (pos == 0 and seg[1] == it.size - 1):
                        raise IOError(f"Server ignored the byte range (HTTP {r.status_code})")
                    with open(it.temp_path(), "r+b") as f:
                        f.seek(pos)
                        for chunk in r.iter_content(self.CHUNK):
                            if self.stop_event.is_set():
                                return
                            if not chunk:
                                continue
                            if seg[1] >= 0:
                                remaining = seg[1] - (seg[0] + seg[2]) + 1
                                if remaining <= 0:
                                    break
                                chunk = chunk[:remaining]
                            f.write(chunk)
                            n = len(chunk)
                            seg[2] += n
                            with self.lock:
                                it.downloaded += n
                            tries = 0
                            self.throttle.consume(n)
                            self.local.consume(n)
                if seg[1] < 0:
                    self.seg_info[idx] = "Finished"
                    return  # unknown size: the stream ended, file complete
                if not it.resumable and not self._seg_done(seg):
                    raise IOError("Connection closed before the file finished (server has no resume support)")
            except Exception as e:
                if self.stop_event.is_set():
                    return
                tries += 1
                if tries >= self.MAX_RETRIES or not it.resumable:
                    self.seg_info[idx] = "Error: " + str(e)[:80]
                    self.errors.append(str(e))
                    return
                self.seg_info[idx] = f"Connection lost, retrying ({tries})…"
                self.stop_event.wait(min(2 * tries, 10))
        if self.stop_event.is_set() and not self._seg_done(seg):
            self.seg_info[idx] = "Paused"


class StopDownload(Exception):
    pass


YTDLP_QUALITIES = [("best", "Best quality"), ("1080", "1080p"), ("720", "720p"),
                   ("480", "480p"), ("audio", "Audio only (MP3)")]


class _QuietLogger:
    def debug(self, msg):
        pass

    def info(self, msg):
        pass

    def warning(self, msg):
        pass

    def error(self, msg):
        pass


class YtdlpTask(BaseTask):
    reports_speed = True

    def run(self):
        it = self.item
        it.status, it.error = "Connecting", ""
        os.makedirs(it.save_dir, exist_ok=True)
        ff = find_ffmpeg(self.settings)
        has_ff = ff is not None
        q = it.quality or "best"
        if it.ytdlp_format:
            fmt = it.ytdlp_format
        elif q == "audio":
            fmt = "ba/b"
        elif q in ("1080", "720", "480"):
            fmt = (f"bv*[height<={q}]+ba/b[height<={q}]/b" if has_ff else f"b[height<={q}]/b")
        else:
            fmt = "bv*+ba/b" if has_ff else "b"
        state = {"files": {}}

        def hook(d):
            if self.stop_event.is_set():
                raise StopDownload()
            fn = d.get("filename") or ""
            if d.get("status") == "downloading":
                it.status = "Downloading"
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                state["files"][fn] = (d.get("downloaded_bytes") or 0, total)
                it.downloaded = sum(v[0] for v in state["files"].values())
                tot = sum(v[1] for v in state["files"].values())
                it.size = int(tot) if tot else -1
                it.speed = d.get("speed") or 0
                it.eta = d.get("eta") if d.get("eta") is not None else -1
                if fn:
                    it.filename = os.path.basename(fn)
                info = d.get("info_dict") or {}
                part = ("video stream" if info.get("vcodec") not in (None, "none") and info.get("acodec") == "none"
                        else "audio stream" if info.get("vcodec") == "none" else "file")
                it.phase = f"Receiving {part}…"
            elif d.get("status") == "finished":
                it.status = "Processing"
                it.phase = "Merging / converting…"
                it.speed, it.eta = 0, -1

        outtmpl = os.path.join(it.save_dir, "%(title).90s [%(id)s].%(ext)s")
        if not it.auto_name and it.filename:
            outtmpl = os.path.join(it.save_dir, safe_filename(os.path.splitext(it.filename)[0])[:150] + ".%(ext)s")
        elif it.title_hint and re.search(r"\.(m3u8|mpd)(\?|$)", it.url, re.I):
            outtmpl = os.path.join(it.save_dir, safe_filename(it.title_hint)[:90] + ".%(ext)s")
        opts = {
            "outtmpl": outtmpl,
            "format": fmt, "noplaylist": True, "quiet": True, "no_warnings": True,
            "continuedl": True, "progress_hooks": [hook], "windowsfilenames": True, "logger": _QuietLogger(),
            "http_headers": {"User-Agent": it.headers.get("User-Agent") or DEFAULT_UA},
        }
        if it.headers.get("Cookie"):
            opts["http_headers"]["Cookie"] = it.headers["Cookie"]
        if it.headers.get("Referer"):
            opts["http_headers"]["Referer"] = it.headers["Referer"]
        audio_only = bool(it.audio_format) or q == "audio" or fmt.startswith("ba")
        pps = []
        if ff:
            opts["ffmpeg_location"] = ff
        if has_ff and not audio_only:
            opts["merge_output_format"] = "mp4"
        if has_ff and (it.audio_format == "mp3" or (q == "audio" and not it.ytdlp_format)):
            pps.append({"key": "FFmpegExtractAudio", "preferredcodec": "mp3",
                        "preferredquality": it.audio_quality or "192"})
        subs_only = it.audio_format == "subs"
        if subs_only:
            opts["skip_download"] = True
            pps = [{"key": "FFmpegSubtitlesConvertor", "format": "srt", "when": "before_dl"}] if has_ff else []
        if it.sub_lang:
            langs = [x.strip() for x in it.sub_lang.split(",") if x.strip()]
            opts["subtitleslangs"] = ["all", "-live_chat"] if "all" in langs else langs
            opts["writesubtitles"] = True
            if it.sub_auto:
                opts["writeautomaticsub"] = True
            if it.embed_subs and has_ff and not audio_only and not subs_only:
                pps.append({"key": "FFmpegEmbedSubtitle", "already_have_subtitle": False})
            elif has_ff and not subs_only:
                pps.append({"key": "FFmpegSubtitlesConvertor", "format": "srt", "when": "before_dl"})
        if pps:
            opts["postprocessors"] = pps
        limits = [int(x) for x in (self.settings.get("speed_limit_kb", 0), it.speed_limit_kb) if x and int(x) > 0]
        if limits:
            opts["ratelimit"] = min(limits) * 1024
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(it.url, download=True)
                path = ""
                if info:
                    reqs = info.get("requested_downloads") or []
                    if reqs:
                        path = reqs[0].get("filepath") or reqs[0].get("_filename") or ""
                    if not path:
                        path = ydl.prepare_filename(info)
            if subs_only:
                files = [v.get("filepath") for v in ((info or {}).get("requested_subtitles") or {}).values() if v.get("filepath")]
                files = [f for f in files if f and os.path.exists(f)]
                if not files:
                    raise RuntimeError("This video has no subtitles in the chosen language")
                it.filename = os.path.basename(files[0]) if len(files) == 1 else f"{len(files)} subtitle files"
                it.size = it.downloaded = sum(os.path.getsize(f) for f in files)
                it.save_dir = os.path.dirname(files[0])
                self.bridge.task_done.emit(it.id, "finished", "")
                return
            if path and not os.path.exists(path) and it.audio_format and it.audio_format != "subs":
                alt = os.path.splitext(path)[0] + "." + it.audio_format
                path = alt if os.path.exists(alt) else path
            if path and os.path.exists(path):
                it.filename = os.path.basename(path)
                it.save_dir = os.path.dirname(path)
                it.size = it.downloaded = os.path.getsize(path)
            self.bridge.task_done.emit(it.id, "finished", "")
        except Exception as e:
            if self.stop_event.is_set() or isinstance(e, StopDownload) or "StopDownload" in repr(e):
                self.bridge.task_done.emit(it.id, "stopped", "")
            else:
                msg = re.sub(r"\x1b\[[0-9;]*m", "", str(e))
                self.bridge.task_done.emit(it.id, "error", msg.replace("ERROR: ", "")[:300])


class TorrentTask(BaseTask):
    reports_speed = True
    _session = None
    _session_lock = threading.Lock()

    @classmethod
    def session(cls):
        with cls._session_lock:
            if cls._session is None:
                cls._session = lt.session({"listen_interfaces": "0.0.0.0:6881,[::]:6881"})
            return cls._session

    def run(self):
        it = self.item
        it.status, it.error = "Connecting", ""
        os.makedirs(it.save_dir, exist_ok=True)
        ses = self.session()
        src = it.torrent_source
        if src.startswith("magnet:"):
            params = lt.parse_magnet_uri(src)
        else:
            params = lt.add_torrent_params()
            params.ti = lt.torrent_info(src)
        params.save_path = it.save_dir
        rate = int(self.settings.get("speed_limit_kb", 0)) * 1024
        handle = ses.add_torrent(params)
        if rate > 0:
            handle.set_download_limit(rate)
        try:
            while not self.stop_event.is_set():
                s = handle.status()
                if s.has_metadata:
                    if s.name:
                        it.filename = s.name
                    it.size = int(s.total_wanted)
                    it.status = "Downloading"
                else:
                    it.status = "Connecting"
                it.downloaded = int(s.total_wanted_done)
                it.speed = float(s.download_rate)
                it.peers = int(s.num_peers)
                dl = max(1, int(s.all_time_download))
                it.ratio = round(float(s.all_time_upload) / dl, 3)
                it.eta = (it.size - it.downloaded) / it.speed if it.speed > 0 and it.size > 0 else -1
                if s.has_metadata and it.size > 0 and it.downloaded >= it.size:
                    break
                self.stop_event.wait(1.0)
        finally:
            try:
                ses.remove_torrent(handle)
            except Exception:
                pass
        if self.stop_event.is_set():
            self.bridge.task_done.emit(it.id, "stopped", "")
        else:
            self.bridge.task_done.emit(it.id, "finished", "")


# Registry used by unique_name() to avoid clashes with not-yet-finished downloads
_ITEM_REGISTRY = {}


def unique_name(folder: str, name: str, exclude_id: str = None, check_items: bool = True) -> str:
    name = safe_filename(name)
    base, ext = os.path.splitext(name)
    taken = set()
    if check_items:
        for it in list(_ITEM_REGISTRY.values()):
            if it.id != exclude_id and os.path.normcase(it.save_dir) == os.path.normcase(folder):
                taken.add(it.filename.lower())
    candidate, i = name, 1
    while (candidate.lower() in taken or os.path.exists(os.path.join(folder, candidate))
           or os.path.exists(os.path.join(folder, candidate + ".mdm"))):
        i += 1
        candidate = f"{base} ({i}){ext}"
    return candidate


# ----------------------------------------------------------------------------
# Local API for the browser extension
# ----------------------------------------------------------------------------
class ApiHandler(BaseHTTPRequestHandler):
    bridge: Bridge = None
    server_version = "ChivetKhDownload/" + VERSION

    def log_message(self, *args):
        pass

    def _allowed(self) -> bool:
        if self.client_address[0] not in ("127.0.0.1", "::1"):
            return False
        if self.headers.get("X-MDM-Client") != "extension":
            return False  # custom header => web pages cannot send it without a CORS preflight
        origin = self.headers.get("Origin", "")
        if origin and not origin.startswith(("chrome-extension://", "moz-extension://", "extension://")):
            return False
        return True

    def _json(self, code: int, obj: dict):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._json(403, {"ok": False})

    def do_GET(self):
        if self.path.startswith("/ping") and self._allowed():
            return self._json(200, {"ok": True, "app": APP_SHORT, "version": VERSION})
        self._json(403, {"ok": False})

    def do_POST(self):
        if not self._allowed():
            return self._json(403, {"ok": False, "error": "forbidden"})
        try:
            length = int(self.headers.get("Content-Length", "0") or 0)
            if length > 12_000_000:
                return self._json(413, {"ok": False})
            data = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            return self._json(400, {"ok": False, "error": "bad json"})
        if self.path == "/add":
            url = str(data.get("url", "")).strip()
            if not url.startswith(("http://", "https://", "magnet:")):
                return self._json(400, {"ok": False, "error": "unsupported url"})
            self.bridge.browser_add.emit(data)
            return self._json(200, {"ok": True})
        if self.path == "/add-links":
            if not isinstance(data.get("links"), list):
                return self._json(400, {"ok": False, "error": "no links"})
            self.bridge.links_add.emit(data)
            return self._json(200, {"ok": True, "count": len(data["links"])})
        if self.path == "/add-batch":
            if not isinstance(data.get("items"), list):
                return self._json(400, {"ok": False, "error": "no items"})
            self.bridge.batch_add.emit(data)
            return self._json(200, {"ok": True, "count": len(data["items"])})
        if self.path == "/show":
            self.bridge.show_window.emit()
            return self._json(200, {"ok": True})
        self._json(404, {"ok": False})


class ApiServer:
    def __init__(self, bridge: Bridge):
        self.bridge = bridge
        self.httpd = None
        self.port = None
        self.error = ""

    def start(self, port: int) -> bool:
        self.stop()
        handler = type("Handler", (ApiHandler,), {"bridge": self.bridge})
        try:
            self.httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
            self.httpd.daemon_threads = True
        except OSError as e:
            self.error = str(e)
            self.httpd = None
            return False
        self.port = port
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        return True

    def stop(self):
        if self.httpd:
            try:
                self.httpd.shutdown()
                self.httpd.server_close()
            except Exception:
                pass
        self.httpd = None


# ----------------------------------------------------------------------------
# Windows integration: start with Windows + chivetkh:// link (lets the extension start the app)
# ----------------------------------------------------------------------------
PROTOCOL = "chivetkh"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_NAME = "ChivetKhDownload"


def launch_command() -> str:
    """Command line that starts this app hidden in the tray (works for the .exe and for source runs)."""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --minimized'
    exe = sys.executable
    w = os.path.join(os.path.dirname(exe), "pythonw.exe")
    if exe.lower().endswith("python.exe") and os.path.exists(w):
        exe = w
    return f'"{exe}" "{os.path.abspath(__file__)}" --minimized'


def set_autostart(enabled: bool):
    if platform.system() != "Windows":
        return
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
            if enabled:
                winreg.SetValueEx(k, RUN_NAME, 0, winreg.REG_SZ, launch_command())
            else:
                try:
                    winreg.DeleteValue(k, RUN_NAME)
                except FileNotFoundError:
                    pass
    except Exception:
        pass


def register_protocol():
    if platform.system() != "Windows":
        return
    try:
        import winreg
        base = rf"Software\Classes\{PROTOCOL}"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, base) as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, f"URL:{APP_NAME}")
            winreg.SetValueEx(k, "URL Protocol", 0, winreg.REG_SZ, "")
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, base + r"\DefaultIcon") as k:
            icon_src = sys.executable if getattr(sys, "frozen", False) else str(app_base_dir() / "app_icon.ico")
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, icon_src)
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, base + r"\shell\open\command") as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, launch_command() + ' "%1"')
    except Exception:
        pass


def started_in_background() -> bool:
    return "--minimized" in sys.argv or any(a.lower().startswith(PROTOCOL + ":") for a in sys.argv[1:])


def another_instance_running(port: int) -> bool:
    try:
        r = requests.get(f"http://127.0.0.1:{port}/ping", headers={"X-MDM-Client": "extension"}, timeout=0.8)
        if r.ok and r.json().get("app") == APP_SHORT:
            if not started_in_background():
                requests.post(f"http://127.0.0.1:{port}/show", headers={"X-MDM-Client": "extension"}, json={}, timeout=1)
            return True
    except Exception:
        pass
    return False


# ----------------------------------------------------------------------------
# Table model & delegates
# ----------------------------------------------------------------------------
COLUMNS = ["File Name", "Q", "Size", "Progress", "Status", "Time left", "Transfer rate", "Peers",
           "Share ratio", "Added"]


class DownloadModel(QAbstractTableModel):
    def __init__(self, items: list):
        super().__init__()
        self.all_items = items
        self.filter_fn = lambda it: True
        self.rows = []

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return len(COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return COLUMNS[section]
        return None

    def item_at(self, row: int):
        return self.rows[row] if 0 <= row < len(self.rows) else None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        it = self.rows[index.row()]
        col = index.column()
        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return it.filename
            if col == 1:
                return "●" if it.in_queue else ""
            if col == 2:
                return human_size(it.size) if it.size > 0 else ("" if it.status != "Finished" else human_size(it.downloaded))
            if col == 3:
                return it.progress()
            if col == 4:
                if it.status == "Downloading" and it.size > 0:
                    return f"{it.progress():.1f}%"
                if it.status == "Downloading":
                    return human_size(it.downloaded)
                return {"Connecting": "Connecting…", "Processing": "Merging…"}.get(it.status, it.status)
            if col == 5:
                return human_eta(it.eta) if it.status == "Downloading" else ""
            if col == 6:
                return human_speed(it.speed) if it.status == "Downloading" else ""
            if col == 7:
                return str(it.peers) if it.kind == "torrent" else ""
            if col == 8:
                return f"{it.ratio:.2f}" if it.kind == "torrent" else ""
            if col == 9:
                return datetime.fromtimestamp(it.added).strftime("%Y-%m-%d %H:%M")
        if role == Qt.ItemDataRole.DecorationRole and col == 0:
            return icon(CATEGORY_ICONS.get(it.category, "other"))
        if role == Qt.ItemDataRole.ToolTipRole:
            tip = f"{it.filename}\n{it.url if it.kind != 'torrent' else 'Torrent'}\nSaved to: {it.save_dir}"
            if it.error:
                tip += f"\nError: {it.error}"
            return tip
        if role == Qt.ItemDataRole.ForegroundRole and col == 4:
            return QColor({"Finished": C_GREEN, "Error": C_RED, "Downloading": C_ACCENT2,
                           "Stopped": C_AMBER, "Queued": C_MUTED}.get(it.status, C_TEXT))
        if role == Qt.ItemDataRole.ForegroundRole and col == 1:
            return QColor(C_ACCENT2)
        if role == Qt.ItemDataRole.TextAlignmentRole and col in (1, 2, 7, 8):
            return int(Qt.AlignmentFlag.AlignCenter)
        return None

    def set_filter(self, fn):
        self.filter_fn = fn
        self.refresh(force=True)

    def refresh(self, force=False):
        new_rows = [it for it in self.all_items if self.filter_fn(it)]
        if force or [i.id for i in new_rows] != [i.id for i in self.rows]:
            self.beginResetModel()
            self.rows = new_rows
            self.endResetModel()
            return True
        if self.rows:
            self.dataChanged.emit(self.index(0, 0), self.index(len(self.rows) - 1, len(COLUMNS) - 1))
        return False


class ProgressDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        value = index.data() or 0.0
        model = index.model()
        it = model.item_at(index.row())
        opt = option.__class__(option)
        self.initStyleOption(opt, index)
        opt.text = ""
        widget = opt.widget
        style = widget.style() if widget else QApplication.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, widget)
        r = option.rect.adjusted(8, option.rect.height() // 2 - 4, -8, -(option.rect.height() // 2 - 4))
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#252a39"))
        painter.drawRoundedRect(QRectF(r), 4, 4)
        if value > 0:
            w = max(8, int(r.width() * value / 100.0))
            g = QLinearGradient(r.left(), 0, r.right(), 0)
            if it and it.status == "Finished":
                g.setColorAt(0, QColor("#10b981"))
                g.setColorAt(1, QColor(C_GREEN))
            elif it and it.status == "Error":
                g.setColorAt(0, QColor("#ef4444"))
                g.setColorAt(1, QColor(C_RED))
            elif it and it.status in ("Stopped", "Queued"):
                g.setColorAt(0, QColor("#d97706"))
                g.setColorAt(1, QColor(C_AMBER))
            else:
                g.setColorAt(0, QColor(C_ACCENT))
                g.setColorAt(1, QColor(C_ACCENT2))
            painter.setBrush(g)
            painter.drawRoundedRect(QRectF(r.left(), r.top(), w, r.height()), 4, 4)
        painter.restore()

    def sizeHint(self, option, index):
        return QSize(140, 30)


# ----------------------------------------------------------------------------
# Dialogs
# ----------------------------------------------------------------------------
class AddDownloadDialog(QDialog):
    def __init__(self, parent, settings: dict, bridge: Bridge, url: str = "", filename: str = "",
                 headers: dict = None, mode: str = "auto", from_browser: bool = False, size_hint: int = 0,
                 quality: str = None, title_hint: str = ""):
        super().__init__(parent)
        self.title_hint = title_hint or ""
        self.settings = settings
        self.bridge = bridge
        self.headers = dict(headers or {})
        self.user_named = False
        self.user_dir = False
        self.probe_seq = 0
        self.result_data = None
        self.setWindowTitle("Add download" + (" — from browser" if from_browser else ""))
        self.setWindowIcon(app_icon())
        self.setMinimumWidth(620)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(12)
        head = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(app_icon().pixmap(40, 40))
        head.addWidget(logo)
        tbox = QVBoxLayout()
        t = QLabel("New download")
        t.setObjectName("title")
        tbox.addWidget(t)
        self.info = QLabel("Paste a link, or drop it on the main window.")
        self.info.setObjectName("muted")
        tbox.addWidget(self.info)
        head.addLayout(tbox, 1)
        lay.addLayout(head)

        form = QFormLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)
        self.url_edit = QLineEdit(url)
        self.url_edit.setPlaceholderText("https://example.com/file.zip  or a YouTube / Facebook / TikTok link")
        form.addRow("URL", self.url_edit)
        self.name_edit = QLineEdit(filename)
        form.addRow("File name", self.name_edit)
        row = QHBoxLayout()
        self.dir_edit = QLineEdit()
        browse = QPushButton("Browse…")
        browse.setIcon(icon("folder"))
        browse.clicked.connect(self.browse_dir)
        row.addWidget(self.dir_edit, 1)
        row.addWidget(browse)
        form.addRow("Save to", row)
        row2 = QHBoxLayout()
        self.cat_combo = QComboBox()
        self.cat_combo.addItem("Auto")
        for c in CATEGORIES[:-1] + ["Other"]:
            self.cat_combo.addItem(icon(CATEGORY_ICONS[c]), c)
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Auto detect", "auto")
        self.mode_combo.addItem("Direct file", "http")
        self.mode_combo.addItem("Video site (yt-dlp)", "ytdlp")
        self.mode_combo.setCurrentIndex(max(0, self.mode_combo.findData(mode)))
        row2.addWidget(QLabel("Category"))
        row2.addWidget(self.cat_combo, 1)
        row2.addSpacing(10)
        row2.addWidget(QLabel("Mode"))
        row2.addWidget(self.mode_combo, 1)
        self.cat_combo.setMinimumWidth(170)
        self.mode_combo.setMinimumWidth(170)
        self.quality_combo.setMinimumWidth(170) if hasattr(self, "quality_combo") else None
        form.addRow("", row2)
        row3 = QHBoxLayout()
        self.conn_spin = QSpinBox()
        self.conn_spin.setRange(1, 32)
        self.conn_spin.setValue(int(settings.get("connections", 8)))
        self.quality_combo = QComboBox()
        for key, label in YTDLP_QUALITIES:
            self.quality_combo.addItem(label, key)
        self.quality_combo.setCurrentIndex(max(0, self.quality_combo.findData(quality or settings.get("ytdlp_quality", "best"))))
        self.conn_label = QLabel("Connections")
        self.quality_label = QLabel("Video quality")
        row3.addWidget(self.conn_label)
        row3.addWidget(self.conn_spin)
        row3.addSpacing(10)
        row3.addWidget(self.quality_label)
        row3.addWidget(self.quality_combo, 1)
        row3.addStretch(1)
        form.addRow("", row3)
        lay.addLayout(form)

        btns = QHBoxLayout()
        btns.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        later = QPushButton("Add to Queue")
        later.setIcon(icon("qstart"))
        later.clicked.connect(lambda: self.finish(False))
        now = QPushButton("Download Now")
        now.setObjectName("primary")
        now.setIcon(icon("resume", "#ffffff"))
        now.setDefault(True)
        now.clicked.connect(lambda: self.finish(True))
        btns.addWidget(cancel)
        btns.addWidget(later)
        btns.addWidget(now)
        lay.addLayout(btns)

        self.probe_timer = QTimer(self)
        self.probe_timer.setSingleShot(True)
        self.probe_timer.setInterval(600)
        self.probe_timer.timeout.connect(self.start_probe)
        self.url_edit.textChanged.connect(self.on_url_changed)
        self.name_edit.textEdited.connect(self.on_name_edited)
        self.dir_edit.textEdited.connect(lambda _: setattr(self, "user_dir", True))
        self.cat_combo.currentIndexChanged.connect(self.update_dir)
        self.mode_combo.currentIndexChanged.connect(self.update_mode_ui)
        self.bridge.probe_result.connect(self.on_probe_result)

        if not url:
            clip = QGuiApplication.clipboard().text().strip()
            if looks_like_url(clip) and not clip.startswith("magnet:"):
                self.url_edit.setText(clip)
        if url and not filename:
            self.on_url_changed(url)
        elif url:
            self.update_dir()
            self.update_mode_ui()
            self.start_probe()
        else:
            self.update_dir()
            self.update_mode_ui()
        if size_hint and size_hint > 0:
            self.info.setText(f"Size: {human_size(size_hint)}")

    # -- helpers
    def effective_mode(self) -> str:
        mode = self.mode_combo.currentData()
        if mode == "auto":
            return "ytdlp" if (is_video_site(self.url_edit.text().strip()) and HAS_YTDLP) else "http"
        return mode

    def current_category(self) -> str:
        if self.cat_combo.currentIndex() > 0:
            return self.cat_combo.currentText()
        return category_for(self.name_edit.text(), self.effective_mode())

    def update_dir(self):
        if self.user_dir:
            return
        base = self.settings.get("download_dir")
        cat = self.current_category()
        d = os.path.join(base, cat) if self.settings.get("category_subfolders", True) else base
        self.dir_edit.setText(d)

    def update_mode_ui(self):
        yt = self.effective_mode() == "ytdlp"
        self.quality_combo.setVisible(yt)
        self.quality_label.setVisible(yt)
        self.conn_spin.setVisible(not yt)
        self.conn_label.setVisible(not yt)
        if yt and not self.user_named:
            self.name_edit.setText("")
            self.name_edit.setPlaceholderText(self.title_hint or "Title is detected automatically")
            if not HAS_YTDLP:
                self.info.setText("yt-dlp is not installed:  pip install yt-dlp")
            else:
                self.info.setText("Video page — will be downloaded with yt-dlp" +
                                  ("" if find_ffmpeg(self.settings) else " (install ffmpeg for best quality)"))
        self.update_dir()

    def on_url_changed(self, text):
        text = text.strip()
        if not self.user_named and text and self.effective_mode() != "ytdlp":
            self.name_edit.setText(filename_from_url(text))
        self.update_mode_ui()
        self.probe_timer.start()

    def on_name_edited(self, _):
        self.user_named = True
        self.update_dir()

    def browse_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Save to", self.dir_edit.text())
        if d:
            self.dir_edit.setText(d)
            self.user_dir = True

    def start_probe(self):
        url = self.url_edit.text().strip()
        if not url.startswith(("http://", "https://")) or self.effective_mode() == "ytdlp":
            return
        self.probe_seq += 1
        seq = self.probe_seq
        headers = {"User-Agent": DEFAULT_UA, "Accept-Encoding": "identity", "Range": "bytes=0-"}
        headers.update({k: v for k, v in self.headers.items() if v})
        self.info.setText("Checking link…")
        bridge = self.bridge

        def work():
            res = {"url": url}
            try:
                with requests.get(url, headers=headers, stream=True, timeout=(10, 15), allow_redirects=True) as r:
                    res["status"] = r.status_code
                    size = -1
                    if r.status_code == 206:
                        m = re.search(r"/(\d+)\s*$", r.headers.get("Content-Range", ""))
                        size = int(m.group(1)) if m else -1
                    elif r.headers.get("Content-Length", "").isdigit():
                        size = int(r.headers["Content-Length"])
                    res["size"] = size
                    res["resumable"] = r.status_code == 206
                    res["name"] = filename_from_headers(r.headers, r.url)
                    res["ctype"] = r.headers.get("Content-Type", "")
            except Exception as e:
                res["error"] = str(e)
            bridge.probe_result.emit(seq, res)

        threading.Thread(target=work, daemon=True).start()

    def on_probe_result(self, seq, res):
        if seq != self.probe_seq:
            return
        try:
            if res.get("error"):
                self.info.setText("Could not check the link (it will still be tried).")
                return
            if res.get("status", 200) >= 400:
                self.info.setText(f"Server answered HTTP {res['status']}")
                return
            if not self.user_named and res.get("name"):
                self.name_edit.setText(res["name"])
                self.update_dir()
            ctype = (res.get("ctype") or "").split(";")[0]
            resume = "Resume supported" if res.get("resumable") else "No resume support"
            self.info.setText(f"Size: {human_size(res.get('size', -1))}   •   {resume}" +
                              (f"   •   {ctype}" if ctype else ""))
            if "text/html" in ctype and self.mode_combo.currentData() == "auto" and HAS_YTDLP:
                self.info.setText(self.info.text() + "  — looks like a web page; try Mode: Video site")
        except RuntimeError:
            pass  # dialog already closed

    def finish(self, start_now: bool):
        url = self.url_edit.text().strip()
        if not looks_like_url(url):
            QMessageBox.warning(self, APP_NAME, "Please enter a valid http(s) link.")
            return
        mode = self.effective_mode()
        if mode == "ytdlp" and not HAS_YTDLP:
            QMessageBox.warning(self, APP_NAME, "yt-dlp is not installed.\n\nRun:  pip install yt-dlp")
            return
        if mode == "ytdlp":
            self.result_data = {"open_video_page": True, "url": url, "headers": self.headers,
                                "title_hint": self.title_hint}
            self.accept()
            return
        name = self.name_edit.text().strip()
        if mode == "http" and not name:
            name = filename_from_url(url)
        self.result_data = {
            "url": url, "filename": name, "save_dir": self.dir_edit.text().strip() or self.settings["download_dir"],
            "category": self.current_category(), "kind": mode, "quality": self.quality_combo.currentData(),
            "connections": self.conn_spin.value(), "start_now": start_now, "auto_name": not self.user_named,
            "headers": self.headers, "title_hint": self.title_hint,
        }
        self.accept()

    def done(self, r):
        try:
            self.bridge.probe_result.disconnect(self.on_probe_result)
        except Exception:
            pass
        super().done(r)


def _fmt_size(f: dict, duration):
    s = f.get("filesize") or f.get("filesize_approx")
    if s:
        return int(s), not f.get("filesize")
    tbr = f.get("tbr")
    if tbr and duration:
        return int(tbr * 1000 / 8 * duration), True
    return None, True


MP3_CHOICES = [("0", "VBR", 245), ("320", "320 kbps", 320), ("256", "256 kbps", 256),
               ("192", "192 kbps", 192), ("128", "128 kbps", 128)]


def build_video_options(info: dict, has_ff: bool) -> list:
    """Turn a yt-dlp info dict into the rows of the 'Download video from a page' list."""
    fmts = [f for f in (info.get("formats") or []) if f.get("format_id")]
    dur = info.get("duration") or 0
    opts = []
    if not fmts:  # single direct file
        fmts = [dict(info, format_id=info.get("format_id") or "0")]
    audios = [f for f in fmts if f.get("vcodec") == "none" and f.get("acodec") not in (None, "none")]
    best_audio = max(audios, key=lambda f: (f.get("ext") == "m4a", f.get("abr") or f.get("tbr") or 0), default=None)
    videos = [f for f in fmts if f.get("vcodec") != "none" and (f.get("height") or 0) > 0]
    for h in sorted({f["height"] for f in videos}, reverse=True):
        same = [f for f in videos if f["height"] == h]
        progressive = [f for f in same if f.get("acodec") != "none"]
        if has_ff:
            v = max(same, key=lambda f: (f.get("ext") == "mp4", f.get("tbr") or 0))
            size, approx = _fmt_size(v, dur)
            if v.get("acodec") == "none" and best_audio:
                a_size, a_approx = _fmt_size(best_audio, dur)
                size = size + a_size if (size and a_size) else None
                approx = approx or a_approx
            sel = f"bv*[height={h}][ext=mp4]+ba[ext=m4a]/bv*[height={h}]+ba/b[height={h}]/bv*[height={h}]"
            ext = "mp4"
        else:
            if not progressive:
                continue
            v = max(progressive, key=lambda f: (f.get("ext") == "mp4", f.get("tbr") or 0))
            size, approx = _fmt_size(v, dur)
            sel, ext = v["format_id"], v.get("ext") or "mp4"
        opts.append(dict(kind="video", label=f"{h}p {ext.upper()}", selector=sel, ext=ext, size=size, approx=approx))
    if not opts:  # formats without resolution info (some generic sites)
        opts.append(dict(kind="video", label="MP4" if has_ff else "Best file", selector="bv*+ba/b" if has_ff else "b",
                         ext="mp4" if has_ff else (info.get("ext") or "mp4"), size=None, approx=True))
    if best_audio:
        a_size, a_approx = _fmt_size(best_audio, dur)
        aext = best_audio.get("ext") or "m4a"
        opts.append(dict(kind="audio", label=f"Audio only, original {aext.upper()}", selector=best_audio["format_id"],
                         ext=aext, size=a_size, approx=a_approx))
    if has_ff:
        for q, label, kbps in MP3_CHOICES:
            size = int(dur * kbps * 1000 / 8) if dur else None
            opts.append(dict(kind="mp3", label=f"Audio only MP3 {label}", selector="ba/b", ext="mp3",
                             size=size, approx=True, mp3q=q))
    return opts


SITE_NAMES = {"youtube": "YouTube", "facebook": "Facebook", "tiktok": "TikTok", "instagram": "Instagram",
              "twitter": "X (Twitter)", "vimeo": "Vimeo", "dailymotion": "Dailymotion", "generic": "Web page",
              "reddit": "Reddit", "bilibili": "Bilibili", "twitch": "Twitch"}


class VideoPageDialog(QDialog):
    def __init__(self, parent, settings: dict, bridge: Bridge, url: str = "", headers: dict = None,
                 title_hint: str = "", from_browser: bool = False):
        super().__init__(parent)
        self.settings = settings
        self.bridge = bridge
        self.headers = dict(headers or {})
        self.title_hint = title_hint or ""
        self.info = None
        self.options = []
        self.seq = 0
        self.user_dir = False
        self.result_data = None
        self.setWindowTitle("Download video from a page")
        self.setWindowIcon(app_icon())
        self.setMinimumSize(680, 600)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(10)
        cap = QLabel("Page address")
        cap.setObjectName("muted")
        lay.addWidget(cap)
        row = QHBoxLayout()
        self.url_edit = QLineEdit(url)
        self.url_edit.setPlaceholderText("https://www.facebook.com/reel/…  ·  YouTube  ·  TikTok  ·  any page with a video")
        self.lookup_btn = QPushButton("Look up")
        self.lookup_btn.setIcon(icon("refresh"))
        row.addWidget(self.url_edit, 1)
        row.addWidget(self.lookup_btn)
        lay.addLayout(row)

        card = QFrame()
        card.setObjectName("vcard")
        card.setStyleSheet(f"QFrame#vcard {{ background: {C_PANEL}; border: 1px solid {C_BORDER}; border-radius: 12px; }}"
                           "QFrame#vcard QLabel { background: transparent; }")
        ch = QHBoxLayout(card)
        ch.setContentsMargins(10, 10, 12, 10)
        ch.setSpacing(12)
        self.thumb = QLabel()
        self.thumb.setFixedSize(128, 76)
        self.thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb.setStyleSheet(f"background: {C_PANEL2}; border-radius: 8px;")
        self.thumb.setPixmap(icon("video", "#4b5268").pixmap(34, 34))
        ch.addWidget(self.thumb)
        info_box = QVBoxLayout()
        info_box.setSpacing(3)
        self.site_lbl = QLabel("—")
        self.site_lbl.setStyleSheet(f"color: {C_ACCENT2}; font-weight: 700;")
        self.title_lbl = QLabel(self.title_hint or "Paste a page address and press Look up")
        self.title_lbl.setWordWrap(True)
        self.title_lbl.setStyleSheet("font-size: 11pt; font-weight: 600;")
        self.meta_lbl = QLabel("")
        self.meta_lbl.setObjectName("muted")
        info_box.addWidget(self.site_lbl)
        info_box.addWidget(self.title_lbl)
        info_box.addWidget(self.meta_lbl)
        info_box.addStretch(1)
        ch.addLayout(info_box, 1)
        lay.addWidget(card)

        self.list = QTreeWidget()
        self.list.setColumnCount(2)
        self.list.setHeaderHidden(True)
        self.list.setRootIsDecorated(False)
        self.list.setIconSize(QSize(18, 18))
        self.list.header().setStretchLastSection(False)
        self.list.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.list.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.list.setMinimumHeight(230)
        self.list.setAllColumnsShowFocus(True)
        lay.addWidget(self.list, 1)

        form = QFormLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(9)
        drow = QHBoxLayout()
        self.dir_edit = QLineEdit()
        b = QPushButton("…")
        b.setFixedWidth(44)
        b.clicked.connect(self.browse)
        drow.addWidget(self.dir_edit, 1)
        drow.addWidget(b)
        form.addRow("Save to", drow)
        self.name_edit = QLineEdit()
        form.addRow("File name", self.name_edit)
        srow = QHBoxLayout()
        self.sub_combo = QComboBox()
        self.sub_combo.setMinimumWidth(240)
        self.embed_cb = QCheckBox("Put them into the video")
        srow.addWidget(self.sub_combo)
        srow.addSpacing(10)
        srow.addWidget(self.embed_cb)
        srow.addStretch(1)
        form.addRow("Subtitles", srow)
        lay.addLayout(form)

        brow = QHBoxLayout()
        helpers = QPushButton("Helpers…")
        helpers.setIcon(icon("options"))
        helpers.clicked.connect(lambda: HelpersDialog(self, self.settings).exec())
        brow.addWidget(helpers)
        brow.addStretch(1)
        self.now_btn = QPushButton("Download Now")
        self.now_btn.setObjectName("primary")
        self.now_btn.setIcon(icon("resume", "#ffffff"))
        self.later_btn = QPushButton("Later")
        self.later_btn.setIcon(icon("qstart"))
        cancel = QPushButton("Cancel")
        self.now_btn.clicked.connect(lambda: self.finish(True))
        self.later_btn.clicked.connect(lambda: self.finish(False))
        cancel.clicked.connect(self.reject)
        for w in (self.now_btn, self.later_btn, cancel):
            brow.addWidget(w)
        lay.addLayout(brow)

        self.lookup_btn.clicked.connect(self.lookup)
        self.url_edit.returnPressed.connect(self.lookup)
        self.list.currentItemChanged.connect(self.on_option_changed)
        self.list.itemDoubleClicked.connect(lambda *_: self.finish(True))
        self.dir_edit.textEdited.connect(lambda _: setattr(self, "user_dir", True))
        self.bridge.lookup_result.connect(self.on_lookup_result)
        self.bridge.thumb_result.connect(self.on_thumb)
        self.set_subtitles({}, {})
        self.update_dir("video")
        self.set_ready(False)
        if url:
            QTimer.singleShot(0, self.lookup)

    # ------------------------------------------------------------ helpers
    def set_ready(self, ok: bool):
        self.now_btn.setEnabled(ok)
        self.later_btn.setEnabled(ok)

    def message_row(self, text: str, color: str = C_MUTED):
        self.list.clear()
        it = QTreeWidgetItem([text, ""])
        it.setForeground(0, QColor(color))
        it.setFlags(Qt.ItemFlag.NoItemFlags)
        self.list.addTopLevelItem(it)

    def update_dir(self, kind: str):
        if self.user_dir:
            return
        base = self.settings.get("download_dir")
        cat = "Video" if kind == "video" else "Music"
        self.dir_edit.setText(os.path.join(base, cat) if self.settings.get("category_subfolders", True) else base)

    def browse(self):
        d = QFileDialog.getExistingDirectory(self, "Save to", self.dir_edit.text())
        if d:
            self.dir_edit.setText(d)
            self.user_dir = True

    def set_subtitles(self, subs: dict, auto: dict):
        self.sub_combo.clear()
        if not subs and not auto:
            self.sub_combo.addItem("None on this page", None)
            self.sub_combo.setEnabled(False)
            self.embed_cb.setEnabled(False)
            return
        self.sub_combo.setEnabled(True)
        self.embed_cb.setEnabled(find_ffmpeg(self.settings) is not None)
        self.sub_combo.addItem("No subtitles", None)
        self.sub_combo.addItem(f"All languages ({len(set(subs) | set(auto if not subs else {}))})", ("all", not subs))
        order = lambda k: (0 if k.startswith("km") else 1 if k.startswith("en") else 2, k)
        for lang in sorted(subs, key=order):
            self.sub_combo.addItem(f"{lang}", (lang, False))
        if len(auto) <= 12 or not subs:
            for lang in sorted(auto, key=order)[:60]:
                if lang not in subs:
                    self.sub_combo.addItem(f"{lang}  (auto)", (lang, True))

    # ------------------------------------------------------------ lookup
    def lookup(self):
        url = self.url_edit.text().strip()
        if not looks_like_url(url):
            self.message_row("Enter a page address that starts with http:// or https://", C_AMBER)
            return
        if not HAS_YTDLP:
            self.message_row("yt-dlp is not installed — open Helpers… or run:  pip install yt-dlp", C_RED)
            return
        self.seq += 1
        seq = self.seq
        self.info, self.options = None, []
        self.set_ready(False)
        self.lookup_btn.setEnabled(False)
        self.site_lbl.setText("Reading page…")
        self.meta_lbl.setText("")
        self.message_row("Looking up the video formats…")
        headers = {"User-Agent": self.headers.get("User-Agent") or DEFAULT_UA}
        for k in ("Cookie", "Referer"):
            if self.headers.get(k):
                headers[k] = self.headers[k]
        bridge = self.bridge

        def work():
            res = {}
            info = None
            try:
                opts = {"quiet": True, "no_warnings": True, "skip_download": True, "noplaylist": True,
                        "logger": _QuietLogger(), "http_headers": headers}
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    if info and info.get("_type") == "playlist":
                        entries = [e for e in (info.get("entries") or []) if e]
                        info = entries[0] if entries else info
                    res["info"] = ydl.sanitize_info(info)
            except Exception as e:
                res["error"] = re.sub(r"\x1b\[[0-9;]*m", "", str(e)).replace("ERROR: ", "")[:400]
            bridge.lookup_result.emit(seq, res)
            thumb = (info or {}).get("thumbnail")
            if thumb:
                try:
                    r = requests.get(thumb, headers={"User-Agent": headers["User-Agent"]}, timeout=8)
                    if r.ok and len(r.content) < 5_000_000:
                        bridge.thumb_result.emit(seq, r.content)
                except Exception:
                    pass

        threading.Thread(target=work, daemon=True).start()

    def on_lookup_result(self, seq, res):
        if seq != self.seq:
            return
        try:
            self.lookup_btn.setEnabled(True)
            if res.get("error"):
                self.site_lbl.setText("Could not read this page")
                self.message_row(res["error"], C_RED)
                tip = "Tip: log in to the site in Chrome, then try again — or update yt-dlp in Helpers…"
                if "Unsupported URL" in res["error"] or not re.search(r"\d{6,}|[?&]v=|/shorts/|/status/|/p/|/reels?/\w", self.url_edit.text()):
                    tip = ("This is a feed / list page, not one video. Open the video itself (click its date or "
                           "Share → Copy link) and paste that link here.")
                hint = QTreeWidgetItem([tip, ""])
                hint.setFlags(Qt.ItemFlag.NoItemFlags)
                hint.setForeground(0, QColor(C_MUTED))
                self.list.addTopLevelItem(hint)
                return
            info = res.get("info") or {}
            self.info = info
            key = (info.get("extractor_key") or info.get("extractor") or "").lower()
            self.site_lbl.setText(SITE_NAMES.get(key, info.get("extractor_key") or "Video"))
            title = info.get("title") or self.title_hint or "video"
            if key == "generic" and self.title_hint and title.lower() in ("index", "master", "playlist", "video", "manifest"):
                title = self.title_hint
            self.title_lbl.setText(title)
            meta = []
            if info.get("uploader"):
                meta.append(str(info["uploader"]))
            if info.get("duration"):
                meta.append(human_eta(info["duration"]).replace(" sec", "s"))
            if info.get("width") and info.get("height"):
                meta.append(f"{info['width']}×{info['height']}")
            self.meta_lbl.setText("  ·  ".join(meta))
            has_ff = find_ffmpeg(self.settings) is not None
            self.options = build_video_options(info, has_ff)
            self.list.clear()
            for opt in self.options:
                if opt["size"]:
                    size = ("≈ " if opt.get("approx") else "") + human_size(opt["size"])
                else:
                    size = "size unknown"
                row = QTreeWidgetItem([opt["label"], size])
                row.setIcon(0, icon("video") if opt["kind"] == "video" else icon("music", "#f472b6" if opt["kind"] == "audio" else C_AMBER))
                row.setForeground(1, QColor(C_MUTED))
                row.setTextAlignment(1, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.list.addTopLevelItem(row)
            if info.get("subtitles") or info.get("automatic_captions"):
                n = len(info.get("subtitles") or {}) or len(info.get("automatic_captions") or {})
                self.options.append(dict(kind="subs", label="Subtitles only (.srt)", selector="", ext="srt",
                                         size=None, approx=True, note=f"{n} language{'s' if n != 1 else ''}"))
                row = QTreeWidgetItem(["Subtitles only (.srt)", self.options[-1]["note"]])
                row.setIcon(0, icon("documents"))
                row.setForeground(1, QColor(C_MUTED))
                row.setTextAlignment(1, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.list.addTopLevelItem(row)
            if not has_ff:
                note = QTreeWidgetItem(["Install ffmpeg (Helpers…) to unlock 1080p+ and MP3", ""])
                note.setFlags(Qt.ItemFlag.NoItemFlags)
                note.setForeground(0, QColor(C_AMBER))
                self.list.addTopLevelItem(note)
            self.name_edit.setText(safe_filename(title)[:150])
            self.set_subtitles(info.get("subtitles") or {}, info.get("automatic_captions") or {})
            if self.options:
                self.list.setCurrentItem(self.list.topLevelItem(0))
                self.set_ready(True)
        except RuntimeError:
            pass  # dialog closed

    def on_thumb(self, seq, data: bytes):
        if seq != self.seq:
            return
        try:
            pm = QPixmap()
            if pm.loadFromData(data):
                pm = pm.scaled(self.thumb.size(), Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
                self.thumb.setPixmap(pm)
        except RuntimeError:
            pass

    def on_option_changed(self, cur, _prev=None):
        if not cur:
            return
        idx = self.list.indexOfTopLevelItem(cur)
        if not (0 <= idx < len(self.options)):
            return
        opt = self.options[idx]
        base = self.name_edit.text().strip()
        known = {o["ext"] for o in self.options} | {"mp4", "m4a", "mp3", "webm"}
        root, ext = os.path.splitext(base)
        if ext.lstrip(".").lower() in known:
            base = root
        self.name_edit.setText(f"{base or 'video'}.{opt['ext']}")
        self.update_dir("video" if opt["kind"] in ("video", "subs") else "audio")
        if opt["kind"] == "subs" and self.sub_combo.currentData() is None and self.sub_combo.count() > 1:
            self.sub_combo.setCurrentIndex(1)
        self.embed_cb.setEnabled(opt["kind"] == "video" and self.sub_combo.isEnabled()
                                 and find_ffmpeg(self.settings) is not None)

    def finish(self, start_now: bool):
        cur = self.list.currentItem()
        idx = self.list.indexOfTopLevelItem(cur) if cur else -1
        if not (0 <= idx < len(self.options)):
            return
        opt = self.options[idx]
        name = safe_filename(self.name_edit.text().strip() or "video") 
        if not name.lower().endswith("." + opt["ext"]):
            name = f"{name}.{opt['ext']}"
        sub = self.sub_combo.currentData()
        if opt["kind"] == "subs" and not sub:
            QMessageBox.information(self, APP_NAME, "Choose a subtitle language first.")
            return
        self.result_data = {
            "url": self.url_edit.text().strip(), "filename": name,
            "save_dir": self.dir_edit.text().strip() or self.settings["download_dir"],
            "kind": "ytdlp", "category": "Video" if opt["kind"] == "video" else "Music",
            "start_now": start_now, "auto_name": False, "headers": self.headers,
            "title_hint": (self.info or {}).get("title") or self.title_hint,
            "ytdlp_format": opt["selector"], "audio_format": "mp3" if opt["kind"] == "mp3" else "subs" if opt["kind"] == "subs" else "",
            "audio_quality": opt.get("mp3q", ""), "sub_lang": sub[0] if sub else "",
            "sub_auto": bool(sub and sub[1]), "embed_subs": bool(sub and self.embed_cb.isChecked()),
            "size": opt.get("size") or -1,
        }
        self.accept()

    def done(self, r):
        for sig, slot in ((self.bridge.lookup_result, self.on_lookup_result), (self.bridge.thumb_result, self.on_thumb)):
            try:
                sig.disconnect(slot)
            except Exception:
                pass
        super().done(r)


class HelpersDialog(QDialog):
    FFMPEG_PAGE = "https://www.gyan.dev/ffmpeg/builds/"

    def __init__(self, parent, settings: dict):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Helpers")
        self.setMinimumSize(560, 420)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16)
        g = QGroupBox("Video helpers")
        f = QFormLayout(g)
        ver = "not installed"
        if HAS_YTDLP:
            try:
                from yt_dlp.version import __version__ as ver
            except Exception:
                ver = "installed"
        self.ytdlp_lbl = QLabel(ver)
        self.ff_lbl = QLabel()
        self.ff_lbl.setWordWrap(True)
        f.addRow("yt-dlp", self.ytdlp_lbl)
        f.addRow("ffmpeg", self.ff_lbl)
        lay.addWidget(g)
        row = QHBoxLayout()
        self.upd_btn = QPushButton("Update yt-dlp")
        self.upd_btn.setIcon(icon("refresh"))
        ch = QPushButton("Choose ffmpeg.exe…")
        ch.setIcon(icon("folder"))
        get = QPushButton("Get ffmpeg")
        get.setIcon(icon("open"))
        row.addWidget(self.upd_btn)
        row.addWidget(ch)
        row.addWidget(get)
        row.addStretch(1)
        lay.addLayout(row)
        self.out = QTextBrowser()
        self.out.setPlaceholderText("Sites change often. If a video stops working, press “Update yt-dlp”, then restart Chivet-kh Download.")
        lay.addWidget(self.out, 1)
        close = QPushButton("Close")
        close.setObjectName("primary")
        close.clicked.connect(self.accept)
        r2 = QHBoxLayout()
        r2.addStretch(1)
        r2.addWidget(close)
        lay.addLayout(r2)
        self.upd_btn.clicked.connect(self.update_ytdlp)
        ch.clicked.connect(self.choose_ffmpeg)
        get.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(self.FFMPEG_PAGE)))
        self.proc = None
        self.refresh()
        if getattr(sys, "frozen", False):
            self.upd_btn.setEnabled(False)
            self.upd_btn.setToolTip("Rebuild the .exe with the newest yt-dlp to update it")

    def refresh(self):
        ff = find_ffmpeg(self.settings)
        self.ff_lbl.setText(ff if ff else "not found — video above 720p is limited and MP3 is unavailable")
        self.ff_lbl.setStyleSheet(f"color: {C_GREEN if ff else C_AMBER};")

    def choose_ffmpeg(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose ffmpeg", str(Path.home()),
                                              "ffmpeg (ffmpeg*.exe ffmpeg);;All files (*)")
        if path:
            self.settings["ffmpeg_path"] = path
            try:
                save_json(SETTINGS_FILE, self.settings)
            except Exception:
                pass
            self.refresh()

    def update_ytdlp(self):
        from PyQt6.QtCore import QProcess
        uv = shutil.which("uv") or str(Path.home() / ".local" / "bin" / ("uv.exe" if os.name == "nt" else "uv"))
        in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
        if os.path.isfile(uv) and in_venv:
            prog, args = uv, ["pip", "install", "-U", "yt-dlp", "--python", sys.executable]
        else:
            prog, args = sys.executable, ["-m", "pip", "install", "-U", "yt-dlp"]
        self.out.append(f"> {os.path.basename(prog)} {' '.join(args)}")
        self.upd_btn.setEnabled(False)
        self.proc = QProcess(self)
        self.proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.proc.readyReadStandardOutput.connect(
            lambda: self.out.append(bytes(self.proc.readAllStandardOutput()).decode("utf-8", "replace").rstrip()))
        self.proc.finished.connect(self.update_done)
        self.proc.start(prog, args)

    def update_done(self, code, _status=None):
        self.upd_btn.setEnabled(True)
        self.out.append("✔ Done — restart Chivet-kh Download to use the new yt-dlp." if code == 0 else f"✖ Update failed (code {code}).")


class SegmentBar(QWidget):
    """Start positions and download progress by connections."""

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(20)
        self.segs, self.size, self.progress = [], -1, 0.0

    def set_data(self, segs, size, progress):
        self.segs, self.size, self.progress = [list(x) for x in (segs or [])], size, progress
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        clip = QPainterPath()
        clip.addRoundedRect(r, 5, 5)
        p.setClipPath(clip)
        p.fillRect(r, QColor("#252a39"))
        g = QLinearGradient(0, r.top(), 0, r.bottom())
        g.setColorAt(0, QColor("#8b6dff"))
        g.setColorAt(0.5, QColor(C_ACCENT))
        g.setColorAt(1, QColor("#3b82f6"))
        if self.size and self.size > 0 and self.segs:
            for s in self.segs:
                x0 = r.left() + r.width() * s[0] / self.size
                w = r.width() * min(s[2], max(0, (s[1] if s[1] >= 0 else self.size - 1) - s[0] + 1)) / self.size
                p.fillRect(QRectF(x0, r.top(), max(0.0, w), r.height()), g)
            p.setPen(QPen(QColor(C_AMBER), 1.6))
            for s in self.segs[1:]:
                x0 = r.left() + r.width() * s[0] / self.size
                p.drawLine(int(x0), int(r.top()), int(x0), int(r.bottom()))
        else:
            p.fillRect(QRectF(r.left(), r.top(), r.width() * self.progress / 100.0, r.height()), g)
        p.setClipping(False)
        p.setPen(QPen(QColor(C_BORDER), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(r, 5, 5)
        p.end()


class ProgressDialog(QDialog):
    def __init__(self, main, it: DownloadItem):
        super().__init__(main)
        self.main = main
        self.item = it
        self.setWindowIcon(app_icon())
        self.setMinimumWidth(640)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(12)

        self.tabs = QTabWidget()
        # --- Download status
        t1 = QWidget()
        g = QGridLayout(t1)
        g.setContentsMargins(16, 14, 16, 14)
        g.setHorizontalSpacing(20)
        g.setVerticalSpacing(7)
        self.url = QLineEdit(it.url if it.kind != "torrent" else it.torrent_source)
        self.url.setReadOnly(True)
        self.url.setObjectName("ro")
        self.url.setCursorPosition(0)
        g.addWidget(self.url, 0, 0, 1, 2)
        self.v = {}
        rows = ["Status", "File size", "Downloaded", "Transfer rate", "Time left", "Resume capability"]
        for i, name in enumerate(rows, start=1):
            k = QLabel(name)
            k.setObjectName("muted")
            val = QLabel("")
            val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            g.addWidget(k, i, 0)
            g.addWidget(val, i, 1)
            self.v[name] = val
        if it.kind == "torrent":
            self.peers_k = QLabel("Peers · share ratio")
            self.peers_k.setObjectName("muted")
            self.v["Peers"] = QLabel("")
            g.addWidget(self.peers_k, len(rows) + 1, 0)
            g.addWidget(self.v["Peers"], len(rows) + 1, 1)
        g.setColumnStretch(1, 1)
        self.tabs.addTab(t1, "Download status")
        # --- Speed limiter
        t2 = QWidget()
        f2 = QVBoxLayout(t2)
        f2.setContentsMargins(16, 14, 16, 14)
        self.lim_cb = QCheckBox("Use speed limiter for this download")
        self.lim_cb.setChecked(it.speed_limit_kb > 0)
        r2 = QHBoxLayout()
        r2.addWidget(QLabel("Maximum download speed"))
        self.lim_spin = QSpinBox()
        self.lim_spin.setRange(8, 1_000_000)
        self.lim_spin.setSuffix(" KB/s")
        self.lim_spin.setValue(it.speed_limit_kb or 500)
        r2.addWidget(self.lim_spin)
        r2.addStretch(1)
        f2.addWidget(self.lim_cb)
        f2.addLayout(r2)
        note = QLabel("The global limit in Options also applies." +
                      ("\nVideo sites: the new limit applies after Pause → Resume." if it.kind == "ytdlp" else ""))
        note.setObjectName("muted")
        f2.addWidget(note)
        f2.addStretch(1)
        self.lim_cb.toggled.connect(self.apply_limit)
        self.lim_spin.valueChanged.connect(self.apply_limit)
        self.tabs.addTab(t2, "Speed Limiter")
        # --- Options on completion
        t3 = QWidget()
        f3 = QVBoxLayout(t3)
        f3.setContentsMargins(16, 14, 16, 14)
        self.cb_complete = QCheckBox("Show the “Download complete” dialog")
        self.cb_complete.setChecked(main.settings.get("show_complete_dialog", True))
        self.cb_open = QCheckBox("Open the file when done")
        self.cb_open.setChecked(it.open_when_done)
        self.cb_folder = QCheckBox("Open the folder when done")
        self.cb_folder.setChecked(it.folder_when_done)
        self.cb_shutdown = QCheckBox("Turn off the computer when done")
        self.cb_shutdown.setChecked(it.shutdown_when_done)
        for cb in (self.cb_complete, self.cb_open, self.cb_folder, self.cb_shutdown):
            f3.addWidget(cb)
            cb.toggled.connect(self.apply_options)
        f3.addStretch(1)
        self.tabs.addTab(t3, "Options on completion")
        lay.addWidget(self.tabs)

        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.setTextVisible(True)
        lay.addWidget(self.bar)

        br = QHBoxLayout()
        self.details_btn = QPushButton("<< Hide details")
        self.details_btn.clicked.connect(self.toggle_details)
        self.pause_btn = QPushButton("Pause")
        self.pause_btn.setObjectName("primary")
        self.pause_btn.setMinimumWidth(120)
        self.pause_btn.clicked.connect(self.pause_resume)
        cancel = QPushButton("Cancel")
        cancel.setMinimumWidth(110)
        cancel.clicked.connect(self.cancel)
        br.addWidget(self.details_btn)
        br.addStretch(1)
        br.addWidget(self.pause_btn)
        br.addWidget(cancel)
        lay.addLayout(br)

        self.details = QWidget()
        dl = QVBoxLayout(self.details)
        dl.setContentsMargins(0, 0, 0, 0)
        dl.setSpacing(6)
        cap = QLabel("Start positions and download progress by connections")
        cap.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cap.setObjectName("muted")
        dl.addWidget(cap)
        self.segbar = SegmentBar()
        dl.addWidget(self.segbar)
        self.conns = QTableWidget(0, 3)
        self.conns.setHorizontalHeaderLabels(["N.", "Downloaded", "Info"])
        self.conns.verticalHeader().setVisible(False)
        self.conns.verticalHeader().setDefaultSectionSize(28)
        self.conns.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.conns.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.conns.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.conns.setShowGrid(False)
        self.conns.setAlternatingRowColors(True)
        hh = self.conns.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        hh.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.conns.setColumnWidth(0, 50)
        self.conns.setColumnWidth(1, 140)
        self.conns.setMinimumHeight(190)
        dl.addWidget(self.conns)
        lay.addWidget(self.details, 1)
        self.refresh()

    # ------------------------------------------------------------ actions
    def toggle_details(self):
        vis = not self.details.isVisible()
        self.details.setVisible(vis)
        self.details_btn.setText("<< Hide details" if vis else "Show details >>")
        QTimer.singleShot(0, lambda: self.adjustSize())

    def pause_resume(self):
        it = self.item
        if it.id in self.main.tasks:
            self.main.stop_item(it)
        elif it.status != "Finished":
            self.main.start_item(it)
            self.main.watch_ids.add(it.id)
        self.refresh()

    def cancel(self):
        if self.item.id in self.main.tasks:
            self.main.stop_item(self.item)
        self.close()

    def apply_limit(self, *_):
        it = self.item
        it.speed_limit_kb = self.lim_spin.value() if self.lim_cb.isChecked() else 0
        task = self.main.tasks.get(it.id)
        if isinstance(task, HttpTask):
            task.local.rate = it.speed_limit_kb * 1024

    def apply_options(self, *_):
        it = self.item
        self.main.settings["show_complete_dialog"] = self.cb_complete.isChecked()
        it.open_when_done = self.cb_open.isChecked()
        it.folder_when_done = self.cb_folder.isChecked()
        it.shutdown_when_done = self.cb_shutdown.isChecked()
        self.main.save_settings()

    # ------------------------------------------------------------ refresh
    def refresh(self):
        it = self.item
        task = self.main.tasks.get(it.id)
        running = task is not None
        pct = it.progress()
        name = it.filename
        self.setWindowTitle(f"{pct:.0f}% {name}" if it.size > 0 else name)
        status = {"Connecting": "Connecting…", "Downloading": "Receiving data…", "Processing": "Merging / converting…",
                  "Stopped": "Paused", "Queued": "Waiting in queue", "Finished": "Complete"}.get(it.status, it.status)
        if it.status == "Error":
            status = "Error: " + (it.error or "unknown")[:140]
        if running and it.phase and it.kind == "ytdlp" and it.status in ("Downloading", "Processing"):
            status = it.phase
        col = {"Error": C_RED, "Finished": C_GREEN, "Stopped": C_AMBER}.get(it.status, C_ACCENT2)
        self.v["Status"].setText(status)
        self.v["Status"].setStyleSheet(f"color: {col}; font-weight: 600;")
        self.v["Status"].setWordWrap(True)
        self.v["File size"].setText(human_size(it.size) if it.size > 0 else "Unknown")
        dl = human_size(it.downloaded) if it.downloaded > 0 else "0 B"
        self.v["Downloaded"].setText(f"{dl}  ( {pct:.2f} % )" if it.size > 0 else dl)
        self.v["Transfer rate"].setText(human_speed(it.speed) if running and it.speed > 0 else "")
        self.v["Time left"].setText(human_eta(it.eta) if running else "")
        if it.kind == "http":
            resume = "Yes" if it.resumable else ("No" if it.segments else "Checking…")
        else:
            resume = "Yes"
        self.v["Resume capability"].setText(resume)
        if "Peers" in self.v:
            self.v["Peers"].setText(f"{it.peers} peers · ratio {it.ratio:.2f}")
        self.bar.setValue(int(pct * 10))
        self.bar.setFormat(f"{pct:.1f}%")
        obj = "done" if it.status == "Finished" else "paused" if it.status in ("Stopped", "Error") else ""
        if self.bar.objectName() != obj:
            self.bar.setObjectName(obj)
            self.bar.style().unpolish(self.bar)
            self.bar.style().polish(self.bar)
        self.pause_btn.setText("Pause" if running else ("Resume" if it.status != "Finished" else "Done"))
        self.pause_btn.setEnabled(it.status != "Finished")
        # connections
        if it.kind == "http":
            segs = it.segments or []
            self.segbar.set_data(segs, it.size, pct)
            info = getattr(task, "seg_info", {}) if task else {}
            rows = []
            for i, sg in enumerate(segs):
                done = sg[1] >= 0 and sg[0] + sg[2] > sg[1]
                txt = info.get(i) or ("Finished" if done else ("Waiting…" if running else "Paused"))
                if not running and not done and txt not in ("Finished",) and not txt.startswith("Error"):
                    txt = "Paused" if it.status != "Error" else txt
                rows.append((str(i + 1), human_size(sg[2]) if sg[2] else "0 B", txt))
            if not segs:
                rows.append(("1", "", "Connecting…" if running else ""))
        else:
            self.segbar.set_data([], it.size, pct)
            info = it.phase if running else ("Finished" if it.status == "Finished" else "Paused")
            if it.kind == "torrent" and running:
                info = f"{it.peers} peers connected"
            rows = [("1", human_size(it.downloaded) if it.downloaded else "0 B", info or "Connecting…")]
        if self.conns.rowCount() != len(rows):
            self.conns.setRowCount(len(rows))
        for r, vals in enumerate(rows):
            for c, val in enumerate(vals):
                cell = self.conns.item(r, c)
                if cell is None:
                    cell = QTableWidgetItem()
                    self.conns.setItem(r, c, cell)
                if cell.text() != val:
                    cell.setText(val)
                if c == 2:
                    cell.setForeground(QColor(C_RED if val.startswith("Error") else C_GREEN if val == "Finished"
                                              else C_AMBER if val.startswith(("Paused", "Connection lost")) else C_TEXT))

    def closeEvent(self, e):
        self.main.progress_dialogs.pop(self.item.id, None)
        super().closeEvent(e)


class CompleteDialog(QDialog):
    def __init__(self, main, it: DownloadItem):
        super().__init__(main)
        self.main = main
        self.item = it
        self.setWindowTitle("Download complete")
        self.setWindowIcon(app_icon())
        self.setMinimumWidth(560)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        path = it.target_path()
        size = it.size if it.size > 0 else (os.path.getsize(path) if os.path.isfile(path) else it.downloaded)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 14)
        lay.setSpacing(8)
        head = QHBoxLayout()
        ic = QLabel()
        ic.setPixmap(icon("finished").pixmap(46, 46))
        head.addWidget(ic)
        hb = QVBoxLayout()
        t = QLabel("Download complete")
        t.setObjectName("title")
        hb.addWidget(t)
        sub = QLabel(f"Downloaded {human_size(size)}  ({size:,} Bytes)")
        sub.setObjectName("muted")
        hb.addWidget(sub)
        head.addLayout(hb, 1)
        lay.addLayout(head)
        lay.addSpacing(4)
        for cap, val in (("Address", it.url if it.kind != "torrent" else it.torrent_source), ("The file saved as", path)):
            c = QLabel(cap)
            c.setObjectName("muted")
            lay.addWidget(c)
            e = QLineEdit(val)
            e.setReadOnly(True)
            e.setCursorPosition(0)
            lay.addWidget(e)
        lay.addSpacing(6)
        br = QHBoxLayout()
        b_open = QPushButton("Open")
        b_open.setObjectName("primary")
        b_open.setIcon(icon("open", "#ffffff"))
        b_with = QPushButton("Open with…")
        b_folder = QPushButton("Open folder")
        b_folder.setIcon(icon("folder"))
        b_close = QPushButton("Close")
        for b in (b_open, b_with, b_folder):
            br.addWidget(b)
        br.addStretch(1)
        br.addWidget(b_close)
        lay.addLayout(br)
        self.dont = QCheckBox("Don't show this dialog again")
        lay.addWidget(self.dont)
        b_open.clicked.connect(lambda: (open_path(path), self.close()))
        b_with.clicked.connect(lambda: (self.open_with(path), self.close()))
        b_folder.clicked.connect(lambda: (reveal_in_folder(path), self.close()))
        b_close.clicked.connect(self.close)
        b_open.setDefault(True)

    @staticmethod
    def open_with(path: str):
        if platform.system() == "Windows" and os.path.exists(path):
            subprocess.Popen(["rundll32.exe", "shell32.dll,OpenAs_RunDLL", os.path.normpath(path)])
        else:
            reveal_in_folder(path)

    def closeEvent(self, e):
        if self.dont.isChecked():
            self.main.settings["show_complete_dialog"] = False
            self.main.save_settings()
        super().closeEvent(e)


BATCH_TYPES = ["Videos", "Images", "Audio", "Documents", "Archives", "Programs", "Other", "Pages"]
IMG_EXTS = "jpg jpeg png gif webp bmp svg avif heic ico tif tiff".split()
PAGE_EXTS = {"", "html", "htm", "php", "asp", "aspx", "jsp", "cfm", "shtml"}


def classify_item(it: dict) -> str:
    url, tag = it.get("url", ""), it.get("tag", "")
    try:
        path = urllib.parse.urlparse(url).path.lower()
    except Exception:
        path = ""
    ext = os.path.splitext(path)[1].lstrip(".")
    if tag in ("hls", "dash") or ext in ("m3u8", "mpd"):
        return "Videos"
    if tag == "img" or ext in IMG_EXTS:
        return "Images"
    if tag == "video" or tag == "media" or ext in EXT_MAP["Video"]:
        return "Videos"
    if tag == "audio" or ext in EXT_MAP["Music"]:
        return "Audio"
    if ext in EXT_MAP["Documents"]:
        return "Documents"
    if ext in EXT_MAP["Compressed"]:
        return "Archives"
    if ext in EXT_MAP["Programs"]:
        return "Programs"
    if tag == "a" and ext in PAGE_EXTS:
        return "Pages"
    return "Other"


class BatchDialog(QDialog):
    """Download files from this page — every link, image, video and audio file the extension found."""

    def __init__(self, main, data: dict):
        super().__init__(main)
        self.main = main
        self.data = data
        self.setWindowTitle("Download files from this page")
        self.setWindowIcon(app_icon())
        self.setMinimumSize(980, 680)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        seen = set()
        self.rows = []
        for it in data.get("items", []):
            url = str(it.get("url", ""))
            if not url.startswith(("http://", "https://")) or url in seen:
                continue
            seen.add(url)
            typ = classify_item(it)
            name = filename_from_url(url)
            if typ == "Images" and "." not in name:
                name += ".jpg"
            self.rows.append({"url": url, "type": typ, "name": name, "w": int(it.get("w") or 0),
                              "h": int(it.get("h") or 0), "size": int(it.get("size") or 0),
                              "text": str(it.get("text") or ""), "tag": it.get("tag", ""), "checked": typ != "Pages"})
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 14)
        lay.setSpacing(10)
        head = QHBoxLayout()
        ic = QLabel()
        ic.setPixmap(icon("all").pixmap(40, 40))
        head.addWidget(ic)
        hb = QVBoxLayout()
        t = QLabel("Download files from this page")
        t.setObjectName("title")
        sub = QLabel((data.get("title") or "") + "  ·  " + (data.get("page") or ""))
        sub.setObjectName("muted")
        sub.setMaximumWidth(860)
        hb.addWidget(t)
        hb.addWidget(sub)
        head.addLayout(hb, 1)
        lay.addLayout(head)

        chips = QHBoxLayout()
        chips.setSpacing(6)
        self.chip = {}
        counts = {k: 0 for k in BATCH_TYPES}
        for r in self.rows:
            counts[r["type"]] += 1
        for typ in BATCH_TYPES:
            b = QPushButton(f"{typ}  {counts[typ]}")
            b.setCheckable(True)
            b.setChecked(typ != "Pages" and counts[typ] > 0)
            b.setEnabled(counts[typ] > 0)
            b.setStyleSheet(f"QPushButton {{ padding: 6px 12px; border-radius: 14px; }}"
                            f"QPushButton:checked {{ background: {C_ACCENT}; border: 1px solid {C_ACCENT}; color: white; }}")
            b.toggled.connect(self.refill)
            self.chip[typ] = b
            chips.addWidget(b)
        chips.addStretch(1)
        lay.addLayout(chips)
        if data.get("which") == "images":
            for typ, b in self.chip.items():
                b.setChecked(typ == "Images" and b.isEnabled())

        frow = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter by name or address…  (e.g.  .mp4   or   cdn)")
        self.search.textChanged.connect(self.refill)
        self.min_px = QSpinBox()
        self.min_px.setRange(0, 4000)
        self.min_px.setValue(120)
        self.min_px.setSuffix(" px")
        self.min_px.setToolTip("Skip small images such as icons and avatars")
        self.min_px.valueChanged.connect(self.refill)
        frow.addWidget(self.search, 1)
        frow.addWidget(QLabel("Images at least"))
        frow.addWidget(self.min_px)
        lay.addLayout(frow)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["File name", "Type", "Info", "Address"])
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(30)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        hh = self.table.horizontalHeader()
        hh.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 330)
        self.table.setColumnWidth(1, 100)
        self.table.setColumnWidth(2, 110)
        self.table.itemChanged.connect(self.on_item_changed)
        self.table.cellDoubleClicked.connect(self.toggle_row)
        lay.addWidget(self.table, 1)

        srow = QHBoxLayout()
        b_all = QPushButton("Select all")
        b_none = QPushButton("Select none")
        b_all.clicked.connect(lambda: self.set_all(True))
        b_none.clicked.connect(lambda: self.set_all(False))
        srow.addWidget(b_all)
        srow.addWidget(b_none)
        srow.addSpacing(16)
        srow.addWidget(QLabel("Save to"))
        folder = safe_filename(data.get("title") or urllib.parse.urlparse(data.get("page") or "").netloc or "Page")[:80]
        self.dir_edit = QLineEdit(os.path.join(main.settings["download_dir"], "Grabbed", folder))
        srow.addWidget(self.dir_edit, 1)
        br = QPushButton("…")
        br.setFixedWidth(44)
        br.clicked.connect(self.browse)
        srow.addWidget(br)
        lay.addLayout(srow)

        brow = QHBoxLayout()
        self.count_lbl = QLabel("")
        self.count_lbl.setObjectName("muted")
        brow.addWidget(self.count_lbl)
        brow.addStretch(1)
        self.now_btn = QPushButton("Download")
        self.now_btn.setObjectName("primary")
        self.now_btn.setIcon(icon("resume", "#ffffff"))
        later = QPushButton("Add to queue")
        later.setIcon(icon("qstart"))
        cancel = QPushButton("Cancel")
        self.now_btn.clicked.connect(lambda: self.finish(True))
        later.clicked.connect(lambda: self.finish(False))
        cancel.clicked.connect(self.reject)
        for w in (self.now_btn, later, cancel):
            brow.addWidget(w)
        lay.addLayout(brow)
        self.visible = []
        self.refill()

    def passes(self, r) -> bool:
        if not self.chip[r["type"]].isChecked():
            return False
        if r["type"] == "Images" and r["w"] and r["h"] and max(r["w"], r["h"]) < self.min_px.value():
            return False
        q = self.search.text().strip().lower()
        return not q or q in r["url"].lower() or q in r["name"].lower() or q in r["text"].lower()

    def refill(self, *_):
        self.table.blockSignals(True)
        self.table.setUpdatesEnabled(False)
        self.visible = [r for r in self.rows if self.passes(r)]
        self.table.setRowCount(len(self.visible))
        type_icon = {"Videos": "video", "Images": "image", "Audio": "music", "Documents": "documents",
                     "Archives": "compressed", "Programs": "programs", "Pages": "open", "Other": "other"}
        for i, r in enumerate(self.visible):
            c0 = QTableWidgetItem(r["name"])
            c0.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsSelectable)
            c0.setCheckState(Qt.CheckState.Checked if r["checked"] else Qt.CheckState.Unchecked)
            c0.setIcon(icon(type_icon.get(r["type"], "other")))
            c0.setToolTip(r["text"] or r["name"])
            info = f"{r['w']}×{r['h']}" if r["w"] and r["h"] else (human_size(r["size"]) if r["size"] else "")
            cells = [c0, QTableWidgetItem(r["type"]), QTableWidgetItem(info), QTableWidgetItem(r["url"])]
            cells[3].setForeground(QColor(C_MUTED))
            cells[3].setToolTip(r["url"])
            for c, cell in enumerate(cells):
                self.table.setItem(i, c, cell)
        self.table.setUpdatesEnabled(True)
        self.table.blockSignals(False)
        self.update_count()

    def on_item_changed(self, cell):
        if cell.column() == 0 and 0 <= cell.row() < len(self.visible):
            self.visible[cell.row()]["checked"] = cell.checkState() == Qt.CheckState.Checked
            self.update_count()

    def toggle_row(self, row, _col):
        cell = self.table.item(row, 0)
        if cell:
            cell.setCheckState(Qt.CheckState.Unchecked if cell.checkState() == Qt.CheckState.Checked else Qt.CheckState.Checked)

    def set_all(self, on: bool):
        for r in self.visible:
            r["checked"] = on
        self.refill()

    def chosen(self):
        return [r for r in self.visible if r["checked"]]

    def update_count(self):
        n = len(self.chosen())
        self.count_lbl.setText(f"{n} of {len(self.rows)} files selected")
        self.now_btn.setText(f"Download {n} file{'s' if n != 1 else ''}")
        self.now_btn.setEnabled(n > 0)

    def browse(self):
        d = QFileDialog.getExistingDirectory(self, "Save to", self.dir_edit.text())
        if d:
            self.dir_edit.setText(d)

    def finish(self, start_now: bool):
        rows = self.chosen()
        if not rows:
            return
        self.main.add_batch(rows, self.dir_edit.text().strip(), self.data, start_now)
        self.accept()


LINK_QUALITIES = [("best", "Best quality (MP4)"), ("1080", "1080p MP4"), ("720", "720p MP4"),
                  ("480", "480p MP4"), ("audio", "Audio only (MP3)")]
SUB_CHOICES = [("", "No subtitles"), ("km,en", "Khmer + English"), ("km", "Khmer"), ("en", "English"),
               ("zh-Hans,zh-Hant,zh", "Chinese"), ("ko", "Korean"), ("all", "All languages")]


def _site_of(url: str) -> str:
    host = urllib.parse.urlparse(url).netloc.lower()
    for key, name in (("facebook", "Facebook"), ("fb.watch", "Facebook"), ("youtu", "YouTube"), ("tiktok", "TikTok"),
                      ("instagram", "Instagram"), ("twitter", "X"), ("x.com", "X"), ("vimeo", "Vimeo"),
                      ("dailymotion", "Dailymotion"), ("bilibili", "Bilibili")):
        if key in host:
            return name
    return host.replace("www.", "") or "Web"


class LinksDialog(QDialog):
    """Paste many links (reels, videos, playlists, channels, pages) → every video inside them → download all."""
    WORKERS = 3

    def __init__(self, main, links: list = None, cookies: dict = None, user_agent: str = "", source: str = ""):
        super().__init__(main)
        self.main = main
        self.cookies = dict(cookies or {})
        self.ua = user_agent or ""
        self.rows = []          # {url,title,duration,site,status,checked,group}
        self.seq = 0
        self.pending = 0
        self.setWindowTitle("Download links")
        self.setWindowIcon(app_icon())
        self.setMinimumSize(1000, 720)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 14)
        lay.setSpacing(10)

        head = QHBoxLayout()
        ic = QLabel()
        ic.setPixmap(icon("queues", C_ACCENT2).pixmap(40, 40))
        head.addWidget(ic)
        hb = QVBoxLayout()
        t = QLabel("Download links")
        t.setObjectName("title")
        sub = QLabel(source or "Paste Reel, video, playlist, channel or page links — one per line. "
                               "Every video inside them is listed below.")
        sub.setObjectName("muted")
        sub.setWordWrap(True)
        hb.addWidget(t)
        hb.addWidget(sub)
        head.addLayout(hb, 1)
        lay.addLayout(head)

        self.edit = QPlainTextEdit()
        self.edit.setPlaceholderText("https://www.facebook.com/reel/1234567890123\n"
                                     "https://www.youtube.com/@channel/videos\n"
                                     "https://www.youtube.com/playlist?list=…\n"
                                     "https://www.tiktok.com/@user/video/…")
        self.edit.setFixedHeight(110)
        self.edit.setStyleSheet(f"QPlainTextEdit {{ background: {C_PANEL2}; border: 1px solid {C_BORDER}; border-radius: 10px; padding: 8px; }}"
                                f"QPlainTextEdit:focus {{ border: 1px solid {C_ACCENT}; }}")
        lay.addWidget(self.edit)
        r1 = QHBoxLayout()
        paste = QPushButton("Paste")
        paste.setIcon(icon("copy"))
        paste.clicked.connect(self.paste)
        r1.addWidget(paste)
        r1.addStretch(1)
        r1.addWidget(QLabel("Max videos per link"))
        self.max_spin = QSpinBox()
        self.max_spin.setRange(1, 5000)
        self.max_spin.setValue(300)
        r1.addWidget(self.max_spin)
        self.find_btn = QPushButton("Find videos")
        self.find_btn.setObjectName("primary")
        self.find_btn.setIcon(icon("refresh", "#ffffff"))
        self.find_btn.clicked.connect(self.find)
        r1.addWidget(self.find_btn)
        lay.addLayout(r1)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Title", "Length", "Site", "Status", "Link"])
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(30)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        hh = self.table.horizontalHeader()
        hh.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        for c, wdt in ((0, 360), (1, 70), (2, 90), (3, 150)):
            self.table.setColumnWidth(c, wdt)
        self.table.itemChanged.connect(self.on_item_changed)
        lay.addWidget(self.table, 1)

        opt = QHBoxLayout()
        opt.addWidget(QLabel("Quality"))
        self.quality = QComboBox()
        for k, v in LINK_QUALITIES:
            self.quality.addItem(v, k)
        self.quality.setMinimumWidth(170)
        opt.addWidget(self.quality)
        opt.addSpacing(14)
        opt.addWidget(QLabel("Subtitles"))
        self.subs = QComboBox()
        for k, v in SUB_CHOICES:
            self.subs.addItem(v, k)
        self.subs.setMinimumWidth(150)
        opt.addWidget(self.subs)
        self.sub_auto = QCheckBox("include auto-generated")
        self.sub_embed = QCheckBox("put into the video")
        opt.addWidget(self.sub_auto)
        opt.addWidget(self.sub_embed)
        opt.addStretch(1)
        lay.addLayout(opt)
        self.subs.currentIndexChanged.connect(self.update_sub_opts)
        self.quality.currentIndexChanged.connect(self.update_sub_opts)
        self.update_sub_opts()

        srow = QHBoxLayout()
        b_all = QPushButton("Select all")
        b_none = QPushButton("Select none")
        b_all.clicked.connect(lambda: self.set_all(True))
        b_none.clicked.connect(lambda: self.set_all(False))
        srow.addWidget(b_all)
        srow.addWidget(b_none)
        srow.addSpacing(16)
        srow.addWidget(QLabel("Save to"))
        base = main.settings["download_dir"]
        self.dir_edit = QLineEdit(os.path.join(base, "Video") if main.settings.get("category_subfolders", True) else base)
        srow.addWidget(self.dir_edit, 1)
        br = QPushButton("…")
        br.setFixedWidth(44)
        br.clicked.connect(self.browse)
        srow.addWidget(br)
        lay.addLayout(srow)

        brow = QHBoxLayout()
        self.count_lbl = QLabel("")
        self.count_lbl.setObjectName("muted")
        brow.addWidget(self.count_lbl)
        brow.addStretch(1)
        self.now_btn = QPushButton("Download all")
        self.now_btn.setObjectName("primary")
        self.now_btn.setIcon(icon("resume", "#ffffff"))
        later = QPushButton("Add to queue")
        later.setIcon(icon("qstart"))
        cancel = QPushButton("Close")
        self.now_btn.clicked.connect(lambda: self.finish(True))
        later.clicked.connect(lambda: self.finish(False))
        cancel.clicked.connect(self.reject)
        for wdg in (self.now_btn, later, cancel):
            brow.addWidget(wdg)
        lay.addLayout(brow)

        self.main.bridge.links_result.connect(self.on_result)
        if links:
            self.edit.setPlainText("\n".join(links))
            QTimer.singleShot(0, self.find)
        self.refill()

    # ------------------------------------------------------------ helpers
    def update_sub_opts(self, *_):
        on = bool(self.subs.currentData())
        self.sub_auto.setEnabled(on)
        self.sub_embed.setEnabled(on and self.quality.currentData() != "audio" and find_ffmpeg(self.main.settings) is not None)

    def paste(self):
        txt = QGuiApplication.clipboard().text()
        cur = self.edit.toPlainText().strip()
        self.edit.setPlainText((cur + "\n" if cur else "") + txt.strip())

    def browse(self):
        d = QFileDialog.getExistingDirectory(self, "Save to", self.dir_edit.text())
        if d:
            self.dir_edit.setText(d)

    def parse_links(self) -> list:
        out = []
        for tok in re.split(r"[\s,]+", self.edit.toPlainText()):
            tok = tok.strip().strip("<>\"'")
            if tok.startswith(("http://", "https://")) and tok not in out:
                out.append(tok)
        return out

    def headers_for(self, url: str) -> dict:
        h = {"User-Agent": self.ua or DEFAULT_UA}
        origin = "{0.scheme}://{0.netloc}".format(urllib.parse.urlparse(url))
        c = self.cookies.get(origin)
        if not c:  # facebook.com cookies also work for m./web. subdomains
            dom = ".".join(urllib.parse.urlparse(url).netloc.split(".")[-2:])
            c = next((v for k, v in self.cookies.items() if k.endswith(dom)), "")
        if c:
            h["Cookie"] = c
        return h

    # ------------------------------------------------------------ lookup
    def find(self):
        if not HAS_YTDLP:
            QMessageBox.warning(self, APP_NAME, "yt-dlp is not installed.\n\nRun:  pip install yt-dlp")
            return
        links = self.parse_links()
        if not links:
            QMessageBox.information(self, APP_NAME, "Paste at least one link that starts with http:// or https://")
            return
        self.seq += 1
        seq = self.seq
        known = {r["url"] for r in self.rows} | {r["group"] for r in self.rows}
        new = [l for l in links if l not in known]
        if not new:
            return
        start = len(self.rows)
        for l in new:
            self.rows.append({"url": l, "title": l, "duration": 0, "site": _site_of(l), "status": "Checking…",
                              "checked": True, "group": l, "pending": True})
        self.pending += len(new)
        self.refill()
        jobs = list(enumerate(new))
        lock = threading.Lock()
        maxn = self.max_spin.value()
        bridge = self.main.bridge

        def worker():
            while True:
                with lock:
                    if not jobs:
                        return
                    i, link = jobs.pop(0)
                bridge.links_result.emit(seq, i, self.expand(link, maxn))

        for _ in range(min(self.WORKERS, len(jobs))):
            threading.Thread(target=worker, daemon=True).start()
        self.find_btn.setText("Finding…")

    def expand(self, link: str, maxn: int) -> dict:
        opts = {"quiet": True, "no_warnings": True, "skip_download": True, "extract_flat": "in_playlist",
                "playlistend": maxn, "logger": _QuietLogger(), "http_headers": self.headers_for(link)}
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(link, download=False)
        except Exception as e:
            msg = re.sub(r"\x1b\[[0-9;]*m", "", str(e)).replace("ERROR: ", "")
            return {"link": link, "error": msg[:200]}
        if not info:
            return {"link": link, "error": "Nothing found"}
        entries = []
        if info.get("_type") in ("playlist", "multi_video"):
            for e in itertools.islice(info.get("entries") or [], maxn):
                if not e:
                    continue
                if e.get("_type") == "playlist":   # channel tabs (Videos / Shorts) → links to expand later
                    entries.append({"url": e.get("url") or e.get("webpage_url"), "title": e.get("title") or "Playlist",
                                    "duration": 0, "nested": True})
                    continue
                wp, u = e.get("webpage_url") or "", e.get("url") or ""
                # several videos on one page share the page address → use each video's own address instead
                url = wp if (wp and wp not in (link, info.get("webpage_url"))) else (u if u.startswith("http") else wp)
                if not url.startswith("http"):
                    fm = [f for f in (e.get("formats") or []) if f.get("url", "").startswith("http")]
                    url = fm[-1]["url"] if fm else ""
                if url:
                    entries.append({"url": url, "title": e.get("title") or e.get("id") or url,
                                    "duration": e.get("duration") or 0})
        else:
            entries.append({"url": info.get("webpage_url") or link, "title": info.get("title") or link,
                            "duration": info.get("duration") or 0})
        return {"link": link, "entries": entries, "playlist": info.get("_type") in ("playlist", "multi_video"),
                "name": info.get("title") or ""}

    def on_result(self, seq, _i, res):
        try:
            link = res["link"]
            idx = next((k for k, r in enumerate(self.rows) if r["group"] == link and r.get("pending")), None)
            if idx is None:
                return
            self.pending -= 1
            if res.get("error"):
                self.rows[idx].update(status="Error: " + res["error"], checked=False, pending=False)
            else:
                ents = res["entries"]
                nested = [e for e in ents if e.get("nested")]
                ents = [e for e in ents if not e.get("nested")]
                seen = {r["url"] for k, r in enumerate(self.rows) if k != idx}
                new_rows = []
                for e in ents:
                    if e["url"] in seen:
                        continue
                    seen.add(e["url"])
                    new_rows.append({"url": e["url"], "title": e["title"], "duration": e["duration"],
                                     "site": _site_of(e["url"]) if not e["url"].startswith(link) else _site_of(link),
                                     "status": f"From: {res['name'][:40]}" if res.get("playlist") else "Ready",
                                     "checked": True, "group": link, "pending": False})
                if not new_rows and not nested:
                    self.rows[idx].update(status="No videos found", checked=False, pending=False)
                else:
                    self.rows[idx:idx + 1] = new_rows
                if nested:   # e.g. a YouTube channel home → its Videos / Shorts tabs
                    extra = "\n".join(e["url"] for e in nested if e.get("url"))
                    self.edit.setPlainText(self.edit.toPlainText().rstrip() + "\n" + extra)
                    QTimer.singleShot(0, self.find)
            if self.pending <= 0:
                self.find_btn.setText("Find videos")
            self.refill()
        except RuntimeError:
            pass

    # ------------------------------------------------------------ table
    def refill(self):
        self.table.blockSignals(True)
        self.table.setUpdatesEnabled(False)
        self.table.setRowCount(len(self.rows))
        for i, r in enumerate(self.rows):
            c0 = QTableWidgetItem(r["title"])
            c0.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsSelectable)
            c0.setCheckState(Qt.CheckState.Checked if r["checked"] else Qt.CheckState.Unchecked)
            c0.setIcon(icon("video"))
            c0.setToolTip(r["title"])
            dur = human_eta(r["duration"]).replace(" min ", ":").replace(" sec", "s") if r["duration"] else ""
            st = QTableWidgetItem(r["status"])
            st.setForeground(QColor(C_RED if r["status"].startswith(("Error", "No videos")) else
                                    C_MUTED if r.get("pending") else C_GREEN))
            st.setToolTip(r["status"])
            ln = QTableWidgetItem(r["url"])
            ln.setForeground(QColor(C_MUTED))
            ln.setToolTip(r["url"])
            for c, cell in enumerate((c0, QTableWidgetItem(dur), QTableWidgetItem(r["site"]), st, ln)):
                self.table.setItem(i, c, cell)
        self.table.setUpdatesEnabled(True)
        self.table.blockSignals(False)
        self.update_count()

    def on_item_changed(self, cell):
        if cell.column() == 0 and 0 <= cell.row() < len(self.rows):
            self.rows[cell.row()]["checked"] = cell.checkState() == Qt.CheckState.Checked
            self.update_count()

    def set_all(self, on: bool):
        for r in self.rows:
            if not r["status"].startswith(("Error", "No videos")):
                r["checked"] = on
        self.refill()

    def chosen(self):
        return [r for r in self.rows if r["checked"]]

    def update_count(self):
        n = len(self.chosen())
        busy = f"  ·  still checking {self.pending} link{'s' if self.pending != 1 else ''}…" if self.pending > 0 else ""
        self.count_lbl.setText(f"{n} of {len(self.rows)} videos selected{busy}")
        self.now_btn.setText(f"Download {n} video{'s' if n != 1 else ''}" if n else "Download all")
        self.now_btn.setEnabled(n > 0)

    def finish(self, start_now: bool):
        rows = self.chosen()
        if not rows:
            return
        q = self.quality.currentData()
        sub = self.subs.currentData() or ""
        folder = self.dir_edit.text().strip() or self.main.settings["download_dir"]
        if q == "audio" and folder.rstrip("\\/").endswith("Video") and self.main.settings.get("category_subfolders", True):
            folder = os.path.join(os.path.dirname(folder.rstrip("\\/")), "Music")
        self.main.add_links(rows, folder, q, sub, self.sub_auto.isChecked() and bool(sub),
                            self.sub_embed.isChecked() and bool(sub), start_now, self.headers_for)
        self.accept()

    def done(self, r):
        try:
            self.main.bridge.links_result.disconnect(self.on_result)
        except Exception:
            pass
        super().done(r)


class OptionsDialog(QDialog):
    def __init__(self, parent, settings: dict):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Options")
        self.setMinimumWidth(560)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16)

        g1 = QGroupBox("Downloads")
        f1 = QFormLayout(g1)
        row = QHBoxLayout()
        self.dir_edit = QLineEdit(settings["download_dir"])
        b = QPushButton("Browse…")
        b.clicked.connect(self.browse)
        row.addWidget(self.dir_edit, 1)
        row.addWidget(b)
        f1.addRow("Default folder", row)
        self.subfolders = QCheckBox("Save each category in its own subfolder (Video, Music, …)")
        self.subfolders.setChecked(settings["category_subfolders"])
        f1.addRow("", self.subfolders)
        self.conns = QSpinBox()
        self.conns.setRange(1, 32)
        self.conns.setValue(settings["connections"])
        f1.addRow("Connections per file", self.conns)
        self.concurrent = QSpinBox()
        self.concurrent.setRange(1, 20)
        self.concurrent.setValue(settings["max_concurrent"])
        f1.addRow("Queue: files at the same time", self.concurrent)
        self.limit = QSpinBox()
        self.limit.setRange(0, 1_000_000)
        self.limit.setSuffix(" KB/s")
        self.limit.setSpecialValueText("Unlimited")
        self.limit.setValue(settings["speed_limit_kb"])
        f1.addRow("Speed limit", self.limit)
        self.quality = QComboBox()
        for key, label in YTDLP_QUALITIES:
            self.quality.addItem(label, key)
        self.quality.setCurrentIndex(max(0, self.quality.findData(settings["ytdlp_quality"])))
        f1.addRow("Default video quality", self.quality)
        lay.addWidget(g1)

        g2 = QGroupBox("Browser integration")
        f2 = QFormLayout(g2)
        self.port = QSpinBox()
        self.port.setRange(1024, 65535)
        self.port.setValue(settings["port"])
        f2.addRow("Local port", self.port)
        self.confirm = QCheckBox("Show the download dialog for downloads sent by the browser")
        self.confirm.setChecked(settings["browser_confirm"])
        f2.addRow("", self.confirm)
        self.prog_cb = QCheckBox("Show the progress window when a download starts")
        self.prog_cb.setChecked(settings.get("show_progress_dialog", True))
        f1.addRow("", self.prog_cb)
        self.comp_cb = QCheckBox("Show the “Download complete” dialog")
        self.comp_cb.setChecked(settings.get("show_complete_dialog", True))
        f1.addRow("", self.comp_cb)
        self.autostart_cb = QCheckBox("Start Chivet-kh Download with Windows (hidden in the tray)")
        self.autostart_cb.setChecked(settings.get("autostart", True))
        f2.addRow("", self.autostart_cb)
        self.tray = QCheckBox("Closing the window keeps the app running in the system tray")
        self.tray.setChecked(settings["close_to_tray"])
        f2.addRow("", self.tray)
        lay.addWidget(g2)

        g3 = QGroupBox("Components")
        f3 = QFormLayout(g3)

        def st(ok, hint):
            lab = QLabel(("✔ Installed" if ok else "✖ Missing — " + hint))
            lab.setStyleSheet(f"color: {C_GREEN if ok else C_AMBER};")
            return lab
        f3.addRow("yt-dlp (video sites)", st(HAS_YTDLP, "pip install yt-dlp"))
        f3.addRow("ffmpeg (best quality / mp3)", st(find_ffmpeg(settings) is not None, "pip install imageio-ffmpeg"))
        f3.addRow("libtorrent (torrents)", st(HAS_LT, "pip install libtorrent"))
        lay.addWidget(g3)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Save).setObjectName("primary")
        bb.accepted.connect(self.save)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def browse(self):
        d = QFileDialog.getExistingDirectory(self, "Default folder", self.dir_edit.text())
        if d:
            self.dir_edit.setText(d)

    def save(self):
        s = self.settings
        s["download_dir"] = self.dir_edit.text().strip() or DEFAULT_SETTINGS["download_dir"]
        s["category_subfolders"] = self.subfolders.isChecked()
        s["connections"] = self.conns.value()
        s["max_concurrent"] = self.concurrent.value()
        s["speed_limit_kb"] = self.limit.value()
        s["ytdlp_quality"] = self.quality.currentData()
        s["port"] = self.port.value()
        s["browser_confirm"] = self.confirm.isChecked()
        s["close_to_tray"] = self.tray.isChecked()
        s["autostart"] = self.autostart_cb.isChecked()
        set_autostart(s["autostart"])
        s["show_progress_dialog"] = self.prog_cb.isChecked()
        s["show_complete_dialog"] = self.comp_cb.isChecked()
        self.accept()


class SchedulerDialog(QDialog):
    DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    def __init__(self, parent, settings: dict):
        super().__init__(parent)
        self.settings = settings
        sc = settings["scheduler"]
        self.setWindowTitle("Scheduler")
        self.setMinimumWidth(460)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16)
        g = QGroupBox("Main queue")
        grid = QGridLayout(g)
        self.start_cb = QCheckBox("Start queue at")
        self.start_cb.setChecked(sc["start_enabled"])
        self.start_time = QTimeEdit(QTime.fromString(sc["start_time"], "HH:mm"))
        self.start_time.setDisplayFormat("HH:mm")
        self.stop_cb = QCheckBox("Stop queue at")
        self.stop_cb.setChecked(sc["stop_enabled"])
        self.stop_time = QTimeEdit(QTime.fromString(sc["stop_time"], "HH:mm"))
        self.stop_time.setDisplayFormat("HH:mm")
        grid.addWidget(self.start_cb, 0, 0)
        grid.addWidget(self.start_time, 0, 1)
        grid.addWidget(self.stop_cb, 1, 0)
        grid.addWidget(self.stop_time, 1, 1)
        days = QHBoxLayout()
        self.day_cbs = []
        for i, d in enumerate(self.DAYS):
            cb = QCheckBox(d)
            cb.setChecked(i in sc["days"])
            self.day_cbs.append(cb)
            days.addWidget(cb)
        grid.addWidget(QLabel("Days"), 2, 0, 1, 2)
        grid.addLayout(days, 3, 0, 1, 2)
        grid.addWidget(QLabel("When the queue finishes"), 4, 0)
        self.finish = QComboBox()
        self.finish.addItem("Do nothing", "nothing")
        self.finish.addItem("Exit Chivet-kh Download", "exit")
        self.finish.addItem("Shut down the computer", "shutdown")
        self.finish.setCurrentIndex(max(0, self.finish.findData(sc["on_finish"])))
        grid.addWidget(self.finish, 4, 1)
        lay.addWidget(g)
        note = QLabel("Use “Add to Queue” in the download dialog to put files into the queue.")
        note.setObjectName("muted")
        note.setWordWrap(True)
        lay.addWidget(note)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Save).setObjectName("primary")
        bb.accepted.connect(self.save)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def save(self):
        self.settings["scheduler"] = {
            "start_enabled": self.start_cb.isChecked(), "start_time": self.start_time.time().toString("HH:mm"),
            "stop_enabled": self.stop_cb.isChecked(), "stop_time": self.stop_time.time().toString("HH:mm"),
            "days": [i for i, cb in enumerate(self.day_cbs) if cb.isChecked()],
            "on_finish": self.finish.currentData(),
        }
        self.accept()


class ExtensionDialog(QDialog):
    def __init__(self, parent, port: int, server_ok: bool):
        super().__init__(parent)
        self.setWindowTitle("Browser extension")
        self.setMinimumSize(560, 470)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16)
        t = QLabel("Connect Chrome / Edge to Chivet-kh Download")
        t.setObjectName("title")
        lay.addWidget(t)
        status = QLabel(f"● Browser integration is listening on 127.0.0.1:{port}" if server_ok
                        else f"● Port {port} is busy — change it in Options")
        status.setStyleSheet(f"color: {C_GREEN if server_ok else C_RED}; font-weight:600;")
        lay.addWidget(status)
        tb = QTextBrowser()
        tb.setOpenExternalLinks(False)
        tb.setHtml(f"""
        <h3>Install the extension (English)</h3>
        <ol>
          <li>Open <b>chrome://extensions</b> (Edge: <b>edge://extensions</b>).</li>
          <li>Turn on <b>Developer mode</b> (top-right switch; on Edge it is on the left).</li>
          <li>Click <b>Load unpacked</b> and choose the folder:<br><code>{EXTENSION_DIR}</code></li>
          <li>Pin the extension. Its popup shows <b>Connected</b> while this app is running.</li>
        </ol>
        <h3>ដំឡើង Extension (ភាសាខ្មែរ)</h3>
        <ol>
          <li>បើក <b>chrome://extensions</b> (ឬ <b>edge://extensions</b> សម្រាប់ Edge)</li>
          <li>បើក <b>Developer mode</b></li>
          <li>ចុច <b>Load unpacked</b> ហើយជ្រើសថត <code>browser_extension</code></li>
          <li>Pin extension ទុក។ ពេលកម្មវិធីនេះកំពុងដំណើរការ វានឹងបង្ហាញថា <b>Connected</b></li>
        </ol>
        <p>Downloads that start in the browser are sent here automatically. Right-click any link, image or
        video and choose <b>Download with Chivet-kh Download</b>, or <b>Grab video from this page</b> on YouTube,
        Facebook or TikTok.</p>
        """)
        lay.addWidget(tb, 1)
        row = QHBoxLayout()
        row.addStretch(1)
        ob = QPushButton("Open extension folder")
        ob.setIcon(icon("folder"))
        ob.clicked.connect(lambda: open_path(str(EXTENSION_DIR)))
        cb = QPushButton("Copy path")
        cb.setIcon(icon("copy"))
        cb.clicked.connect(lambda: QGuiApplication.clipboard().setText(str(EXTENSION_DIR)))
        close = QPushButton("Close")
        close.setObjectName("primary")
        close.clicked.connect(self.accept)
        row.addWidget(ob)
        row.addWidget(cb)
        row.addWidget(close)
        lay.addLayout(row)


# ----------------------------------------------------------------------------
# Main window
# ----------------------------------------------------------------------------
class EmptyState(QWidget):
    add_clicked = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setObjectName("empty")
        self.setStyleSheet(f"QWidget#empty {{ background: {C_PANEL}; border: 1px solid {C_BORDER}; border-radius: 12px; }}")
        lay = QVBoxLayout(self)
        lay.addStretch(1)
        ic = QLabel()
        ic.setPixmap(icon("resume", "#5b6178").pixmap(64, 64))
        ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(ic)
        t = QLabel("No downloads yet")
        t.setStyleSheet("font-size: 14pt; font-weight: 700; background: transparent;")
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(t)
        s = QLabel("The downloads you add, send from the browser, or drop on this window show here.")
        s.setStyleSheet(f"color: {C_MUTED}; background: transparent;")
        s.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(s)
        b = QPushButton("Add new download")
        b.setObjectName("link")
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.clicked.connect(self.add_clicked.emit)
        h = QHBoxLayout()
        h.addStretch(1)
        h.addWidget(b)
        h.addStretch(1)
        lay.addLayout(h)
        lay.addStretch(1)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.settings = load_settings()
        self.items = [DownloadItem.from_dict(d) for d in load_json(DOWNLOADS_FILE, []) if isinstance(d, dict)]
        for it in self.items:
            _ITEM_REGISTRY[it.id] = it
        self.tasks = {}
        self.last_bytes = {}
        self.queue_running = False
        self.quitting = False
        self.dialogs = []
        self.progress_dialogs = {}
        self.watch_ids = set()
        self.last_save = 0
        self.sched_fired = set()
        self.tray_hint_shown = False
        self.throttle = Throttle()
        self.throttle.rate = self.settings["speed_limit_kb"] * 1024
        self.bridge = Bridge()
        self.bridge.task_done.connect(self.on_task_done)
        self.bridge.browser_add.connect(self.on_browser_add)
        self.bridge.batch_add.connect(self.on_batch_add)
        self.bridge.links_add.connect(self.on_links_add)
        self.bridge.show_window.connect(self.bring_to_front)
        self.server = ApiServer(self.bridge)
        self.server_ok = self.server.start(self.settings["port"])

        self.setWindowTitle(f"{APP_NAME} {VERSION}")
        self.setWindowIcon(app_icon())
        self.resize(1240, 720)
        self.setAcceptDrops(True)
        self.build_actions()
        self.build_menu()
        self.build_toolbar()
        self.build_body()
        self.build_statusbar()
        self.build_tray()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(500)
        self.sched_timer = QTimer(self)
        self.sched_timer.timeout.connect(self.check_scheduler)
        self.sched_timer.start(15000)
        self.refresh_all(force=True)

    # ---------------- UI construction
    def build_actions(self):
        A = lambda ic, text, slot, sc=None: self._action(ic, text, slot, sc)
        self.a_add = A("add", "Add URL", self.add_url_dialog, "Ctrl+N")
        self.a_vpage = A("video", "Download video from a page…", lambda: self.video_page_dialog(), "Ctrl+Shift+N")
        self.a_links = A("queues", "Links", lambda: self.links_dialog(), "Ctrl+L")
        self.a_links.setToolTip("Download all videos from many links (reels, playlists, channels, pages)")
        self.a_torrent = A("magnet", "Add Torrent", self.add_torrent_file, "Ctrl+T")
        self.a_magnet = A("magnet", "Add magnet link…", self.add_magnet)
        self.a_resume = A("resume", "Resume", self.resume_selected, "Ctrl+R")
        self.a_stop = A("stop", "Stop", self.stop_selected, "Ctrl+S")
        self.a_stopall = A("stopall", "Stop All", self.stop_all)
        self.a_delete = A("delete", "Delete", self.delete_selected, "Delete")
        self.a_delclean = A("delclean", "Delete Completed", self.delete_completed)
        self.a_options = A("options", "Options", self.show_options)
        self.a_sched = A("scheduler", "Scheduler", self.show_scheduler)
        self.a_qstart = A("qstart", "Start Queue", self.start_queue)
        self.a_qstop = A("qstop", "Stop Queue", self.stop_queue)
        self.a_open = A("open", "Open", self.open_selected)
        self.a_folder = A("folder", "Open folder", self.open_selected_folder)
        self.a_copy = A("copy", "Copy link", self.copy_selected_url)
        self.a_redl = A("refresh", "Download again", self.redownload_selected)
        self.a_toqueue = A("qstart", "Add to queue / remove from queue", self.toggle_queue_selected)
        self.a_ext = A("puzzle", "Browser extension…", self.show_extension)
        self.a_about = A("info", "About", self.show_about)
        self.a_exit = A("stopall", "Exit", self.quit_app, "Ctrl+Q")

    def _action(self, ic, text, slot, sc=None):
        a = QAction(icon(ic), text, self)
        a.triggered.connect(slot)
        if sc:
            a.setShortcut(QKeySequence(sc))
        return a

    def build_menu(self):
        mb = self.menuBar()
        m = mb.addMenu("Tasks")
        for a in (self.a_add, self.a_vpage, self.a_links, self.a_torrent, self.a_magnet):
            m.addAction(a)
        m.addSeparator()
        m.addAction(self.a_exit)
        m = mb.addMenu("File")
        for a in (self.a_open, self.a_folder, self.a_copy):
            m.addAction(a)
        m = mb.addMenu("Downloads")
        for a in (self.a_resume, self.a_stop, self.a_stopall, None, self.a_delete, self.a_delclean, None,
                  self.a_qstart, self.a_qstop, self.a_sched, None, self.a_options):
            m.addSeparator() if a is None else m.addAction(a)
        m = mb.addMenu("View")
        self.a_show_cats = QAction("Categories panel", self, checkable=True, checked=True)
        self.a_show_cats.toggled.connect(lambda v: self.tree.setVisible(v))
        m.addAction(self.a_show_cats)
        m = mb.addMenu("Help")
        m.addAction(self.a_ext)
        m.addAction(self.a_about)

    def build_toolbar(self):
        tb = QToolBar("Main")
        tb.setMovable(False)
        tb.setIconSize(QSize(30, 30))
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.addToolBar(tb)
        amenu = QMenu(self)
        amenu.addAction(QAction(icon("add"), "Add URL…", self, triggered=lambda: self.add_url_dialog()))
        amenu.addAction(self.a_vpage)
        amenu.addAction(self.a_links)
        self.a_add.setMenu(amenu)
        tb.addAction(self.a_add)
        tb.widgetForAction(self.a_add).setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        tmenu = QMenu(self)
        tmenu.addAction(self.a_torrent)
        tmenu.addAction(self.a_magnet)
        self.a_torrent.setMenu(tmenu)
        tb.addAction(self.a_torrent)
        tb.widgetForAction(self.a_torrent).setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        tb.addAction(self.a_links)
        tb.addSeparator()
        for a in (self.a_resume, self.a_stop, self.a_stopall, self.a_delete, self.a_delclean):
            tb.addAction(a)
        tb.addSeparator()
        for a in (self.a_options, self.a_sched, self.a_qstart, self.a_qstop):
            tb.addAction(a)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)
        tb.addAction(self.a_ext)
        for a in tb.actions():
            w = tb.widgetForAction(a)
            if isinstance(w, QToolButton):
                w.setMinimumWidth(78)
                w.setCursor(Qt.CursorShape.PointingHandCursor)

    def build_body(self):
        central = QWidget()
        central.setObjectName("central")
        lay = QHBoxLayout(central)
        lay.setContentsMargins(10, 10, 10, 6)
        split = QSplitter(Qt.Orientation.Horizontal)
        split.setChildrenCollapsible(False)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIconSize(QSize(18, 18))
        self.tree.setIndentation(16)
        self.tree.setMinimumWidth(200)
        self.tree_nodes = {}

        def node(parent, key, label, ic):
            n = QTreeWidgetItem([label])
            n.setIcon(0, icon(ic))
            n.setData(0, Qt.ItemDataRole.UserRole, key)
            if parent is None:
                self.tree.addTopLevelItem(n)
            else:
                parent.addChild(n)
            self.tree_nodes[key] = (n, label)
            return n

        root = node(None, "all", "All Downloads", "all")
        for c in CATEGORIES + ["Other"]:
            node(root, "cat:" + c, c, CATEGORY_ICONS[c])
        unf = node(None, "unfinished", "Unfinished", "unfinished")
        fin = node(None, "finished", "Finished", "finished")
        node(None, "queue", "Queue", "queues")
        for parent, prefix in ((unf, "unf"), (fin, "fin")):
            for c in ("Video", "Images", "Music", "Programs", "Compressed", "Documents"):
                node(parent, f"{prefix}:{c}", c, CATEGORY_ICONS[c])
        root.setExpanded(True)
        self.tree.setCurrentItem(root)
        self.tree.currentItemChanged.connect(self.on_category_changed)

        self.model = DownloadModel(self.items)
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.setIconSize(QSize(18, 18))
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(36)
        self.table.setItemDelegateForColumn(3, ProgressDelegate(self.table))
        hh = self.table.horizontalHeader()
        hh.setHighlightSections(False)
        hh.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col, w in ((1, 30), (2, 88), (3, 140), (4, 100), (5, 90), (6, 100), (7, 52), (8, 80), (9, 125)):
            hh.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
            self.table.setColumnWidth(col, w)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        self.table.doubleClicked.connect(self.on_double_click)
        self.table.selectionModel().selectionChanged.connect(lambda *_: self.update_actions())

        self.empty = EmptyState()
        self.empty.add_clicked.connect(self.add_url_dialog)
        self.stack = QStackedWidget()
        self.stack.addWidget(self.empty)
        self.stack.addWidget(self.table)

        split.addWidget(self.tree)
        split.addWidget(self.stack)
        split.setStretchFactor(1, 1)
        split.setSizes([220, 1000])
        lay.addWidget(split)
        self.setCentralWidget(central)

    def build_statusbar(self):
        sb = self.statusBar()
        self.lbl_count = QLabel()
        self.lbl_speed = QLabel()
        self.lbl_queue = QLabel()
        self.lbl_api = QLabel()
        sb.addWidget(self.lbl_count)
        sb.addWidget(self.lbl_speed)
        sb.addWidget(self.lbl_queue)
        sb.addPermanentWidget(self.lbl_api)
        self.update_api_label()

    def update_api_label(self):
        if self.server_ok:
            self.lbl_api.setText(f"<span style='color:{C_GREEN}'>●</span> Browser integration · port {self.settings['port']}")
        else:
            self.lbl_api.setText(f"<span style='color:{C_RED}'>●</span> Port {self.settings['port']} busy — browser integration off")

    def build_tray(self):
        self.tray = None
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = QSystemTrayIcon(app_icon(), self)
        self.tray.setToolTip(APP_NAME)
        menu = QMenu()
        show = QAction("Show Chivet-kh Download", self)
        show.triggered.connect(self.bring_to_front)
        menu.addAction(show)
        menu.addAction(self.a_add)
        menu.addAction(self.a_stopall)
        menu.addSeparator()
        menu.addAction(self.a_exit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda r: self.bring_to_front()
                                    if r == QSystemTrayIcon.ActivationReason.Trigger else None)
        self.tray.show()

    # ---------------- filtering
    def on_category_changed(self, cur, _prev=None):
        key = cur.data(0, Qt.ItemDataRole.UserRole) if cur else "all"
        unfinished = lambda it: it.status != "Finished"
        if key == "all":
            fn = lambda it: True
        elif key == "unfinished":
            fn = unfinished
        elif key == "finished":
            fn = lambda it: it.status == "Finished"
        elif key == "queue":
            fn = lambda it: it.in_queue
        elif key.startswith("cat:"):
            c = key[4:]
            fn = lambda it, c=c: it.category == c
        elif key.startswith("unf:"):
            c = key[4:]
            fn = lambda it, c=c: it.category == c and it.status != "Finished"
        elif key.startswith("fin:"):
            c = key[4:]
            fn = lambda it, c=c: it.category == c and it.status == "Finished"
        else:
            fn = lambda it: True
        self.model.set_filter(fn)
        self.refresh_all()

    # ---------------- periodic update
    def tick(self):
        now = time.monotonic()
        total_speed = 0.0
        for iid, task in list(self.tasks.items()):
            it = task.item
            if not task.reports_speed:
                prev_b, prev_t = self.last_bytes.get(iid, (it.downloaded, now - 0.5))
                dt = max(0.05, now - prev_t)
                inst = max(0.0, (it.downloaded - prev_b) / dt)
                it.speed = inst if it.speed <= 0 else it.speed * 0.6 + inst * 0.4
                self.last_bytes[iid] = (it.downloaded, now)
                it.eta = ((it.size - it.downloaded) / it.speed) if (it.speed > 1 and it.size > 0) else -1
            total_speed += it.speed or 0
        self.total_speed = total_speed
        for dlg in list(self.progress_dialogs.values()):
            try:
                dlg.refresh()
            except RuntimeError:
                pass
        self.process_queue()
        self.refresh_all()
        if time.time() - self.last_save > 5:
            self.save_items()

    def refresh_all(self, force=False):
        sel = self.selected_ids()
        reset = self.model.refresh(force=force)
        if reset and sel:
            self.select_ids(sel)
        self.stack.setCurrentIndex(1 if self.model.rowCount() else 0)
        has_torrents = any(i.kind == "torrent" for i in self.items)
        for col in (7, 8):
            if self.table.isColumnHidden(col) == has_torrents:
                self.table.setColumnHidden(col, not has_torrents)
        counts = {"all": len(self.items), "unfinished": 0, "finished": 0, "queue": 0}
        for it in self.items:
            done = it.status == "Finished"
            counts["finished" if done else "unfinished"] += 1
            counts["cat:" + it.category] = counts.get("cat:" + it.category, 0) + 1
            pre = "fin:" if done else "unf:"
            counts[pre + it.category] = counts.get(pre + it.category, 0) + 1
            if it.in_queue:
                counts["queue"] += 1
        for key, (n, label) in self.tree_nodes.items():
            c = counts.get(key, 0)
            text = f"{label}  ({c})" if c else label
            if n.text(0) != text:
                n.setText(0, text)
        active = len(self.tasks)
        self.lbl_count.setText(f"{len(self.items)} downloads" + (f" · {active} active" if active else ""))
        sp = getattr(self, "total_speed", 0)
        self.lbl_speed.setText(f"↓ {human_speed(sp)}" if sp > 0 else "")
        self.lbl_queue.setText("Queue running" if self.queue_running else "")
        self.update_actions()
        if self.tray:
            self.tray.setToolTip(f"{APP_NAME}\n{active} active" + (f" · {human_speed(sp)}" if sp > 0 else ""))

    def update_actions(self):
        sel = self.selected_items()
        can_resume = any(it.id not in self.tasks and it.status != "Finished" for it in sel)
        can_stop = any(it.id in self.tasks for it in sel)
        self.a_resume.setEnabled(can_resume)
        self.a_stop.setEnabled(can_stop)
        self.a_stopall.setEnabled(bool(self.tasks))
        self.a_delete.setEnabled(bool(sel))
        self.a_delclean.setEnabled(any(it.status == "Finished" for it in self.items))
        self.a_qstart.setEnabled(not self.queue_running)
        self.a_qstop.setEnabled(self.queue_running)
        self.a_open.setEnabled(len(sel) == 1 and sel[0].status == "Finished")
        self.a_folder.setEnabled(len(sel) == 1)
        self.a_copy.setEnabled(bool(sel))
        self.a_redl.setEnabled(bool(sel) and all(it.id not in self.tasks for it in sel))
        self.a_toqueue.setEnabled(bool(sel))

    # ---------------- selection helpers
    def selected_items(self):
        rows = sorted({i.row() for i in self.table.selectionModel().selectedRows()})
        return [self.model.item_at(r) for r in rows if self.model.item_at(r)]

    def selected_ids(self):
        return [it.id for it in self.selected_items()]

    def select_ids(self, ids):
        sm = self.table.selectionModel()
        for r, it in enumerate(self.model.rows):
            if it.id in ids:
                sm.select(self.model.index(r, 0), QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)

    def find_item(self, iid):
        for it in self.items:
            if it.id == iid:
                return it
        return None

    # ---------------- adding
    def add_url_dialog(self, url: str = "", filename: str = "", headers: dict = None, mode: str = "auto",
                       from_browser: bool = False, size_hint: int = 0, quality: str = None, title_hint: str = ""):
        if not isinstance(url, str):
            url = ""
        if url and HAS_YTDLP and is_video_site(url) and mode != "http":
            return self.video_page_dialog(url, headers, title_hint, from_browser)
        dlg = AddDownloadDialog(self, self.settings, self.bridge, url, filename, headers, mode, from_browser,
                                size_hint, quality, title_hint)
        if from_browser:
            dlg.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.dialogs.append(dlg)

        def done(code):
            if dlg in self.dialogs:
                self.dialogs.remove(dlg)
            if code == QDialog.DialogCode.Accepted and dlg.result_data:
                if dlg.result_data.get("open_video_page"):
                    d = dlg.result_data
                    QTimer.singleShot(0, lambda: self.video_page_dialog(d["url"], d["headers"], d.get("title_hint", "")))
                else:
                    self.add_item(dlg.result_data)
            dlg.deleteLater()
        dlg.finished.connect(done)
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def video_page_dialog(self, url: str = "", headers: dict = None, title_hint: str = "", from_browser: bool = False):
        if not url:
            clip = QGuiApplication.clipboard().text().strip()
            url = clip if (looks_like_url(clip) and not clip.startswith("magnet:")) else ""
        dlg = VideoPageDialog(self, self.settings, self.bridge, url, headers, title_hint, from_browser)
        if from_browser:
            dlg.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.dialogs.append(dlg)

        def done(code):
            if dlg in self.dialogs:
                self.dialogs.remove(dlg)
            if code == QDialog.DialogCode.Accepted and dlg.result_data:
                self.add_item(dlg.result_data)
            dlg.deleteLater()
        dlg.finished.connect(done)
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def show_progress(self, it: DownloadItem):
        dlg = self.progress_dialogs.get(it.id)
        if dlg is None:
            dlg = ProgressDialog(self, it)
            self.progress_dialogs[it.id] = dlg
        self.watch_ids.add(it.id)
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()
        return dlg

    def add_item(self, d: dict) -> DownloadItem:
        kind = d.get("kind", "http")
        save_dir = d["save_dir"]
        if kind == "ytdlp":
            name = d.get("filename") or d.get("title_hint") or ("Video — " + urllib.parse.urlparse(d["url"]).netloc)
            if d.get("filename") and not d.get("auto_name", True):
                name = unique_name(save_dir, d["filename"])
        elif kind == "torrent":
            name = d.get("filename") or "Torrent"
        else:
            name = unique_name(save_dir, d.get("filename") or filename_from_url(d["url"]))
        it = DownloadItem(url=d["url"], filename=name, save_dir=save_dir, kind=kind,
                          category=d.get("category") or category_for(name, kind),
                          connections=int(d.get("connections", self.settings["connections"])),
                          headers=dict(d.get("headers") or {}), auto_name=bool(d.get("auto_name", True)),
                          quality=d.get("quality") or self.settings["ytdlp_quality"],
                          torrent_source=d.get("torrent_source", ""), title_hint=d.get("title_hint", ""),
                          ytdlp_format=d.get("ytdlp_format", ""), audio_format=d.get("audio_format", ""),
                          audio_quality=d.get("audio_quality", ""), sub_lang=d.get("sub_lang", ""),
                          sub_auto=bool(d.get("sub_auto")), embed_subs=bool(d.get("embed_subs")))
        if d.get("size") and d["size"] > 0:
            it.size = int(d["size"])
        if it.category == "Other" and kind == "http":
            it.category = category_for(name)
        it.in_queue = not d.get("start_now", True)
        it.status = "Queued" if it.in_queue else "Stopped"
        self.items.append(it)
        _ITEM_REGISTRY[it.id] = it
        if d.get("start_now", True):
            self.start_item(it)
            if not d.get("silent"):
                self.watch_ids.add(it.id)
                if self.settings.get("show_progress_dialog", True):
                    self.show_progress(it)
        self.save_items()
        self.refresh_all()
        return it

    def on_browser_add(self, data: dict):
        url = str(data.get("url", "")).strip()
        headers = {}
        if data.get("referrer"):
            headers["Referer"] = str(data["referrer"])
        if data.get("cookies"):
            headers["Cookie"] = str(data["cookies"])
        if data.get("userAgent"):
            headers["User-Agent"] = str(data["userAgent"])
        if url.startswith("magnet:"):
            self.add_torrent_source(url)
            return
        if data.get("quick") and data.get("kind") == "image":
            # images: save at once into the Images folder, no dialogs
            name = safe_filename(os.path.basename(str(data.get("filename") or ""))) if data.get("filename") else ""
            base = self.settings["download_dir"]
            save_dir = os.path.join(base, "Images") if self.settings["category_subfolders"] else base
            it = self.add_item({"url": url, "filename": name or filename_from_url(url), "save_dir": save_dir,
                                "category": "Images", "kind": "http", "headers": headers, "start_now": True,
                                "auto_name": not name, "silent": True, "connections": 1})
            it.category = "Images"
            self.statusBar().showMessage(f"Saving image: {it.filename}", 4000)
            return
        mode = data.get("mode") or "auto"
        if mode not in ("auto", "http", "ytdlp"):
            mode = "auto"
        filename = safe_filename(os.path.basename(str(data.get("filename") or ""))) if data.get("filename") else ""
        quality = data.get("quality") if data.get("quality") in dict(YTDLP_QUALITIES) else None
        title = str(data.get("title") or "")[:120]
        try:
            size_hint = int(data.get("size") or 0)
        except (TypeError, ValueError):
            size_hint = 0
        if data.get("lookup") or (mode == "ytdlp" and self.settings.get("browser_confirm", True)):
            if not HAS_YTDLP:
                self.bring_to_front()
                QMessageBox.warning(self, APP_NAME, "yt-dlp is not installed.\n\nRun:  pip install yt-dlp")
                return
            self.video_page_dialog(url, headers, title, from_browser=True)
            return
        if self.settings.get("browser_confirm", True):
            self.add_url_dialog(url, filename, headers, mode, from_browser=True, size_hint=size_hint,
                                quality=quality, title_hint=title)
        else:
            kind = "ytdlp" if (mode == "ytdlp" or (mode == "auto" and is_video_site(url) and HAS_YTDLP)) else "http"
            name = filename or filename_from_url(url)
            cat = category_for(name, kind)
            base = self.settings["download_dir"]
            save_dir = os.path.join(base, cat) if self.settings["category_subfolders"] else base
            self.add_item({"url": url, "filename": name if kind == "http" else "", "save_dir": save_dir,
                           "category": cat, "kind": kind, "headers": headers, "start_now": True,
                           "auto_name": not filename, "quality": quality, "title_hint": title})
            if self.tray:
                self.tray.showMessage(APP_NAME, f"Started: {name}", app_icon(), 2500)

    def on_batch_add(self, data: dict):
        if not data.get("items"):
            return
        dlg = BatchDialog(self, data)
        self.dialogs.append(dlg)

        def done(_code):
            if dlg in self.dialogs:
                self.dialogs.remove(dlg)
            dlg.deleteLater()
        dlg.finished.connect(done)
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def links_dialog(self, links: list = None, cookies: dict = None, ua: str = "", source: str = ""):
        dlg = LinksDialog(self, links, cookies, ua, source)
        self.dialogs.append(dlg)

        def done(_c):
            if dlg in self.dialogs:
                self.dialogs.remove(dlg)
            dlg.deleteLater()
        dlg.finished.connect(done)
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()
        return dlg

    def on_links_add(self, data: dict):
        links = [str(l.get("url") if isinstance(l, dict) else l) for l in data.get("links", [])]
        links = [l for l in links if l.startswith(("http://", "https://"))]
        if not links:
            return
        src = f"{len(links)} video links collected from: {data.get('title') or data.get('page') or 'the page'}"
        self.links_dialog(links, data.get("cookies") or {}, str(data.get("userAgent") or ""), src)

    def add_links(self, rows: list, folder: str, quality: str, sub: str, sub_auto: bool, embed: bool,
                  start_now: bool, headers_for):
        for r in rows:
            it = DownloadItem(url=r["url"], filename=r["title"][:150], save_dir=folder, kind="ytdlp",
                              category="Music" if quality == "audio" else "Video",
                              headers=headers_for(r["url"]), auto_name=True, quality=quality,
                              title_hint=r["title"], sub_lang=sub, sub_auto=sub_auto, embed_subs=embed)
            it.in_queue, it.status = True, "Queued"
            self.items.append(it)
            _ITEM_REGISTRY[it.id] = it
        self.save_items()
        self.refresh_all(force=True)
        if start_now:
            self.start_queue()
        self.statusBar().showMessage(f"Added {len(rows)} videos" + (" — downloading" if start_now else " to the queue"), 6000)

    def add_batch(self, rows: list, folder: str, data: dict, start_now: bool):
        cookies = data.get("cookies") or {}
        ua = str(data.get("userAgent") or "")
        page = str(data.get("page") or "")
        folder = folder or os.path.join(self.settings["download_dir"], "Grabbed")
        added = 0
        for r in rows:
            url = r["url"]
            origin = "{0.scheme}://{0.netloc}".format(urllib.parse.urlparse(url))
            headers = {"Referer": page}
            if ua:
                headers["User-Agent"] = ua
            if cookies.get(origin):
                headers["Cookie"] = str(cookies[origin])
            stream = r["tag"] in ("hls", "dash") or re.search(r"\.(m3u8|mpd)(\?|$)", url, re.I)
            kind = "ytdlp" if stream and HAS_YTDLP else "http"
            name = unique_name(folder, r["name"]) if kind == "http" else (data.get("title") or "video")
            it = DownloadItem(url=url, filename=name, save_dir=folder, kind=kind,
                              category=category_for(name, kind) if r["type"] != "Images" else "Images",
                              connections=int(self.settings["connections"]), headers=headers, auto_name=True,
                              quality=self.settings["ytdlp_quality"], title_hint=str(data.get("title") or ""))
            it.in_queue, it.status = True, "Queued"
            self.items.append(it)
            _ITEM_REGISTRY[it.id] = it
            added += 1
        self.save_items()
        self.refresh_all(force=True)
        if start_now:
            self.start_queue()
        self.statusBar().showMessage(f"Added {added} files from the page" + (" — downloading" if start_now else " to the queue"), 6000)
        if self.tray:
            self.tray.showMessage(APP_NAME, f"{added} files added", app_icon(), 2500)

    def add_torrent_file(self):
        if not self.require_lt():
            return
        path, _ = QFileDialog.getOpenFileName(self, "Open torrent", str(Path.home()), "Torrent files (*.torrent)")
        if path:
            self.add_torrent_source(path)

    def add_magnet(self):
        if not self.require_lt():
            return
        clip = QGuiApplication.clipboard().text().strip()
        text, ok = QInputDialog.getText(self, "Add magnet link", "Magnet link:",
                                        text=clip if clip.startswith("magnet:") else "")
        if ok and text.strip().startswith("magnet:"):
            self.add_torrent_source(text.strip())

    def require_lt(self) -> bool:
        if HAS_LT:
            return True
        QMessageBox.information(self, APP_NAME, "Torrent support needs libtorrent.\n\nRun:  pip install libtorrent\n"
                                                "then restart Chivet-kh Download.")
        return False

    def add_torrent_source(self, src: str):
        if not self.require_lt():
            return
        name = "Magnet link"
        if src.startswith("magnet:"):
            m = re.search(r"[?&]dn=([^&]+)", src)
            if m:
                name = safe_filename(urllib.parse.unquote_plus(m.group(1)))
        else:
            name = os.path.splitext(os.path.basename(src))[0]
        base = self.settings["download_dir"]
        save_dir = os.path.join(base, "Torrents") if self.settings["category_subfolders"] else base
        self.add_item({"url": src if src.startswith("magnet:") else Path(src).as_uri(), "filename": name,
                       "save_dir": save_dir, "kind": "torrent", "category": "Torrents", "torrent_source": src,
                       "start_now": True})

    # ---------------- running
    def start_item(self, it: DownloadItem):
        if it.id in self.tasks or it.status == "Finished":
            return
        if it.kind == "ytdlp" and not HAS_YTDLP:
            it.status, it.error = "Error", "yt-dlp is not installed (pip install yt-dlp)"
            return
        if it.kind == "torrent" and not HAS_LT:
            it.status, it.error = "Error", "libtorrent is not installed (pip install libtorrent)"
            return
        cls = {"http": HttpTask, "ytdlp": YtdlpTask, "torrent": TorrentTask}.get(it.kind, HttpTask)
        task = cls(it, self.settings, self.throttle, self.bridge)
        self.tasks[it.id] = task
        it.status, it.error, it.speed, it.eta = "Connecting", "", 0, -1
        self.last_bytes.pop(it.id, None)
        task.start()

    def stop_item(self, it: DownloadItem):
        task = self.tasks.get(it.id)
        if task:
            task.stop()

    def on_task_done(self, iid: str, result: str, message: str):
        task = self.tasks.pop(iid, None)
        it = self.find_item(iid)
        if not it:
            return
        it.speed, it.eta = 0, -1
        if result == "finished":
            it.status = "Finished"
            it.finished_at = time.time()
            it.in_queue = False
            it.segments = []
            if it.size <= 0:
                it.size = it.downloaded
            dlg = self.progress_dialogs.pop(it.id, None)
            if dlg:
                dlg.close()
            watched = it.id in self.watch_ids
            self.watch_ids.discard(it.id)
            if watched and self.settings.get("show_complete_dialog", True):
                cd = CompleteDialog(self, it)
                cd.show()
                cd.raise_()
                cd.activateWindow()
            elif self.tray and not self.isActiveWindow():
                self.tray.showMessage("Download complete", it.filename, app_icon(), 3000)
            if it.open_when_done:
                open_path(it.target_path())
            if it.folder_when_done:
                reveal_in_folder(it.target_path())
            if it.shutdown_when_done:
                self.save_items()
                self.shutdown_computer()
        elif result == "stopped":
            it.status = "Queued" if (it.in_queue and getattr(task, "requeue", False)) else "Stopped"
        else:
            it.status = "Error"
            it.error = message
            self.statusBar().showMessage(f"{it.filename}: {message}", 8000)
        dlg = self.progress_dialogs.get(iid)
        if dlg:
            try:
                dlg.refresh()
            except RuntimeError:
                pass
        self.save_items()
        self.process_queue()
        self.refresh_all()

    def process_queue(self):
        if not self.queue_running:
            return
        running_q = [i for i in self.items if i.in_queue and i.id in self.tasks]
        waiting = [i for i in self.items if i.in_queue and i.id not in self.tasks and i.status == "Queued"]
        slots = int(self.settings["max_concurrent"]) - len(running_q)
        for it in waiting[:max(0, slots)]:
            self.start_item(it)
        if not running_q and not waiting:
            self.queue_running = False
            self.on_queue_finished()

    def on_queue_finished(self):
        action = self.settings["scheduler"].get("on_finish", "nothing")
        if self.tray:
            self.tray.showMessage(APP_NAME, "Queue finished", app_icon(), 3000)
        if action == "exit":
            QTimer.singleShot(1500, self.quit_app)
        elif action == "shutdown":
            self.shutdown_computer()

    def shutdown_computer(self):
        if True:  # Windows shows a 60 s warning; "shutdown /a" cancels it
            self.save_items()
            system = platform.system()
            try:
                if system == "Windows":
                    subprocess.Popen(["shutdown", "/s", "/t", "60", "/c", "Chivet-kh Download: downloads finished. Run  shutdown /a  to cancel."])
                elif system == "Darwin":
                    subprocess.Popen(["osascript", "-e", 'tell app "System Events" to shut down'])
                else:
                    subprocess.Popen(["shutdown", "-h", "+1"])
            except Exception as e:
                self.statusBar().showMessage(f"Shutdown failed: {e}", 8000)

    def start_queue(self):
        for it in self.items:
            if it.in_queue and it.status in ("Stopped", "Error") and it.id not in self.tasks:
                it.status = "Queued"
        if not any(it.in_queue and it.status == "Queued" for it in self.items):
            self.statusBar().showMessage("The queue is empty — use “Add to Queue” or right-click → Add to queue", 6000)
            return
        self.queue_running = True
        self.process_queue()
        self.refresh_all()

    def stop_queue(self):
        self.queue_running = False
        for it in self.items:
            if it.in_queue and it.id in self.tasks:
                self.tasks[it.id].requeue = True
                self.stop_item(it)
        self.refresh_all()

    def check_scheduler(self):
        sc = self.settings["scheduler"]
        now = datetime.now()
        if now.weekday() not in sc.get("days", []):
            return
        hm = now.strftime("%H:%M")
        key_day = now.strftime("%Y-%m-%d")
        if sc.get("start_enabled") and hm == sc.get("start_time") and ("start", key_day) not in self.sched_fired:
            self.sched_fired.add(("start", key_day))
            self.start_queue()
        if sc.get("stop_enabled") and hm == sc.get("stop_time") and ("stop", key_day) not in self.sched_fired:
            self.sched_fired.add(("stop", key_day))
            self.stop_queue()

    # ---------------- toolbar actions
    def resume_selected(self):
        sel = [it for it in self.selected_items() if it.status != "Finished"]
        for it in sel:
            self.start_item(it)
            self.watch_ids.add(it.id)
        if len(sel) == 1 and self.settings.get("show_progress_dialog", True):
            self.show_progress(sel[0])
        self.refresh_all()

    def stop_selected(self):
        for it in self.selected_items():
            self.stop_item(it)

    def stop_all(self):
        self.queue_running = False
        for t in list(self.tasks.values()):
            t.stop()

    def delete_selected(self):
        sel = self.selected_items()
        if not sel:
            return
        box = QMessageBox(self)
        box.setWindowTitle("Delete")
        box.setIcon(QMessageBox.Icon.Question)
        box.setText(f"Remove {len(sel)} download(s) from the list?")
        cb = QCheckBox("Also delete the downloaded files from disk")
        box.setCheckBox(cb)
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        if box.exec() != QMessageBox.StandardButton.Yes:
            return
        self.remove_items(sel, cb.isChecked())

    def remove_items(self, items, delete_files: bool):
        for it in items:
            task = self.tasks.pop(it.id, None)
            if task:
                task.stop()
                if task.thread:
                    task.thread.join(timeout=3)
            if it.kind == "http":
                try:
                    if os.path.exists(it.temp_path()):
                        os.remove(it.temp_path())
                except OSError:
                    pass
            if delete_files and it.status == "Finished":
                p = it.target_path()
                try:
                    if os.path.isdir(p):
                        shutil.rmtree(p)
                    elif os.path.exists(p):
                        os.remove(p)
                except OSError as e:
                    self.statusBar().showMessage(f"Could not delete {p}: {e}", 6000)
            if it in self.items:
                self.items.remove(it)
            _ITEM_REGISTRY.pop(it.id, None)
        self.save_items()
        self.refresh_all(force=True)

    def delete_completed(self):
        done = [it for it in self.items if it.status == "Finished"]
        if done and QMessageBox.question(self, "Delete Completed",
                                         f"Remove {len(done)} finished download(s) from the list?\n"
                                         "(Files stay on your disk.)") == QMessageBox.StandardButton.Yes:
            self.remove_items(done, False)

    def open_selected(self):
        sel = self.selected_items()
        if sel:
            open_path(sel[0].target_path())

    def open_selected_folder(self):
        sel = self.selected_items()
        if sel:
            it = sel[0]
            p = it.target_path() if it.status == "Finished" else it.save_dir
            reveal_in_folder(p)

    def copy_selected_url(self):
        QGuiApplication.clipboard().setText("\n".join(it.url for it in self.selected_items()))

    def redownload_selected(self):
        for it in self.selected_items():
            if it.id in self.tasks:
                continue
            if it.kind == "http":
                try:
                    if os.path.exists(it.temp_path()):
                        os.remove(it.temp_path())
                except OSError:
                    pass
                if it.status == "Finished":
                    it.filename = unique_name(it.save_dir, it.filename, exclude_id=it.id)
            it.segments, it.downloaded, it.size, it.status = [], 0, -1, "Stopped"
            self.start_item(it)
        self.refresh_all()

    def toggle_queue_selected(self):
        for it in self.selected_items():
            if it.status == "Finished":
                continue
            it.in_queue = not it.in_queue
            if it.in_queue and it.id not in self.tasks:
                it.status = "Queued"
            elif not it.in_queue and it.status == "Queued":
                it.status = "Stopped"
        self.save_items()
        self.refresh_all()

    def on_double_click(self, index):
        it = self.model.item_at(index.row())
        if not it:
            return
        if it.status == "Finished":
            open_path(it.target_path())
        else:
            self.show_progress(it)

    def show_context_menu(self, pos):
        if not self.selected_items():
            return
        m = QMenu(self)
        for a in (self.a_open, self.a_folder, None, self.a_resume, self.a_stop, self.a_redl, None,
                  self.a_toqueue, self.a_copy, None, self.a_delete):
            m.addSeparator() if a is None else m.addAction(a)
        it = self.selected_items()[0]
        if it.error:
            m.addSeparator()
            err = QAction(icon("info", C_RED), "Error: " + it.error[:80], self)
            err.setEnabled(False)
            m.addAction(err)
        m.exec(self.table.viewport().mapToGlobal(pos))

    def show_options(self):
        old_port = self.settings["port"]
        dlg = OptionsDialog(self, self.settings)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.throttle.rate = self.settings["speed_limit_kb"] * 1024
            if self.settings["port"] != old_port or not self.server_ok:
                self.server_ok = self.server.start(self.settings["port"])
                self.update_api_label()
            self.save_settings()

    def show_scheduler(self):
        if SchedulerDialog(self, self.settings).exec() == QDialog.DialogCode.Accepted:
            self.save_settings()

    def show_extension(self):
        ExtensionDialog(self, self.settings["port"], self.server_ok).exec()

    def show_about(self):
        QMessageBox.about(self, "About", f"<h3>{APP_NAME} {VERSION}</h3>"
                          "<p>Multi-connection downloads, video sites (yt-dlp), torrents (libtorrent), queue, "
                          "scheduler and browser integration.</p>")

    # ---------------- drag & drop
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls() or e.mimeData().hasText():
            e.acceptProposedAction()

    def dropEvent(self, e):
        md = e.mimeData()
        urls = []
        if md.hasUrls():
            for u in md.urls():
                if u.isLocalFile() and u.toLocalFile().lower().endswith(".torrent"):
                    self.add_torrent_source(u.toLocalFile())
                elif u.scheme() in ("http", "https", "magnet"):
                    urls.append(u.toString())
        elif md.hasText():
            urls = [t for t in md.text().split() if looks_like_url(t)]
        for u in urls[:20]:
            if u.startswith("magnet:"):
                self.add_torrent_source(u)
            else:
                self.add_url_dialog(u)

    # ---------------- persistence / window
    def save_items(self):
        self.last_save = time.time()
        try:
            save_json(DOWNLOADS_FILE, [it.to_dict() for it in self.items])
        except Exception as e:
            self.statusBar().showMessage(f"Could not save the download list: {e}", 6000)

    def save_settings(self):
        try:
            save_json(SETTINGS_FILE, self.settings)
        except Exception as e:
            self.statusBar().showMessage(f"Could not save settings: {e}", 6000)

    def bring_to_front(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, e):
        if not self.quitting and self.tray and self.settings.get("close_to_tray", True):
            e.ignore()
            self.hide()
            if not self.tray_hint_shown:
                self.tray_hint_shown = True
                self.tray.showMessage(APP_NAME, "Still running in the tray so the browser can send downloads.",
                                      app_icon(), 3000)
            return
        self.shutdown()
        e.accept()
        QApplication.instance().quit()

    def quit_app(self):
        self.quitting = True
        self.shutdown()
        QApplication.instance().quit()

    def shutdown(self):
        if getattr(self, "_shut", False):
            return
        self._shut = True
        for t in list(self.tasks.values()):
            t.stop()
        deadline = time.time() + 4
        for t in list(self.tasks.values()):
            if t.thread:
                t.thread.join(timeout=max(0.1, deadline - time.time()))
        for it in self.items:
            if it.id in self.tasks:
                it.status = "Queued" if it.in_queue else "Stopped"
        self.tasks.clear()
        self.save_items()
        self.save_settings()
        self.server.stop()
        if self.tray:
            self.tray.hide()


def main():
    settings = load_settings()
    if another_instance_running(settings.get("port", DEFAULT_PORT)):
        return
    if hasattr(Qt.HighDpiScaleFactorRoundingPolicy, "PassThrough"):
        QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication([a for a in sys.argv if not a.lower().startswith(PROTOCOL + ":")])
    app.setApplicationName(APP_NAME)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    app.setWindowIcon(app_icon())
    app.setQuitOnLastWindowClosed(False)
    register_protocol()
    set_autostart(settings.get("autostart", True))
    w = MainWindow()
    if started_in_background() and w.tray:
        w.hide()
    else:
        w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
