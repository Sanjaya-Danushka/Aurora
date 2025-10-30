#!/usr/bin/env python3
import sys
import os
import subprocess
import json
from threading import Thread
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLineEdit, QTableWidget, QTableWidgetItem, QTextEdit,
                             QLabel, QFileDialog, QMessageBox, QHeaderView, QFrame, QSplitter,
                             QScrollArea, QCheckBox, QListWidget, QListWidgetItem, QSizePolicy,
                             QDialog, QTabWidget, QGroupBox, QGridLayout)
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QThread, QSize, QTimer, QRectF, QItemSelectionModel
from PyQt6.QtGui import QColor, QFont, QIcon, QPixmap, QPainter
from PyQt6.QtSvg import QSvgRenderer

from git_manager import GitManager

from styles import Styles


class GitDialog(QDialog):
    """Dialog for Git repository management with clear button structure"""
    
    def __init__(self, log_signal, show_message_signal, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Git Repository Manager")
        self.setModal(True)
        self.setMinimumSize(600, 700)
        self.setMaximumSize(800, 900)
        self.setStyleSheet("""
            QDialog {
                background-color: #1E1E1E;
                color: #F0F0F0;
                border: 1px solid rgba(0, 191, 174, 0.2);
            }
        """)
        
        # Create main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Title
        title = QLabel("Git Repository Manager")
        title.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                color: #00BFAE;
                margin-bottom: 10px;
            }
        """)
        layout.addWidget(title)
        
        # Create tab widget for different sections
        tab_widget = QTabWidget()
        tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid rgba(0, 191, 174, 0.2);
                background-color: rgba(42, 45, 51, 0.3);
            }
            QTabBar::tab {
                background-color: rgba(42, 45, 51, 0.5);
                color: #F0F0F0;
                padding: 8px 16px;
                margin-right: 2px;
                border-radius: 4px 4px 0 0;
            }
            QTabBar::tab:selected {
                background-color: rgba(0, 191, 174, 0.2);
                color: #00BFAE;
            }
            QTabBar::tab:hover {
                background-color: rgba(42, 45, 51, 0.7);
            }
        """)
        
        # Tab 1: Repository Actions
        actions_tab = QWidget()
        actions_layout = QVBoxLayout(actions_tab)
        actions_layout.setContentsMargins(15, 15, 15, 15)
        actions_layout.setSpacing(15)
        
        # Main Action Section
        main_action_group = self.create_group_box("Repository Installation")
        main_action_layout = QVBoxLayout(main_action_group)
        main_action_layout.setSpacing(10)
        
        install_git_btn = self.create_primary_button("📥 Install from Git Repository", "Clone and install a Git repository")
        install_git_btn.clicked.connect(lambda: self.show_git_install_dialog(log_signal, show_message_signal))
        main_action_layout.addWidget(install_git_btn)
        
        main_action_group.setLayout(main_action_layout)
        actions_layout.addWidget(main_action_group)
        
        # Repository Management Section
        manage_group = self.create_group_box("Repository Management")
        manage_layout = QVBoxLayout(manage_group)
        manage_layout.setSpacing(10)
        
        # Create button grid
        button_grid = QWidget()
        grid_layout = QGridLayout(button_grid)
        grid_layout.setSpacing(8)
        
        open_repos_btn = self.create_secondary_button("📁 Open Repos", "Open git-repos directory")
        open_repos_btn.clicked.connect(lambda: self.open_git_repos_dir(log_signal))
        grid_layout.addWidget(open_repos_btn, 0, 0)
        
        update_all_btn = self.create_secondary_button("🔄 Update All", "Update all Git repositories")
        update_all_btn.clicked.connect(lambda: self.update_all_git_repos(log_signal, show_message_signal))
        grid_layout.addWidget(update_all_btn, 0, 1)
        
        clean_repos_btn = self.create_danger_button("🗑️ Clean", "Clean build artifacts")
        clean_repos_btn.clicked.connect(lambda: self.clean_git_repos(log_signal, show_message_signal))
        grid_layout.addWidget(clean_repos_btn, 1, 0)
        
        manage_layout.addWidget(button_grid)
        manage_group.setLayout(manage_layout)
        actions_layout.addWidget(manage_group)
        
        actions_layout.addStretch()
        tab_widget.addTab(actions_tab, "Actions")
        
        # Tab 2: Recent Repositories
        repos_tab = QWidget()
        repos_layout = QVBoxLayout(repos_tab)
        repos_layout.setContentsMargins(15, 15, 15, 15)
        repos_layout.setSpacing(15)
        
        recent_group = self.create_group_box("Recent Repositories")
        recent_layout = QVBoxLayout(recent_group)
        recent_layout.setSpacing(10)
        
        # Recent repos list
        self.recent_repos_list = QListWidget()
        self.recent_repos_list.setStyleSheet("""
            QListWidget {
                background-color: rgba(42, 45, 51, 0.4);
                border: 1px solid rgba(0, 191, 174, 0.15);
                color: #F0F0F0;
                font-size: 11px;
                min-height: 200px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid rgba(0, 191, 174, 0.1);
            }
            QListWidget::item:hover {
                background-color: rgba(0, 191, 174, 0.15);
            }
            QListWidget::item:selected {
                background-color: rgba(0, 191, 174, 0.25);
                color: #00BFAE;
            }
        """)
        self.recent_repos_list.itemDoubleClicked.connect(lambda item: self.open_repo_directory(item, log_signal))
        
        refresh_btn = self.create_secondary_button("🔄 Refresh List", "Refresh the recent repositories list")
        refresh_btn.clicked.connect(lambda: self.load_recent_git_repos())
        
        recent_layout.addWidget(QLabel("Double-click to open repository:"))
        recent_layout.addWidget(self.recent_repos_list)
        recent_layout.addWidget(refresh_btn)
        
        recent_group.setLayout(recent_layout)
        repos_layout.addWidget(recent_group)
        
        repos_layout.addStretch()
        tab_widget.addTab(repos_tab, "Repositories")
        
        layout.addWidget(tab_widget)
        
        # Bottom button bar
        button_bar = QWidget()
        button_layout = QHBoxLayout(button_bar)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(10)
        
        button_layout.addStretch()
        
        close_btn = QPushButton("Close")
        close_btn.setFixedSize(100, 35)
        close_btn.clicked.connect(self.accept)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(42, 45, 51, 0.6);
                color: #F0F0F0;
                border: 1px solid rgba(0, 191, 174, 0.2);
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: rgba(42, 45, 51, 0.8);
                border-color: rgba(0, 191, 174, 0.4);
            }
        """)
        button_layout.addWidget(close_btn)
        
        layout.addWidget(button_bar)
        
        # Load recent repos
        self.load_recent_git_repos()
    
    def create_group_box(self, title):
        """Create a styled group box"""
        group = QGroupBox(title)
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                color: #00BFAE;
                border: 2px solid rgba(0, 191, 174, 0.3);
                border-radius: 6px;
                margin-top: 1ex;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #00BFAE;
                font-size: 13px;
            }
        """)
        return group
    
    def create_primary_button(self, text, tooltip):
        """Create a primary action button"""
        btn = QPushButton(text)
        btn.setToolTip(tooltip)
        btn.setMinimumHeight(40)
        btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 191, 174, 0.8);
                color: #1E1E1E;
                border: 1px solid rgba(0, 191, 174, 0.3);
                border-radius: 6px;
                padding: 10px 16px;
                font-size: 12px;
                font-weight: 500;
                text-align: left;
            }
            QPushButton:hover {
                background-color: rgba(0, 191, 174, 0.9);
                border-color: rgba(0, 191, 174, 0.5);
            }
            QPushButton:pressed {
                background-color: rgba(0, 191, 174, 0.7);
            }
        """)
        return btn
    
    def create_secondary_button(self, text, tooltip):
        """Create a secondary action button"""
        btn = QPushButton(text)
        btn.setToolTip(tooltip)
        btn.setMinimumHeight(35)
        btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(42, 45, 51, 0.5);
                color: #F0F0F0;
                border: 1px solid rgba(0, 191, 174, 0.15);
                border-radius: 4px;
                padding: 8px 12px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: rgba(42, 45, 51, 0.7);
                border-color: rgba(0, 191, 174, 0.35);
                color: #00BFAE;
            }
        """)
        return btn
    
    def create_danger_button(self, text, tooltip):
        """Create a danger/action button"""
        btn = QPushButton(text)
        btn.setToolTip(tooltip)
        btn.setMinimumHeight(35)
        btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(220, 53, 69, 0.2);
                color: #FF6B6B;
                border: 1px solid rgba(220, 53, 69, 0.3);
                border-radius: 4px;
                padding: 8px 12px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: rgba(220, 53, 69, 0.3);
                border-color: rgba(220, 53, 69, 0.5);
                color: #FF9999;
            }
        """)
        return btn
    
    def show_git_install_dialog(self, log_signal, show_message_signal):
        """Show the Git installation dialog"""
        from git_manager import GitManager
        git_manager = GitManager(log_signal, show_message_signal, None)
        git_manager.install_from_git()
    
    def open_git_repos_dir(self, log_signal):
        """Open the git-repos directory"""
        git_repos_dir = os.path.expanduser("~/git-repos")
        try:
            if os.path.exists(git_repos_dir):
                subprocess.run(["xdg-open", git_repos_dir], check=True)
                log_signal.emit("Opened git-repos directory")
            else:
                log_signal.emit("git-repos directory doesn't exist yet")
                QMessageBox.information(self, "No Repos Yet", "You haven't cloned any Git repositories yet.\nUse 'Install from Git' to get started!")
        except Exception as e:
            log_signal.emit(f"Failed to open directory: {e}")
    
    def update_all_git_repos(self, log_signal, show_message_signal):
        """Update all Git repositories"""
        git_repos_dir = os.path.expanduser("~/git-repos")
        if not os.path.exists(git_repos_dir):
            log_signal.emit("No git-repos directory found")
            return
        
        repos = [d for d in os.listdir(git_repos_dir)
                if os.path.isdir(os.path.join(git_repos_dir, d)) and
                os.path.exists(os.path.join(git_repos_dir, d, ".git"))]
        
        if not repos:
            log_signal.emit("No Git repositories found")
            return
        
        log_signal.emit(f"Updating {len(repos)} Git repositories...")
        
        def update_thread():
            updated = 0
            failed = 0
            for repo in repos:
                repo_path = os.path.join(git_repos_dir, repo)
                try:
                    log_signal.emit(f"Updating {repo}...")
                    result = subprocess.run(["git", "-C", repo_path, "pull"],
                                          capture_output=True, text=True, timeout=60)
                    if result.returncode == 0:
                        updated += 1
                        log_signal.emit(f"✓ Updated {repo}")
                    else:
                        failed += 1
                        log_signal.emit(f"✗ Failed to update {repo}: {result.stderr.strip()}")
                except Exception as e:
                    failed += 1
                    log_signal.emit(f"✗ Error updating {repo}: {e}")
            
            log_signal.emit(f"Update complete: {updated} updated, {failed} failed")
            if updated > 0 or failed > 0:
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(0, lambda: show_message_signal.emit("Git Update Complete", f"Updated {updated} repos, {failed} failed"))
        
        import threading
        threading.Thread(target=update_thread, daemon=True).start()
    
    def clean_git_repos(self, log_signal, show_message_signal):
        """Clean Git repositories"""
        git_repos_dir = os.path.expanduser("~/git-repos")
        if not os.path.exists(git_repos_dir):
            log_signal.emit("No git-repos directory found")
            return
        
        repos = [d for d in os.listdir(git_repos_dir)
                if os.path.isdir(os.path.join(git_repos_dir, d)) and
                os.path.exists(os.path.join(git_repos_dir, d, ".git"))]
        
        if not repos:
            log_signal.emit("No Git repositories found")
            return
        
        reply = QMessageBox.question(
            self, "Clean Git Repositories",
            f"This will clean build artifacts from {len(repos)} repositories.\n\n"
            "This will run 'git clean -fdx' and remove untracked and ignored files.\n"
            "Are you sure you want to continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        log_signal.emit(f"Cleaning {len(repos)} Git repositories...")
        
        def clean_thread():
            cleaned = 0
            failed = 0
            for repo in repos:
                repo_path = os.path.join(git_repos_dir, repo)
                try:
                    log_signal.emit(f"Cleaning {repo}...")
                    result = subprocess.run(["git", "-C", repo_path, "clean", "-fdx"],
                                          capture_output=True, text=True, timeout=30)
                    if result.returncode == 0:
                        cleaned += 1
                        log_signal.emit(f"✓ Cleaned {repo}")
                    else:
                        failed += 1
                        log_signal.emit(f"✗ Failed to clean {repo}: {result.stderr.strip()}")
                except Exception as e:
                    failed += 1
                    log_signal.emit(f"✗ Error cleaning {repo}: {e}")
            
            log_signal.emit(f"Clean complete: {cleaned} cleaned, {failed} failed")
            if cleaned > 0 or failed > 0:
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(0, lambda: show_message_signal.emit("Git Clean Complete", f"Cleaned {cleaned} repos, {failed} failed"))
        
        import threading
        threading.Thread(target=clean_thread, daemon=True).start()
    
    def load_recent_git_repos(self):
        """Load recent Git repositories"""
        git_repos_dir = os.path.expanduser("~/git-repos")
        if not os.path.exists(git_repos_dir):
            self.recent_repos_list.clear()
            return
        
        repos = []
        try:
            for item in os.listdir(git_repos_dir):
                repo_path = os.path.join(git_repos_dir, item)
                if os.path.isdir(repo_path) and os.path.exists(os.path.join(repo_path, ".git")):
                    mtime = os.path.getmtime(repo_path)
                    repos.append((item, mtime, repo_path))
            
            repos.sort(key=lambda x: x[1], reverse=True)
            recent_repos = repos[:5]
            
            self.recent_repos_list.clear()
            for repo_name, _, repo_path in recent_repos:
                item = QListWidgetItem(f"📁 {repo_name}")
                item.setToolTip(f"Double-click to open: {repo_path}")
                item.setData(Qt.ItemDataRole.UserRole, repo_path)
                self.recent_repos_list.addItem(item)
                
        except Exception as e:
            print(f"Error loading recent repos: {e}")
    
    def open_repo_directory(self, item, log_signal):
        """Open repository directory"""
        repo_path = item.data(Qt.ItemDataRole.UserRole)
        if repo_path and os.path.exists(repo_path):
            try:
                subprocess.run(["xdg-open", repo_path], check=True)
                log_signal.emit(f"Opened repository: {os.path.basename(repo_path)}")
            except Exception as e:
                log_signal.emit(f"Failed to open repository: {e}")

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
    
    def __init__(self, command, sudo=False):
        super().__init__()
        self.command = command
        self.sudo = sudo
    
    def run(self):
        try:
            if self.sudo:
                self.command = ["pkexec", "--disable-internal-agent"] + self.command
            
            process = subprocess.Popen(
                self.command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
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

class ArchPkgManagerUniGetUI(QMainWindow):
    packages_ready = pyqtSignal(list)
    discover_results_ready = pyqtSignal(list)
    show_message = pyqtSignal(str, str)
    log_signal = pyqtSignal(str)
    load_error = pyqtSignal()
    search_timer = QTimer()
    
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
        self.packages_ready.connect(self.on_packages_loaded)
        self.discover_results_ready.connect(self.display_discover_results)
        self.show_message.connect(self._show_message)
        self.log_signal.connect(self.log)
        self.load_error.connect(self.on_load_error)
        self.setup_ui()
        # Set initial nav button state
        for btn_id, btn in self.nav_buttons.items():
            btn.setChecked(btn_id == self.current_view)
        self.center_window()
        
        # Initialize the default view
        self.switch_view(self.current_view)
        
        # Debounce search input
        self.search_timer.setInterval(300)
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.perform_search)
        self.search_input.textChanged.connect(self.on_search_text_changed)

    def on_search_text_changed(self):
        self.search_timer.start()

    def perform_search(self):
        query = self.search_input.text().strip()
        if len(query) < 3:
            self.package_table.setRowCount(0)
            self.log("Type a package name to search in AUR and official repositories")
            return
        if self.current_view == "discover":
            self.search_discover_packages(query)
        else:
            self.filter_packages()

    def set_minimal_icon(self):
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        painter.setBrush(QColor(0, 212, 255))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(4, 4, 56, 56)
        
        font = QFont("Segoe UI", 32, QFont.Weight.Bold)
        painter.setFont(font)
        painter.setPen(QColor(26, 26, 26))
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "A")
        
        painter.end()
        
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
        
        # Icon label - large and prominent
        icon_label = QLabel()
        icon_label.setObjectName("navIcon")
        icon_label.setFixedSize(50, 50)  # Larger icon container
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Try to load and render SVG in white
        try:
            svg_renderer = QSvgRenderer(icon_path)
            if svg_renderer.isValid():
                # Create pixmap and render SVG in white
                pixmap = QPixmap(50, 50)
                pixmap.fill(Qt.GlobalColor.transparent)
                
                painter = QPainter(pixmap)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
                
                try:
                    # Set composition mode and color for white rendering
                    svg_renderer.render(painter, QRectF(pixmap.rect()))
                    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                    painter.fillRect(pixmap.rect(), QColor("white"))
                except:
                    pass  # If render fails, leave pixmap transparent
                
                painter.end()
                icon_label.setPixmap(pixmap)
            else:
                raise
        except:
            # Fallback to black icon or emoji
            icon = QIcon(icon_path)
            if not icon.isNull():
                icon_label.setPixmap(icon.pixmap(50, 50))
            else:
                emoji = self.get_fallback_icon(icon_path)
                icon_label.setText(emoji)
        
        layout.addWidget(icon_label, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Text label - below icon
        text_label = QLabel(text)
        text_label.setObjectName("navText")
        text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)  # Center align text
        layout.addWidget(text_label, alignment=Qt.AlignmentFlag.AlignCenter)
        
        layout.addStretch()
        
        btn.clicked.connect(lambda checked, v=view_id: self.switch_view(v))
        
        return btn
    
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
        try:
            svg_renderer = QSvgRenderer(icon_path)
            if svg_renderer.isValid():
                # Create pixmap and render SVG in white
                pixmap = QPixmap(28, 28)  # Match icon size
                pixmap.fill(Qt.GlobalColor.transparent)
                
                painter = QPainter(pixmap)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
                
                try:
                    from PyQt6.QtCore import QRectF
                    svg_renderer.render(painter, QRectF(pixmap.rect()))
                    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                    painter.fillRect(pixmap.rect(), QColor("white"))
                except:
                    pass
                
                painter.end()
                icon_label.setPixmap(pixmap)
            else:
                raise
        except:
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
        else:
            return "📦"
    
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
        
        def get_white_icon_pixmap(path, size=20):
            pixmap = QPixmap(size, size)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            renderer = QSvgRenderer(path)
            if renderer.isValid():
                try:
                    renderer.render(painter, QRectF(pixmap.rect()))
                    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                    painter.fillRect(pixmap.rect(), QColor("white"))
                except:
                    pass
            painter.end()
            return pixmap
        
        refresh_btn.setIcon(QIcon(get_white_icon_pixmap(os.path.join(icon_dir, "refresh.svg"))))
        refresh_btn.setToolTip("Refresh")
        refresh_btn.clicked.connect(self.refresh_packages)
        layout.addWidget(refresh_btn)
        
        return header
    
    def show_git_dialog(self):
        """Show Git repository management dialog"""
        dialog = GitDialog(self.log_signal, self.show_message, self)
        dialog.exec()
    
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
        
        sources_label = QLabel("Sources")
        sources_label.setObjectName("sectionLabel")
        self.sources_layout.addWidget(sources_label)
        
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
        self.loading_widget = QWidget()
        self.loading_widget.setObjectName("loadingSpinner")
        self.loading_widget.setVisible(False)  # Hidden by default
        loading_layout = QVBoxLayout(self.loading_widget)
        loading_layout.setContentsMargins(0, 20, 0, 20)
        loading_layout.setSpacing(12)
        loading_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Simple spinner using QLabel with programmatic animation
        self.spinner_label = QLabel("⟳")
        self.spinner_label.setFixedSize(48, 48)
        self.spinner_label.setStyleSheet(Styles.get_spinner_label_stylesheet())
        loading_layout.addWidget(self.spinner_label, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Set up timer for animation
        self.spinner_timer = QTimer()
        self.spinner_timer.timeout.connect(self.animate_spinner)
        self.spinner_angle = 0
        
        # Loading text
        loading_label = QLabel("Checking for updates...")
        loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_layout.addWidget(loading_label)
        
        layout.addWidget(self.loading_widget)
        
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
        
        def get_white_icon_pixmap(path, size=20):
            pixmap = QPixmap(size, size)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            renderer = QSvgRenderer(path)
            if renderer.isValid():
                
                try:
                    renderer.render(painter, QRectF(pixmap.rect()))
                    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                    painter.fillRect(pixmap.rect(), QColor("white"))
                except:
                    pass
            painter.end()
            return pixmap
        
        self.load_more_btn.setIcon(QIcon(get_white_icon_pixmap(os.path.join(icon_dir, "load-more.svg"))))
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
            
            update_btn = QPushButton("⬇️  Update selected packages")
            update_btn.setMinimumHeight(36)
            update_btn.clicked.connect(self.update_selected)
            layout.addWidget(update_btn)
            
            ignore_btn = QPushButton("🚫  Ignore selected packages")
            ignore_btn.setMinimumHeight(36)
            ignore_btn.clicked.connect(self.ignore_selected)
            layout.addWidget(ignore_btn)
            
            manage_btn = QPushButton("📋  Manage ignored updates")
            manage_btn.setMinimumHeight(36)
            manage_btn.clicked.connect(self.manage_ignored)
            layout.addWidget(manage_btn)
            
            layout.addStretch()
            self.toolbar_layout.addLayout(layout)
        elif self.current_view == "installed":
            
            layout.addStretch()
            self.toolbar_layout.addLayout(layout)
        elif self.current_view == "discover":
            layout = QHBoxLayout()
            layout.setSpacing(12)
            
            install_btn = QPushButton("Install selected packages")
            install_btn.setMinimumHeight(36)
            install_btn.clicked.connect(self.install_selected)
            icon_dir = os.path.join(os.path.dirname(__file__), "assets", "icons", "discover")
            
            def get_white_icon_pixmap(path, size=20):
                pixmap = QPixmap(size, size)
                pixmap.fill(Qt.GlobalColor.transparent)
                painter = QPainter(pixmap)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                renderer = QSvgRenderer(path)
                if renderer.isValid():
                    renderer.render(painter, QRectF(pixmap.rect()))
                    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                    painter.fillRect(pixmap.rect(), QColor("white"))
                painter.end()
                return pixmap
            
            install_btn.setIcon(QIcon(get_white_icon_pixmap(os.path.join(icon_dir, "install-selected packge.svg"))))
            
            layout.addWidget(install_btn)
            
            layout.addStretch()
            
            # Add some spacing before Git button so it's not against the corner
            layout.addSpacing(10)
            
            # Git button on the right side
            git_btn = QPushButton()
            git_btn.setFixedSize(44, 44)  # Slightly larger for better spacing
            git_btn.setToolTip("Git Repository Manager")
            git_btn.clicked.connect(self.show_git_dialog)
            git_btn.setStyleSheet("""
                QPushButton {
                    padding: 4px;
                    margin: 2px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: rgba(0, 191, 174, 0.1);
                }
            """)
            
            # Try to use git.svg icon, fallback to emoji
            try:
                git_icon_pixmap = get_white_icon_pixmap(os.path.join(icon_dir, "git.svg"))
                git_btn.setIcon(QIcon(git_icon_pixmap))
                git_btn.setIconSize(QSize(24, 24))  # Smaller icon to fit in padded button
            except:
                git_btn.setText("📁")
            
            layout.addWidget(git_btn)
            
            self.toolbar_layout.addLayout(layout)
        # For bundles, no toolbar
    
    def switch_view(self, view_id):
        self.current_view = view_id
        self.console.clear()
        
        # Update button states
        for btn_id, btn in self.nav_buttons.items():
            btn.setChecked(btn_id == view_id)
        
        # Update header
        headers = {
            "updates": ("🔄 Software Updates", "24 packages were found, 24 of which match the specified filters"),
            "installed": ("📦 Installed Packages", "View all installed packages on your system"),
            "discover": ("🔍 Discover Packages", "Search and discover new packages to install"),
            "bundles": ("📋 Package Bundles", "Manage package bundles"),
        }
        
        header_text, info_text = headers.get(view_id, ("NeoArch", ""))
        self.header_label.setText(header_text)
        self.header_info.setText(info_text)
        
        self.update_table_columns(view_id)
        self.update_filters_panel(view_id)
        self.update_toolbar()
        self.search_input.clear()
        
        # Load data for view
        if view_id == "updates":
            self.load_updates()
        elif view_id == "installed":
            self.load_installed_packages()
        elif view_id == "discover":
            self.package_table.setRowCount(0)
            self.log("Type a package name to search in AUR and official repositories")
        elif view_id == "bundles":
            self.package_table.setRowCount(0)
            self.log("Package bundles feature")
    
    def update_filters_panel(self, view_id):
        # Clear existing filters section
        while self.filters_layout.count():
            item = self.filters_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Recreate filters based on view
        filters_label = QLabel("Filters")
        filters_label.setObjectName("sectionLabel")
        self.filters_layout.addWidget(filters_label)
        
        if view_id == "updates":
            # For updates view, filter by source
            filter_options = ["pacman", "AUR"]
        elif view_id == "installed":
            # For installed view, filter by update status
            filter_options = ["Updates available", "Installed"]
        else:
            filter_options = []
        
        self.filter_checkboxes = {}
        for option in filter_options:
            checkbox = QCheckBox(option)
            checkbox.setChecked(True)
            if view_id == "updates":
                checkbox.stateChanged.connect(self.apply_update_filters)
            elif view_id == "installed":
                checkbox.stateChanged.connect(self.apply_filters)
            self.filter_checkboxes[option] = checkbox
            self.filters_layout.addWidget(checkbox)
        
        # Update visibility
        if view_id in ["installed", "updates"]:
            self.sources_section.setVisible(False)
            self.filters_section.setVisible(True)
        elif view_id == "discover":
            self.sources_section.setVisible(True)
            self.filters_section.setVisible(False)
            self.update_discover_sources()
        else:
            self.sources_section.setVisible(True)
            self.filters_section.setVisible(True)
    
    def update_discover_sources(self):
        while self.sources_layout.count() > 1:
            item = self.sources_layout.takeAt(1)
            if item.widget():
                item.widget().deleteLater()
        
        sources = [
            ("pacman", "pacman.svg"),
            ("AUR", "aur.svg"),
            ("Flatpak", "flatpack.svg")
        ]
        self.source_checkboxes = {}
        for source, icon_file in sources:
            # Create container widget
            container = QWidget()
            layout = QHBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(8)
            
            # Icon
            icon_label = QLabel()
            icon_path = os.path.join(os.path.dirname(__file__), "assets", "icons", "discover", icon_file)
            try:
                svg_renderer = QSvgRenderer(icon_path)
                if svg_renderer.isValid():
                    pixmap = QPixmap(20, 20)
                    pixmap.fill(Qt.GlobalColor.transparent)
                    painter = QPainter(pixmap)
                    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                    svg_renderer.render(painter, QRectF(pixmap.rect()))
                    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                    painter.fillRect(pixmap.rect(), QColor("white"))
                    painter.end()
                    icon_label.setPixmap(pixmap)
                else:
                    icon_label.setText("📦")
            except:
                icon_label.setText("📦")
            
            layout.addWidget(icon_label)
            
            # Checkbox
            checkbox = QCheckBox(source)
            checkbox.setChecked(True)
            checkbox.stateChanged.connect(self.apply_source_filter)
            layout.addWidget(checkbox)
            
            layout.addStretch()
            
            self.source_checkboxes[source] = checkbox
            self.sources_layout.addWidget(container)
    
    def apply_source_filter(self):
        if self.current_view == "discover" and self.search_results:
            self.display_discover_results()
    
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
        elif view_id == "discover":
            self.package_table.setColumnCount(6)
            self.package_table.setHorizontalHeaderLabels(["", "Package Name", "Package ID", "Version", "Description", "Source"])
            self.package_table.setObjectName("discoverTable")  # Apply special styling
            self.package_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            self.package_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            self.package_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
            self.package_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
            self.package_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
            self.package_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
            
            # Add icons to headers
            icon_dir = os.path.join(os.path.dirname(__file__), "assets", "icons", "discover")
            
            def get_white_icon_pixmap(path, size=16):
                pixmap = QPixmap(size, size)
                pixmap.fill(Qt.GlobalColor.transparent)
                painter = QPainter(pixmap)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                renderer = QSvgRenderer(path)
                if renderer.isValid():
                    renderer.render(painter, QRectF(pixmap.rect()))
                    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                    painter.fillRect(pixmap.rect(), QColor("white"))
                painter.end()
                return pixmap
            
            header_item1 = QTableWidgetItem()
            header_item1.setIcon(QIcon(get_white_icon_pixmap(os.path.join(icon_dir, "packagename.svg"))))
            header_item1.setText("Package Name")
            self.package_table.setHorizontalHeaderItem(1, header_item1)
            
            header_item2 = QTableWidgetItem()
            header_item2.setIcon(QIcon(get_white_icon_pixmap(os.path.join(icon_dir, "pacakgeid.svg"))))
            header_item2.setText("Package ID")
            self.package_table.setHorizontalHeaderItem(2, header_item2)
            
            header_item3 = QTableWidgetItem()
            header_item3.setIcon(QIcon(get_white_icon_pixmap(os.path.join(icon_dir, "version.svg"))))
            header_item3.setText("Version")
            self.package_table.setHorizontalHeaderItem(3, header_item3)
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
        self.log("Checking for updates...")
        self.package_table.setRowCount(0)
        self.all_packages = []
        self.current_page = 0
        
        # Show loading spinner and start animation
        self.loading_widget.setVisible(True)
        self.package_table.setVisible(False)
        self.load_more_btn.setVisible(False)
        self.spinner_timer.start(100)  # Update every 100ms for smooth animation
        
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
                
                self.packages_ready.emit(packages)
            except Exception as e:
                self.log(f"Error: {str(e)}")
                self.load_error.emit()
        
        Thread(target=load_in_thread, daemon=True).start()
    
    def load_installed_packages(self):
        self.log("Loading installed packages...")
        self.package_table.setRowCount(0)
        self.all_packages = []
        self.current_page = 0
        
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
                
                self.packages_ready.emit(packages)
            except Exception as e:
                self.log(f"Error: {str(e)}")
                self.load_error.emit()
        
        Thread(target=load_in_thread, daemon=True).start()
    
    def on_packages_loaded(self, packages):
        self.all_packages = packages
        self.current_page = 0
        self.packages_per_page = 10
        self.package_table.setRowCount(0)
        self.display_page()
        self.log(f"Loaded {len(packages)} packages total. Showing first 10...")
        
        # Hide loading spinner, stop animation, and show packages table
        self.loading_widget.setVisible(False)
        self.spinner_timer.stop()
        self.package_table.setVisible(True)
    
    def on_load_error(self):
        # Hide loading spinner, stop animation, and show packages table (empty)
        self.loading_widget.setVisible(False)
        self.spinner_timer.stop()
        self.package_table.setVisible(True)
        self.log("Failed to load packages. Please check the logs for details.")
    
    def display_page(self):
        self.package_table.setUpdatesEnabled(False)
        start = self.current_page * self.packages_per_page
        end = start + self.packages_per_page
        page_packages = self.all_packages[start:end]
        
        for pkg in page_packages:
            if self.current_view == "installed":
                self.add_package_row(pkg['name'], pkg['id'], pkg['version'], pkg.get('new_version', pkg['version']), pkg.get('source', 'pacman'), pkg)
            else:
                self.add_package_row(pkg['name'], pkg['id'], pkg['version'], pkg.get('new_version', pkg['version']), pkg.get('source', 'pacman'))
        
        self.package_table.setUpdatesEnabled(True)
        
        has_more = end < len(self.all_packages)
        self.load_more_btn.setVisible(has_more)
        if has_more:
            remaining = len(self.all_packages) - end
            self.load_more_btn.setText(f"Load More ({remaining} remaining)")
    
    def load_more_packages(self):
        self.current_page += 1
        start = self.current_page * self.packages_per_page
        end = start + self.packages_per_page
        
        if hasattr(self, 'search_results') and self.search_results:
            page_packages = self.search_results[start:end]
            total = len(self.search_results)
        else:
            page_packages = self.all_packages[start:end]
            total = len(self.all_packages)
        
        self.package_table.setUpdatesEnabled(False)
        for pkg in page_packages:
            if self.current_view == "installed":
                self.add_package_row(pkg['name'], pkg['id'], pkg['version'], pkg.get('new_version', pkg['version']), pkg.get('source', 'pacman'), pkg)
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
            checkbox = self.package_table.cellWidget(i, 0)
            if checkbox:
                checkbox.setChecked(False)
    
    def add_discover_row(self, pkg):
        row = self.package_table.rowCount()
        self.package_table.insertRow(row)
        
        checkbox = QCheckBox()
        checkbox.setChecked(False)  # Default to unchecked
        self.package_table.setCellWidget(row, 0, checkbox)
        checkbox.stateChanged.connect(lambda state, r=row: self.on_checkbox_changed(r, state))
        
        name_item = QTableWidgetItem(pkg['name'])
        name_item.setToolTip(pkg['name'])
        font = QFont()
        font.setBold(True)
        name_item.setFont(font)
        self.package_table.setItem(row, 1, name_item)
        self.package_table.setItem(row, 2, QTableWidgetItem(pkg['id']))
        self.package_table.setItem(row, 3, QTableWidgetItem(pkg['version']))
        desc_item = QTableWidgetItem(pkg.get('description', ''))
        desc_item.setForeground(QColor("#C9C9C9"))
        desc_item.setToolTip(pkg.get('description', ''))
        self.package_table.setItem(row, 4, desc_item)
        self.package_table.setItem(row, 5, QTableWidgetItem(pkg['source']))
    
    def add_package_row(self, name, pkg_id, version, new_version, source, pkg_data=None):
        row = self.package_table.rowCount()
        self.package_table.insertRow(row)
        
        checkbox = QCheckBox()
        checkbox.setChecked(True)
        self.package_table.setCellWidget(row, 0, checkbox)
        checkbox.stateChanged.connect(lambda state, r=row: self.on_checkbox_changed(r, state))
        
        name_item = QTableWidgetItem(name)
        font = QFont()
        font.setBold(True)
        name_item.setFont(font)
        self.package_table.setItem(row, 1, name_item)
        self.package_table.setItem(row, 2, QTableWidgetItem(pkg_id))
        self.package_table.setItem(row, 3, QTableWidgetItem(version))
        
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
    
    def search_discover_packages(self, query):
        self.log(f"Searching for '{query}' in AUR, official repositories, and Flatpak...")
        self.package_table.setRowCount(0)
        self.search_results = []
        
        def search_in_thread():
            try:
                packages = []
                
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
                
                result_flatpak = subprocess.run(["flatpak", "search", query], capture_output=True, text=True, timeout=30)
                if result_flatpak.returncode == 0 and result_flatpak.stdout:
                    lines = result_flatpak.stdout.strip().split('\n')
                    for line in lines:
                        parts = line.split()
                        if len(parts) >= 2:
                            name = parts[0]
                            version = parts[1]
                            description = ' '.join(parts[2:]) if len(parts) > 2 else ''
                            packages.append({
                                'name': name,
                                'version': version,
                                'id': name,
                                'source': 'Flatpak',
                                'description': description,
                                'has_update': False
                            })
                
                self.discover_results_ready.emit(packages)
            except Exception as e:
                self.log(f"Search error: {str(e)}")
        
        Thread(target=search_in_thread, daemon=True).start()

    def display_discover_results(self, packages=None):
        if packages is not None:
            self.search_results = packages
        
        show_pacman = self.source_checkboxes.get("pacman", QCheckBox()).isChecked() if isinstance(self.source_checkboxes.get("pacman"), QCheckBox) else True
        show_aur = self.source_checkboxes.get("AUR", QCheckBox()).isChecked() if isinstance(self.source_checkboxes.get("AUR"), QCheckBox) else True
        show_flatpak = self.source_checkboxes.get("Flatpak", QCheckBox()).isChecked() if isinstance(self.source_checkboxes.get("Flatpak"), QCheckBox) else True
        
        filtered = []
        for pkg in self.search_results:
            if pkg['source'] == 'pacman' and show_pacman:
                filtered.append(pkg)
            elif pkg['source'] == 'AUR' and show_aur:
                filtered.append(pkg)
            elif pkg['source'] == 'Flatpak' and show_flatpak:
                filtered.append(pkg)
        
        # Sort results by relevance to the query
        query = self.search_input.text().strip().lower()
        filtered.sort(key=lambda pkg: (query in pkg['name'].lower(), query in (pkg.get('description') or '').lower()), reverse=True)
        
        self.package_table.setUpdatesEnabled(False)
        self.package_table.setRowCount(0)
        
        start = 0
        end = min(10, len(filtered))
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
            self.log(f"No packages found matching '{query}'.")
        else:
            self.log(f"Found {len(filtered)} packages matching '{query}'. Showing first 10...")

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
                self.log("Type a package name to search in AUR and official repositories")
    
    def update_selected(self):
        packages = []
        for row in range(self.package_table.rowCount()):
            checkbox = self.package_table.cellWidget(row, 0)
            if checkbox and isinstance(checkbox, QCheckBox) and checkbox.isChecked():
                pkg_name = self.package_table.item(row, 1).text()
                packages.append(pkg_name.lower())
        
        if not packages:
            self.log("No packages selected for update")
            # QMessageBox.warning(self, "No Selection", "Please select packages to update")
            return
        
        self.log(f"Selected packages for update: {', '.join(packages)}")
        
        # reply = QMessageBox.question(self, "Confirm Update", 
        #                             f"Update {len(packages)} package(s)?")
        # if reply != QMessageBox.StandardButton.Yes:
        #     return
        
        self.log(f"Proceeding with update of {len(packages)} packages...")
        
        self.log(f"Starting update of {len(packages)} packages...")
        
        def update():
            self.log("Update thread started")
            try:
                cmd = ["pacman", "-Syu", "--noconfirm"] + packages
                self.log(f"Running command: {' '.join(cmd)}")
                worker = CommandWorker(cmd, sudo=True)
                worker.output.connect(self.log)
                worker.error.connect(self.log)
                def on_finished():
                    self.log("Update completed")
                    self.show_message.emit("Update Complete", f"Successfully updated {len(packages)} package(s).")
                worker.finished.connect(on_finished)
                worker.run()
            except Exception as e:
                self.log(f"Error in update thread: {str(e)}")
        
        Thread(target=update, daemon=True).start()
    
    def ignore_selected(self):
        selected_rows = self.package_table.selectionModel().selectedRows()
        if not selected_rows:
            self.log("No packages selected to ignore")
            # QMessageBox.warning(self, "No Selection", "Please select packages to ignore")
            return
        
        self.log(f"Ignored {len(selected_rows)} package(s)")
    
    def manage_ignored(self):
        QMessageBox.information(self, "Manage Ignored", "Manage ignored updates here")
    
    def install_selected(self):
        packages_by_source = {}
        for row in range(self.package_table.rowCount()):
            checkbox = self.package_table.cellWidget(row, 0)
            if checkbox and isinstance(checkbox, QCheckBox) and checkbox.isChecked():
                pkg_name = self.package_table.item(row, 1).text().lower()
                source = self.package_table.item(row, 5).text()
                if source not in packages_by_source:
                    packages_by_source[source] = []
                packages_by_source[source].append(pkg_name)
        
        if not packages_by_source:
            self.log_signal.emit("No packages selected for installation")
            return
        
        self.log_signal.emit(f"Selected packages: {', '.join([f'{pkg} ({source})' for source, pkgs in packages_by_source.items() for pkg in pkgs])}")
        
        self.log_signal.emit(f"Proceeding with installation...")
        
        def install():
            self.log_signal.emit("Installation thread started")
            try:
                for source, packages in packages_by_source.items():
                    if source == 'pacman':
                        cmd = ["pacman", "-S", "--noconfirm"] + packages
                    elif source == 'AUR':
                        cmd = ["yay", "-S", "--noconfirm"] + packages
                    elif source == 'Flatpak':
                        cmd = ["flatpak", "install", "--noninteractive", "--or-update"] + packages
                    else:
                        self.log_signal.emit(f"Unknown source {source} for packages {packages}")
                        continue
                    
                    self.log_signal.emit(f"Running command for {source}: {' '.join(cmd)}")
                    worker = CommandWorker(cmd, sudo=(source != 'Flatpak'))
                    worker.output.connect(lambda msg: self.log_signal.emit(msg))
                    worker.error.connect(lambda msg: self.log_signal.emit(msg))
                    worker.run()
                
                self.log_signal.emit("Install completed")
                self.show_message.emit("Installation Complete", f"Successfully installed packages.")
            except Exception as e:
                self.log_signal.emit(f"Error in installation thread: {str(e)}")
        
        Thread(target=install, daemon=True).start()
    
    def uninstall_selected(self):
        selected_rows = self.package_table.selectionModel().selectedRows()
        if not selected_rows:
            self.log("No packages selected for uninstallation")
            # QMessageBox.warning(self, "No Selection", "Please select packages to uninstall")
            return
        
        packages = []
        for row in selected_rows:
            pkg_name = self.package_table.item(row.row(), 1).text()
            packages.append(pkg_name.lower())
        
        self.log(f"Selected packages for uninstallation: {', '.join(packages)}")
        
        # reply = QMessageBox.question(self, "Confirm Uninstall", 
        #                             f"Uninstall {len(packages)} package(s)?")
        # if reply != QMessageBox.StandardButton.Yes:
        #     self.log("Uninstallation cancelled by user")
        #     return
        self.log(f"Proceeding with uninstallation of {len(packages)} packages...")
        
        self.log(f"Starting uninstallation of {len(packages)} packages...")
        
        def uninstall():
            self.log("Uninstallation thread started")
            try:
                cmd = ["pacman", "-R", "--noconfirm"] + packages
                self.log(f"Running command: {' '.join(cmd)}")
                worker = CommandWorker(cmd, sudo=True)
                worker.output.connect(self.log)
                worker.error.connect(self.log)
                def on_finished():
                    self.log("Uninstall completed")
                    self.show_message.emit("Uninstallation Complete", f"Successfully uninstalled {len(packages)} package(s).")
                worker.finished.connect(on_finished)
                worker.run()
            except Exception as e:
                self.log(f"Error in uninstallation thread: {str(e)}")
        
        Thread(target=uninstall, daemon=True).start()
    
    def apply_filters(self):
        if self.current_view != "installed" or not self.all_packages:
            return
        
        show_updates = self.filter_checkboxes.get("Updates available", True)
        show_installed = self.filter_checkboxes.get("Installed", True)
        
        if isinstance(show_updates, QCheckBox):
            show_updates = show_updates.isChecked()
        if isinstance(show_installed, QCheckBox):
            show_installed = show_installed.isChecked()
        
        filtered = []
        for pkg in self.all_packages:
            if pkg.get('has_update') and show_updates:
                filtered.append(pkg)
            elif not pkg.get('has_update') and show_installed:
                filtered.append(pkg)
        
        self.package_table.setUpdatesEnabled(False)
        self.package_table.setRowCount(0)
        
        for pkg in filtered[:10]:
            if self.current_view == "installed":
                self.add_package_row(pkg['name'], pkg['id'], pkg['version'], pkg.get('new_version', pkg['version']), pkg.get('source', 'pacman'), pkg)
            else:
                self.add_package_row(pkg['name'], pkg['id'], pkg['version'], pkg.get('new_version', pkg['version']), pkg.get('source', 'pacman'))
        
        self.package_table.setUpdatesEnabled(True)
        
        has_more = len(filtered) > 10
        self.load_more_btn.setVisible(has_more)
        if has_more:
            remaining = len(filtered) - 10
            self.load_more_btn.setText(f"Load More ({remaining} remaining)")
        
        self.log(f"Showing {len(filtered[:10])} of {len(filtered)} packages")

    def apply_update_filters(self):
        if self.current_view != "updates" or not self.all_packages:
            return
        
        show_pacman = self.filter_checkboxes.get("pacman", True)
        show_aur = self.filter_checkboxes.get("AUR", True)
        
        if isinstance(show_pacman, QCheckBox):
            show_pacman = show_pacman.isChecked()
        if isinstance(show_aur, QCheckBox):
            show_aur = show_aur.isChecked()
        
        filtered = []
        for pkg in self.all_packages:
            if pkg.get('source') == 'pacman' and show_pacman:
                filtered.append(pkg)
            elif pkg.get('source') == 'AUR' and show_aur:
                filtered.append(pkg)
        
        # Update the all_packages to show filtered results
        self.all_packages = filtered
        self.current_page = 0
        self.package_table.setRowCount(0)
        self.display_page()
        self.log(f"Filtered to {len(filtered)} packages (pacman: {show_pacman}, AUR: {show_aur})")

    def on_selection_changed(self):
        selected_rows = set(index.row() for index in self.package_table.selectionModel().selectedRows())
        for row in range(self.package_table.rowCount()):
            checkbox = self.package_table.cellWidget(row, 0)
            if checkbox:
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
    
    def animate_spinner(self):
        """Animate the spinner by rotating it"""
        self.spinner_angle = (self.spinner_angle + 30) % 360
        pixmap = QPixmap(48, 48)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.translate(24, 24)
        painter.rotate(self.spinner_angle)
        painter.translate(-24, -24)
        font = QFont()
        font.setPixelSize(32)
        painter.setFont(font)
        painter.setPen(QColor("#00BFAE"))
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "⟳")
        painter.end()
        self.spinner_label.setPixmap(pixmap)
    
    def show_about(self):
        QMessageBox.information(self, "About NeoArch", 
                              "NeoArch - Elevate Your \nArch Experience\nVersion 1.0\n\nBuilt with PyQt6")
    
    def log(self, message):
        self.console.append(message)

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
    
    app = QApplication(sys.argv)
    window = ArchPkgManagerUniGetUI()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
