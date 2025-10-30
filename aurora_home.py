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
from components import SourceCard, FilterCard, LargeSearchBox

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
        self.docker_manager = None  # Docker manager instance
        self.current_search_mode = 'both'  # Default search mode
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
        self.search_timer.setInterval(800)
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.perform_search)
        self.search_input.textChanged.connect(self.on_search_text_changed)

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
            self.log("Type a package name to search in AUR and official repositories")
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
                if pixmap.isNull():
                    raise ValueError("Pixmap is null")
                pixmap.fill(Qt.GlobalColor.transparent)
                
                with QPainter(pixmap) as painter:
                    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
                    
                    try:
                        # Set composition mode and color for white rendering
                        svg_renderer.render(painter, QRectF(pixmap.rect()))
                        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                        painter.fillRect(pixmap.rect(), QColor("white"))
                    except:
                        pass
                
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
                if pixmap.isNull():
                    raise ValueError("Pixmap is null")
                pixmap.fill(Qt.GlobalColor.transparent)
                
                with QPainter(pixmap) as painter:
                    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
                    
                    try:
                        from PyQt6.QtCore import QRectF
                        svg_renderer.render(painter, QRectF(pixmap.rect()))
                        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                        painter.fillRect(pixmap.rect(), QColor("white"))
                    except:
                        pass
                
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
        elif "docker" in icon_path.lower():
            return "🐳"
        else:
            return "📦"
    
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
        try:
            pixmap = QPixmap(icon_size, icon_size)
            if pixmap.isNull():
                raise ValueError("Pixmap is null")
            pixmap.fill(Qt.GlobalColor.transparent)
            with QPainter(pixmap) as painter:
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                renderer = QSvgRenderer(icon_path)
                if renderer.isValid():
                    renderer.render(painter, QRectF(pixmap.rect()))
                    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                    painter.fillRect(pixmap.rect(), QColor("white"))
            btn.setIcon(QIcon(pixmap))
            btn.setIconSize(QSize(icon_size, icon_size))
        except:
            # Fallback to emoji based on icon path
            emoji = self.get_fallback_icon(icon_path)
            if "help" in icon_path.lower():
                emoji = "❓"
            elif "add" in icon_path.lower() or "sudo" in icon_path.lower():
                emoji = "➕"
            btn.setText(emoji)
        
        return btn
    
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
        
        def get_white_icon_pixmap(path, size=20):
            pixmap = QPixmap(size, size)
            if pixmap.isNull():
                raise ValueError("Pixmap is null")
            pixmap.fill(Qt.GlobalColor.transparent)
            with QPainter(pixmap) as painter:
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                renderer = QSvgRenderer(path)
                if renderer.isValid():
                    try:
                        renderer.render(painter, QRectF(pixmap.rect()))
                        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                        painter.fillRect(pixmap.rect(), QColor("white"))
                    except:
                        pass
            return pixmap
        
        refresh_btn.setIcon(QIcon(get_white_icon_pixmap(os.path.join(icon_dir, "refresh.svg"))))
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
            checkbox = self.package_table.cellWidget(row, 0)
            if checkbox and checkbox.isChecked():
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
        
        def get_white_icon_pixmap(path, size=20):
            pixmap = QPixmap(size, size)
            if pixmap.isNull():
                raise ValueError("Pixmap is null")
            pixmap.fill(Qt.GlobalColor.transparent)
            with QPainter(pixmap) as painter:
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                renderer = QSvgRenderer(path)
                if renderer.isValid():
                    
                    try:
                        renderer.render(painter, QRectF(pixmap.rect()))
                        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                        painter.fillRect(pixmap.rect(), QColor("white"))
                    except:
                        pass
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
            layout = QHBoxLayout()
            layout.addStretch()
            self.toolbar_layout.addLayout(layout)
        elif self.current_view == "discover":
            layout = QHBoxLayout()
            layout.setSpacing(8)  # Tighter spacing
            
            install_btn = QPushButton("Install selected packages")
            install_btn.setMinimumHeight(36)
            install_btn.clicked.connect(self.install_selected)
            icon_dir = os.path.join(os.path.dirname(__file__), "assets", "icons", "discover")
            
            def get_white_icon_pixmap(path, size=20):
                pixmap = QPixmap(size, size)
                if pixmap.isNull():
                    raise ValueError("Pixmap is null")
                pixmap.fill(Qt.GlobalColor.transparent)
                with QPainter(pixmap) as painter:
                    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                    renderer = QSvgRenderer(path)
                    if renderer.isValid():
                        renderer.render(painter, QRectF(pixmap.rect()))
                        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                        painter.fillRect(pixmap.rect(), QColor("white"))
                return pixmap
            
            install_btn.setIcon(QIcon(get_white_icon_pixmap(os.path.join(icon_dir, "install-selected packge.svg"))))
            
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
                "Go to Package Bundles",
                self.go_to_bundles
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
            layout.addWidget(help_btn)
            
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
            "discover": ("/home/alexa/StudioProjects/Aurora/assets/icons/discover/search.svg", "Discover Packages", "Search and discover new packages to install"),
            "bundles": ("📋 Package Bundles", "Manage package bundles"),
        }
        
        header_data = headers.get(view_id, ("NeoArch", ""))
        if len(header_data) == 3:  # Icon, title, subtitle
            icon_path, title, subtitle = header_data
            try:
                pixmap = QPixmap(24, 24)
                if pixmap.isNull():
                    raise ValueError("Pixmap is null")
                pixmap.fill(Qt.GlobalColor.transparent)
                with QPainter(pixmap) as painter:
                    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                    renderer = QSvgRenderer(icon_path)
                    if renderer.isValid():
                        renderer.render(painter, QRectF(pixmap.rect()))
                        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                        painter.fillRect(pixmap.rect(), QColor("#00BFAE"))
                self.header_icon.setPixmap(pixmap)
                self.header_icon.setVisible(True)
            except:
                self.header_icon.setVisible(False)
            self.header_label.setText(title)
            self.header_info.setText(subtitle)
        else:  # Title, subtitle
            title, subtitle = header_data
            self.header_icon.setVisible(False)
            self.header_label.setText(title)
            self.header_info.setText(subtitle)
        
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
            self.large_search_box.setVisible(True)
            self.package_table.setVisible(False)
            self.load_more_btn.setVisible(False)
            self.package_table.setRowCount(0)
            self.header_info.setText("Search and discover new packages to install")
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
        if view_id == "updates":
            # For updates view, filter by source
            self.filter_card = FilterCard(self)
            self.filter_card.filter_changed.connect(self.on_filter_selection_changed)
            
            # Add source filters
            self.filter_card.add_filter("pacman")
            self.filter_card.add_filter("AUR")
            
            self.filters_layout.addWidget(self.filter_card)
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
        if view_id in ["installed", "updates"]:
            self.sources_section.setVisible(False)
            self.filters_section.setVisible(True)
            if hasattr(self, 'sources_title_label'):
                self.sources_title_label.setVisible(True)
        elif view_id == "discover":
            self.sources_section.setVisible(True)
            self.filters_section.setVisible(False)
            if hasattr(self, 'sources_title_label'):
                self.sources_title_label.setVisible(False)
            self.update_discover_sources()
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
        
        # Add the five main sources
        sources = [
            ("pacman", os.path.join(os.path.dirname(__file__), "assets", "icons", "discover", "pacman.svg")),
            ("AUR", os.path.join(os.path.dirname(__file__), "assets", "icons", "discover", "aur.svg")),
            ("Flatpak", os.path.join(os.path.dirname(__file__), "assets", "icons", "discover", "flatpack.svg")),
            ("npm", os.path.join(os.path.dirname(__file__), "assets", "icons", "discover", "node.svg")),
            ("pip", os.path.join(os.path.dirname(__file__), "assets", "icons", "discover", "python.svg"))
        ]
        
        for source_name, icon_path in sources:
            self.source_card.add_source(source_name, icon_path)
        
        self.sources_layout.addWidget(self.source_card)
        
        # Initialize Git Manager for sources panel
        if not hasattr(self, 'git_manager') or self.git_manager is None:
            from git_manager import GitManager
            self.git_manager = GitManager(self.log_signal, self.show_message, self.sources_layout, self)
    
    def on_source_selection_changed(self, source_states):
        """Handle changes in source selection"""
        self.log(f"Source selection changed: {source_states}")
        # Apply source filtering if we have search results
        if self.current_view == "discover" and hasattr(self, 'search_results') and self.search_results:
            self.display_discover_results()
    
    def on_search_mode_changed(self, search_mode):
        """Handle changes in search mode"""
        self.log(f"Search mode changed to: {search_mode}")
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
                if pixmap.isNull():
                    return pixmap
                pixmap.fill(Qt.GlobalColor.transparent)
                with QPainter(pixmap) as painter:
                    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                    renderer = QSvgRenderer(path)
                    if renderer.isValid():
                        try:
                            renderer.render(painter, QRectF(pixmap.rect()))
                            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                            painter.fillRect(pixmap.rect(), QColor("white"))
                        except:
                            pass
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
                
                # Search pip packages
                try:
                    result_pip = subprocess.run(["pip", "search", query], capture_output=True, text=True, timeout=30)
                    if result_pip.returncode == 0 and result_pip.stdout:
                        lines = result_pip.stdout.strip().split('\n')
                        for line in lines:
                            if ' - ' in line:
                                parts = line.split(' - ', 1)
                                if len(parts) == 2:
                                    name = parts[0].strip()
                                    description = parts[1].strip()
                                    packages.append({
                                        'name': name,
                                        'version': 'latest',
                                        'id': name,
                                        'source': 'pip',
                                        'description': description,
                                        'has_update': False
                                    })
                except (subprocess.CalledProcessError, FileNotFoundError):
                    # pip search not available (deprecated in newer pip versions)
                    pass
                
                self.discover_results_ready.emit(packages)
            except Exception as e:
                self.log(f"Search error: {str(e)}")
        
        Thread(target=search_in_thread, daemon=True).start()

    def display_discover_results(self, packages=None):
        if packages is not None:
            self.search_results = packages
        
        # Get selected sources from the SourceCard component
        selected_sources = {}
        if hasattr(self, 'source_card') and self.source_card:
            selected_sources = self.source_card.get_selected_sources()
        else:
            # Fallback to showing all sources if component not initialized
            selected_sources = {"pacman": True, "AUR": True, "Flatpak": True, "npm": True, "pip": True}
        
        show_pacman = selected_sources.get("pacman", True)
        show_aur = selected_sources.get("AUR", True)
        show_flatpak = selected_sources.get("Flatpak", True)
        show_npm = selected_sources.get("npm", True)
        show_pip = selected_sources.get("pip", True)
        
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
            elif pkg['source'] == 'pip' and show_pip:
                filtered.append(pkg)
        
        # Sort results by relevance to the query based on search mode
        query = self.search_input.text().strip().lower()
        search_mode = self.current_search_mode
        
        def get_sort_key(pkg):
            name_match = query in pkg['name'].lower()
            id_match = query in pkg['id'].lower()
            desc_match = query in (pkg.get('description') or '').lower()
            
            if search_mode == 'name':
                return (name_match, False, False)
            elif search_mode == 'id':
                return (id_match, False, False)
            else:  # 'both'
                return (name_match or id_match, desc_match, False)
        
        filtered.sort(key=get_sort_key, reverse=True)
        
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
                    elif source == 'npm':
                        cmd = ["npm", "install", "-g"] + packages
                    elif source == 'pip':
                        cmd = ["pip", "install"] + packages
                    else:
                        self.log_signal.emit(f"Unknown source {source} for packages {packages}")
                        continue
                    
                    self.log_signal.emit(f"Running command for {source}: {' '.join(cmd)}")
                    worker = CommandWorker(cmd, sudo=(source in ['pacman', 'AUR']))
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
        
        # Get selected filters from the FilterCard component
        selected_filters = {}
        if hasattr(self, 'filter_card') and self.filter_card:
            selected_filters = self.filter_card.get_selected_filters()
        else:
            # Fallback to showing all filters if component is not initialized
            selected_filters = {"Updates available": True, "Installed": True}
        
        show_updates = selected_filters.get("Updates available", True)
        show_installed = selected_filters.get("Installed", True)
        
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
        
        # Get selected filters from the FilterCard component
        selected_filters = {}
        if hasattr(self, 'filter_card') and self.filter_card:
            selected_filters = self.filter_card.get_selected_filters()
        else:
            # Fallback to showing all filters if component not initialized
            selected_filters = {"pacman": True, "AUR": True}
        
        show_pacman = selected_filters.get("pacman", True)
        show_aur = selected_filters.get("AUR", True)
        
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
        if not hasattr(self, 'spinner_label') or not self.spinner_label:
            return
            
        pixmap = QPixmap(48, 48)
        if pixmap.isNull():
            return  # Skip animation if pixmap can't be created
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
        
        self.spinner_angle = (self.spinner_angle + 10) % 360
    
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
