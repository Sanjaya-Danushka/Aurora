#!/usr/bin/env python3
import sys
import os
import subprocess
import json
import re
import shutil
import tempfile
from threading import Thread, Event
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLineEdit, QTableWidget, QTableWidgetItem, QTextEdit,
                             QLabel, QFileDialog, QMessageBox, QHeaderView, QFrame, QSplitter,
                             QScrollArea, QCheckBox, QListWidget, QListWidgetItem, QSizePolicy,
                             QDialog, QTabWidget, QGroupBox, QGridLayout, QRadioButton)
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QThread, QSize, QTimer, QRectF, QItemSelectionModel, qInstallMessageHandler, QtMsgType
from PyQt6.QtGui import QColor, QFont, QIcon, QPixmap, QPainter
from PyQt6.QtSvg import QSvgRenderer
from collections import Counter

from git_manager import GitManager

from styles import Styles
from components import SourceCard, FilterCard, LargeSearchBox, LoadingSpinner

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

class PackageLoaderWorker(QObject):
    packages_loaded = pyqtSignal(list)
    error_occurred = pyqtSignal(str)
    finished = pyqtSignal()
    
    def __init__(self, command):
        super().__init__()
        self.command = command
    
    def run(self):
        try:
            result = subprocess.run(self.command, capture_output=True, text=True, timeout=60)
            packages = []
            if result.returncode == 0 and result.stdout:
                for line in result.stdout.strip().split('\n'):
                    if line.strip():
                        parts = line.split()
                        if len(parts) >= 2:
                            packages.append({
                                'name': parts[0],
                                'version': parts[1],
                                'id': parts[0]
                            })
            self.packages_ready.emit(packages)
        except Exception as e:
            self.error_occurred.emit(f"Error: {str(e)}")
        finally:
            self.finished.emit()

