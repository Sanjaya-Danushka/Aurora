#!/usr/bin/env python3
import sys
import os
import subprocess
import json
import re
import shutil
import tempfile
import importlib.util
import traceback
from threading import Thread, Event
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLineEdit, QTableWidget, QTableWidgetItem, QTextEdit,
                             QLabel, QFileDialog, QMessageBox, QHeaderView, QFrame, QSplitter,
                             QScrollArea, QCheckBox, QListWidget, QListWidgetItem, QSizePolicy,
                             QDialog, QTabWidget, QGroupBox, QGridLayout, QRadioButton, QSpinBox)
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QThread, QSize, QTimer, QRectF, QItemSelectionModel, qInstallMessageHandler, QtMsgType
from PyQt6.QtGui import QColor, QFont, QIcon, QPixmap, QPainter
from PyQt6.QtSvg import QSvgRenderer
from collections import Counter

from git_manager import GitManager

from styles import Styles
from components import (SourceCard, FilterCard, LargeSearchBox, LoadingSpinner, PluginsView, PluginsSidebar,
                       GeneralSettingsWidget, AutoUpdateSettingsWidget, PluginsSettingsWidget)
from plugin_manager import PluginsManager
from workers import CommandWorker, PackageLoaderWorker
import config_utils
import sys_utils
import snapshot_service
import update_service
import uninstall_service
import ignore_service
import bundle_service
import askpass_service
import settings_service
import filters_service
import install_service
import packages_service

def _qt_msg_handler(mode, context, message):
    s = str(message)
    if "QPainter::" in s:
        return
    if mode in (QtMsgType.QtDebugMsg, QtMsgType.QtInfoMsg):
        return
    try:
        sys.stderr.write(s + "\n")
    except Exception:
        pass

qInstallMessageHandler(_qt_msg_handler)

app = QApplication(sys.argv)