class CommandWorker(QObject):
    finished = pyqtSignal()
    output = pyqtSignal(str)
    error = pyqtSignal(str)
    
    def __init__(self, command, sudo=False, env=None):
        super().__init__()
        self.command = command
        self.sudo = sudo
        self.env = env if env is not None else os.environ.copy()
    
    def run(self):
        try:
            if self.sudo:
                self.command = ["pkexec", "--disable-internal-agent"] + self.command
            
            process = subprocess.Popen(
                self.command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                text=True,
                bufsize=1,
                preexec_fn=os.setsid,
                env=self.env
            )
            
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                if line:
                    self.output.emit(line.strip())
            
            _, stderr = process.communicate()
            if stderr and process.returncode != 0:
                self.error.emit(f"Error: {stderr}")
            
            self.finished.emit()
        except Exception as e:
            self.error.emit(f"Error running command: {str(e)}")
            self.finished.emit()
    
    def _command_exists(self, cmd):
        """Check if a command exists in PATH"""
        return subprocess.run(['which', cmd], capture_output=True).returncode == 0

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
            else:
                # Fallback: try to load as regular icon
                painter.end()
                return QIcon(icon_path)

            painter.end()
            return QIcon(pixmap)
        except:
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

    def get_ignore_file_path(self):
        cfg = os.path.join(os.path.expanduser('~'), '.config', 'neoarch')
        try:
            os.makedirs(cfg, exist_ok=True)
        except Exception:
            pass
        return os.path.join(cfg, 'ignored_updates.json')

    def load_ignored_updates(self):
        p = self.get_ignore_file_path()
        try:
            with open(p, 'r') as f:
                data = json.load(f)
            if isinstance(data, list):
                return set(data)
        except Exception:
            pass
        return set()

    def save_ignored_updates(self, items):
        p = self.get_ignore_file_path()
        try:
            with open(p, 'w') as f:
                json.dump(sorted(list(items)), f)
        except Exception:
            pass

    def get_local_updates_file_path(self):
        cfg = os.path.join(os.path.expanduser('~'), '.config', 'neoarch')
        try:
            os.makedirs(cfg, exist_ok=True)
        except Exception:
            pass
        return os.path.join(cfg, 'local_updates.json')

    def load_local_update_entries(self):
        p = self.get_local_updates_file_path()
        try:
            with open(p, 'r') as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
        except Exception:
            pass
        return []

    def cmd_exists(self, cmd):
        return shutil.which(cmd) is not None

    def get_missing_dependencies(self):
        missing = []
        if not self.cmd_exists("flatpak"):
            missing.append("flatpak")
        if not self.cmd_exists("git"):
            missing.append("git")
        if not self.cmd_exists("node"):
            missing.append("nodejs")
        if not self.cmd_exists("npm"):
            missing.append("npm")
        if not self.cmd_exists("docker"):
            missing.append("docker")
        if not self.cmd_exists("yay"):
            missing.append("yay")
        return missing

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
        self.loading_widget.setVisible(True)
        self.loading_widget.set_message("Updating tools...")
        self.loading_widget.start_animation()
        def do_update():
            try:
                deps = ["flatpak", "git", "nodejs", "npm", "docker"]
                if self.cmd_exists("pacman"):
                    w1 = CommandWorker(["pacman", "-Syu", "--noconfirm"] + deps, sudo=True)
                    w1.output.connect(self.log)
                    w1.error.connect(self.log)
                    w1.run()
                try:
                    self.ensure_flathub_user_remote()
                except Exception:
                    pass
                # Flatpak updates mark
                try:
                    update_ids = set()
                    for scope in ([], ["--user"], ["--system"]):
                        cmdu = ["flatpak"] + scope + ["list", "--app", "--updates", "--columns=application,version"]
                        fu = subprocess.run(cmdu, capture_output=True, text=True, timeout=60)
                        if fu.returncode == 0 and fu.stdout:
                            for ln in [x for x in fu.stdout.strip().split('\n') if x.strip()]:
                                cols = ln.split('\t')
                                if cols:
                                    update_ids.add(cols[0].strip())
                    if update_ids:
                        for pkg in packages:
                            if pkg.get('source') == 'Flatpak' and pkg.get('name') in update_ids:
                                pkg['has_update'] = True
                except Exception:
                    pass
                if self.cmd_exists("flatpak"):
                    w2 = CommandWorker(["flatpak", "--user", "update", "-y"], sudo=False)
                    w2.output.connect(self.log)
                    w2.error.connect(self.log)
                    w2.run()
                if self.cmd_exists("npm"):
                    env = os.environ.copy()
                    try:
                        npm_prefix = os.path.join(os.path.expanduser('~'), '.npm-global')
                        os.makedirs(npm_prefix, exist_ok=True)
                        env['npm_config_prefix'] = npm_prefix
                        env['NPM_CONFIG_PREFIX'] = npm_prefix
                        env['PATH'] = os.path.join(npm_prefix, 'bin') + os.pathsep + env.get('PATH', '')
                    except Exception:
                        pass
                    w3 = CommandWorker(["npm", "update", "-g"], sudo=False, env=env)
                    w3.output.connect(self.log)
                    w3.error.connect(self.log)
                    w3.run()
                if self.cmd_exists("yay"):
                    env, _ = self.prepare_askpass_env()
                    w4 = CommandWorker(["yay", "-Syu", "--noconfirm"], sudo=False, env=env)
                    w4.output.connect(self.log)
                    w4.error.connect(self.log)
                    w4.run()
                self.show_message.emit("Environment", "Tools updated")
            except Exception as e:
                self.show_message.emit("Environment", f"Update failed: {str(e)}")
            finally:
                self.loading_widget.stop_animation()
                self.loading_widget.setVisible(False)
        Thread(target=do_update, daemon=True).start()
    
    def get_sudo_askpass(self):
        candidates = [
            "ksshaskpass",
            "ssh-askpass",
            "qt5-askpass",
            "lxqt-openssh-askpass",
        ]
        for c in candidates:
            p = shutil.which(c)
            if p:
                return p
        return None

    def prepare_askpass_env(self):
        env = os.environ.copy()
        cleanup_path = None
        # Always use our custom askpass to ensure consistent UI and messaging
        try:
            script = """#!/bin/sh
title=${NEOARCH_ASKPASS_TITLE:-"NeoArch - AUR Install"}
text=${NEOARCH_ASKPASS_TEXT:-"AUR packages are community-maintained and may be unsafe.\nEnter your password to proceed."}
icon=${NEOARCH_ASKPASS_ICON:-"dialog-password"}
if command -v kdialog >/dev/null 2>&1; then
  kdialog --title "$title" --icon "$icon" --password "$text"
elif command -v zenity >/dev/null 2>&1; then
  zenity --password --title="$title" --text="$text" --window-icon="$icon"
elif command -v yad >/dev/null 2>&1; then
  yad --title="$title" --text="$text" --entry --hide-text --window-icon="$icon"
else
  exit 1
fi
"""
            fd, path = tempfile.mkstemp(prefix="neoarch-askpass-", suffix=".sh")
            with os.fdopen(fd, "w") as f:
                f.write(script)
            os.chmod(path, 0o700)
            cleanup_path = path
            env["SUDO_ASKPASS"] = path
            env["SSH_ASKPASS"] = path
            env["SUDO_ASKPASS_REQUIRE"] = "force"
        except Exception:
            pass
        return env, cleanup_path

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
            else:
                # Fallback: try to load as regular icon
                painter.end()
                return QIcon(icon_path)

            painter.end()
            return QIcon(pixmap)
        except:
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
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        
        # Toolbar
        self.toolbar_widget = QWidget()
        self.toolbar_layout = QVBoxLayout(self.toolbar_widget)
        self.toolbar_layout.setContentsMargins(0,0,0,0)
        layout.addWidget(self.toolbar_widget)
        
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
        
        layout.addWidget(loading_container)
        
        # Large search box for discover page
        self.large_search_box = LargeSearchBox()
        self.large_search_box.search_requested.connect(self.on_large_search_requested)
        layout.addWidget(self.large_search_box)
        
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
        layout.addWidget(self.package_table, 1)
        self.load_more_btn = QPushButton("Load More Packages")
        self.load_more_btn.setMinimumHeight(36)
        icon_dir = os.path.join(os.path.dirname(__file__), "assets", "icons", "discover")
        
        self.load_more_btn.setIcon(self.get_svg_icon(os.path.join(icon_dir, "load-more.svg"), 20))
        self.load_more_btn.clicked.connect(self.load_more_packages)
        self.load_more_btn.setVisible(False)
        layout.addWidget(self.load_more_btn)
        
        # Console Output
        console_label = QLabel("Console Output")
        console_label.setObjectName("sectionLabel")
        layout.addWidget(console_label)
        
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setMaximumHeight(150)
        layout.addWidget(self.console)
        
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
            QTimer.singleShot(0, self.refresh_bundles_table)
    
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
        # Removed verbose log: self.log("Checking for updates...")
        self.package_table.setRowCount(0)
        self.all_packages = []
        self.current_page = 0
        # Prepare updates loading context
        self.cancel_update_load = False
        self.loading_context = "updates"
        
        # Show loading spinner and start animation
        self.loading_widget.setVisible(True)
        self.package_table.setVisible(False)
        self.load_more_btn.setVisible(False)
        self.loading_widget.start_animation()
        
        def load_in_thread():
            try:
                packages = []
                
                # Check for official repository updates
                result = subprocess.run(["pacman", "-Qu"], capture_output=True, text=True, timeout=60)
                if result.returncode == 0 and result.stdout:
                    for line in result.stdout.strip().split('\n'):
                        if line.strip():
                            # Parse format: package_name current_version -> new_version
                            if ' -> ' in line:
                                parts = line.split(' -> ')
                                if len(parts) == 2:
                                    package_info = parts[0].strip().split()
                                    new_version = parts[1].strip()
                                    if len(package_info) >= 2:
                                        package_name = package_info[0]
                                        current_version = package_info[1]
                                        packages.append({
                                            'name': package_name,
                                            'version': current_version,
                                            'new_version': new_version,
                                            'id': package_name,
                                            'source': 'pacman'  # Default to pacman
                                        })
                
                # Check for AUR updates using yay (if available)
                try:
                    result_aur = subprocess.run(["yay", "-Qua"], capture_output=True, text=True, timeout=60)
                    if result_aur.returncode == 0 and result_aur.stdout:
                        for line in result_aur.stdout.strip().split('\n'):
                            if line.strip():
                                # Parse format: package_name current_version -> new_version
                                if ' -> ' in line:
                                    parts = line.split(' -> ')
                                    if len(parts) == 2:
                                        package_info = parts[0].strip().split()
                                        new_version = parts[1].strip()
                                        if len(package_info) >= 2:
                                            package_name = package_info[0]
                                            current_version = package_info[1]
                                            packages.append({
                                                'name': package_name,
                                                'version': current_version,
                                                'new_version': new_version,
                                                'id': package_name,
                                                'source': 'AUR'
                                            })
                except (subprocess.CalledProcessError, FileNotFoundError):
                    # yay not available, try other AUR helpers
                    for aur_helper in ['paru', 'trizen', 'pikaur']:
                        try:
                            result_aur = subprocess.run([aur_helper, "-Qua"], capture_output=True, text=True, timeout=60)
                            if result_aur.returncode == 0 and result_aur.stdout:
                                for line in result_aur.stdout.strip().split('\n'):
                                    if line.strip():
                                        if ' -> ' in line:
                                            parts = line.split(' -> ')
                                            if len(parts) == 2:
                                                package_info = parts[0].strip().split()
                                                new_version = parts[1].strip()
                                                if len(package_info) >= 2:
                                                    package_name = package_info[0]
                                                    current_version = package_info[1]
                                                    packages.append({
                                                        'name': package_name,
                                                        'version': current_version,
                                                        'new_version': new_version,
                                                        'id': package_name,
                                                        'source': 'AUR'
                                                    })
                                break  # Found a working AUR helper, stop trying others
                        except (subprocess.CalledProcessError, FileNotFoundError):
                            continue
                # Check for Flatpak updates (installed apps with updates)
                added_flatpak = False
                try:
                    # Build installed app -> installed version map (cover both user and system scopes)
                    installed_map = {}
                    for scope in ([], ["--user"], ["--system"]):
                        try:
                            cmd = ["flatpak"] + scope + ["list", "--app", "--columns=application,version"]
                            li = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                            if li.returncode == 0 and li.stdout:
                                for ln in [x for x in li.stdout.strip().split('\n') if x.strip()]:
                                    c = ln.split('\t')
                                    if c and c[0].strip():
                                        installed_map[c[0].strip()] = (c[1].strip() if len(c) > 1 else '')
                        except Exception:
                            continue

                    seen_apps = set()
                    # Prefer direct list of installed updates across scopes
                    for scope in ([], ["--user"], ["--system"]):
                        try:
                            cmd = ["flatpak"] + scope + ["list", "--app", "--updates", "--columns=application,version"]
                            fp = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                            if fp.returncode == 0 and fp.stdout:
                                for line in [l for l in fp.stdout.strip().split('\n') if l.strip()]:
                                    cols = line.split('\t')
                                    app_id = cols[0].strip() if len(cols) > 0 else ''
                                    inst = cols[1].strip() if len(cols) > 1 else ''
                                    if app_id and app_id not in seen_apps:
                                        packages.append({
                                            'name': app_id,
                                            'version': inst or installed_map.get(app_id, ''),
                                            'new_version': '',
                                            'id': app_id,
                                            'source': 'Flatpak'
                                        })
                                        seen_apps.add(app_id)
                                        added_flatpak = True
                        except Exception:
                            continue

                    # Fallback: query remotes for updates and intersect with installed apps
                    if not added_flatpak:
                        try:
                            rl = subprocess.run(["flatpak", "remote-ls", "--updates", "--columns=application,version"], capture_output=True, text=True, timeout=60)
                            if rl.returncode == 0 and rl.stdout:
                                for ln in [x for x in rl.stdout.strip().split('\n') if x.strip()]:
                                    c = ln.split('\t')
                                    app_id = c[0].strip() if len(c) > 0 else ''
                                    latest = c[1].strip() if len(c) > 1 else ''
                                    if app_id and app_id in installed_map and app_id not in seen_apps:
                                        packages.append({
                                            'name': app_id,
                                            'version': installed_map.get(app_id, ''),
                                            'new_version': latest,
                                            'id': app_id,
                                            'source': 'Flatpak'
                                        })
                                        seen_apps.add(app_id)
                                        added_flatpak = True
                        except Exception:
                            pass
                except Exception:
                    pass
                # Check for npm global updates in both default and user-prefix envs, merge results
                try:
                    results = []
                    # default env
                    np_def = subprocess.run(["npm", "outdated", "-g", "--json"], capture_output=True, text=True, timeout=60)
                    results.append((np_def.returncode, np_def.stdout))
                    # user-prefix env
                    env_user = os.environ.copy()
                    try:
                        npm_prefix = os.path.join(os.path.expanduser('~'), '.npm-global')
                        os.makedirs(npm_prefix, exist_ok=True)
                        env_user['npm_config_prefix'] = npm_prefix
                        env_user['NPM_CONFIG_PREFIX'] = npm_prefix
                        env_user['PATH'] = os.path.join(npm_prefix, 'bin') + os.pathsep + env_user.get('PATH', '')
                    except Exception:
                        pass
                    np_user = subprocess.run(["npm", "outdated", "-g", "--json"], capture_output=True, text=True, env=env_user, timeout=60)
                    results.append((np_user.returncode, np_user.stdout))
                    seen = set()
                    for code, out in results:
                        if code in (0, 1) and out and out.strip():
                            try:
                                data = json.loads(out)
                                if isinstance(data, dict):
                                    for name, info in data.items():
                                        cur = (info.get('current') or info.get('installed') or '').strip()
                                        lat = (info.get('latest') or '').strip()
                                        key = (name, cur, lat)
                                        if name and cur and lat and cur != lat and key not in seen:
                                            packages.append({
                                                'name': name,
                                                'version': cur,
                                                'new_version': lat,
                                                'id': name,
                                                'source': 'npm'
                                            })
                                            seen.add(key)
                            except Exception:
                                pass
                except Exception:
                    pass
                # Check for Local updates via config
                try:
                    entries = self.load_local_update_entries()
                    for e in entries:
                        name = (e.get('name') or '').strip()
                        if not name:
                            continue
                        installed = (e.get('installed_version') or '').strip()
                        if not installed and e.get('installed_version_cmd'):
                            try:
                                r = subprocess.run(["bash", "-lc", e['installed_version_cmd']], capture_output=True, text=True, timeout=30)
                                if r.returncode == 0:
                                    installed = (r.stdout or '').strip().splitlines()[0].strip()
                            except Exception:
                                installed = ''
                        latest = (e.get('latest_version') or '').strip()
                        if not latest and e.get('latest_version_cmd'):
                            try:
                                r = subprocess.run(["bash", "-lc", e['latest_version_cmd']], capture_output=True, text=True, timeout=30)
                                if r.returncode == 0:
                                    latest = (r.stdout or '').strip().splitlines()[0].strip()
                            except Exception:
                                latest = ''
                        if installed and latest and installed != latest:
                            packages.append({
                                'name': name,
                                'version': installed,
                                'new_version': latest,
                                'id': (e.get('id') or name),
                                'source': 'Local'
                            })
                except Exception:
                    pass
                try:
                    ignored = self.load_ignored_updates()
                    if ignored:
                        packages = [p for p in packages if p.get('name') not in ignored]
                except Exception:
                    pass
                # Only deliver results if still on Updates and not cancelled
                if not self.cancel_update_load and self.loading_context == 'updates' and self.current_view == 'updates':
                    self.packages_ready.emit(packages)
            except Exception as e:
                self.log(f"Error: {str(e)}")
                self.load_error.emit()
        
        Thread(target=load_in_thread, daemon=True).start()
    
    def load_installed_packages(self):
        # Removed verbose log: self.log("Loading installed packages...")
        self.package_table.setRowCount(0)
        self.all_packages = []
        self.current_page = 0
        # Mark context to avoid cross-view UI updates
        self.loading_context = "installed"
        
        def load_in_thread():
            try:
                result = subprocess.run(["pacman", "-Q"], capture_output=True, text=True, timeout=60)
                packages = []
                updates = {}
                
                if result.returncode == 0 and result.stdout:
                    lines = result.stdout.strip().split('\n')
                    for i, line in enumerate(lines):
                        if line.strip():
                            parts = line.split()
                            if len(parts) >= 2:
                                packages.append({
                                    'name': parts[0],
                                    'version': parts[1],
                                    'id': parts[0],
                                    'source': 'pacman',
                                    'has_update': False
                                })
                        if i % 100 == 0 and i > 0:
                            import time
                            time.sleep(0.01)
                
                result_updates = subprocess.run(["pacman", "-Qu"], capture_output=True, text=True, timeout=30)
                if result_updates.returncode == 0 and result_updates.stdout:
                    for line in result_updates.stdout.strip().split('\n'):
                        if line.strip():
                            parts = line.split()
                            if len(parts) >= 2:
                                updates[parts[0]] = parts[2] if len(parts) > 2 else parts[1]
                
                for pkg in packages:
                    if pkg['name'] in updates:
                        pkg['has_update'] = True
                        pkg['new_version'] = updates[pkg['name']]
                
                result_aur = subprocess.run(["pacman", "-Qm"], capture_output=True, text=True, timeout=30)
                aur_packages = set()
                if result_aur.returncode == 0 and result_aur.stdout:
                    for line in result_aur.stdout.strip().split('\n'):
                        if line.strip():
                            parts = line.split()
                            if len(parts) >= 1:
                                aur_packages.add(parts[0])
                
                for pkg in packages:
                    if pkg['name'] in aur_packages:
                        pkg['source'] = 'AUR'
                # AUR updates using helper
                try:
                    aur_updates = {}
                    helper = None
                    # Prefer yay, fallback others
                    for h in ['yay', 'paru', 'trizen', 'pikaur']:
                        try:
                            r = subprocess.run([h, "-Qua"], capture_output=True, text=True, timeout=60)
                            if r.returncode in (0, 1):
                                helper = h
                                output = (r.stdout or '').strip()
                                if output:
                                    for ln in [x for x in output.split('\n') if x.strip()]:
                                        # try to parse: name old -> new  OR name new
                                        parts = ln.split()
                                        if len(parts) >= 2:
                                            name = parts[0]
                                            # if contains '->', new version likely at end
                                            if '->' in ln:
                                                try:
                                                    new_v = parts[-1]
                                                except Exception:
                                                    new_v = ''
                                            else:
                                                new_v = parts[1]
                                            aur_updates[name] = new_v
                                break
                        except Exception:
                            continue
                    if aur_updates:
                        for pkg in packages:
                            if pkg.get('source') == 'AUR' and pkg['name'] in aur_updates:
                                pkg['has_update'] = True
                                pkg['new_version'] = aur_updates.get(pkg['name'], pkg.get('new_version', ''))
                except Exception:
                    pass

                # Flatpak installed apps (build installed map across scopes)
                try:
                    installed_map = {}
                    seen = set()
                    for scope in ([], ["--user"], ["--system"]):
                        cmd = ["flatpak"] + scope + ["list", "--app", "--columns=application,version"]
                        fp = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                        if fp.returncode == 0 and fp.stdout:
                            for ln in [x for x in fp.stdout.strip().split('\n') if x.strip()]:
                                c = ln.split('\t')
                                app_id = c[0].strip() if len(c) > 0 else ''
                                ver = c[1].strip() if len(c) > 1 else ''
                                if app_id:
                                    installed_map[app_id] = ver
                                if app_id and app_id not in seen:
                                    packages.append({
                                        'name': app_id,
                                        'version': ver,
                                        'id': app_id,
                                        'source': 'Flatpak',
                                        'has_update': False
                                    })
                                    seen.add(app_id)
                except Exception:
                    pass
                # Flatpak updates mark
                try:
                    update_ids = set()
                    for scope in ([], ["--user"], ["--system"]):
                        cmdu = ["flatpak"] + scope + ["list", "--app", "--updates", "--columns=application,version"]
                        fu = subprocess.run(cmdu, capture_output=True, text=True, timeout=60)
                        if fu.returncode == 0 and fu.stdout:
                            for ln in [x for x in fu.stdout.strip().split('\n') if x.strip()]:
                                cols = ln.split('\t')
                                if cols:
                                    update_ids.add(cols[0].strip())
                    if not update_ids:
                        # Fallback to remote-ls and intersect with installed_map
                        try:
                            rl = subprocess.run(["flatpak", "remote-ls", "--updates", "--columns=application,version"], capture_output=True, text=True, timeout=60)
                            if rl.returncode == 0 and rl.stdout:
                                for ln in [x for x in rl.stdout.strip().split('\n') if x.strip()]:
                                    c = ln.split('\t')
                                    app_id = c[0].strip() if len(c) > 0 else ''
                                    latest = c[1].strip() if len(c) > 1 else ''
                                    if app_id and app_id in installed_map:
                                        update_ids.add(app_id)
                                        # annotate new_version if we can
                                        for pkg in packages:
                                            if pkg.get('source') == 'Flatpak' and pkg.get('name') == app_id:
                                                if latest:
                                                    pkg['new_version'] = latest
                        except Exception:
                            pass
                    if update_ids:
                        for pkg in packages:
                            if pkg.get('source') == 'Flatpak' and pkg.get('name') in update_ids:
                                pkg['has_update'] = True
                except Exception:
                    pass
                # npm global packages
                try:
                    np = subprocess.run(["npm", "ls", "-g", "--depth=0", "--json"], capture_output=True, text=True, timeout=60)
                    if np.returncode == 0 and np.stdout:
                        data = json.loads(np.stdout)
                        deps = (data.get('dependencies') or {}) if isinstance(data, dict) else {}
                        for name, info in deps.items():
                            ver = (info.get('version') or '').strip()
                            if name and ver:
                                packages.append({
                                    'name': name,
                                    'version': ver,
                                    'id': name,
                                    'source': 'npm',
                                    'has_update': False
                                })
                except Exception:
                    pass
                # npm outdated mark
                try:
                    results = []
                    np_def = subprocess.run(["npm", "outdated", "-g", "--json"], capture_output=True, text=True, timeout=60)
                    results.append((np_def.returncode, np_def.stdout))
                    env_user = os.environ.copy()
                    try:
                        npm_prefix = os.path.join(os.path.expanduser('~'), '.npm-global')
                        os.makedirs(npm_prefix, exist_ok=True)
                        env_user['npm_config_prefix'] = npm_prefix
                        env_user['NPM_CONFIG_PREFIX'] = npm_prefix
                        env_user['PATH'] = os.path.join(npm_prefix, 'bin') + os.pathsep + env_user.get('PATH', '')
                    except Exception:
                        pass
                    np_user = subprocess.run(["npm", "outdated", "-g", "--json"], capture_output=True, text=True, env=env_user, timeout=60)
                    results.append((np_user.returncode, np_user.stdout))
                    outdated = {}
                    for code, out in results:
                        if code in (0, 1) and out and out.strip():
                            try:
                                data = json.loads(out)
                                if isinstance(data, dict):
                                    for name, info in data.items():
                                        lat = (info.get('latest') or '').strip()
                                        cur = (info.get('current') or info.get('installed') or '').strip()
                                        if name and lat and cur and cur != lat:
                                            outdated[name] = lat
                            except Exception:
                                pass
                    if outdated:
                        for pkg in packages:
                            if pkg.get('source') == 'npm' and pkg.get('name') in outdated:
                                pkg['has_update'] = True
                                pkg['new_version'] = outdated[pkg['name']]
                except Exception:
                    pass
                # Local entries and update mark
                try:
                    entries = self.load_local_update_entries()
                    for e in entries:
                        name = (e.get('name') or '').strip()
                        if not name:
                            continue
                        installed = (e.get('installed_version') or '').strip()
                        if not installed and e.get('installed_version_cmd'):
                            try:
                                r = subprocess.run(["bash", "-lc", e['installed_version_cmd']], capture_output=True, text=True, timeout=30)
                                if r.returncode == 0 and r.stdout:
                                    installed = (r.stdout or '').strip().splitlines()[0].strip()
                            except Exception:
                                installed = ''
                        latest = (e.get('latest_version') or '').strip()
                        if not latest and e.get('latest_version_cmd'):
                            try:
                                r = subprocess.run(["bash", "-lc", e['latest_version_cmd']], capture_output=True, text=True, timeout=30)
                                if r.returncode == 0 and r.stdout:
                                    latest = (r.stdout or '').strip().splitlines()[0].strip()
                            except Exception:
                                latest = ''
                        if installed:
                            pkg = {
                                'name': name,
                                'version': installed,
                                'new_version': latest or installed,
                                'id': (e.get('id') or name),
                                'source': 'Local',
                                'has_update': (bool(latest) and latest != installed)
                            }
                            packages.append(pkg)
                except Exception:
                    pass

                # Apply ignored updates mask like Updates page
                try:
                    ignored = self.load_ignored_updates()
                    if ignored:
                        for pkg in packages:
                            if pkg.get('name') in ignored and pkg.get('has_update'):
                                pkg['has_update'] = False
                except Exception:
                    pass
                
                self.packages_ready.emit(packages)
            except Exception as e:
                self.log(f"Error: {str(e)}")
                self.load_error.emit()
        
        Thread(target=load_in_thread, daemon=True).start()
    
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
        
        # Show loading spinner
        self.loading_widget.setVisible(True)
        self.loading_widget.set_message("Searching packages...")
        self.loading_widget.start_animation()
        self.package_table.setVisible(False)
        
        def search_in_thread():
            try:
                packages = []
                
                tokens = [t for t in query.split() if t]
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
                    except:
                        pass
                
                try:
                    self.ensure_flathub_user_remote()
                except Exception:
                    pass
                result_flatpak = subprocess.run([
                    "flatpak", "search", "--columns=application,name,description,version", query
                ], capture_output=True, text=True, timeout=30)
                if result_flatpak.returncode == 0 and result_flatpak.stdout:
                    lines = [l for l in result_flatpak.stdout.strip().split('\n') if l.strip()]
                    for line in lines:
                        cols = line.split('\t')
                        if not cols:
                            continue
                        app_id = cols[0].strip() if len(cols) > 0 else ''
                        app_name = cols[1].strip() if len(cols) > 1 and cols[1].strip() else app_id
                        description = cols[2].strip() if len(cols) > 2 else ''
                        version = cols[3].strip() if len(cols) > 3 else ''
                        if app_id:
                            packages.append({
                                'name': app_name,
                                'version': version,
                                'id': app_id,
                                'source': 'Flatpak',
                                'description': description,
                                'has_update': False
                            })
                
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
        def update():
            try:
                for source, pkgs in packages_by_source.items():
                    if source == 'pacman':
                        cmd = ["pacman", "-S", "--noconfirm"] + pkgs
                        worker = CommandWorker(cmd, sudo=True)
                        worker.output.connect(self.log)
                        worker.error.connect(self.log)
                        worker.run()
                    elif source == 'AUR':
                        env, _ = self.prepare_askpass_env()
                        cmd = ["yay", "-S", "--noconfirm"] + pkgs
                        worker = CommandWorker(cmd, sudo=False, env=env)
                        worker.output.connect(self.log)
                        worker.error.connect(self.log)
                        worker.run()
                    elif source == 'Flatpak':
                        cmd = ["flatpak", "update", "-y", "--noninteractive"] + pkgs
                        worker = CommandWorker(cmd, sudo=False)
                        worker.output.connect(self.log)
                        worker.error.connect(self.log)
                        worker.run()
                    elif source == 'npm':
                        env = os.environ.copy()
                        try:
                            npm_prefix = os.path.join(os.path.expanduser('~'), '.npm-global')
                            os.makedirs(npm_prefix, exist_ok=True)
                            env['npm_config_prefix'] = npm_prefix
                            env['NPM_CONFIG_PREFIX'] = npm_prefix
                            env['PATH'] = os.path.join(npm_prefix, 'bin') + os.pathsep + env.get('PATH', '')
                        except Exception:
                            pass
                        cmd = ["npm", "update", "-g"] + pkgs
                        worker = CommandWorker(cmd, sudo=False, env=env)
                        worker.output.connect(self.log)
                        worker.error.connect(self.log)
                        worker.run()
                    elif source == 'Local':
                        entries = { (e.get('id') or e.get('name')): e for e in self.load_local_update_entries() }
                        for token in pkgs:
                            e = entries.get(token) or entries.get(token.strip())
                            if not e:
                                continue
                            upd = e.get('update_cmd')
                            if not upd:
                                continue
                            try:
                                process = subprocess.Popen(["bash", "-lc", upd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                                while True:
                                    line = process.stdout.readline() if process.stdout else ""
                                    if not line and process.poll() is not None:
                                        break
                                    if line:
                                        self.log(line.strip())
                                _, stderr = process.communicate()
                                if process.returncode != 0 and stderr:
                                    self.log(f"Error: {stderr}")
                            except Exception as ex:
                                self.log(str(ex))
                self.show_message.emit("Update Complete", f"Successfully updated {sum(len(v) for v in packages_by_source.values())} package(s).")
                QTimer.singleShot(0, self.refresh_packages)
            except Exception as e:
                self.log(f"Error in update thread: {str(e)}")
        Thread(target=update, daemon=True).start()
    
    def ignore_selected(self):
        items = []
        for row in range(self.package_table.rowCount()):
            checkbox = self.get_row_checkbox(row)
            if checkbox is not None and checkbox.isChecked():
                name_item = self.package_table.item(row, 1)
                if name_item:
                    items.append(name_item.text().strip())
        if not items:
            self.log("No packages selected to ignore")
            return
        ignored = self.load_ignored_updates()
        for n in items:
            ignored.add(n)
        self.save_ignored_updates(ignored)
        self.log(f"Ignored {len(items)} package(s)")
        if self.current_view == "updates":
            self.load_updates()
    
    def manage_ignored(self):
        ignored = sorted(self.load_ignored_updates())
        dlg = QDialog(self)
        dlg.setWindowTitle("Manage Ignored Updates")
        v = QVBoxLayout()
        hdr = QLabel(f"Ignored packages: {len(ignored)}")
        v.addWidget(hdr)
        search = QLineEdit()
        search.setPlaceholderText("Filter packages...")
        v.addWidget(search)
        tbl = QTableWidget()
        tbl.setColumnCount(5)
        tbl.setHorizontalHeaderLabels(["", "Package", "Source", "Installed", "Available"])
        tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        tbl.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        tbl.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        tbl.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        v.addWidget(tbl)
        row = QWidget()
        h = QHBoxLayout(row)
        btn_unignore = QPushButton("Unignore Selected")
        btn_unall = QPushButton("Unignore All")
        btn_close = QPushButton("Close")
        h.addWidget(btn_unignore)
        h.addWidget(btn_unall)
        h.addStretch()
        h.addWidget(btn_close)
        v.addWidget(row)

        installed = {}
        try:
            r = subprocess.run(["pacman", "-Q"], capture_output=True, text=True, timeout=20)
            if r.returncode == 0 and r.stdout:
                for ln in r.stdout.strip().split('\n'):
                    ps = ln.split()
                    if len(ps) >= 2:
                        installed[ps[0]] = ps[1]
        except Exception:
            pass
        aur_set = set()
        try:
            r = subprocess.run(["pacman", "-Qm"], capture_output=True, text=True, timeout=10)
            if r.returncode == 0 and r.stdout:
                for ln in r.stdout.strip().split('\n'):
                    ps = ln.split()
                    if ps:
                        aur_set.add(ps[0])
        except Exception:
            pass
        new_versions = {}
        try:
            r = subprocess.run(["pacman", "-Qu"], capture_output=True, text=True, timeout=20)
            if r.returncode == 0 and r.stdout:
                for ln in r.stdout.strip().split('\n'):
                    if ' -> ' in ln:
                        left, nv = ln.split(' -> ', 1)
                        nm = left.split()[0]
                        new_versions[nm] = nv.strip()
        except Exception:
            pass
        try:
            r = subprocess.run(["yay", "-Qua"], capture_output=True, text=True, timeout=20)
            if r.returncode == 0 and r.stdout:
                for ln in r.stdout.strip().split('\n'):
                    if ' -> ' in ln:
                        left, nv = ln.split(' -> ', 1)
                        nm = left.split()[0]
                        new_versions[nm] = nv.strip()
        except Exception:
            pass

        tbl.setRowCount(len(ignored))
        for i, name in enumerate(ignored):
            cb = QCheckBox()
            cb.setObjectName("tableCheckbox")
            w = QWidget()
            l = QHBoxLayout(w)
            l.setContentsMargins(0,0,0,0)
            l.addWidget(cb)
            l.addStretch()
            tbl.setCellWidget(i, 0, w)
            tbl.setItem(i, 1, QTableWidgetItem(name))
            src = "AUR" if name in aur_set else "pacman"
            tbl.setItem(i, 2, QTableWidgetItem(src))
            tbl.setItem(i, 3, QTableWidgetItem(installed.get(name, "")))
            tbl.setItem(i, 4, QTableWidgetItem(new_versions.get(name, "")))

        def apply_filter(text):
            t = text.strip().lower()
            for r in range(tbl.rowCount()):
                nm = tbl.item(r,1).text().lower() if tbl.item(r,1) else ""
                tbl.setRowHidden(r, t not in nm)
        search.textChanged.connect(apply_filter)

        def unignore_selected():
            sel = []
            for r in range(tbl.rowCount()):
                w = tbl.cellWidget(r, 0)
                if not w:
                    continue
                chks = w.findChildren(QCheckBox)
                if chks and chks[0].isChecked():
                    nm = tbl.item(r,1).text()
                    sel.append(nm)
            if sel:
                s = self.load_ignored_updates()
                for nm in sel:
                    s.discard(nm)
                self.save_ignored_updates(s)
                for r in reversed(range(tbl.rowCount())):
                    w = tbl.cellWidget(r,0)
                    if not w:
                        continue
                    chks = w.findChildren(QCheckBox)
                    if chks and chks[0].isChecked():
                        tbl.removeRow(r)
                QTimer.singleShot(0, self.refresh_packages)
        btn_unignore.clicked.connect(unignore_selected)

        def unignore_all():
            self.save_ignored_updates(set())
            tbl.setRowCount(0)
            QTimer.singleShot(0, self.refresh_packages)
        btn_unall.clicked.connect(unignore_all)

        btn_close.clicked.connect(dlg.accept)
        dlg.setLayout(v)
        dlg.resize(820, 520)
        dlg.exec()

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
        items = []
        for row in range(self.package_table.rowCount()):
            checkbox = self.get_row_checkbox(row)
            if checkbox is not None and checkbox.isChecked():
                info = self.get_row_info(row)
                if info.get("name") and info.get("source"):
                    items.append(info)
        if not items:
            self.log("No selected rows to add to bundle")
            return
        # de-dupe by (source, id/name)
        existing = {(i.get('source'), i.get('id') or i.get('name')) for i in self.bundle_items}
        added = 0
        for it in items:
            key = (it.get('source'), it.get('id') or it.get('name'))
            if key not in existing:
                self.bundle_items.append(it)
                existing.add(key)
                added += 1
        self.log(f"Added {added} item(s) to bundle")
        if self.current_view == "bundles":
            self.refresh_bundles_table()

    def refresh_bundles_table(self):
        if self.current_view != "bundles":
            return
        self.package_table.setRowCount(0)
        self.package_table.setUpdatesEnabled(False)
        for it in self.bundle_items:
            # Reuse discover-like row rendering
            pkg = {
                'name': it.get('name', ''),
                'id': it.get('id') or it.get('name', ''),
                'version': it.get('version', ''),
                'source': it.get('source', ''),
            }
            self.add_discover_row(pkg)
        self.package_table.setUpdatesEnabled(True)
        try:
            self.package_table.clearSelection()
        except Exception:
            pass

        self.load_more_btn.setVisible(False)
        # Ensure table is visible in Bundles view
        try:
            self.package_table.setVisible(True)
        except Exception:
            pass

    def export_bundle(self):
        if not self.bundle_items:
            self._show_message("Export Bundle", "Bundle is empty")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export Bundle", os.path.expanduser("~"), "Bundle JSON (*.json)")
        if not path:
            return
        data = {"app": "NeoArch", "items": self.bundle_items}
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            self._show_message("Export Bundle", f"Saved {len(self.bundle_items)} items to {path}")
        except Exception as e:
            self._show_message("Export Bundle", f"Failed: {e}")

    def import_bundle(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import Bundle", os.path.expanduser("~"), "Bundle JSON (*.json)")
        if not path:
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            items = data.get('items') if isinstance(data, dict) else None
            if not isinstance(items, list):
                self._show_message("Import Bundle", "Invalid bundle file")
                return
            existing = {(i.get('source'), i.get('id') or i.get('name')) for i in self.bundle_items}
            added = 0
            for it in items:
                if not isinstance(it, dict):
                    continue
                src = (it.get('source') or '').strip()
                nm = (it.get('name') or '').strip()
                pkg_id = (it.get('id') or nm).strip()
                if not src or not nm:
                    continue
                key = (src, pkg_id or nm)
                if key not in existing:
                    self.bundle_items.append({
                        'name': nm,
                        'id': pkg_id or nm,
                        'version': (it.get('version') or '').strip(),
                        'source': src,
                    })
                    existing.add(key)
                    added += 1
            self._show_message("Import Bundle", f"Added {added} items")
            if self.current_view == "bundles":
                self.refresh_bundles_table()
        except Exception as e:
            self._show_message("Import Bundle", f"Failed: {e}")

    def remove_selected_from_bundle(self):
        if self.current_view != "bundles":
            return
        keys_to_remove = []
        for row in range(self.package_table.rowCount()):
            chk = self.get_row_checkbox(row)
            if chk is not None and chk.isChecked():
                info = self.get_row_info(row, view_id='bundles')
                keys_to_remove.append((info.get('source'), info.get('id') or info.get('name')))
        if not keys_to_remove:
            self.log("No selected items to remove from bundle")
            return
        before = len(self.bundle_items)
        self.bundle_items = [it for it in self.bundle_items if (it.get('source'), it.get('id') or it.get('name')) not in keys_to_remove]
        removed = before - len(self.bundle_items)
        self.log(f"Removed {removed} items from bundle")
        self.refresh_bundles_table()

    def clear_bundle(self):
        if not self.bundle_items:
            return
        self.bundle_items = []
        self.refresh_bundles_table()

    def install_bundle(self):
        if not self.bundle_items:
            self._show_message("Install Bundle", "Bundle is empty")
            return
        items = list(self.bundle_items)
        # install in thread
        def run():
            try:
                by_src = {}
                for it in items:
                    src = it.get('source') or 'pacman'
                    name = it.get('name') or ''
                    pkg_id = it.get('id') or name
                    if not name:
                        continue
                    by_src.setdefault(src, []).append(pkg_id if src == 'Flatpak' else name)
                for src, lst in by_src.items():
                    if not lst:
                        continue
                    if src == 'pacman':
                        cmd = ["pacman", "-S", "--noconfirm"] + lst
                        w = CommandWorker(cmd, sudo=True)
                        w.output.connect(self.log); w.error.connect(self.log); w.run()
                    elif src == 'AUR':
                        env, _ = self.prepare_askpass_env()
                        cmd = ["yay", "-S", "--noconfirm"] + lst
                        w = CommandWorker(cmd, sudo=False, env=env)
                        w.output.connect(self.log); w.error.connect(self.log); w.run()
                    elif src == 'Flatpak':
                        cmd = ["flatpak", "install", "-y", "--noninteractive"] + lst
                        w = CommandWorker(cmd, sudo=False)
                        w.output.connect(self.log); w.error.connect(self.log); w.run()
                    elif src == 'npm':
                        env = os.environ.copy()
                        try:
                            npm_prefix = os.path.join(os.path.expanduser('~'), '.npm-global')
                            os.makedirs(npm_prefix, exist_ok=True)
                            env['npm_config_prefix'] = npm_prefix
                            env['NPM_CONFIG_PREFIX'] = npm_prefix
                            env['PATH'] = os.path.join(npm_prefix, 'bin') + os.pathsep + env.get('PATH', '')
                        except Exception:
                            pass
                        cmd = ["npm", "install", "-g"] + lst
                        w = CommandWorker(cmd, sudo=False, env=env)
                        w.output.connect(self.log); w.error.connect(self.log); w.run()
                    elif src == 'Local':
                        entries = { (e.get('id') or e.get('name')): e for e in self.load_local_update_entries() }
                        for token in lst:
                            e = entries.get(token) or entries.get(token.strip())
                            if not e:
                                continue
                            cmd = e.get('install_cmd') or e.get('update_cmd')
                            if not cmd:
                                continue
                            try:
                                process = subprocess.Popen(["bash", "-lc", cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                                while True:
                                    line = process.stdout.readline() if process.stdout else ""
                                    if not line and process.poll() is not None:
                                        break
                                    if line:
                                        self.log(line.strip())
                                _, stderr = process.communicate()
                                if process.returncode != 0 and stderr:
                                    self.log(f"Error: {stderr}")
                            except Exception as ex:
                                self.log(str(ex))
                self.show_message.emit("Install Bundle", f"Installed {sum(len(v) for v in by_src.values())} package(s)")
            except Exception as e:
                self.log(f"Bundle install error: {str(e)}")
        Thread(target=run, daemon=True).start()
    
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
        
        def install():
            self.install_cancel_event = Event()
            self.installation_progress.emit("start", True)  # Start with cancel enabled
            self.log_signal.emit("Installation thread started")
            
            success = True
            current_download_info = ""
            
            # Calculate total packages and sources for progress tracking
            total_packages = sum(len(pkgs) for pkgs in packages_by_source.values())
            total_sources = len(packages_by_source)
            completed_packages = 0
            completed_sources = 0
            
            def update_progress_message(msg=""):
                """Update the loading spinner message with overall progress"""
                if completed_sources == total_sources:
                    percentage = 100
                else:
                    # Show progress based on sources completed
                    percentage = int((completed_sources / total_sources) * 100) if total_sources > 0 else 0
                
                base_msg = f"Installing: {completed_packages}/{total_packages} packages ({percentage}%)"
                if current_download_info and msg:
                    self.loading_widget.set_message(f"{base_msg}\n{current_download_info}")
                elif current_download_info:
                    self.loading_widget.set_message(f"{base_msg}\n{current_download_info}")
                elif msg:
                    self.loading_widget.set_message(f"{base_msg}\n{msg}")
                else:
                    self.loading_widget.set_message(base_msg)
            
            def parse_output_line(line):
                """Parse pacman/yay output for download information"""
                nonlocal current_download_info
                
                # Look for download progress lines
                if "downloading" in line.lower() and ("mib" in line.lower() or "kib" in line.lower() or "gib" in line.lower()):
                    # Extract size information from "downloading package.tar.xz (10.5 MiB)"
                    size_match = re.search(r'\(([\d.]+)\s*(MiB|KiB|GiB|B)\)', line)
                    if size_match:
                        size, unit = size_match.groups()
                        current_download_info = f"Downloading {size} {unit}"
                        update_progress_message("")
                
                # Look for progress bar lines like "package.tar.xz ... 10.5 MiB/s 00:30 [####################] 100%"
                elif re.search(r'\[.*\]\s*\d+%', line):
                    progress_match = re.search(r'(\d+)%', line)
                    if progress_match:
                        percentage = progress_match.group(1)
                        if current_download_info:
                            current_download_info = f"{current_download_info} - {percentage}%"
                        else:
                            current_download_info = f"Downloading... {percentage}%"
                        update_progress_message("")
                
                # Reset download info when download completes
                elif "installed" in line.lower() or "upgraded" in line.lower():
                    current_download_info = ""
                    update_progress_message("")
            
            try:
                for source, packages in packages_by_source.items():
                    if self.install_cancel_event.is_set():
                        self.log_signal.emit("Installation cancelled by user")
                        self.installation_progress.emit("cancelled", False)
                        return
                    
                    update_progress_message(f"Installing from {source}...")
                    
                    if source == 'pacman':
                        cmd = ["pacman", "-S", "--noconfirm"] + packages
                    elif source == 'AUR':
                        cmd = [
                            "yay",
                            "-S", "--noconfirm",
                            "--sudoloop",
                            "--answerclean", "None",
                            "--answerdiff", "None",
                            "--answeredit", "None"
                        ] + packages
                    elif source == 'Flatpak':
                        try:
                            self.ensure_flathub_user_remote()
                        except Exception:
                            pass
                        cmd = ["flatpak", "--user", "install", "-y", "flathub"] + packages
                    elif source == 'npm':
                        cmd = ["npm", "install", "--location=user"] + packages
                    else:
                        self.log_signal.emit(f"Unknown source {source} for packages {packages}")
                        continue
                    
                    self.log_signal.emit(f"Running command for {source}: {' '.join(cmd)}")
                    
                    # Check for cancellation before each command
                    if self.install_cancel_event.is_set():
                        self.log_signal.emit("Installation cancelled by user")
                        self.installation_progress.emit("cancelled", False)
                        return
                    
                    # Prepare environment and worker
                    env = os.environ.copy()
                    cleanup_path = None
                    if source == 'AUR':
                        env, cleanup_path = self.prepare_askpass_env()
                        # Configure git to use HTTPS instead of SSH for GitHub URLs
                        # This prevents "Permission denied (publickey)" errors during AUR builds
                        env['GIT_CONFIG_KEY_0'] = 'url.https://github.com/.insteadOf'
                        env['GIT_CONFIG_VALUE_0'] = 'git@github.com:'
                        env['GIT_CONFIG_KEY_1'] = 'url.https://github.com/.insteadOf'  
                        env['GIT_CONFIG_VALUE_1'] = 'ssh://git@github.com/'
                        env['GIT_CONFIG_COUNT'] = '2'
                        # Customize prompt content
                        try:
                            title = "NeoArch - Confirm AUR Install"
                            if len(packages) <= 3:
                                pkg_list = ", ".join(packages)
                            else:
                                pkg_list = ", ".join(packages[:3]) + f" and {len(packages)-3} more"
                            text = (
                                "AUR packages are community-maintained and may be unsafe.\n"
                                f"Packages: {pkg_list}\n\n"
                                "Enter your password to proceed."
                            )
                            env["NEOARCH_ASKPASS_TITLE"] = title
                            env["NEOARCH_ASKPASS_TEXT"] = text
                            env["NEOARCH_ASKPASS_ICON"] = "dialog-password"
                        except Exception:
                            pass
                    worker = CommandWorker(cmd, sudo=(source == 'pacman'), env=env)
                    worker.output.connect(lambda msg: self.log_signal.emit(msg))
                    worker.error.connect(lambda msg: self.log_signal.emit(msg))
                    
                    # Also connect to parse download progress
                    worker.output.connect(parse_output_line)
                    
                    # Run the command with cancellation check
                    try:
                        exec_cmd = worker.command
                        if source == 'pacman':
                            exec_cmd = ["pkexec", "--disable-internal-agent"] + exec_cmd
                        process = subprocess.Popen(
                            exec_cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            stdin=subprocess.DEVNULL,
                            text=True,
                            bufsize=1,
                            preexec_fn=os.setsid,
                            env=worker.env
                        )
                        

                        while True:
                            if self.install_cancel_event.is_set():
                                process.terminate()
                                try:
                                    process.wait(timeout=5)
                                except subprocess.TimeoutExpired:
                                    process.kill()
                                self.log_signal.emit("Installation cancelled by user")
                                self.installation_progress.emit("cancelled", False)
                                return
                                
                            if process.poll() is not None:
                                break
                            
                            # Read output
                            if process.stdout:
                                line = process.stdout.readline()
                                if line:
                                    line = line.strip()
                                    parse_output_line(line)
                                    worker.output.emit(line)
                            
                            import time
                            time.sleep(0.1)  # Small delay to prevent busy waiting
                        
                        # Check return code
                        if process.returncode == 0:
                            # Success - increment completed packages and sources
                            completed_packages += len(packages)
                            completed_sources += 1
                            update_progress_message(f"Completed {source} packages")
                            self.log_signal.emit(f"Successfully installed {len(packages)} {source} package(s)")
                        else:
                            success = False
                            if process.stderr:
                                error_output = process.stderr.read()
                                if error_output:
                                    error_text = f"Error: {error_output}"
                                    # Check for tar ownership error
                                    if "Cannot change ownership" in error_output and "Value too large for defined data type" in error_output:
                                        error_text += "\n\nThis error occurs when tar tries to set file ownership to UIDs/GIDs that don't exist in the current environment.\n"
                                        error_text += "To fix this, you can modify the PKGBUILD to add '--no-same-owner' to the tar command.\n"
                                        error_text += "For example, change 'tar -xzf file.tar.gz' to 'tar -xzf file.tar.gz --no-same-owner'"
                                    worker.error.emit(error_text)
                            break
                    finally:
                        # Remove temporary askpass script if created
                        if source == 'AUR' and cleanup_path and os.path.exists(cleanup_path):
                            try:
                                os.remove(cleanup_path)
                            except Exception:
                                pass
                
                if success and not self.install_cancel_event.is_set():
                    update_progress_message("Installation complete!")
                    self.log_signal.emit("Install completed")
                    self.show_message.emit("Installation Complete", f"Successfully installed {total_packages} package(s).")
                    self.installation_progress.emit("success", False)
                elif not success and not self.install_cancel_event.is_set():
                    self.log_signal.emit("Install failed")
                    self.installation_progress.emit("failed", False)
                    
            except Exception as e:
                self.log_signal.emit(f"Error in installation thread: {str(e)}")
                self.installation_progress.emit("failed", False)
            finally:
                if hasattr(self, 'install_cancel_event'):
                    delattr(self, 'install_cancel_event')
        
        Thread(target=install, daemon=True).start()
    
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
        
        def uninstall():
            self.log("Uninstallation thread started")
            try:
                for source, pkgs in packages_by_source.items():
                    if not pkgs:
                        continue
                    if source in ('pacman', 'AUR'):
                        cmd = ["pacman", "-R", "--noconfirm"] + pkgs
                        self.log(f"Running: {' '.join(cmd)}")
                        worker = CommandWorker(cmd, sudo=True)
                        worker.output.connect(self.log)
                        worker.error.connect(self.log)
                        worker.run()
                    elif source == 'Flatpak':
                        cmd = ["flatpak", "uninstall", "-y", "--noninteractive"] + pkgs
                        self.log(f"Running: {' '.join(cmd)}")
                        worker = CommandWorker(cmd, sudo=False)
                        worker.output.connect(self.log)
                        worker.error.connect(self.log)
                        worker.run()
                    elif source == 'npm':
                        env = os.environ.copy()
                        try:
                            npm_prefix = os.path.join(os.path.expanduser('~'), '.npm-global')
                            os.makedirs(npm_prefix, exist_ok=True)
                            env['npm_config_prefix'] = npm_prefix
                            env['NPM_CONFIG_PREFIX'] = npm_prefix
                            env['PATH'] = os.path.join(npm_prefix, 'bin') + os.pathsep + env.get('PATH', '')
                        except Exception:
                            pass
                        cmd = ["npm", "uninstall", "-g"] + pkgs
                        self.log(f"Running: {' '.join(cmd)}")
                        worker = CommandWorker(cmd, sudo=False, env=env)
                        worker.output.connect(self.log)
                        worker.error.connect(self.log)
                        worker.run()
                self.show_message.emit("Uninstallation Complete", f"Successfully processed {sum(len(v) for v in packages_by_source.values())} package(s).")
                QTimer.singleShot(0, self.load_installed_packages)
            except Exception as e:
                self.log(f"Error in uninstallation thread: {str(e)}")
        
        Thread(target=uninstall, daemon=True).start()
    
    def apply_filters(self):
        if self.current_view != "installed":
            return
        base = getattr(self, 'installed_all', []) or []
        # Filter by SourceCard selection
        selected_sources = {"pacman": True, "AUR": True, "Flatpak": True, "npm": True, "Local": True}
        if hasattr(self, 'source_card') and self.source_card:
            try:
                selected_sources.update(self.source_card.get_selected_sources())
            except Exception:
                pass
        filtered_by_source = []
        for pkg in base:
            s = pkg.get('source')
            if s in selected_sources and selected_sources.get(s, True):
                filtered_by_source.append(pkg)
        # Filter by status (Updates/Installed)
        selected_filters = {"Updates available": True, "Installed": True}
        if hasattr(self, 'filter_card') and self.filter_card:
            try:
                selected_filters = self.filter_card.get_selected_filters()
            except Exception:
                pass
        show_updates = selected_filters.get("Updates available", True)
        show_installed = selected_filters.get("Installed", True)
        final = []
        for pkg in filtered_by_source:
            if pkg.get('has_update') and show_updates:
                final.append(pkg)
            elif not pkg.get('has_update') and show_installed:
                final.append(pkg)
        # Display via standard paginator
        self.all_packages = final
        self.current_page = 0
        self.package_table.setRowCount(0)
        self.display_page()

    def apply_update_filters(self):
        if self.current_view != "updates" or not self.all_packages:
            return
        
        # Use SourceCard selection (available in Updates view) to filter sources
        selected_sources = {}
        if hasattr(self, 'source_card') and self.source_card:
            try:
                selected_sources = self.source_card.get_selected_sources()
            except Exception:
                selected_sources = {}
        # Fallback to enabling all known sources in Updates view
        if not selected_sources:
            selected_sources = {"pacman": True, "AUR": True, "Flatpak": True, "npm": True, "Local": True}

        show_pacman = selected_sources.get("pacman", True)
        show_aur = selected_sources.get("AUR", True)
        show_flatpak = selected_sources.get("Flatpak", True)
        show_npm = selected_sources.get("npm", True)
        show_local = selected_sources.get("Local", True)

        filtered = []
        for pkg in self.all_packages:
            src = pkg.get('source')
            if src == 'pacman' and show_pacman:
                filtered.append(pkg)
            elif src == 'AUR' and show_aur:
                filtered.append(pkg)
            elif src == 'Flatpak' and show_flatpak:
                filtered.append(pkg)
            elif src == 'npm' and show_npm:
                filtered.append(pkg)
            elif src == 'Local' and show_local:
                filtered.append(pkg)

        # Update the all_packages to show filtered results
        self.all_packages = filtered
        self.current_page = 0
        self.package_table.setRowCount(0)
        self.display_page()
        self.log(
            f"Filtered to {len(filtered)} packages "
            f"(pacman: {show_pacman}, AUR: {show_aur}, Flatpak: {show_flatpak}, npm: {show_npm}, Local: {show_local})"
        )

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
    
    def show_settings(self):
        QMessageBox.information(self, "Settings", "Settings dialog coming soon")
    
    def _show_message(self, title, text):
        self.log(f"{title}: {text}")
    
    def log(self, message):
        self.console.append(message)
    
    def show_about(self):
        QMessageBox.information(self, "About NeoArch", 
                              "NeoArch - Elevate Your \nArch Experience\nVersion 1.0\n\nBuilt with PyQt6")

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