class ArchPkgManagerUniGetUI(QMainWindow):
    packages_ready = pyqtSignal(list)
    discover_results_ready = pyqtSignal(list)
    show_message = pyqtSignal(str, str)
    log_signal = pyqtSignal(str)
    load_error = pyqtSignal()
    search_timer = QTimer()
    installation_progress = pyqtSignal(str, bool)  # status, can_cancel
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NeoArch - Package Manager")
        self.setGeometry(100, 100, 1600, 900)  # Increased width to accommodate sidebar
        self.setMinimumSize(1200, 800)  # Set minimum size
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet(Styles.get_dark_stylesheet())
        # self.set_minimal_icon()
        
        self.current_view = "discover"
        self.updating = False
        self.all_packages = []
        self.search_results = []
        self.packages_per_page = 10
        self.current_page = 0
        self.loader_thread = None
        self.git_manager = None  # Will be initialized when sources layout is ready
        self.docker_manager = None  # Docker manager instance
        self.current_search_mode = 'both'
        self.filtered_results = []
        # Working bundle state (list of {name,id,source,version?})
        self.bundle_items = []
        # Settings state
        self.settings = self.load_settings()
        # Plugins runtime
        self.plugins = []
        self.plugin_timer = QTimer()
        self.plugin_timer.setInterval(60000)
        self.plugin_timer.timeout.connect(self.run_plugin_tick)
        self._icon_cache = {}
        self._source_icon_cache = {}
        self._flathub_checked = False
        self.plugins_manager = PluginsManager(self)
        self.packages_ready.connect(self.on_packages_loaded)
        self.discover_results_ready.connect(self.display_discover_results)
        self.show_message.connect(self._show_message)
        self.log_signal.connect(self.log)
        self.load_error.connect(self.on_load_error)
        self.installation_progress.connect(self.on_installation_progress)
        # Background loading coordination
        self.loading_context = None
        self.cancel_update_load = False
        self.cancel_discover_search = False
        # Nav badges (e.g., updates count)
        self.nav_badges = {}
        self.setup_ui()
        # Set initial nav button state
        for btn_id, btn in self.nav_buttons.items():
            btn.setChecked(btn_id == self.current_view)
        self.center_window()
        
        # Initialize the default view
        self.switch_view(self.current_view)
        
        # Show welcome animation in console on first launch
        QTimer.singleShot(500, self.show_welcome_animation)
        # Initialize plugins shortly after UI is ready
        QTimer.singleShot(1000, self.initialize_plugins)
        
        # Debounce search input
        self.search_timer.setInterval(800)
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.perform_search)
        self.search_input.textChanged.connect(self.on_search_text_changed)
        QTimer.singleShot(1500, self.run_first_run_checks)

    def on_large_search_requested(self, query):
        """Handle search request from large search box"""
        self.search_input.setText(query)
        self.perform_search()

    def on_search_text_changed(self):
        self.search_timer.start()

    def perform_search(self):
        query = self.search_input.text().strip()
        if len(query) < 3:
            if self.current_view == "discover":
                self.large_search_box.setVisible(True)
                self.package_table.setVisible(False)
                self.load_more_btn.setVisible(False)
            self.package_table.setRowCount(0)
            self.header_info.setText("Search and discover new packages to install")
            # Removed verbose log message: "Type a package name to search in AUR and official repositories"
            return
        if self.current_view == "discover":
            self.large_search_box.setVisible(False)
            self.package_table.setVisible(True)
            self.search_discover_packages(query)
        else:
            self.filter_packages()

    def set_minimal_icon(self):
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        with QPainter(pixmap) as painter:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            painter.setBrush(QColor(0, 212, 255))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(4, 4, 56, 56)
            
            font = QFont("Segoe UI", 32, QFont.Weight.Bold)
            painter.setFont(font)
            painter.setPen(QColor(26, 26, 26))
            painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "A")
        
        icon = QIcon(pixmap)
        self.setWindowIcon(icon)
    
    def center_window(self):
        screen = QApplication.primaryScreen()
        screen_geometry = screen.geometry()
        x = (screen_geometry.width() - self.width()) // 2
        y = (screen_geometry.height() - self.height()) // 2
        self.move(x, y)
    
    def setup_ui(self):
        central_widget = QWidget()
        central_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Left Sidebar
        sidebar = self.create_sidebar()
        main_layout.addWidget(sidebar)
        
        # Main Content Area
        content = self.create_content_area()
        main_layout.addWidget(content, 1)
        
        # Ensure proper sizing
        self.adjustSize()
    
    def create_sidebar(self):
        sidebar = QWidget()
        sidebar.setFixedWidth(180)  # Further reduced from 200
        sidebar.setMinimumHeight(650)
        sidebar.setObjectName("sidebar")
        
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(15, 20, 15, 0)
        layout.setSpacing(20)  # Increased spacing between cards
        
        # Header
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(5, 5, 5, 5)  # Add some padding
        header_layout.setSpacing(10)  # Increase spacing
        
        # Logo on the left - smaller to fit better
        logo_label = QLabel()
        logo_path = os.path.join(os.path.dirname(__file__), "assets", "icons", "discover", "logo1.png")
        try:
            pixmap = QPixmap(logo_path)
            if not pixmap.isNull():
                # Scale logo to fit nicely in sidebar (45px wide for better fit)
                scaled_pixmap = pixmap.scaledToWidth(45, Qt.TransformationMode.SmoothTransformation)
                logo_label.setPixmap(scaled_pixmap)
            else:
                logo_label.setText("🖥️")
                logo_label.setStyleSheet("font-size: 28px; color: white;")
        except:
            logo_label.setText("🖥️")
            logo_label.setStyleSheet("font-size: 28px; color: white;")
        
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_label.setFixedWidth(45)  # Smaller for more text space
        header_layout.addWidget(logo_label)
        
        # Text container on the right - expanded to take remaining space
        text_widget = QWidget()
        text_layout = QVBoxLayout(text_widget)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(0)  # Tight spacing
        
        # Title - ensure it's visible with proper contrast
        title_label = QLabel("NeoArch")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: white; background: transparent;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        text_layout.addWidget(title_label)
        
        # Subtitle - line by line
        subtitle_label = QLabel("Elevate Your\nArch Experience")
        subtitle_label.setStyleSheet("font-size: 10px; color: rgba(255, 255, 255, 0.9); background: transparent; line-height: 1.1;")
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        subtitle_label.setWordWrap(True)  # Allow wrapping for multi-line text
        text_layout.addWidget(subtitle_label)
        
        header_layout.addWidget(text_widget, 1)  # Give it stretch factor of 1 to take remaining space
        
        layout.addWidget(header_widget)
        
        # Spacer
        layout.addSpacing(15)  # Adjusted spacing for horizontal header
        
        # Navigation buttons with icons
        nav_items = [
            (os.path.join(os.path.dirname(__file__), "assets", "icons", "discover.svg"), "Discover", "discover"),
            (os.path.join(os.path.dirname(__file__), "assets", "icons", "updates.svg"), "Updates", "updates"), 
            (os.path.join(os.path.dirname(__file__), "assets", "icons", "installed.svg"), "Installed", "installed"),
            (os.path.join(os.path.dirname(__file__), "assets", "icons", "plugins", "plugins.svg"), "Plugins", "plugins"),
            (os.path.join(os.path.dirname(__file__), "assets", "icons", "local-builds.svg"), "Bundles", "bundles")
        ]
        
        self.nav_buttons = {}
        
        for icon_path, text, view_id in nav_items:
            btn = self.create_nav_button(icon_path, text, view_id)
            self.nav_buttons[view_id] = btn
            layout.addWidget(btn)
        
        layout.addStretch()
        
        # Bottom section with card-style buttons
        bottom_layout = QVBoxLayout()
        bottom_layout.setContentsMargins(0, 0, 0, 20)
        bottom_layout.setSpacing(12)  # Consistent spacing
        
        # Settings button - card style
        settings_btn = self.create_bottom_card_button(os.path.join(os.path.dirname(__file__), "assets", "icons", "settings.svg"), "Settings", self.show_settings)
        bottom_layout.addWidget(settings_btn)
        
        # About button - card style
        about_btn = self.create_bottom_card_button(os.path.join(os.path.dirname(__file__), "assets", "icons", "about.svg"), "About", self.show_about)
        bottom_layout.addWidget(about_btn)
        
        layout.addLayout(bottom_layout)
        
        return sidebar
    
    def create_nav_button(self, icon_path, text, view_id):
        btn = QPushButton()
        btn.setObjectName("navBtn")
        btn.setProperty("view_id", view_id)
        btn.setCheckable(True)
        
        # Create vertical layout for icon + text
        layout = QVBoxLayout(btn)
        layout.setContentsMargins(12, 16, 12, 16)  # Balanced padding
        layout.setSpacing(6)  # Space between icon and text
        
        # Icon container to support badge overlay
        icon_container = QWidget()
        icon_container.setFixedSize(50, 50)
        icon_container.setObjectName("navIconContainer")
        try:
            icon_container.setStyleSheet("background-color: transparent;")
        except Exception:
            pass


        # Absolute children in container
        icon_label = QLabel(icon_container)
        icon_label.setObjectName("navIcon")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setGeometry(0, 0, 50, 50)

        # Try to load and render SVG in white
        pixmap = self.get_svg_icon(icon_path, 50).pixmap(50, 50)
        if pixmap and not pixmap.isNull():
            icon_label.setPixmap(pixmap)
        else:
            # Fallback to black icon or emoji
            icon = QIcon(icon_path)
            if not icon.isNull():
                icon_label.setPixmap(icon.pixmap(50, 50))
            else:
                emoji = self.get_fallback_icon(icon_path)
                icon_label.setText(emoji)

        # Small badge for Updates
        if view_id == "updates":
            try:
                badge = QLabel("", icon_container)
                badge.setObjectName("navBadge")
                badge.setFixedSize(18, 18)
                badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
                badge.setStyleSheet(
                    """
                    QLabel#navBadge {
                        background-color: #E53935;
                        color: white;
                        border-radius: 9px;
                        font-size: 10px;
                        font-weight: 700;
                    }
                    """
                )
                # Position top-right over the icon (container is 50x50, badge 18x18)
                badge.move(32, 0)
                badge.setVisible(False)
                self.nav_badges[view_id] = badge
            except Exception:
                pass

        layout.addWidget(icon_container, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Text label - below icon
        text_label = QLabel(text)
        text_label.setObjectName("navText")
        text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)  # Center align text
        layout.addWidget(text_label, alignment=Qt.AlignmentFlag.AlignCenter)
        
        layout.addStretch()
        
        btn.clicked.connect(lambda checked, v=view_id: self.switch_view(v))
        
        return btn

    def set_updates_count(self, count):
        """Update the updates count in nav and header."""
        # Update badge on nav button
        badge = self.nav_badges.get("updates")
        if badge is not None:
            try:
                n = int(count) if count is not None else 0
                if n > 0:
                    text = str(n)
                    badge.setText(text)
                    # Dynamically size the badge to fit the text
                    fm = badge.fontMetrics()
                    w = max(18, fm.horizontalAdvance(text) + 8)
                    badge.setFixedSize(w, 18)
                    # Anchor to top-right of icon container
                    parent = badge.parentWidget()
                    if parent is not None:
                        badge.move(max(0, parent.width() - badge.width()), 0)
                    badge.setVisible(True)
                else:
                    badge.setVisible(False)
            except Exception:
                pass
        # Optionally reflect in label text
        btn = self.nav_buttons.get("updates") if hasattr(self, 'nav_buttons') else None
        if btn:
            label = btn.findChild(QLabel, "navText")
            if label:
                try:
                    n = int(count) if count is not None else 0
                    label.setText(f"Updates{f' ({n})' if n > 0 else ''}")
                except Exception:
                    label.setText("Updates")

    def update_updates_header_counts(self):
        """Update the header info subtitle for Updates with real counts."""
        if self.current_view != "updates":
            return
        total = len(getattr(self, 'updates_all', []) or [])
        matched = len(self.all_packages or [])
        try:
            self.header_info.setText(f"{total} packages were found, {matched} of which match the specified filters")
        except Exception:
            pass
    
    def create_bottom_card_button(self, icon_path, text, callback):
        btn = QPushButton()
        btn.setObjectName("bottomCardBtn")
        
        # Create horizontal layout for icon + text
        layout = QHBoxLayout(btn)
        layout.setContentsMargins(12, 16, 12, 16)  # Balanced padding
        layout.setSpacing(8)  # Space between icon and text
        
        # Icon label - smaller for bottom cards
        icon_label = QLabel()
        icon_label.setObjectName("bottomCardIcon")
        icon_label.setFixedSize(28, 28)  # Smaller than main nav
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Try to load and render SVG in white
        pixmap = self.get_svg_icon(icon_path, 28).pixmap(28, 28)
        if pixmap and not pixmap.isNull():
            icon_label.setPixmap(pixmap)
        else:
            # Fallback to black icon or emoji
            icon = QIcon(icon_path)
            if not icon.isNull():
                icon_label.setPixmap(icon.pixmap(28, 28))
            else:
                emoji = "⚙️" if "settings" in icon_path else "ℹ️"
                icon_label.setText(emoji)
        
        layout.addWidget(icon_label, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Text label - right of icon
        text_label = QLabel(text)
        text_label.setObjectName("bottomCardText")
        text_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)  # Left align text, vertically centered
        layout.addWidget(text_label, alignment=Qt.AlignmentFlag.AlignLeft)
        
        layout.addStretch()
        
        btn.clicked.connect(callback)
        
        return btn
    
    def get_fallback_icon(self, icon_path):
        # Return emoji based on icon path
        if "discover" in icon_path:
            return "🔍"
        elif "updates" in icon_path:
            return "⬆️"
        elif "installed" in icon_path:
            return "📦"
        elif "local" in icon_path or "bundles" in icon_path:
            return "🎁"
        elif "settings" in icon_path:
            return "⚙️"
        elif "docker" in icon_path.lower():
            return "🐳"
        else:
            return "📦"
    
    def get_source_icon(self, source, size=18):
        icon_dir = os.path.join(os.path.dirname(__file__), "assets", "icons", "discover")
        mapping = {
            "pacman": "pacman.svg",
            "AUR": "aur.svg",
            "Flatpak": "flatpack.svg",
            "npm": "node.svg",
        }
        filename = mapping.get(source, "packagename.svg")
        icon_path = os.path.join(icon_dir, filename)
        try:
            cache = getattr(self, "_source_icon_cache", None)
            if isinstance(cache, dict):
                key = (source, int(size))
                cached = cache.get(key)
                if cached is not None and not cached.isNull():
                    return cached
        except Exception:
            pass

        try:
            pixmap = QPixmap(size, size)
            if pixmap.isNull() or not pixmap.size().isValid():
                return QIcon()

            pixmap.fill(Qt.GlobalColor.transparent)

            painter = QPainter(pixmap)
            if not painter.isActive():
                return QIcon()

            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

            renderer = QSvgRenderer(icon_path)
            if renderer.isValid():
                renderer.render(painter, QRectF(pixmap.rect()))
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                painter.fillRect(pixmap.rect(), QColor("white"))
                painter.end()
                icon = QIcon(pixmap)
            else:
                # Fallback: try to load as regular icon
                painter.end()
                icon = QIcon(icon_path)

            try:
                if isinstance(getattr(self, "_source_icon_cache", None), dict):
                    self._source_icon_cache[(source, int(size))] = icon
            except Exception:
                pass
            return icon
        except Exception:
            return QIcon()
    
    def ensure_flathub_user_remote(self):
        try:
            result = subprocess.run([
                "flatpak", "--user", "remotes"
            ], capture_output=True, text=True, timeout=10)
            if result.returncode != 0 or "flathub" not in (result.stdout or ""):
                subprocess.run([
                    "flatpak", "--user", "remote-add", "--if-not-exists",
                    "flathub", "https://flathub.org/repo/flathub.flatpakrepo"
                ], capture_output=True, text=True, timeout=30)
        except Exception:
            pass
        try:
            self._flathub_checked = True
        except Exception:
            pass
    
    def get_ignore_file_path(self):
        return config_utils.get_ignore_file_path()

    def load_ignored_updates(self):
        return config_utils.load_ignored_updates()

    def save_ignored_updates(self, items):
        return config_utils.save_ignored_updates(items)

    def get_local_updates_file_path(self):
        return config_utils.get_local_updates_file_path()

    def load_local_update_entries(self):
        return config_utils.load_local_update_entries()

    def cmd_exists(self, cmd):
        return sys_utils.cmd_exists(cmd)

    def get_missing_dependencies(self):
        return sys_utils.get_missing_dependencies()

    def run_first_run_checks(self):
        missing = self.get_missing_dependencies()
        if not missing:
            return
        text = "The following dependencies are missing and are required for best experience:\n\n" + "\n".join(f"• {m}" for m in missing) + "\n\nInstall now?"
        reply = QMessageBox.question(self, "Setup Environment", text, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes)
        if reply == QMessageBox.StandardButton.Yes:
            Thread(target=lambda: self.install_dependencies(missing), daemon=True).start()

    def install_dependencies(self, missing):
        try:
            pacman_pkgs = [p for p in missing if p != "yay"]
            if pacman_pkgs:
                cmd = ["pacman", "-S", "--needed", "--noconfirm"] + pacman_pkgs
                worker = CommandWorker(cmd, sudo=True)
                worker.output.connect(self.log)
                worker.error.connect(self.log)
                done_event = Event()
                worker.finished.connect(lambda: done_event.set())
                worker.run()
                done_event.wait(timeout=1)
            if "yay" in missing and self.cmd_exists("git"):
                self.install_yay_helper()
            self.show_message.emit("Environment", "Dependency setup completed")
        except Exception as e:
            self.show_message.emit("Environment", f"Setup failed: {str(e)}")

    def install_yay_helper(self):
        tmpdir = tempfile.mkdtemp(prefix="neoarch-yay-")
        try:
            clone = subprocess.run(["git", "clone", "https://aur.archlinux.org/yay-bin.git", tmpdir], capture_output=True, text=True, timeout=120)
            if clone.returncode != 0:
                self.log(f"Error: {clone.stderr}")
                return
            env, cleanup = self.prepare_askpass_env()
            cmd = f"cd '{tmpdir}' && makepkg -si --noconfirm"
            process = subprocess.Popen(["bash", "-lc", cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
            while True:
                line = process.stdout.readline() if process.stdout else ""
                if not line and process.poll() is not None:
                    break
                if line:
                    self.log(line.strip())
            _, stderr = process.communicate()
            if process.returncode != 0 and stderr:
                self.log(f"Error: {stderr}")
        finally:
            try:
                shutil.rmtree(tmpdir, ignore_errors=True)
            except Exception:
                pass

    def update_core_tools(self):
        return update_service.update_core_tools(self)
    
    def get_sudo_askpass(self):
        return askpass_service.get_sudo_askpass()

    def prepare_askpass_env(self):
        return askpass_service.prepare_askpass_env()

    def get_source_accent(self, source):
        m = {
            "pacman": "#4FC3F7",
            "AUR": "#FF8A65",
            "Flatpak": "#26A69A",
            "npm": "#E53935",
        }
        return m.get(source, "#00BFAE")

    def apply_checkbox_accent(self, checkbox, source):
        hex_color = self.get_source_accent(source)
        c = QColor(hex_color)
        r, g, b = c.red(), c.green(), c.blue()
        checkbox.setStyleSheet(
            f"""
            QCheckBox#tableCheckbox {{
                color: #F0F0F0;
                font-size: 13px;
                font-weight: 500;
                spacing: 8px;
            }}
            QCheckBox#tableCheckbox::indicator {{
                width: 20px;
                height: 20px;
                border-radius: 10px;
                border: 2px solid rgba({r}, {g}, {b}, 0.4);
                background-color: transparent;
            }}
            QCheckBox#tableCheckbox::indicator:checked {{
                background-color: {hex_color};
                border: 2px solid {hex_color};
            }}
            QCheckBox#tableCheckbox::indicator:hover {{
                border-color: rgba({r}, {g}, {b}, 0.8);
            }}
            """
        )

    def get_svg_icon(self, icon_path, size=18):
        try:
            cache = getattr(self, "_icon_cache", None)
            if isinstance(cache, dict):
                key = (os.path.abspath(icon_path), int(size))
                cached = cache.get(key)
                if cached is not None and not cached.isNull():
                    return cached
        except Exception:
            pass

        try:
            pixmap = QPixmap(size, size)
            if pixmap.isNull() or not pixmap.size().isValid():
                return QIcon()

            pixmap.fill(Qt.GlobalColor.transparent)

            painter = QPainter(pixmap)
            if not painter.isActive():
                return QIcon()

            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

            renderer = QSvgRenderer(icon_path)
            if renderer.isValid():
                renderer.render(painter, QRectF(pixmap.rect()))
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                painter.fillRect(pixmap.rect(), QColor("white"))
                painter.end()
                icon = QIcon(pixmap)
            else:
                # Fallback: try to load as regular icon
                painter.end()
                icon = QIcon(icon_path)

            try:
                if isinstance(getattr(self, "_icon_cache", None), dict):
                    self._icon_cache[(os.path.abspath(icon_path), int(size))] = icon
            except Exception:
                pass
            return icon
        except Exception:
            return QIcon()
    
    def create_toolbar_button(self, icon_path, tooltip, callback, icon_size=24):
        """Create a reusable toolbar button with icon and tooltip"""
        btn = QPushButton()
        btn.setFixedSize(40, 40)  # Slightly smaller for better fit
        btn.setToolTip(tooltip)
        btn.clicked.connect(callback)
        btn.setStyleSheet("""
            QPushButton {
                padding: 6px;
                margin: 2px;
                border: none;
                border-radius: 6px;
                background-color: transparent;
            }
            QPushButton:hover {
                background-color: rgba(0, 191, 174, 0.15);
                border-radius: 6px;
            }
            QPushButton:pressed {
                background-color: rgba(0, 191, 174, 0.25);
            }
        """)
        
        # Try to load SVG icon, fallback to emoji
        icon = self.get_svg_icon(icon_path, icon_size)
        if not icon.isNull():
            btn.setIcon(icon)
            btn.setIconSize(QSize(icon_size, icon_size))
        else:
            # Fallback to emoji based on icon path
            emoji = self.get_fallback_icon(icon_path)
            if "help" in icon_path.lower():
                emoji = "❓"
            elif "add" in icon_path.lower() or "sudo" in icon_path.lower():
                emoji = "➕"
            btn.setText(emoji)
        
        return btn
    
    def get_row_checkbox(self, row):
        cell = self.package_table.cellWidget(row, 0)
        if not cell:
            return None
        if isinstance(cell, QCheckBox):
            return cell
        try:
            chks = cell.findChildren(QCheckBox)
            return chks[0] if chks else None
        except Exception:
            return None

    def create_content_area(self):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header
        header = self.create_header()
        layout.addWidget(header)
        
        # Main Content (Splitter)
        splitter = QSplitter()
        splitter.setOrientation(Qt.Orientation.Horizontal)
        
        # Left panel: Filters/Sources
        left_panel = self.create_filters_panel()
        splitter.addWidget(left_panel)
        
        # Right panel: Packages table + Console
        right_panel = self.create_packages_panel()
        splitter.addWidget(right_panel)
        
        splitter.setCollapsible(0, True)
        splitter.setCollapsible(1, False)
        splitter.setSizes([200, 950])
        
        layout.addWidget(splitter, 1)
        
        return content
    
    def create_header(self):
        header = QFrame()
        header.setStyleSheet(Styles.get_header_stylesheet())
        header.setFixedHeight(70)
        
        layout = QHBoxLayout(header)
        layout.setContentsMargins(20, 0, 20, 0)
        
        # Icon label (hidden by default)
        self.header_icon = QLabel()
        self.header_icon.setVisible(False)
        layout.addWidget(self.header_icon)
        
        self.header_label = QLabel("🔄 Software Updates")
        self.header_label.setObjectName("headerLabel")
        layout.addWidget(self.header_label)
        
        self.header_info = QLabel("24 packages were found, 24 of which match the specified filters")
        self.header_info.setStyleSheet("color: #a0a0a0; font-size: 12px;")
        layout.addWidget(self.header_info)
        
        layout.addStretch()
        
        search_input = QLineEdit()
        search_input.setPlaceholderText("Search for packages")
        search_input.setFixedWidth(250)
        search_input.setFixedHeight(36)
        self.search_input = search_input
        layout.addWidget(search_input)
        
        refresh_btn = QPushButton()
        refresh_btn.setFixedSize(36, 36)
        icon_dir = os.path.join(os.path.dirname(__file__), "assets", "icons", "discover")
        
        refresh_btn.setIcon(self.get_svg_icon(os.path.join(icon_dir, "refresh.svg"), 20))
        refresh_btn.setToolTip("Refresh")
        refresh_btn.clicked.connect(self.refresh_packages)
        layout.addWidget(refresh_btn)
        
        return header
    
    def show_docker_install_dialog(self):
        """Show Docker container management dialog"""
        if not self.docker_manager:
            from docker_manager import DockerManager
            self.docker_manager = DockerManager(self.log_signal, self.show_message, self.sources_layout, self)
        
        self.docker_manager.install_from_docker()
    
    def on_plugin_install_requested(self, plugin_id):
        try:
            if hasattr(self, 'plugins_view') and self.plugins_view:
                self.plugins_manager.install_by_id(self.plugins_view, plugin_id)
        except Exception as e:
            self._show_message("Plugins", f"Install error: {e}")
    
    def on_plugin_launch_requested(self, plugin_id):
        try:
            if hasattr(self, 'plugins_view') and self.plugins_view:
                self.plugins_manager.launch_by_id(self.plugins_view, plugin_id)
        except Exception as e:
            self._show_message("Plugins", f"Launch error: {e}")
    
    def on_plugin_uninstall_requested(self, plugin_id):
        try:
            if hasattr(self, 'plugins_view') and self.plugins_view:
                self.plugins_manager.uninstall_by_id(self.plugins_view, plugin_id)
        except Exception as e:
            self._show_message("Plugins", f"Uninstall error: {e}")
    
    def open_plugins_folder(self):
        try:
            folder = self.get_user_plugins_dir()
            try:
                os.makedirs(folder, exist_ok=True)
            except Exception:
                pass
            subprocess.Popen(["xdg-open", folder], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            self._show_message("Plugins", f"Cannot open folder: {e}")
    
    def show_git_install_dialog(self):
        """Show Git repository installation dialog"""
        if not self.git_manager:
            from git_manager import GitManager
            self.git_manager = GitManager(self.log_signal, self.show_message, self.sources_layout, self)
        
        self.git_manager.install_from_git()
    
    def show_help(self):
        """Show help dialog"""
        QMessageBox.information(self, "Help - NeoArch", 
                              "NeoArch Package Manager Help\n\n"
                              "• Discover: Search and install packages from pacman, AUR, and Flatpak\n"
                              "• Updates: View and update available package updates\n"
                              "• Installed: View all installed packages\n"
                              "• Bundles: Manage package bundles\n\n"
                              "For more information, visit the project documentation.")
    
    def go_to_bundles(self):
        """Switch to bundles view"""
        self.switch_view("bundles")
    
    def show_settings(self):
        self.switch_view("settings")

    def on_plugins_filter_changed(self, text, installed_only):
        try:
            if hasattr(self, 'plugins_view') and self.plugins_view:
                cats = []
                try:
                    if hasattr(self, 'plugins_sidebar') and self.plugins_sidebar:
                        cats = self.plugins_sidebar.get_selected_categories()
                except Exception:
                    cats = []
                self.plugins_view.set_filter(text, installed_only, cats)
        except Exception:
            pass
    
    def sudo_install_selected(self):
        """Install selected packages with sudo privileges"""
        selected_rows = []
        for row in range(self.package_table.rowCount()):
            checkbox = self.get_row_checkbox(row)
            if checkbox is not None and checkbox.isChecked():
                selected_rows.append(row)
        
        if not selected_rows:
            QMessageBox.information(self, "No Selection", "Please select packages to install.")
            return
        
        # Get package names
        packages_to_install = []
        for row in selected_rows:
            package_name = self.package_table.item(row, 1).text()
            packages_to_install.append(package_name)
        
        # Show confirmation dialog
        package_list = "\n".join(f"• {pkg}" for pkg in packages_to_install)
        reply = QMessageBox.question(
            self, "Install Packages with Sudo",
            f"This will install the following packages with elevated privileges:\n\n{package_list}\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.log(f"Installing packages with sudo: {', '.join(packages_to_install)}")
            # Note: Actual sudo installation would require additional implementation
            QMessageBox.information(self, "Sudo Install", "Sudo installation feature is under development.")
    
    def create_filters_panel(self):
        panel = QFrame()
        panel.setStyleSheet(Styles.get_filters_panel_stylesheet())
        
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        
        self.sources_section = QWidget()
        self.sources_layout = QVBoxLayout(self.sources_section)
        self.sources_layout.setContentsMargins(0, 0, 0, 0)
        self.sources_layout.setSpacing(8)
        
        self.sources_title_label = QLabel("Sources")
        self.sources_title_label.setObjectName("sectionLabel")
        self.sources_layout.addWidget(self.sources_title_label)
        
        sources = ["pacman", "AUR", "Flatpak"]
        self.source_checkboxes = {}
        for source in sources:
            checkbox = QCheckBox(source)
            checkbox.setChecked(True)
            self.source_checkboxes[source] = checkbox
            self.sources_layout.addWidget(checkbox)
        
        layout.addWidget(self.sources_section)
        
        layout.addSpacing(12)
        
        # Filters Section
        self.filters_section = QWidget()
        self.filters_layout = QVBoxLayout(self.filters_section)
        self.filters_layout.setContentsMargins(0, 0, 0, 0)
        self.filters_layout.setSpacing(8)
        
        layout.addWidget(self.filters_section)
        layout.addStretch()
        
        return panel
    
    def create_packages_panel(self):
        panel = QWidget()
        self.packages_panel_layout = QVBoxLayout(panel)
        self.packages_panel_layout.setContentsMargins(12, 12, 12, 12)
        self.packages_panel_layout.setSpacing(12)
        
        # Toolbar
        self.toolbar_widget = QWidget()
        self.toolbar_layout = QVBoxLayout(self.toolbar_widget)
        self.toolbar_layout.setContentsMargins(0,0,0,0)
        self.packages_panel_layout.addWidget(self.toolbar_widget)
        
        # Loading spinner widget
        self.loading_widget = LoadingSpinner(message="Checking for updates...")
        self.loading_widget.setVisible(False)  # Hidden by default
        
        # Cancel button for installation
        self.cancel_install_btn = QPushButton("Cancel Installation")
        self.cancel_install_btn.setMinimumHeight(36)
        self.cancel_install_btn.setVisible(False)  # Hidden by default
        self.cancel_install_btn.clicked.connect(self.cancel_installation)
        
        # Container for loading widget and cancel button
        loading_container = QWidget()
        loading_layout = QHBoxLayout(loading_container)
        loading_layout.setContentsMargins(0, 0, 0, 0)
        loading_layout.addStretch()  # Left stretch to center
        loading_layout.addWidget(self.loading_widget)
        loading_layout.addWidget(self.cancel_install_btn)
        loading_layout.addStretch()  # Right stretch to center
        
        self.packages_panel_layout.addWidget(loading_container)
        
        # Large search box for discover page
        self.large_search_box = LargeSearchBox()
        self.large_search_box.search_requested.connect(self.on_large_search_requested)
        self.packages_panel_layout.addWidget(self.large_search_box)
        
        # Settings container (hidden by default)
        self.settings_container = QScrollArea()
        self.settings_container.setWidgetResizable(True)
        self.settings_container.setVisible(False)
        self.settings_root = QWidget()
        self.settings_layout = QVBoxLayout(self.settings_root)
        self.settings_layout.setContentsMargins(12, 12, 12, 12)
        self.settings_layout.setSpacing(12)
        self.settings_container.setWidget(self.settings_root)
        self.packages_panel_layout.addWidget(self.settings_container)
        
        # Plugins view (hidden by default)
        self.plugins_view = PluginsView(self, self.get_svg_icon)
        self.plugins_view.install_requested.connect(self.on_plugin_install_requested)
        self.plugins_view.launch_requested.connect(self.on_plugin_launch_requested)
        try:
            self.plugins_view.uninstall_requested.connect(self.on_plugin_uninstall_requested)
        except Exception:
            pass
        self.plugins_view.setVisible(False)
        
        # Create plugins tab widget
        self.plugins_tab_widget = QTabWidget()
        self.plugins_tab_widget.setVisible(False)
        
        # Built-in plugins tab
        builtin_tab = QWidget()
        builtin_layout = QVBoxLayout(builtin_tab)
        builtin_layout.addWidget(self.plugins_view)
        self.plugins_tab_widget.addTab(builtin_tab, "Built-in Plugins")
        
        self.packages_panel_layout.addWidget(self.plugins_tab_widget)
        
        # Packages Table
        self.package_table = QTableWidget()
        self.package_table.setColumnCount(6)
        self.package_table.setHorizontalHeaderLabels(
            ["", "Package Name", "Package ID", "Version", "New Version", "Source"]
        )
        self.package_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.package_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.package_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.package_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.package_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.package_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.package_table.verticalHeader().setVisible(False)
        self.package_table.setAlternatingRowColors(True)
        self.package_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.package_table.setSelectionMode(QTableWidget.SelectionMode.MultiSelection)
        self.package_table.selectionModel().selectionChanged.connect(self.on_selection_changed)
        self.packages_panel_layout.addWidget(self.package_table, 1)
        self.load_more_btn = QPushButton("Load More Packages")
        self.load_more_btn.setMinimumHeight(36)
        icon_dir = os.path.join(os.path.dirname(__file__), "assets", "icons", "discover")
        
        self.load_more_btn.setIcon(self.get_svg_icon(os.path.join(icon_dir, "load-more.svg"), 20))
        self.load_more_btn.clicked.connect(self.load_more_packages)
        self.load_more_btn.setVisible(False)
        self.packages_panel_layout.addWidget(self.load_more_btn)
        
        # Console Output
        self.console_label = QLabel("Console Output")
        self.console_label.setObjectName("sectionLabel")
        self.packages_panel_layout.addWidget(self.console_label)
        
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setMaximumHeight(150)
        try:
            self.console.document().setMaximumBlockCount(500)
        except Exception:
            pass
        self.packages_panel_layout.addWidget(self.console)
        
        return panel
    
    def update_toolbar(self):
        # Clear existing toolbar
        while self.toolbar_layout.count():
            item = self.toolbar_layout.takeAt(0)
            if item.layout():
                # Remove the layout
                layout = item.layout()
                while layout.count():
                    child = layout.takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()
                item.layout().deleteLater()
        
        if self.current_view == "updates":
            layout = QHBoxLayout()
            layout.setSpacing(12)
            
            update_btn = QPushButton("Update Selected")
            update_btn.setMinimumHeight(36)
            update_btn.setStyleSheet(
                """
                QPushButton {
                    background-color: transparent;
                    color: #F0F0F0;
                    border: 1px solid rgba(0, 191, 174, 0.3);
                    border-radius: 6px;
                    padding: 6px 12px;
                    font-size: 12px;
                    font-weight: 500;
                }
                QPushButton:hover { background-color: rgba(0, 191, 174, 0.15); border-color: rgba(0, 191, 174, 0.5); }
                QPushButton:pressed { background-color: rgba(0, 191, 174, 0.25); }
                """
            )
            update_btn.clicked.connect(self.update_selected)
            layout.addWidget(update_btn)
            
            ignore_btn = QPushButton("Ignore Selected")
            ignore_btn.setMinimumHeight(36)
            ignore_btn.setStyleSheet(
                """
                QPushButton {
                    background-color: transparent;
                    color: #F0F0F0;
                    border: 1px solid rgba(0, 191, 174, 0.3);
                    border-radius: 6px;
                    padding: 6px 12px;
                    font-size: 12px;
                    font-weight: 500;
                }
                QPushButton:hover { background-color: rgba(0, 191, 174, 0.15); border-color: rgba(0, 191, 174, 0.5); }
                QPushButton:pressed { background-color: rgba(0, 191, 174, 0.25); }
                """
            )
            ignore_btn.clicked.connect(self.ignore_selected)
            layout.addWidget(ignore_btn)
            
            manage_btn = QPushButton("Manage Ignored")
            manage_btn.setMinimumHeight(36)
            manage_btn.setStyleSheet(
                """
                QPushButton {
                    background-color: transparent;
                    color: #F0F0F0;
                    border: 1px solid rgba(0, 191, 174, 0.3);
                    border-radius: 6px;
                    padding: 6px 12px;
                    font-size: 12px;
                    font-weight: 500;
                }
                QPushButton:hover { background-color: rgba(0, 191, 174, 0.15); border-color: rgba(0, 191, 174, 0.5); }
                QPushButton:pressed { background-color: rgba(0, 191, 174, 0.25); }
                """
            )
            manage_btn.clicked.connect(self.manage_ignored)
            layout.addWidget(manage_btn)
            
            layout.addStretch()
            # Right-side action icons similar to Discover
            icon_dir = os.path.join(os.path.dirname(__file__), "assets", "icons", "discover")
            bundles_btn = self.create_toolbar_button(
                os.path.join(os.path.dirname(__file__), "assets", "icons", "local-builds.svg"),
                "Add selected to Bundle",
                self.add_selected_to_bundle
            )
            layout.addWidget(bundles_btn)

            sudo_btn = self.create_toolbar_button(
                os.path.join(os.path.dirname(__file__), "assets", "icons", "sudo.svg"),
                "Run Updates (sudo where needed)",
                lambda: self.update_selected()
            )
            layout.addWidget(sudo_btn)

            tools_btn = self.create_toolbar_button(
                os.path.join(icon_dir, "download.svg"),
                "Update Tools",
                self.update_core_tools
            )
            help_btn = self.create_toolbar_button(
                os.path.join(os.path.dirname(__file__), "assets", "icons", "about.svg"),
                "Help & Documentation",
                self.show_help
            )
            layout.addWidget(tools_btn)
            layout.addWidget(help_btn)

            self.toolbar_layout.addLayout(layout)
        elif self.current_view == "installed":
            layout = QHBoxLayout()
            layout.setSpacing(12)
            update_btn = QPushButton("Update Selected")
            update_btn.setMinimumHeight(36)
            update_btn.setStyleSheet(
                """
                QPushButton {
                    background-color: transparent;
                    color: #F0F0F0;
                    border: 1px solid rgba(0, 191, 174, 0.3);
                    border-radius: 6px;
                    padding: 6px 12px;
                    font-size: 12px;
                    font-weight: 500;
                }
                QPushButton:hover { background-color: rgba(0, 191, 174, 0.15); border-color: rgba(0, 191, 174, 0.5); }
                QPushButton:pressed { background-color: rgba(0, 191, 174, 0.25); }
                """
            )
            update_btn.clicked.connect(self.update_selected)
            layout.addWidget(update_btn)

            uninstall_btn = QPushButton("Uninstall Selected")
            uninstall_btn.setMinimumHeight(36)
            uninstall_btn.setStyleSheet(
                """
                QPushButton {
                    background-color: transparent;
                    color: #F0F0F0;
                    border: 1px solid rgba(0, 191, 174, 0.3);
                    border-radius: 6px;
                    padding: 6px 12px;
                    font-size: 12px;
                    font-weight: 500;
                }
                QPushButton:hover { background-color: rgba(0, 191, 174, 0.15); border-color: rgba(0, 191, 174, 0.5); }
                QPushButton:pressed { background-color: rgba(0, 191, 174, 0.25); }
                """
            )
            uninstall_btn.clicked.connect(self.uninstall_selected)
            layout.addWidget(uninstall_btn)

            layout.addStretch()
            icon_dir = os.path.join(os.path.dirname(__file__), "assets", "icons", "discover")
            bundles_btn = self.create_toolbar_button(
                os.path.join(os.path.dirname(__file__), "assets", "icons", "local-builds.svg"),
                "Add selected to Bundle",
                self.add_selected_to_bundle
            )
            layout.addWidget(bundles_btn)
            tools_btn = self.create_toolbar_button(
                os.path.join(icon_dir, "download.svg"),
                "Update Tools",
                self.update_core_tools
            )
            help_btn = self.create_toolbar_button(
                os.path.join(os.path.dirname(__file__), "assets", "icons", "about.svg"),
                "Help & Documentation",
                self.show_help
            )
            layout.addWidget(tools_btn)
            layout.addWidget(help_btn)
            self.toolbar_layout.addLayout(layout)
        elif self.current_view == "discover":
            layout = QHBoxLayout()
            layout.setSpacing(8)  # Tighter spacing
            
            install_btn = QPushButton("Install selected packages")
            install_btn.setMinimumHeight(36)
            install_btn.clicked.connect(self.install_selected)
            icon_dir = os.path.join(os.path.dirname(__file__), "assets", "icons", "discover")
            
            install_btn.setIcon(self.get_svg_icon(os.path.join(icon_dir, "install-selected packge.svg"), 20))
            
            layout.addWidget(install_btn)

            # Git button on the left side
            git_btn = self.create_toolbar_button(
                os.path.join(icon_dir, "git.svg"),
                "Install via GitHub",
                self.show_git_install_dialog
            )
            layout.addWidget(git_btn)
            
            # Docker button next to Git
            docker_btn = self.create_toolbar_button(
                os.path.join(icon_dir, "docker.svg"),
                "Install via Docker",
                self.show_docker_install_dialog
            )
            layout.addWidget(docker_btn)
            
            layout.addStretch()  # Push remaining buttons to the right
            
            # Action buttons on the right side
            bundles_btn = self.create_toolbar_button(
                os.path.join(os.path.dirname(__file__), "assets", "icons", "local-builds.svg"),
                "Add selected to Bundle",
                self.add_selected_to_bundle
            )
            layout.addWidget(bundles_btn)
            
            sudo_btn = self.create_toolbar_button(
                os.path.join(os.path.dirname(__file__), "assets", "icons", "sudo.svg"),
                "Install with Sudo Privileges",
                self.sudo_install_selected
            )
            layout.addWidget(sudo_btn)
            
            # Help button on the far right
            help_btn = self.create_toolbar_button(
                os.path.join(os.path.dirname(__file__), "assets", "icons", "about.svg"),
                "Help & Documentation",
                self.show_help
            )
            tools_btn = self.create_toolbar_button(
                os.path.join(icon_dir, "download.svg"),
                "Update Tools",
                self.update_core_tools
            )
            layout.addWidget(tools_btn)
            layout.addWidget(help_btn)
            
            self.toolbar_layout.addLayout(layout)
        elif self.current_view == "plugins":
            layout = QHBoxLayout()
            layout.setSpacing(12)
            refresh_btn = QPushButton("Refresh")
            refresh_btn.setMinimumHeight(36)
            refresh_btn.clicked.connect(lambda: self.plugins_view.refresh_all())
            layout.addWidget(refresh_btn)
            layout.addStretch()
            help_btn = self.create_toolbar_button(
                os.path.join(os.path.dirname(__file__), "assets", "icons", "about.svg"),
                "Help & Documentation",
                self.show_help
            )
            layout.addWidget(help_btn)
            self.toolbar_layout.addLayout(layout)
        elif self.current_view == "bundles":
            layout = QHBoxLayout()
            layout.setSpacing(12)
            install_bundle_btn = QPushButton("Install Bundle")
            install_bundle_btn.setMinimumHeight(36)
            install_bundle_btn.setStyleSheet(
                """
                QPushButton {
                    background-color: transparent;
                    color: #F0F0F0;
                    border: 1px solid rgba(0, 191, 174, 0.3);
                    border-radius: 6px;
                    padding: 6px 12px;
                    font-size: 12px;
                    font-weight: 500;
                }
                QPushButton:hover { background-color: rgba(0, 191, 174, 0.15); border-color: rgba(0, 191, 174, 0.5); }
                QPushButton:pressed { background-color: rgba(0, 191, 174, 0.25); }
                """
            )
            install_bundle_btn.clicked.connect(self.install_bundle)
            layout.addWidget(install_bundle_btn)

            export_btn = QPushButton("Export Bundle")
            export_btn.setMinimumHeight(36)
            export_btn.setStyleSheet(install_bundle_btn.styleSheet())
            export_btn.clicked.connect(self.export_bundle)
            layout.addWidget(export_btn)

            import_btn = QPushButton("Import Bundle")
            import_btn.setMinimumHeight(36)
            import_btn.setStyleSheet(install_bundle_btn.styleSheet())
            import_btn.clicked.connect(self.import_bundle)
            layout.addWidget(import_btn)

            remove_sel_btn = QPushButton("Remove Selected")
            remove_sel_btn.setMinimumHeight(36)
            remove_sel_btn.setStyleSheet(install_bundle_btn.styleSheet())
            remove_sel_btn.clicked.connect(self.remove_selected_from_bundle)
            layout.addWidget(remove_sel_btn)

            clear_btn = QPushButton("Clear Bundle")
            clear_btn.setMinimumHeight(36)
            clear_btn.setStyleSheet(install_bundle_btn.styleSheet())
            clear_btn.clicked.connect(self.clear_bundle)
            layout.addWidget(clear_btn)

            layout.addStretch()
            help_btn = self.create_toolbar_button(
                os.path.join(os.path.dirname(__file__), "assets", "icons", "about.svg"),
                "Help & Documentation",
                self.show_help
            )
            layout.addWidget(help_btn)
            self.toolbar_layout.addLayout(layout)
    
    def show_welcome_animation(self):
        """Display a welcome animation in the console when the app first opens"""
        welcome_messages = [
            "🌟 Welcome to NeoArch Package Manager!",
            "🚀 Ready to elevate your Arch experience",
            "📦 Search, install, and manage packages with ease",
            "⚡ Multi-repo support: pacman, AUR, Flatpak & npm",
            "🔍 Start by searching for packages above"
        ]
        
        self.welcome_index = 0
        
        def animate_next_message():
            if self.welcome_index < len(welcome_messages):
                self.log(welcome_messages[self.welcome_index])
                self.welcome_index += 1
                QTimer.singleShot(800, animate_next_message)  # 800ms delay between messages
            else:
                # Clear the console after the animation completes
                QTimer.singleShot(2000, lambda: self.console.clear())  # Wait 2 seconds then clear
        
        # Start the animation
        animate_next_message()
    
    def switch_view(self, view_id):
        self.current_view = view_id
        self.console.clear()
        # Stop any spinners and cancel background loads when switching views
        try:
            self.loading_widget.stop_animation()
            self.loading_widget.setVisible(False)
            self.cancel_install_btn.setVisible(False)
            self.settings_container.setVisible(False)
            if hasattr(self, 'plugins_view') and self.plugins_view:
                self.plugins_view.setVisible(False)
            if hasattr(self, 'plugins_tab_widget') and self.plugins_tab_widget:
                self.plugins_tab_widget.setVisible(False)
        except Exception:
            pass
        # Cancel ongoing non-install tasks
        self.cancel_update_load = True
        self.cancel_discover_search = True
        # Tag the current view as the active loading context
        self.loading_context = view_id
        
        # Update button states
        for btn_id, btn in self.nav_buttons.items():
            btn.setChecked(btn_id == view_id)
        
        # Update header
        headers = {
            "updates": ("🔄 Software Updates", ""),
            "installed": ("📦 Installed Packages", "View all installed packages on your system"),
            "discover": ("/home/alexa/StudioProjects/Aurora/assets/icons/discover/search.svg", "Discover Packages", "Search and discover new packages to install"),
            "bundles": ("📋 Package Bundles", "Manage package bundles"),
            "plugins": (os.path.join(os.path.dirname(__file__), "assets", "icons", "plugins", "plugins.svg"), "Plugins", "Extensions and system tools"),
            "settings": (os.path.join(os.path.dirname(__file__), "assets", "icons", "settings.svg"), "Settings", "Configure NeoArch settings and plugins"),
        }
        
        header_data = headers.get(view_id, ("NeoArch", ""))
        if len(header_data) == 3:  # Icon, title, subtitle
            icon_path, title, subtitle = header_data
            self.header_icon.setPixmap(self.get_svg_icon(icon_path, 24).pixmap(24, 24))
            self.header_icon.setVisible(True)
            self.header_label.setText(title)
            self.header_info.setText(subtitle)
        else:  # Title, subtitle
            title, subtitle = header_data
            self.header_icon.setVisible(False)
            self.header_label.setText(title)
            self.header_info.setText(subtitle)
        # Update dynamic counts if on updates
        if view_id == "updates":
            QTimer.singleShot(0, self.update_updates_header_counts)
        
        self.update_table_columns(view_id)
        self.update_filters_panel(view_id)
        self.update_toolbar()
        self.search_input.clear()
        if view_id != "discover":
            self.large_search_box.setVisible(False)
        
        # Load data for view
        if view_id == "updates":
            self.load_updates()
        elif view_id == "installed":
            self.load_installed_packages()
        elif view_id == "discover":
            self.large_search_box.setVisible(True)
            self.package_table.setVisible(False)
            self.load_more_btn.setVisible(False)
            self.package_table.setRowCount(0)
            self.header_info.setText("Search and discover new packages to install")
            # Removed verbose log: self.log("Type a package name to search in AUR and official repositories")
        elif view_id == "bundles":
            self.package_table.setRowCount(0)
            self.header_info.setText("Create, import, export, and install bundles of packages across sources")
            self.package_table.setVisible(True)
            self.load_more_btn.setVisible(False)
            # Show console in non-settings views
            try:
                self.console_label.setVisible(True)
                self.console.setVisible(True)
            except Exception:
                pass
            QTimer.singleShot(0, self.refresh_bundles_table)
        elif view_id == "plugins":
            # Show plugins view with tabs, hide others
            try:
                self.loading_widget.setVisible(False)
                self.loading_widget.stop_animation()
            except Exception:
                pass
            self.large_search_box.setVisible(False)
            self.settings_container.setVisible(False)
            self.package_table.setVisible(False)
            self.load_more_btn.setVisible(False)
            
            # Clear and add PluginsSidebar
            while self.filters_layout.count():
                item = self.filters_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            try:
                self.plugins_sidebar = PluginsSidebar(self)
                self.plugins_sidebar.filter_changed.connect(self.on_plugins_filter_changed)
                # Populate sidebar with the same list as cards
                try:
                    if hasattr(self, 'plugins_view') and self.plugins_view:
                        self.plugins_sidebar.set_plugins(self.plugins_view.plugins)
                        cats = sorted({(p.get('category') or '') for p in self.plugins_view.plugins if p.get('category')})
                        try:
                            self.plugins_sidebar.set_categories(cats)
                        except Exception:
                            pass
                except Exception:
                    pass
                # Allow install from sidebar
                try:
                    self.plugins_sidebar.install_requested.connect(self.on_plugin_install_requested)
                    self.plugins_sidebar.uninstall_requested.connect(self.on_plugin_uninstall_requested)
                except Exception:
                    pass
                self.filters_layout.addWidget(self.plugins_sidebar)
            except Exception:
                pass
            self.plugins_tab_widget.setVisible(True)
            # Ensure built-in plugins grid is visible
            try:
                self.plugins_view.setVisible(True)
            except Exception:
                pass
            self.plugins_view.refresh_all()

            self.header_info.setText("Install and launch extensions like BleachBit and Timeshift")
            try:
                self.console_label.setVisible(False)
                self.console.setVisible(False)
            except Exception:
                pass
        elif view_id == "settings":
            # Show settings panel, hide package table & search
            try:
                self.loading_widget.setVisible(False)
                self.loading_widget.stop_animation()
            except Exception:
                pass
            self.large_search_box.setVisible(False)
            self.package_table.setVisible(False)
            self.load_more_btn.setVisible(False)
            self.settings_container.setVisible(True)
            # Hide console in Settings view
            try:
                self.console_label.setVisible(False)
                self.console.setVisible(False)
            except Exception:
                pass
            self.header_info.setText("Configure NeoArch settings and plugins")
            QTimer.singleShot(0, self.build_settings_ui)
        # Notify plugins about view change
        try:
            self.run_plugin_hook('on_view_changed', view_id)
        except Exception:
            pass
        # Other views: ensure console visible
        if view_id not in ("settings", "plugins"):
            try:
                self.console_label.setVisible(True)
                self.console.setVisible(True)
            except Exception:
                pass
    
    def update_filters_panel(self, view_id):
        # Clear existing filters section
        while self.filters_layout.count():
            item = self.filters_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Recreate filters based on view
        if view_id == "updates":
            self.update_updates_sources()
        elif view_id == "installed":
            # For installed view, filter by update status
            self.filter_card = FilterCard(self)
            self.filter_card.filter_changed.connect(self.on_filter_selection_changed)
            
            # Add status filters
            self.filter_card.add_filter("Updates available")
            self.filter_card.add_filter("Installed")
            
            self.filters_layout.addWidget(self.filter_card)
        else:
            filter_options = []
        
        # Update visibility
        if view_id == "installed":
            self.sources_section.setVisible(True)
            self.filters_section.setVisible(True)
            if hasattr(self, 'sources_title_label'):
                self.sources_title_label.setVisible(True)
            self.update_installed_sources()
        elif view_id == "updates":
            self.sources_section.setVisible(True)
            self.filters_section.setVisible(False)
            if hasattr(self, 'sources_title_label'):
                self.sources_title_label.setVisible(True)
        elif view_id == "discover":
            self.sources_section.setVisible(True)
            self.filters_section.setVisible(False)
            if hasattr(self, 'sources_title_label'):
                self.sources_title_label.setVisible(False)
            self.update_discover_sources()
        elif view_id == "bundles":
            # No source or status filters for bundles
            self.sources_section.setVisible(False)
            self.filters_section.setVisible(False)
            if hasattr(self, 'sources_title_label'):
                self.sources_title_label.setVisible(False)
        elif view_id == "plugins":
            # Show a VS Code-like extensions sidebar in filters_section
            self.sources_section.setVisible(False)
            self.filters_section.setVisible(True)
            if hasattr(self, 'sources_title_label'):
                self.sources_title_label.setVisible(False)
            # Clear and add PluginsSidebar
            while self.filters_layout.count():
                item = self.filters_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            try:
                self.plugins_sidebar = PluginsSidebar(self)
                self.plugins_sidebar.filter_changed.connect(self.on_plugins_filter_changed)
                # Populate sidebar with the same list as cards
                try:
                    if hasattr(self, 'plugins_view') and self.plugins_view:
                        self.plugins_sidebar.set_plugins(self.plugins_view.plugins)
                        cats = sorted({(p.get('category') or '') for p in self.plugins_view.plugins if p.get('category')})
                        try:
                            self.plugins_sidebar.set_categories(cats)
                        except Exception:
                            pass
                except Exception:
                    pass
                # Allow install from sidebar
                try:
                    self.plugins_sidebar.install_requested.connect(self.on_plugin_install_requested)
                    self.plugins_sidebar.uninstall_requested.connect(self.on_plugin_uninstall_requested)
                except Exception:
                    pass
                self.filters_layout.addWidget(self.plugins_sidebar)
            except Exception:
                pass
        elif view_id == "settings":
            self.sources_section.setVisible(False)
            self.filters_section.setVisible(False)
            if hasattr(self, 'sources_title_label'):
                self.sources_title_label.setVisible(False)
        else:
            self.sources_section.setVisible(True)
            self.filters_section.setVisible(True)
            if hasattr(self, 'sources_title_label'):
                self.sources_title_label.setVisible(True)
    
    def on_filter_selection_changed(self, filter_states):
        """Handle changes in filter selection"""
        self.log(f"Filter selection changed: {filter_states}")
        # Apply filtering based on current view
        if self.current_view == "installed":
            self.apply_filters()
        elif self.current_view == "updates":
            self.apply_update_filters()
    
    def update_discover_sources(self):
        """Update the discover sources using the new SourceCard component"""
        # Clear existing sources layout (except the title label)
        while self.sources_layout.count() > 1:
            item = self.sources_layout.takeAt(1)
            if item.widget():
                item.widget().deleteLater()
        
        # Always create a new SourceCard component
        self.source_card = SourceCard(self)
        self.source_card.source_changed.connect(self.on_source_selection_changed)
        self.source_card.search_mode_changed.connect(self.on_search_mode_changed)
        
        # Add the four main sources
        sources = [
            ("pacman", os.path.join(os.path.dirname(__file__), "assets", "icons", "discover", "pacman.svg")),
            ("AUR", os.path.join(os.path.dirname(__file__), "assets", "icons", "discover", "aur.svg")),
            ("Flatpak", os.path.join(os.path.dirname(__file__), "assets", "icons", "discover", "flatpack.svg")),
            ("npm", os.path.join(os.path.dirname(__file__), "assets", "icons", "discover", "node.svg")),
            ("Local", os.path.join(os.path.dirname(__file__), "assets", "icons", "local-builds.svg")),
        ]
        
        for source_name, icon_path in sources:
            self.source_card.add_source(source_name, icon_path)
        
        self.sources_layout.addWidget(self.source_card)

    def update_updates_sources(self):
        while self.sources_layout.count() > 1:
            item = self.sources_layout.takeAt(1)
            if item.widget():
                item.widget().deleteLater()
        self.source_card = SourceCard(self)
        self.source_card.source_changed.connect(self.on_updates_source_changed)
        sources = [
            ("pacman", os.path.join(os.path.dirname(__file__), "assets", "icons", "discover", "pacman.svg")),
            ("AUR", os.path.join(os.path.dirname(__file__), "assets", "icons", "discover", "aur.svg")),
            ("Flatpak", os.path.join(os.path.dirname(__file__), "assets", "icons", "discover", "flatpack.svg")),
            ("npm", os.path.join(os.path.dirname(__file__), "assets", "icons", "discover", "node.svg")),
            ("Local", os.path.join(os.path.dirname(__file__), "assets", "icons", "local-builds.svg"))
        ]
        for source_name, icon_path in sources:
            self.source_card.add_source(source_name, icon_path)
        self.sources_layout.addWidget(self.source_card)
        if not hasattr(self, 'git_manager') or self.git_manager is None:
            from git_manager import GitManager
            self.git_manager = GitManager(self.log_signal, self.show_message, self.sources_layout, self)

    def update_installed_sources(self):
        while self.sources_layout.count() > 1:
            item = self.sources_layout.takeAt(1)
            if item.widget():
                item.widget().deleteLater()
        self.source_card = SourceCard(self)
        self.source_card.source_changed.connect(self.on_installed_source_changed)
        sources = [
            ("pacman", os.path.join(os.path.dirname(__file__), "assets", "icons", "discover", "pacman.svg")),
            ("AUR", os.path.join(os.path.dirname(__file__), "assets", "icons", "discover", "aur.svg")),
            ("Flatpak", os.path.join(os.path.dirname(__file__), "assets", "icons", "discover", "flatpack.svg")),
            ("npm", os.path.join(os.path.dirname(__file__), "assets", "icons", "discover", "node.svg"))
        ]
        for source_name, icon_path in sources:
            self.source_card.add_source(source_name, icon_path)
        try:
            for obj_name in ("searchModeTitle",):
                w = self.source_card.findChild(QLabel, obj_name)
                if w:
                    w.setVisible(False)
            for rb in self.source_card.findChildren(QRadioButton, "searchModeRadio"):
                rb.setVisible(False)
        except Exception:
            pass
        self.sources_layout.addWidget(self.source_card)

    def on_installed_source_changed(self, source_states):
        # Re-apply combined filters (source + status)
        self.apply_filters()

    def on_updates_source_changed(self, source_states):
        base = getattr(self, 'updates_all', self.all_packages)
        show_pacman = source_states.get("pacman", True)
        show_aur = source_states.get("AUR", True)
        show_flatpak = source_states.get("Flatpak", True)
        show_npm = source_states.get("npm", True)
        show_local = source_states.get("Local", True)
        filtered = []
        for pkg in base:
            s = pkg.get('source')
            if s == 'pacman' and show_pacman:
                filtered.append(pkg)
            elif s == 'AUR' and show_aur:
                filtered.append(pkg)
            elif s == 'Flatpak' and show_flatpak:
                filtered.append(pkg)
            elif s == 'npm' and show_npm:
                filtered.append(pkg)
            elif s == 'Local' and show_local:
                filtered.append(pkg)
        self.all_packages = filtered
        self.current_page = 0
        self.package_table.setRowCount(0)
        self.display_page()
        self.update_load_more_visibility()
        # Refresh counts after filtering
        self.update_updates_header_counts()
        
        # Initialize Git Manager for sources panel
        if not hasattr(self, 'git_manager') or self.git_manager is None:
            from git_manager import GitManager
            self.git_manager = GitManager(self.log_signal, self.show_message, self.sources_layout, self)
    
    def on_source_selection_changed(self, source_states):
        """Handle changes in source selection"""
        # Removed verbose log: self.log(f"Source selection changed: {source_states}")
        # Apply source filtering if we have search results
        if self.current_view == "discover" and hasattr(self, 'search_results') and self.search_results:
            self.display_discover_results(selected_sources=source_states)
    
    def on_search_mode_changed(self, search_mode):
        """Handle changes in search mode"""
        # Removed verbose log: self.log(f"Search mode changed to: {search_mode}")
        # Store the current search mode for future searches
        self.current_search_mode = search_mode
        # Re-run search if we have a current query
        current_query = self.search_input.text().strip()
        if current_query and self.current_view == "discover":
            self.search_discover_packages(current_query)
    
    def update_table_columns(self, view_id):
        if view_id == "installed":
            self.package_table.setColumnCount(6)
            self.package_table.setHorizontalHeaderLabels(["", "Package Name", "Package ID", "Version", "Source", "Status"])
            self.package_table.setObjectName("")  # Reset object name
            self.package_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            self.package_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            self.package_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
            self.package_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
            self.package_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
            self.package_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        elif view_id == "bundles":
            self.package_table.setColumnCount(5)
            self.package_table.setHorizontalHeaderLabels(["", "Package Name", "Package ID", "Version", "Source"])
            self.package_table.setObjectName("bundlesTable")
            header = self.package_table.horizontalHeader()
            header.setStretchLastSection(False)
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
            header.setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
            self.package_table.setColumnWidth(0, 48)
            self.package_table.setColumnWidth(2, 220)
            self.package_table.setColumnWidth(3, 140)
            self.package_table.setColumnWidth(4, 120)
            self.package_table.setShowGrid(False)
            self.package_table.setIconSize(QSize(20, 20))
            self.package_table.setWordWrap(True)
            self.package_table.verticalHeader().setDefaultSectionSize(56)
        elif view_id == "discover":
            self.package_table.setColumnCount(5)
            self.package_table.setHorizontalHeaderLabels(["", "Package Name", "Package ID", "Version", "Source"])
            self.package_table.setObjectName("discoverTable")  # Apply special styling
            header = self.package_table.horizontalHeader()
            header.setStretchLastSection(False)
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
            header.setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
            self.package_table.setColumnWidth(0, 48)
            self.package_table.setColumnWidth(2, 220)
            self.package_table.setColumnWidth(3, 140)
            self.package_table.setColumnWidth(4, 120)
            self.package_table.setShowGrid(False)
            self.package_table.setIconSize(QSize(20, 20))
            self.package_table.setWordWrap(True)
            self.package_table.verticalHeader().setDefaultSectionSize(56)
        else:
            self.package_table.setColumnCount(6)
            self.package_table.setHorizontalHeaderLabels(["", "Package Name", "Package ID", "Version", "New Version", "Source"])
            self.package_table.setObjectName("")  # Reset object name
            self.package_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            self.package_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            self.package_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
            self.package_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
            self.package_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
            self.package_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
    
    def load_updates(self):
        return packages_service.load_updates(self)
    
    def load_installed_packages(self):
        return packages_service.load_installed_packages(self)
    
    def on_packages_loaded(self, packages):
        # Ignore results if user has navigated away from the originating view
        if self.loading_context != self.current_view or self.current_view not in ("updates", "installed"):
            return
        self.all_packages = packages
        if self.current_view == "updates":
            self.updates_all = packages
        elif self.current_view == "installed":
            self.installed_all = packages
        self.current_page = 0
        self.packages_per_page = 10
        self.package_table.setRowCount(0)
        self.display_page()
        if self.current_view == "updates" and hasattr(self, 'source_card') and self.source_card:
            try:
                states = self.source_card.get_selected_sources()
                self.on_updates_source_changed(states)
            except Exception:
                pass
        elif self.current_view == "installed" and hasattr(self, 'source_card') and self.source_card:
            try:
                states = self.source_card.get_selected_sources()
                self.on_installed_source_changed(states)
            except Exception:
                pass
        self.log(f"Loaded {len(packages)} packages total. Showing first 10...")
        
        # Hide loading spinner, stop animation, and show packages table
        self.loading_widget.setVisible(False)
        self.loading_widget.stop_animation()
        self.package_table.setVisible(True)
        # Update counts and nav badge
        if self.current_view == "updates":
            try:
                self.set_updates_count(len(self.updates_all or []))
            except Exception:
                pass
            self.update_updates_header_counts()
    
    def on_load_error(self):
        # Hide loading spinner, stop animation, and show packages table (empty)
        self.loading_widget.setVisible(False)
        self.loading_widget.stop_animation()
        self.package_table.setVisible(True)
        self.log("Failed to load packages. Please check the logs for details.")
    
    def cancel_installation(self):
        """Cancel the ongoing installation process"""
        if hasattr(self, 'install_cancel_event'):
            self.install_cancel_event.set()
            self.log("Installation cancellation requested...")
    
    def on_installation_progress(self, status, can_cancel):
        if status == "start":
            self.load_more_btn.setVisible(False)
            self.loading_widget.set_message("Installing packages...")
            self.loading_widget.setVisible(True)
            self.loading_widget.start_animation()
            self.cancel_install_btn.setVisible(can_cancel)
        elif status == "success":
            self.loading_widget.set_message("Success")
            self.cancel_install_btn.setVisible(False)
            # Keep spinner visible briefly to show success, then hide
            QTimer.singleShot(1500, lambda: self.finish_installation_progress())
        elif status == "failed":
            self.loading_widget.set_message("Install failed")
            self.cancel_install_btn.setVisible(False)
            # Keep spinner visible briefly to show failure, then hide
            QTimer.singleShot(2000, lambda: self.finish_installation_progress())
        elif status == "cancelled":
            self.loading_widget.set_message("Installation cancelled")
            self.cancel_install_btn.setVisible(False)
            # Keep spinner visible briefly to show cancellation, then hide
            QTimer.singleShot(1500, lambda: self.finish_installation_progress())
    
    def finish_installation_progress(self):
        self.loading_widget.setVisible(False)
        self.loading_widget.stop_animation()
        self.update_load_more_visibility()
    
    def update_load_more_visibility(self):
        if self.current_view == "discover":
            if hasattr(self, 'filtered_results') and self.filtered_results:
                total = len(self.filtered_results)
                displayed = (self.current_page + 1) * self.packages_per_page
                has_more = displayed < total
                self.load_more_btn.setVisible(has_more)
            else:
                self.load_more_btn.setVisible(False)
        elif self.current_view == "installed":
            if self.all_packages:
                total = len(self.all_packages)
                displayed = (self.current_page + 1) * self.packages_per_page
                has_more = displayed < total
                self.load_more_btn.setVisible(has_more)
            else:
                self.load_more_btn.setVisible(False)
        elif self.current_view == "updates":
            if self.all_packages:
                total = len(self.all_packages)
                displayed = (self.current_page + 1) * self.packages_per_page
                has_more = displayed < total
                self.load_more_btn.setVisible(has_more)
            else:
                self.load_more_btn.setVisible(False)
    
    def display_page(self):
        self.package_table.setUpdatesEnabled(False)
        start = self.current_page * self.packages_per_page
        end = start + self.packages_per_page
        page_packages = self.all_packages[start:end]
        
        for pkg in page_packages:
            if self.current_view == "installed":
                self.add_package_row(pkg['name'], pkg['id'], pkg['version'], pkg.get('new_version', pkg['version']), pkg.get('source', 'pacman'), pkg)
            elif self.current_view == "discover":
                self.add_discover_row(pkg)
            else:
                self.add_package_row(pkg['name'], pkg['id'], pkg['version'], pkg.get('new_version', pkg['version']), pkg.get('source', 'pacman'))
        
        self.package_table.setUpdatesEnabled(True)
        # Make sure nothing is selected by default
        try:
            self.package_table.clearSelection()
        except Exception:
            pass
        
        has_more = end < len(self.all_packages)
        self.load_more_btn.setVisible(has_more)
        if has_more:
            remaining = len(self.all_packages) - end
            self.load_more_btn.setText(f"Load More ({remaining} remaining)")
        # Keep header subtitle accurate for Updates
        if self.current_view == "updates":
            self.update_updates_header_counts()
    
    def load_more_packages(self):
        self.current_page += 1
        start = self.current_page * self.packages_per_page
        end = start + self.packages_per_page
        
        if self.current_view == "discover":
            dataset = self.get_filtered_discover_results()
        else:
            dataset = self.search_results if self.search_results else self.all_packages
        
        page_packages = dataset[start:end]
        total = len(dataset)
        
        self.package_table.setUpdatesEnabled(False)
        for pkg in page_packages:
            if self.current_view == "installed":
                self.add_package_row(pkg['name'], pkg['id'], pkg['version'], pkg.get('new_version', pkg['version']), pkg.get('source', 'pacman'), pkg)
            elif self.current_view == "discover":
                self.add_discover_row(pkg)
            else:
                self.add_package_row(pkg['name'], pkg['id'], pkg['version'], pkg.get('new_version', pkg['version']), pkg.get('source', 'pacman'))
        self.package_table.setUpdatesEnabled(True)
        
        has_more = end < total
        self.load_more_btn.setVisible(has_more)
        if has_more:
            remaining = total - end
            self.load_more_btn.setText(f"Load More ({remaining} remaining)")
        else:
            self.log("All results loaded")
        
        # Uncheck the newly loaded items
        old_count = self.package_table.rowCount() - len(page_packages)
        for i in range(old_count, self.package_table.rowCount()):
            checkbox = self.get_row_checkbox(i)
            if checkbox is not None:
                checkbox.setChecked(False)
    
    def add_discover_row(self, pkg):
        row = self.package_table.rowCount()
        self.package_table.insertRow(row)
        
        checkbox = QCheckBox()
        checkbox.setObjectName("tableCheckbox")
        checkbox.setChecked(False)
        self.apply_checkbox_accent(checkbox, pkg.get('source', ''))
        cb_container = QWidget()
        cb_container.setStyleSheet("background: transparent;")
        cb_layout = QHBoxLayout(cb_container)
        cb_layout.setContentsMargins(0, 0, 0, 0)
        cb_layout.addStretch()
        cb_layout.addWidget(checkbox)
        cb_layout.addStretch()
        self.package_table.setCellWidget(row, 0, cb_container)
        checkbox.stateChanged.connect(lambda state, r=row: self.on_checkbox_changed(r, state))
        
        name_item = QTableWidgetItem(pkg['name'])
        name_item.setToolTip(pkg['name'])
        font = QFont()
        font.setBold(True)
        name_item.setFont(font)
        icon_dir = os.path.join(os.path.dirname(__file__), "assets", "icons", "discover")
        name_item.setIcon(self.get_svg_icon(os.path.join(icon_dir, "packagename.svg"), 20))
        self.package_table.setItem(row, 1, name_item)
        id_item = QTableWidgetItem(pkg['id'])
        id_item.setIcon(self.get_svg_icon(os.path.join(icon_dir, "pacakgeid.svg"), 18))
        self.package_table.setItem(row, 2, id_item)
        ver_item = QTableWidgetItem(pkg['version'])
        ver_item.setIcon(self.get_svg_icon(os.path.join(icon_dir, "version.svg"), 18))
        self.package_table.setItem(row, 3, ver_item)
        source_chip = QWidget()
        source_chip.setObjectName("sourceChip")
        chip_layout = QHBoxLayout(source_chip)
        chip_layout.setContentsMargins(6, 2, 6, 2)
        chip_layout.setSpacing(6)
        chip_icon = QLabel()
        source_icon = self.get_source_icon(pkg.get('source', ''), 16)
        if not source_icon.isNull():
            chip_icon.setPixmap(source_icon.pixmap(16, 16))
        chip_layout.addWidget(chip_icon)
        chip_text = QLabel(pkg.get('source', ''))
        chip_layout.addWidget(chip_text)
        self.package_table.setCellWidget(row, 4, source_chip)
    
    def add_package_row(self, name, pkg_id, version, new_version, source, pkg_data=None):
        row = self.package_table.rowCount()
        self.package_table.insertRow(row)
        
        checkbox = QCheckBox()
        checkbox.setObjectName("tableCheckbox")
        # Always start unchecked in all views
        checkbox.setChecked(False)
        self.apply_checkbox_accent(checkbox, source if source else "")
        cb_container = QWidget()
        cb_container.setStyleSheet("background: transparent;")
        cb_layout = QHBoxLayout(cb_container)
        cb_layout.setContentsMargins(0, 0, 0, 0)
        cb_layout.addStretch()
        cb_layout.addWidget(checkbox)
        cb_layout.addStretch()
        self.package_table.setCellWidget(row, 0, cb_container)
        checkbox.stateChanged.connect(lambda state, r=row: self.on_checkbox_changed(r, state))
        
        name_item = QTableWidgetItem(name)
        font = QFont()
        font.setBold(True)
        name_item.setFont(font)
        icon_dir = os.path.join(os.path.dirname(__file__), "assets", "icons", "discover")
        name_item.setIcon(self.get_svg_icon(os.path.join(icon_dir, "packagename.svg"), 20))
        self.package_table.setItem(row, 1, name_item)
        id_item = QTableWidgetItem(pkg_id)
        id_item.setIcon(self.get_svg_icon(os.path.join(icon_dir, "pacakgeid.svg"), 18))
        self.package_table.setItem(row, 2, id_item)
        ver_item = QTableWidgetItem(version)
        ver_item.setIcon(self.get_svg_icon(os.path.join(icon_dir, "version.svg"), 18))
        self.package_table.setItem(row, 3, ver_item)
        
        if self.current_view == "installed" and pkg_data:
            self.package_table.setItem(row, 4, QTableWidgetItem(pkg_data.get('source', 'pacman')))
            status = "⬆️ Update available" if pkg_data.get('has_update') else "✓ Up to date"
            status_item = QTableWidgetItem(status)
            if pkg_data.get('has_update'):
                status_item.setForeground(QColor(255, 165, 0))
            else:
                status_item.setForeground(QColor(16, 185, 129))
            self.package_table.setItem(row, 5, status_item)
        elif self.package_table.columnCount() > 4:
            new_version_item = QTableWidgetItem(new_version)
            if self.current_view == "updates":
                # Make new version green to indicate available update
                new_version_item.setForeground(QColor(16, 185, 129))  # Green color
            self.package_table.setItem(row, 4, new_version_item)
            self.package_table.setItem(row, 5, QTableWidgetItem(source))
    
    def filter_packages(self):
        query = self.search_input.text().lower()
        
        if not query:
            self.current_page = 0
            self.package_table.setRowCount(0)
            if self.current_view != "discover":
                self.display_page()
                if self.current_view == "updates":
                    self.update_updates_header_counts()
            return
        
        if self.current_view == "discover":
            self.search_discover_packages(query)
        else:
            self.search_results = [pkg for pkg in self.all_packages if query in pkg['name'].lower()]
            self.current_page = 0
            
            self.package_table.setUpdatesEnabled(False)
            self.package_table.setRowCount(0)
            
            start = 0
            end = min(10, len(self.search_results))
            for pkg in self.search_results[start:end]:
                if self.current_view == "installed":
                    self.add_package_row(pkg['name'], pkg['id'], pkg['version'], pkg.get('new_version', pkg['version']), pkg.get('source', 'pacman'), pkg)
                else:
                    self.add_package_row(pkg['name'], pkg['id'], pkg['version'], pkg.get('new_version', pkg['version']), pkg.get('source', 'pacman'))
            
            self.package_table.setUpdatesEnabled(True)
            
            has_more = end < len(self.search_results)
            self.load_more_btn.setVisible(has_more)
            if has_more:
                remaining = len(self.search_results) - end
                self.load_more_btn.setText(f"📥 Load More ({remaining} remaining)")
            
            self.log(f"Found {len(self.search_results)} packages matching '{query}'. Showing first 10...")
            if self.current_view == "updates":
                # Use search result count for matched in header
                try:
                    total = len(getattr(self, 'updates_all', []) or [])
                    matched = len(self.search_results or [])
                    self.header_info.setText(f"{total} packages were found, {matched} of which match the specified filters")
                except Exception:
                    pass
    
    def search_discover_packages(self, query):
        # Removed verbose search message: self.log(f"Searching for '{query}' in AUR, official repositories, and Flatpak...")
        self.package_table.setRowCount(0)
        self.search_results = []
        # Prepare discover loading context
        self.cancel_discover_search = False
        self.loading_context = "discover"

        try:
            if hasattr(self, 'source_card') and self.source_card:
                _src = self.source_card.get_selected_sources()
            else:
                _src = {"pacman": True, "AUR": True, "Flatpak": True, "npm": True}
        except Exception:
            _src = {"pacman": True, "AUR": True, "Flatpak": True, "npm": True}
        show_pacman = bool(_src.get("pacman", True))
        show_aur = bool(_src.get("AUR", True))
        show_flatpak = bool(_src.get("Flatpak", True))
        show_npm = bool(_src.get("npm", True))
        
        # Show loading spinner
        self.loading_widget.setVisible(True)
        self.loading_widget.set_message("Searching packages...")
        self.loading_widget.start_animation()
        self.package_table.setVisible(False)
        
        def search_in_thread():
            try:
                packages = []
                
                tokens = [t for t in query.split() if t]
                if show_pacman:
                    pacman_seen = set()
                    if len(tokens) > 1:
                        for tok in tokens:
                            try:
                                result = subprocess.run(["pacman", "-Ss", tok], capture_output=True, text=True, timeout=30)
                            except Exception:
                                result = None
                            if result and result.returncode == 0 and result.stdout:
                                lines = result.stdout.strip().split('\n')
                                i = 0
                                while i < len(lines):
                                    if lines[i].strip() and '/' in lines[i]:
                                        parts = lines[i].split()
                                        if len(parts) >= 2:
                                            name = parts[0].split('/')[-1]
                                            version = parts[1]
                                            description = ' '.join(parts[2:]) if len(parts) > 2 else ''
                                            key = ('pacman', name)
                                            if key not in pacman_seen:
                                                pacman_seen.add(key)
                                                packages.append({
                                                    'name': name,
                                                    'version': version,
                                                    'id': name,
                                                    'source': 'pacman',
                                                    'description': description,
                                                    'has_update': False
                                                })
                                    i += 1
                    else:
                        result = subprocess.run(["pacman", "-Ss", query], capture_output=True, text=True, timeout=30)
                        if result.returncode == 0 and result.stdout:
                            lines = result.stdout.strip().split('\n')
                            i = 0
                            while i < len(lines):
                                if lines[i].strip() and '/' in lines[i]:
                                    parts = lines[i].split()
                                    if len(parts) >= 2:
                                        name = parts[0].split('/')[-1]
                                        version = parts[1]
                                        description = ' '.join(parts[2:]) if len(parts) > 2 else ''
                                        packages.append({
                                            'name': name,
                                            'version': version,
                                            'id': name,
                                            'source': 'pacman',
                                            'description': description,
                                            'has_update': False
                                        })
                                i += 1

                if show_aur:
                    result_aur = subprocess.run(["curl", "-s", f"https://aur.archlinux.org/rpc/?v=5&type=search&by=name&arg={query}"], capture_output=True, text=True, timeout=10)
                    if result_aur.returncode == 0:
                        try:
                            data = json.loads(result_aur.stdout)
                            if data.get('results'):
                                for pkg in data['results']:
                                    packages.append({
                                        'name': pkg.get('Name', ''),
                                        'version': pkg.get('Version', ''),
                                        'id': pkg.get('Name', ''),
                                        'source': 'AUR',
                                        'description': pkg.get('Description', ''),
                                        'tags': ', '.join(pkg.get('Keywords', []))
                                    })
                        except Exception:
                            pass

                if show_flatpak:
                    try:
                        if not getattr(self, "_flathub_checked", False):
                            try:
                                self.ensure_flathub_user_remote()
                            except Exception:
                                pass
                            try:
                                self._flathub_checked = True
                            except Exception:
                                pass
                    except Exception:
                        pass
                    result_flatpak = subprocess.run([
                        "flatpak", "search", "--columns=application,name,description,version", query
                    ], capture_output=True, text=True, timeout=30)
                    if result_flatpak.returncode == 0 and result_flatpak.stdout:
                        lines = [l for l in result_flatpak.stdout.strip().split('\n') if l.strip()]
                        for line in lines:
                            ls = line.strip()
                            low = ls.lower()
                            if ('no match' in low) or ('no results' in low) or ('not found' in low):
                                continue
                            cols = line.split('\t')
                            if len(cols) < 2:
                                continue
                            app_id = cols[0].strip()
                            app_name = cols[1].strip() if cols[1].strip() else app_id
                            description = cols[2].strip() if len(cols) > 2 else ''
                            version = cols[3].strip() if len(cols) > 3 else ''
                            if app_id and ('no match' not in app_id.lower()) and ('not found' not in app_id.lower()):
                                packages.append({
                                    'name': app_name,
                                    'version': version,
                                    'id': app_id,
                                    'source': 'Flatpak',
                                    'description': description,
                                    'has_update': False
                                })

                if show_npm:
                    # Search npm packages
                    try:
                        result_npm = subprocess.run(["npm", "search", "--json", query], capture_output=True, text=True, timeout=30)
                        if result_npm.returncode == 0 and result_npm.stdout:
                            npm_data = json.loads(result_npm.stdout)
                            for pkg in npm_data:
                                packages.append({
                                    'name': pkg.get('name', ''),
                                    'version': pkg.get('version', ''),
                                    'id': pkg.get('name', ''),
                                    'source': 'npm',
                                    'description': pkg.get('description', ''),
                                    'has_update': False
                                })
                    except (subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError):
                        # npm not available, try alternative method
                        pass
                
                # Only deliver results if still on Discover and not cancelled
                if not self.cancel_discover_search and self.loading_context == 'discover' and self.current_view == 'discover':
                    self.discover_results_ready.emit(packages)
            except Exception as e:
                self.log(f"Search error: {str(e)}")
        
        Thread(target=search_in_thread, daemon=True).start()

    def get_filtered_discover_results(self, selected_sources=None):
        if selected_sources is None:
            if hasattr(self, 'source_card') and self.source_card:
                selected_sources = self.source_card.get_selected_sources()
            else:
                selected_sources = {"pacman": True, "AUR": True, "Flatpak": True, "npm": True}
        show_pacman = selected_sources.get("pacman", True)
        show_aur = selected_sources.get("AUR", True)
        show_flatpak = selected_sources.get("Flatpak", True)
        show_npm = selected_sources.get("npm", True)
        filtered = []
        for pkg in self.search_results:
            if pkg['source'] == 'pacman' and show_pacman:
                filtered.append(pkg)
            elif pkg['source'] == 'AUR' and show_aur:
                filtered.append(pkg)
            elif pkg['source'] == 'Flatpak' and show_flatpak:
                filtered.append(pkg)
            elif pkg['source'] == 'npm' and show_npm:
                filtered.append(pkg)
        query = self.search_input.text().strip().lower()
        search_mode = self.current_search_mode
        def get_sort_key(pkg):
            name_lower = pkg['name'].lower()
            id_lower = pkg['id'].lower()
            desc_lower = (pkg.get('description') or '').lower()
            exact = (name_lower == query) or (id_lower == query)
            starts = name_lower.startswith(query) or id_lower.startswith(query)
            contains = (query in name_lower) or (query in id_lower)
            desc_contains = (query in desc_lower)
            source_priority = {'pacman': 3, 'AUR': 2, 'Flatpak': 1, 'npm': 0}.get(pkg.get('source'), 0)
            if search_mode == 'name':
                exact_flag = (name_lower == query)
                starts_flag = name_lower.startswith(query)
                contains_flag = (query in name_lower)
                return (exact_flag, starts_flag, contains_flag, source_priority, desc_contains)
            elif search_mode == 'id':
                exact_flag = (id_lower == query)
                starts_flag = id_lower.startswith(query)
                contains_flag = (query in id_lower)
                return (exact_flag, starts_flag, contains_flag, source_priority, desc_contains)
            else:
                return (exact, starts, contains, source_priority, desc_contains)
        filtered.sort(key=get_sort_key, reverse=True)
        return filtered

    def display_discover_results(self, packages=None, selected_sources=None):
        # Safety: do nothing if the user is no longer on Discover
        if self.current_view != "discover" or self.loading_context != "discover":
            return
        if packages is not None:
            self.search_results = packages
        
        # Hide loading spinner and show package table
        self.loading_widget.setVisible(False)
        self.loading_widget.stop_animation()
        self.package_table.setVisible(True)
        
        if selected_sources is None:
            # Get selected sources from the SourceCard component
            selected_sources = {}
            if hasattr(self, 'source_card') and self.source_card:
                selected_sources = self.source_card.get_selected_sources()
            else:
                # Fallback to showing all sources if component not initialized
                selected_sources = {"pacman": True, "AUR": True, "Flatpak": True, "npm": True}
        
        filtered = self.get_filtered_discover_results(selected_sources)
        self.filtered_results = filtered
        self.current_page = 0
        query = self.search_input.text().strip()
        
        self.package_table.setUpdatesEnabled(False)
        self.package_table.setRowCount(0)
        
        start = 0
        end = min(self.packages_per_page, len(filtered))
        for pkg in filtered[start:end]:
            if self.current_view == "discover":
                self.add_discover_row(pkg)
            else:
                self.add_package_row(pkg['name'], pkg['id'], pkg['version'], pkg['version'], pkg['source'])
        
        self.package_table.setUpdatesEnabled(True)
        
        has_more = end < len(filtered)
        self.load_more_btn.setVisible(has_more)
        if has_more:
            remaining = len(filtered) - end
            self.load_more_btn.setText(f"Load More ({remaining} remaining)")
        
        # Provide feedback if no results match
        if not filtered:
            self.header_info.setText(f"No packages found matching '{query}'.")
            self.log(f"No packages found matching '{query}'.")
        else:
            count = len(filtered)
            self.header_info.setText(f"{count} packages were found, {count} of which match the specified filters")
            self.log(f"Found {count} packages matching '{query}'. Showing first 10...")

    def refresh_packages(self):
        if self.current_view == "updates":
            self.load_updates()
        elif self.current_view == "installed":
            self.load_installed_packages()
        elif self.current_view == "discover":
            query = self.search_input.text().strip()
            if query:
                self.search_discover_packages(query)
            else:
                self.package_table.setRowCount(0)
                # Removed verbose log: self.log("Type a package name to search in AUR and official repositories")
    
    def update_selected(self):
        packages_by_source = {}
        for row in range(self.package_table.rowCount()):
            checkbox = self.get_row_checkbox(row)
            if checkbox is not None and checkbox.isChecked():
                name_item = self.package_table.item(row, 1)
                id_item = self.package_table.item(row, 2)
                # Source column differs by view: Updates has Source at col 5; Installed at col 4
                source_col = 5 if self.current_view == "updates" else 4
                source_item = self.package_table.item(row, source_col)
                # On Installed view, only update rows that actually have an update available
                if self.current_view == "installed":
                    status_item = self.package_table.item(row, 5)
                    if not status_item or "Update" not in (status_item.text() or ""):
                        continue
                if not name_item:
                    continue
                pkg_name = name_item.text().strip()
                pkg_id = id_item.text().strip() if id_item else pkg_name
                source = source_item.text() if source_item else "pacman"
                if source not in packages_by_source:
                    packages_by_source[source] = []
                token = pkg_id if source == 'Flatpak' else pkg_name
                packages_by_source[source].append(token)
        if not packages_by_source:
            self.log("No packages selected for update")
            return
        self.log(f"Selected packages for update: {', '.join([f'{pkg} ({source})' for source, pkgs in packages_by_source.items() for pkg in pkgs])}")
        update_service.update_packages(self, packages_by_source)
    
    def ignore_selected(self):
        return ignore_service.ignore_selected(self)
    
    def manage_ignored(self):
        return ignore_service.manage_ignored(self)

    def get_source_text(self, row, view_id=None):
        vid = view_id or self.current_view
        try:
            if vid in ("discover", "bundles"):
                cell = self.package_table.cellWidget(row, 4)
                if cell:
                    labels = cell.findChildren(QLabel)
                    if labels:
                        return labels[-1].text()
                return ""
            elif vid == "updates":
                itm = self.package_table.item(row, 5)
                return itm.text() if itm else ""
            elif vid == "installed":
                itm = self.package_table.item(row, 4)
                return itm.text() if itm else ""
        except Exception:
            return ""
        return ""

    def get_row_info(self, row, view_id=None):
        vid = view_id or self.current_view
        name_item = self.package_table.item(row, 1)
        id_item = self.package_table.item(row, 2)
        version_item = self.package_table.item(row, 3)
        name = name_item.text().strip() if name_item else ""
        pkg_id = id_item.text().strip() if id_item else name
        version = version_item.text().strip() if version_item else ""
        source = self.get_source_text(row, vid)
        return {"name": name, "id": pkg_id, "version": version, "source": source}
    
    def add_selected_to_bundle(self):
        return bundle_service.add_selected_to_bundle(self)

    def refresh_bundles_table(self):
        return bundle_service.refresh_bundles_table(self)

    def export_bundle(self):
        return bundle_service.export_bundle(self)

    def import_bundle(self):
        return bundle_service.import_bundle(self)

    def remove_selected_from_bundle(self):
        return bundle_service.remove_selected_from_bundle(self)

    def clear_bundle(self):
        return bundle_service.clear_bundle(self)

    def install_bundle(self):
        return bundle_service.install_bundle(self)
    
    def install_selected(self):
        packages_by_source = {}
        for row in range(self.package_table.rowCount()):
            checkbox = self.get_row_checkbox(row)
            if checkbox is not None and checkbox.isChecked():
                name_item = self.package_table.item(row, 1)
                id_item = self.package_table.item(row, 2)
                pkg_name = name_item.text().strip() if name_item else ''
                pkg_id = id_item.text().strip() if id_item else pkg_name
                if self.current_view == "discover":
                    source = ""
                    chip = self.package_table.cellWidget(row, 4)
                    if chip is not None:
                        labels = chip.findChildren(QLabel)
                        if labels:
                            source = labels[-1].text()
                else:
                    source_item = self.package_table.item(row, 5)
                    source = source_item.text() if source_item else "pacman"
                if source not in packages_by_source:
                    packages_by_source[source] = []
                install_token = pkg_id if source == 'Flatpak' else pkg_name
                packages_by_source[source].append(install_token)
        
        if not packages_by_source:
            self.log_signal.emit("No packages selected for installation")
            return
        
        self.log_signal.emit(f"Selected packages: {', '.join([f'{pkg} ({source})' for source, pkgs in packages_by_source.items() for pkg in pkgs])}")
        
        self.log_signal.emit(f"Proceeding with installation...")
        install_service.install_packages(self, packages_by_source)
    
    def uninstall_selected(self):
        selected_rows = self.package_table.selectionModel().selectedRows()
        if not selected_rows:
            self.log("No packages selected for uninstallation")
            return
        
        # Group selections by source
        packages_by_source = {}
        for model_index in selected_rows:
            row = model_index.row()
            name_item = self.package_table.item(row, 1)
            id_item = self.package_table.item(row, 2)
            source_item = self.package_table.item(row, 4)
            if not name_item or not source_item:
                continue
            name = (name_item.text() or "").strip()
            pkg_id = (id_item.text() or name).strip() if id_item else name
            source = (source_item.text() or "pacman").strip()
            if source not in packages_by_source:
                packages_by_source[source] = []
            token = pkg_id if source == 'Flatpak' else name
            packages_by_source[source].append(token)
        
        flat_summary = ', '.join([f"{pkg} ({src})" for src, pkgs in packages_by_source.items() for pkg in pkgs])
        self.log(f"Selected for uninstallation: {flat_summary}")
        uninstall_service.uninstall_packages(self, packages_by_source)
    
    def apply_filters(self):
        return filters_service.apply_filters(self)

    def apply_update_filters(self):
        return filters_service.apply_update_filters(self)

    def on_selection_changed(self):
        selected_rows = set(index.row() for index in self.package_table.selectionModel().selectedRows())
        for row in range(self.package_table.rowCount()):
            checkbox = self.get_row_checkbox(row)
            if checkbox is not None:
                checkbox.setChecked(row in selected_rows)
    
    def on_checkbox_changed(self, row, state):
        model = self.package_table.selectionModel()
        if state == Qt.CheckState.Checked.value:
            model.select(self.package_table.model().index(row, 0), QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)
        else:
            model.select(self.package_table.model().index(row, 0), QItemSelectionModel.SelectionFlag.Deselect | QItemSelectionModel.SelectionFlag.Rows)
    
    def select_all_sources(self):
        for checkbox in self.source_checkboxes.values():
            checkbox.setChecked(True)
    
    def clear_sources(self):
        for checkbox in self.source_checkboxes.values():
            checkbox.setChecked(False)
    
    def load_settings(self):
        return settings_service.load_settings()
    
    def save_settings(self):
        return settings_service.save_settings(self.settings, self.log)
    
    def get_user_plugins_dir(self):
        p = os.path.join(os.path.expanduser('~'), '.config', 'aurora', 'plugins')
        try:
            os.makedirs(p, exist_ok=True)
        except Exception:
            pass
        return p
    
    def scan_plugins(self):
        plugs = []
        try:
            user_dir = self.get_user_plugins_dir()
            for fn in sorted(os.listdir(user_dir)):
                if fn.endswith('.py'):
                    plugs.append({'name': os.path.splitext(fn)[0], 'path': os.path.join(user_dir, fn), 'location': 'User'})
        except Exception:
            pass
        return plugs
    
    def build_settings_ui(self):
        while self.settings_layout.count():
            item = self.settings_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        tabs = QTabWidget()
        gen = GeneralSettingsWidget(self)
        auto_update = AutoUpdateSettingsWidget(self)
        plugs = PluginsSettingsWidget(self)
        tabs.addTab(gen, "General")
        tabs.addTab(auto_update, "Auto Update")
        tabs.addTab(plugs, "Plugins")
        self.settings_layout.addWidget(tabs)
        self.settings_layout.addStretch()
    
    def build_general_settings(self, layout):
        box = QGroupBox("General Settings")
        grid = QGridLayout(box)
        cb_auto = QCheckBox("Auto check updates on launch")
        cb_auto.setChecked(bool(self.settings.get('auto_check_updates')))
        cb_auto.toggled.connect(lambda v: self._update_setting('auto_check_updates', v))
        grid.addWidget(cb_auto, 0, 0, 1, 2)
        cb_local = QCheckBox("Include Local source (custom scripts)")
        cb_local.setChecked(bool(self.settings.get('include_local_source')))
        cb_local.toggled.connect(lambda v: self._update_setting('include_local_source', v))
        grid.addWidget(cb_local, 1, 0, 1, 2)
        cb_npm = QCheckBox("Use npm user mode for global installs")
        cb_npm.setChecked(bool(self.settings.get('npm_user_mode')))
        cb_npm.toggled.connect(lambda v: self._update_setting('npm_user_mode', v))
        grid.addWidget(cb_npm, 2, 0, 1, 2)
        layout.addWidget(box)
        
        path_box = QGroupBox("Bundle Autosave")
        pgrid = QGridLayout(path_box)
        cb_bsave = QCheckBox("Autosave bundle to file")
        cb_bsave.setChecked(bool(self.settings.get('bundle_autosave', True)))
        cb_bsave.toggled.connect(lambda v: self._update_setting('bundle_autosave', v))
        pgrid.addWidget(cb_bsave, 0, 0, 1, 3)
        from_path = self.settings.get('bundle_autosave_path') or os.path.join(os.path.expanduser('~'), '.config', 'aurora', 'bundles', 'default.json')
        try:
            os.makedirs(os.path.dirname(from_path), exist_ok=True)
        except Exception:
            pass
        path_edit = QLineEdit(from_path)
        browse_btn = QPushButton("Browse…")
        def on_browse():
            path, _ = QFileDialog.getSaveFileName(self, "Select Bundle Autosave Path", from_path, "Bundle JSON (*.json)")
            if path:
                path_edit.setText(path)
                self._update_setting('bundle_autosave_path', path)
        browse_btn.clicked.connect(on_browse)
        pgrid.addWidget(QLabel("Autosave path:"), 1, 0)
        pgrid.addWidget(path_edit, 1, 1)
        pgrid.addWidget(browse_btn, 1, 2)
        layout.addWidget(path_box)
        
        # Auto Update Settings
        auto_update_box = QGroupBox("Auto Update")
        auto_grid = QGridLayout(auto_update_box)
        cb_auto_update = QCheckBox("Enable automatic updates")
        cb_auto_update.setChecked(bool(self.settings.get('auto_update_enabled')))
        cb_auto_update.toggled.connect(lambda v: self._update_setting('auto_update_enabled', v))
        auto_grid.addWidget(cb_auto_update, 0, 0, 1, 2)
        
        auto_grid.addWidget(QLabel("Update interval (hours):"), 1, 0)
        interval_spin = QSpinBox()
        interval_spin.setRange(1, 168)  # 1 hour to 1 week
        interval_spin.setValue(int(self.settings.get('auto_update_interval_hours', 24)))
        interval_spin.valueChanged.connect(lambda v: self._update_setting('auto_update_interval_hours', v))
        auto_grid.addWidget(interval_spin, 1, 1)
        
        layout.addWidget(auto_update_box)
        
        # Snapshot Settings
        snapshot_box = QGroupBox("Snapshots")
        snap_grid = QGridLayout(snapshot_box)
        cb_snapshot = QCheckBox("Create snapshot before updates")
        cb_snapshot.setChecked(bool(self.settings.get('snapshot_before_update')))
        cb_snapshot.toggled.connect(lambda v: self._update_setting('snapshot_before_update', v))
        snap_grid.addWidget(cb_snapshot, 0, 0, 1, 2)
        
        snap_btns = QHBoxLayout()
        create_snap_btn = QPushButton("Create Snapshot")
        create_snap_btn.clicked.connect(self.create_snapshot)
        snap_btns.addWidget(create_snap_btn)
        
        revert_snap_btn = QPushButton("Revert to Snapshot")
        revert_snap_btn.clicked.connect(self.revert_to_snapshot)
        snap_btns.addWidget(revert_snap_btn)
        
        delete_snap_btn = QPushButton("Delete Snapshots")
        delete_snap_btn.clicked.connect(self.delete_snapshots)
        snap_btns.addWidget(delete_snap_btn)
        
        snap_btns.addStretch()
        snap_grid.addLayout(snap_btns, 1, 0, 1, 2)
        
        layout.addWidget(snapshot_box)
        
        btns = QHBoxLayout()
        btn_export = QPushButton("Export Settings")
        btn_export.clicked.connect(self.export_settings)
        btn_import = QPushButton("Import Settings")
        btn_import.clicked.connect(self.import_settings)
        btns.addWidget(btn_export)
        btns.addWidget(btn_import)
        btns.addStretch()
    
    def _update_setting(self, key, value):
        self.settings[key] = value
        self.save_settings()
    
    def export_settings(self):
        return settings_service.export_settings(self)
    
    def import_settings(self):
        return settings_service.import_settings(self)
    
    # -------------------- Plugin runtime --------------------
    def initialize_plugins(self):
        try:
            self.ensure_default_plugins(force_enable=True)
            self.reload_plugins()
            self.run_plugin_hook('on_startup')
            try:
                self.plugin_timer.start()
            except Exception:
                pass
        except Exception as e:
            self.log(f"Plugin init error: {e}")
    
    def ensure_default_plugins(self, force_enable=False):
        user_dir = self.get_user_plugins_dir()
        defaults = {
            'auto_check_updates.py': (
                """
def on_startup(app):
    try:
        if app.settings.get('auto_check_updates', True):
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(800, lambda: app.switch_view("updates"))
    except Exception as e:
        try:
            app.log(f"auto_check_updates plugin: {e}")
        except Exception:
            pass
                """.strip()
            ),
            'flathub_remote.py': (
                """
def on_startup(app):
    try:
        app.ensure_flathub_user_remote()
    except Exception as e:
        try:
            app.log(f"flathub_remote plugin: {e}")
        except Exception:
            pass
                """.strip()
            ),
            'bundle_autoload.py': (
                """
from PyQt6.QtCore import QTimer
import os, json

def on_view_changed(app, view_id):
    if view_id != "bundles":
        return
    try:
        base = os.path.join(os.path.expanduser('~'), '.config', 'aurora', 'bundles')
        path = os.path.join(base, 'default.json')
        if not os.path.exists(path):
            return
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        items = data.get('items') if isinstance(data, dict) else None
        if not isinstance(items, list):
            return
        existing = {(i.get('source'), (i.get('id') or i.get('name'))) for i in app.bundle_items}
        added = 0
        for it in items:
            if not isinstance(it, dict):
                continue
            src = (it.get('source') or '').strip()
            nm = (it.get('name') or '').strip()
            pid = (it.get('id') or nm).strip()
            if not src or not nm:
                continue
            key = (src, pid or nm)
            if key not in existing:
                app.bundle_items.append({'name': nm, 'id': pid or nm, 'version': (it.get('version') or '').strip(), 'source': src})
                existing.add(key)
                added += 1
        if added:
            try:
                app.refresh_bundles_table()
            except Exception:
                pass
            try:
                app._show_message("Bundle", f"Loaded {added} items from default bundle")
            except Exception:
                pass
    except Exception as e:
        try:
            app.log(f"bundle_autoload plugin: {e}")
        except Exception:
            pass
                """.strip()
            ),
            'notify_install.py': (
                """
from PyQt6.QtWidgets import QMessageBox

def on_startup(app):
    try:
        app.installation_progress.connect(lambda status, can_cancel: _on_status(app, status))
    except Exception:
        pass

def _on_status(app, status):
    try:
        if status == "success":
            QMessageBox.information(app, "Install", "Installation complete.")
        elif status == "failed":
            QMessageBox.warning(app, "Install", "Installation failed. See console for details.")
        elif status == "cancelled":
            QMessageBox.information(app, "Install", "Installation cancelled.")
    except Exception:
        try:
            app._show_message("Install", status)
        except Exception:
            pass
                """.strip()
            ),
            'bundle_autosave.py': (
                """
import os, json, hashlib

_last_hash = None

def _hash_items(items):
    try:
        s = json.dumps(items or [], sort_keys=True)
        return hashlib.sha256(s.encode('utf-8')).hexdigest()
    except Exception:
        return None

def _save(app):
    try:
        if not app.settings.get('bundle_autosave', True):
            return
        path = app.settings.get('bundle_autosave_path')
        if not path:
            return
        os.makedirs(os.path.dirname(path), exist_ok=True)
        items = list(app.bundle_items)
        global _last_hash
        h = _hash_items(items)
        if h and h == _last_hash:
            return
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({'app': 'NeoArch', 'items': items}, f, indent=2)
        _last_hash = h
        try:
            app._show_message('Bundle', f'Autosaved bundle to {path}')
        except Exception:
            pass
    except Exception as e:
        try:
            app.log(f"bundle_autosave plugin: {e}")
        except Exception:
            pass

def on_view_changed(app, view_id):
    if view_id == 'bundles':
        _save(app)

def on_tick(app):
    _save(app)
                """.strip()
            ),
            'auto_refresh_updates.py': (
                """
import time

_last = 0

def on_tick(app):
    global _last
    try:
        minutes = int(app.settings.get('auto_refresh_updates_minutes') or 0)
    except Exception:
        minutes = 0
    if minutes <= 0:
        return
    now = time.time()
    if _last and now - _last < minutes * 60:
        return
    _last = now
    try:
        if app.current_view == 'updates':
            app.load_updates()
    except Exception as e:
        try:
            app.log(f"auto_refresh_updates: {e}")
        except Exception:
            pass
                """.strip()
            ),
            'auto_update.py': (
                """
import time
import subprocess
import os
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QMessageBox

_last_update = 0
_last_check = 0

def on_tick(app):
    global _last_update, _last_check
    try:
        if not app.settings.get('auto_update_enabled', False):
            return
        
        days = int(app.settings.get('auto_update_interval_days', 7))
        interval_seconds = days * 24 * 3600
        
        now = time.time()
        if _last_check and now - _last_check < 3600:  # Check once per hour
            return
        
        _last_check = now
        
        # Check if it's time for update
        if _last_update and now - _last_update < interval_seconds:
            return
        
        # Ask user permission for update
        reply = QMessageBox.question(app, "Scheduled Update", 
                                   f"It's been {days} days since the last update.\n\n"
                                   "Would you like to update your system now?\n\n"
                                   "This will update packages and create snapshots if enabled.",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                   QMessageBox.StandardButton.Yes)
        
        if reply != QMessageBox.StandardButton.Yes:
            # User declined, reset check timer but don't update last_update
            return
        
        _last_update = now
        
        # Create snapshot BEFORE updates if enabled
        if app.settings.get('snapshot_before_update', False):
            try:
                if app.cmd_exists("timeshift"):
                    # Count existing snapshots and clean up if needed
                    try:
                        result = subprocess.run(["timeshift", "--list"], capture_output=True, text=True, timeout=30)
                        if result.returncode == 0:
                            lines = result.stdout.strip().split('\n')
                            snapshot_count = sum(1 for line in lines if line.strip() and not line.startswith('Num') and not line.startswith('---'))
                            
                            # If we have 2 or more snapshots, delete oldest ones to keep only 1
                            if snapshot_count >= 2:
                                delete_result = subprocess.run(["pkexec", "timeshift", "--delete-all", "--skip", "1"], 
                                                             capture_output=True, text=True, timeout=300)
                                if delete_result.returncode == 0:
                                    app.log("Auto-update: Cleaned up old snapshots (keeping latest)")
                                else:
                                    app.log(f"Auto-update: Failed to clean up snapshots: {delete_result.stderr}")
                    except Exception as e:
                        app.log(f"Auto-update: Error checking snapshots: {e}")
                    
                    # Create snapshot before updates
                    timestamp = subprocess.run(["date", "+%Y-%m-%d_%H-%M-%S"], capture_output=True, text=True).stdout.strip()
                    comment = f"NeoArch pre-update snapshot {timestamp}"
                    result = subprocess.run(["pkexec", "timeshift", "--create", "--comments", comment], 
                                          capture_output=True, text=True, timeout=300)
                    if result.returncode == 0:
                        app.log(f"Auto-update: Pre-update snapshot created: {comment}")
                        app.show_message.emit("Snapshot", f"Pre-update snapshot created: {comment}")
                    else:
                        app.log(f"Auto-update: Failed to create pre-update snapshot: {result.stderr}")
            except Exception as e:
                app.log(f"Auto-update: Pre-update snapshot creation failed: {e}")
        
        # Perform updates
        update_success = False
        try:
            app.log("Auto-update: Starting scheduled system updates...")
            
            # Update pacman packages
            if app.cmd_exists("pacman"):
                result = subprocess.run(["pkexec", "pacman", "-Syu", "--noconfirm"], 
                                      capture_output=True, text=True, timeout=1800)
                if result.returncode == 0:
                    app.log("Auto-update: Pacman updates completed successfully")
                    update_success = True
                    app.show_message.emit("Auto Update", "System packages updated successfully")
                else:
                    app.log(f"Auto-update: Pacman update failed: {result.stderr}")
                    app.show_message.emit("Auto Update", f"Pacman update failed: {result.stderr}")
            
            # Update AUR packages if yay is available
            if app.cmd_exists("yay"):
                try:
                    env, _ = app.prepare_askpass_env()
                    result = subprocess.run(["yay", "-Syu", "--noconfirm"], 
                                          capture_output=True, text=True, timeout=1800, env=env)
                    if result.returncode == 0:
                        app.log("Auto-update: AUR updates completed successfully")
                        update_success = True
                    else:
                        app.log(f"Auto-update: AUR update failed: {result.stderr}")
                except Exception as e:
                    app.log(f"Auto-update: AUR update error: {e}")
            
            # Update Flatpak
            if app.cmd_exists("flatpak"):
                scopes = [["--user"], ["--system"]] if app.cmd_exists("sudo") else [["--user"]]
                for scope in scopes:
                    try:
                        result = subprocess.run(["flatpak"] + scope + ["update", "-y"], 
                                              capture_output=True, text=True, timeout=900)
                        if result.returncode == 0:
                            app.log(f"Auto-update: Flatpak {scope[0]} updates completed")
                            update_success = True
                        else:
                            app.log(f"Auto-update: Flatpak {scope[0]} update failed: {result.stderr}")
                    except Exception as e:
                        app.log(f"Auto-update: Flatpak {scope[0]} update error: {e}")
            
            # Update npm global packages
            if app.cmd_exists("npm"):
                try:
                    env = os.environ.copy()
                    npm_prefix = os.path.join(os.path.expanduser('~'), '.npm-global')
                    os.makedirs(npm_prefix, exist_ok=True)
                    env['npm_config_prefix'] = npm_prefix
                    env['NPM_CONFIG_PREFIX'] = npm_prefix
                    env['PATH'] = os.path.join(npm_prefix, 'bin') + os.pathsep + env.get('PATH', '')
                    
                    result = subprocess.run(["npm", "update", "-g"], 
                                          capture_output=True, text=True, timeout=600, env=env)
                    if result.returncode == 0:
                        app.log("Auto-update: NPM global packages updated")
                        update_success = True
                    else:
                        app.log(f"Auto-update: NPM update failed: {result.stderr}")
                except Exception as e:
                    app.log(f"Auto-update: NPM update error: {e}")
                    
        except Exception as e:
            app.log(f"Auto-update: General error: {e}")
        
        if update_success:
            app.show_message.emit("Auto Update", f"System update completed successfully! Next check in {days} days.")
        else:
            app.show_message.emit("Auto Update", "Some updates failed. Check the console for details.")
                """.strip()
            ),
        }
        for fname, code in defaults.items():
            fpath = os.path.join(user_dir, fname)
            if not os.path.exists(fpath):
                try:
                    with open(fpath, 'w', encoding='utf-8') as f:
                        f.write(code + "\n")
                except Exception as e:
                    self.log(f"Default plugin write failed {fname}: {e}")
            if force_enable:
                name = os.path.splitext(fname)[0]
                enabled = set(self.settings.get('enabled_plugins') or [])
                if name not in enabled:
                    enabled.add(name)
                    self.settings['enabled_plugins'] = sorted(enabled)
        if force_enable:
            self.save_settings()
    
    def load_enabled_plugins(self):
        loaded = []
        plugs = {p['name']: p for p in self.scan_plugins()}
        enabled = self.settings.get('enabled_plugins') or []
        for name in enabled:
            p = plugs.get(name)
            if not p:
                continue
            path = p.get('path')
            try:
                spec = importlib.util.spec_from_file_location(name, path)
                if not spec or not spec.loader:
                    continue
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                loaded.append(mod)
            except Exception as e:
                self.log(f"Failed to load plugin {name}: {e}\n{traceback.format_exc()}")
        return loaded
    
    def reload_plugins(self):
        self.plugins = self.load_enabled_plugins()
    
    def reload_plugins_and_notify(self):
        self.reload_plugins()
        self._show_message("Plugins", f"Reloaded {len(self.plugins)} plugin(s)")
    
    def install_default_plugins(self):
        self.ensure_default_plugins(force_enable=True)
        self.refresh_plugins_table()
        self.reload_plugins()
        self._show_message("Plugins", "Default plugins installed and enabled")
    
    def run_plugin_hook(self, hook_name, *args, **kwargs):
        for mod in self.plugins:
            try:
                func = getattr(mod, hook_name, None)
                if callable(func):
                    func(self, *args, **kwargs)
            except Exception as e:
                self.log(f"Plugin hook {hook_name} error: {e}\n{traceback.format_exc()}")
    
    def run_plugin_tick(self):
        try:
            self.run_plugin_hook('on_tick')
        except Exception:
            pass
    
    def _show_message(self, title, text):
        self.log(f"{title}: {text}")
    
    def log(self, message):
        self.console.append(message)
    
    def show_about(self):
        QMessageBox.information(self, "About NeoArch", 
                              "NeoArch - Elevate Your \nArch Experience\nVersion 1.0\n\nBuilt with PyQt6")

    def create_snapshot(self):
        return snapshot_service.create_snapshot(self)

    def revert_to_snapshot(self):
        return snapshot_service.revert_to_snapshot(self)

    def _restore_snapshot(self, snapshot_num):
        return snapshot_service.restore_snapshot(self, snapshot_num)

    def delete_snapshots(self):
        return snapshot_service.delete_snapshots(self)

    def install_plugin(self):
        path, _ = QFileDialog.getOpenFileName(self, "Install Plugin", os.path.expanduser('~'), "Python Plugin (*.py)")
        if not path:
            return
        try:
            dst = os.path.join(self.get_user_plugins_dir(), os.path.basename(path))
            shutil.copy2(path, dst)
            self._show_message("Install Plugin", f"Installed: {os.path.basename(path)}")
            # Refresh plugins table if it exists
            try:
                # Find the plugins widget and refresh it
                if hasattr(self, 'settings_container'):
                    tabs = self.settings_container.widget().findChild(QTabWidget)
                    if tabs:
                        for i in range(tabs.count()):
                            widget = tabs.widget(i)
                            if hasattr(widget, 'refresh_plugins_table'):
                                widget.refresh_plugins_table()
                                break
            except:
                pass
        except Exception as e:
            self._show_message("Install Plugin", f"Failed: {e}")
    
    def remove_selected_plugins(self):
        # This method needs to be called from the plugins settings widget
        # We'll implement it to work with the current table selection
        try:
            # Find the plugins widget and call its remove method
            if hasattr(self, 'settings_container'):
                tabs = self.settings_container.widget().findChild(QTabWidget)
                if tabs:
                    for i in range(tabs.count()):
                        widget = tabs.widget(i)
                        if hasattr(widget, 'remove_selected_plugins'):
                            widget.remove_selected_plugins()
                            break
        except Exception as e:
            self._show_message("Remove Plugins", f"Error: {e}")
    
    def reload_plugins_and_notify(self):
        self.reload_plugins()
        self._show_message("Plugins", f"Reloaded {len(self.plugins)} plugin(s)")
    
    def install_default_plugins(self):
        self.ensure_default_plugins(force_enable=True)
        self.refresh_plugins_table()
        self.reload_plugins()
        self._show_message("Plugins", "Default plugins installed and enabled")
    
    def scan_plugins(self):
        plugs = []
        try:
            user_dir = self.get_user_plugins_dir()
            for fn in sorted(os.listdir(user_dir)):
                if fn.endswith('.py'):
                    plugs.append({'name': os.path.splitext(fn)[0], 'path': os.path.join(user_dir, fn), 'location': 'User'})
        except Exception:
            pass
        return plugs
    
    def refresh_plugins_table(self):
        # This method is used internally by the main class
        # The component will call this if needed
        pass

def main():
    if len(sys.argv) > 1:
        if sys.argv[1] in ["--help", "-h"]:
            print("NeoArch - Elevate Your Arch Experience")
            print("Usage: python aurora_home.py")
            print("A graphical package manager for Arch Linux with AUR support.")
            sys.exit(0)
        else:
            print(f"Unknown option: {sys.argv[1]}")
            print("Use --help for usage information.")
            sys.exit(1)
    
    if os.geteuid() == 0:
        print("Do not run this application as root.")
        sys.exit(1)
    
    window = ArchPkgManagerUniGetUI()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
