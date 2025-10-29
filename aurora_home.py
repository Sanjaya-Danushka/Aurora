#!/usr/bin/env python3
import sys
import os
import subprocess
import json
from threading import Thread
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLineEdit, QTableWidget, QTableWidgetItem, QTextEdit,
                             QLabel, QFileDialog, QMessageBox, QHeaderView, QFrame, QSplitter,
                             QScrollArea, QCheckBox, QListWidget, QListWidgetItem, QSizePolicy)
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QThread, QSize, QTimer
from PyQt6.QtGui import QColor, QFont, QIcon, QPixmap, QPainter

DARK_STYLESHEET = """
QMainWindow {
    background-color: #0d1117;
    color: #c9d1d9;
}

QWidget {
    background-color: #0d1117;
    color: #c9d1d9;
    font-family: 'Segoe UI', sans-serif;
    font-size: 13px;
}

QLineEdit {
    background-color: rgba(177, 186, 196, 0.1);
    color: #c9d1d9;
    border: 2px solid rgba(177, 186, 196, 0.2);
    border-radius: 8px;
    padding: 10px 12px;
    font-size: 14px;
    selection-background-color: #1f6feb;
}

QLineEdit:focus {
    background-color: rgba(177, 186, 196, 0.15);
    border: 2px solid #1f6feb;
    outline: none;
}

QPushButton {
    background-color: rgba(177, 186, 196, 0.1);
    color: #c9d1d9;
    border: 1px solid rgba(177, 186, 196, 0.2);
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: 500;
    font-size: 13px;
}

QPushButton:hover {
    background-color: rgba(177, 186, 196, 0.2);
    border-color: rgba(177, 186, 196, 0.4);
}

QPushButton:pressed {
    background-color: rgba(177, 186, 196, 0.3);
}

QPushButton#sidebarBtn {
    background-color: transparent;
    border: none;
    color: #8b949e;
    padding: 12px 16px;
    text-align: left;
    font-size: 14px;
    font-weight: 500;
    border-radius: 6px;
}

QPushButton#sidebarBtn:hover {
    background-color: rgba(177, 186, 196, 0.1);
    color: #c9d1d9;
}

QPushButton#navBtn {
    background-color: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    color: #ffffff;
    font-size: 11px;
    font-weight: 500;
    padding: 0px;
    margin: 8px 0px;  /* More margin between cards */
    min-height: 100px;  /* More square proportion */
    max-width: 150px;  /* Square shape */
    text-align: center;
}

QPushButton#navBtn:hover {
    background-color: rgba(255, 255, 255, 0.08);
    border-color: rgba(255, 255, 255, 0.2);
}

QPushButton#navBtn:checked {
    background-color: rgba(31, 111, 235, 0.15);
    border-color: #1f6feb;
    color: #ffffff;
}

QPushButton#navBtn:pressed {
}

QLabel#navIcon {
    background-color: transparent;
    border-radius: 8px;
    font-size: 26px;
    color: #e1e5e9;  /* Light gray instead of pure white */
}

QPushButton#navBtn:hover QLabel#navIcon {
    background-color: transparent;
    color: #ffffff;  /* White on hover */
}

QPushButton#navBtn:checked QLabel#navIcon {
    background-color: transparent;
    color: #ffffff;
}

QLabel#navText {
    color: #e1e5e9;  /* Light gray text */
    font-weight: 400;
    font-size: 10px;
    letter-spacing: 0.8px;
    margin-top: 4px;
    text-transform: uppercase;
}

QPushButton#navBtn:checked QLabel#navText {
    color: #ffffff;
    font-weight: 600;
}

QPushButton#bottomCardBtn {
    background-color: transparent;
    border: none;
    border-radius: 8px;
    color: #ffffff;
    font-size: 11px;
    font-weight: 500;
    padding: 0px;
    margin: 0px;
    min-height: 70px;
    max-width: 150px;
    text-align: center;
}

QPushButton#bottomCardBtn:hover {
    background-color: rgba(255, 255, 255, 0.08);
    border-color: rgba(255, 255, 255, 0.2);
}

QPushButton#bottomCardBtn:pressed {
    background-color: rgba(255, 255, 255, 0.15);
}

QPushButton#bottomCardBtn QLabel {
    color: #ffffff;
}

QLabel#bottomCardIcon {
    background-color: transparent;
    border-radius: 6px;
    font-size: 18px;
    color: #ffffff;
}

QPushButton#bottomCardBtn:hover QLabel#bottomCardIcon {
    background-color: transparent;
}

QLabel#bottomCardText {
    color: #e1e5e9;
    font-weight: 400;
    font-size: 10px;
    letter-spacing: 0.8px;
    margin-top: 4px;
    text-transform: uppercase;
}

QPushButton#bottomCardBtn:hover QLabel#bottomCardText {
    color: #ffffff;
}

QWidget#sidebar {
    background-color: #1a1a1a;
    border-right: 1px solid rgba(255, 255, 255, 0.1);
}

QLabel#sidebarHeader {
    color: #ffffff;
    font-size: 24px;
    font-weight: 800;
    letter-spacing: 1px;
    text-align: center;
    padding: 10px 0;
    margin-bottom: 10px;
}

QTableWidget {
    background-color: rgba(177, 186, 196, 0.05);
    alternate-background-color: rgba(177, 186, 196, 0.02);
    gridline-color: rgba(177, 186, 196, 0.1);
    border: 1px solid rgba(177, 186, 196, 0.1);
    border-radius: 8px;
    selection-background-color: rgba(31, 111, 235, 0.3);
    selection-color: #c9d1d9;
}

QTableWidget::item {
    padding: 12px 8px;
    border: none;
    border-bottom: 1px solid rgba(177, 186, 196, 0.05);
}

QTableWidget::item:selected {
    background-color: rgba(31, 111, 235, 0.2);
    color: #c9d1d9;
}

QHeaderView::section {
    background-color: rgba(177, 186, 196, 0.1);
    color: #1f6feb;
    padding: 12px 8px;
    border: none;
    font-weight: 600;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    border-bottom: 2px solid rgba(177, 186, 196, 0.1);
}

QTextEdit {
    background-color: rgba(177, 186, 196, 0.05);
    color: #8b949e;
    border: 1px solid rgba(177, 186, 196, 0.1);
    border-radius: 6px;
    font-family: 'Consolas', 'Monaco', monospace;
    font-size: 12px;
    padding: 8px;
}

QLabel {
    color: #c9d1d9;
}

QLabel#headerLabel {
    color: #ffffff;
    font-size: 20px;
    font-weight: 700;
}

QLabel#sectionLabel {
    color: #1f6feb;
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

QFrame {
    background-color: transparent;
    border: none;
}

QCheckBox {
    color: #c9d1d9;
    spacing: 8px;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 3px;
    border: 2px solid rgba(177, 186, 196, 0.3);
    background-color: rgba(177, 186, 196, 0.1);
}

QCheckBox::indicator:checked {
    background-color: #1f6feb;
    border: 2px solid #1f6feb;
}

QCheckBox::indicator:hover {
    border-color: rgba(177, 186, 196, 0.5);
}

QListWidget {
    background-color: transparent;
    border: none;
    outline: none;
}

QListWidget::item {
    padding: 8px 12px;
    border-radius: 4px;
    margin: 2px 0;
}

QListWidget::item:hover {
    background-color: rgba(177, 186, 196, 0.1);
}

QListWidget::item:selected {
    background-color: rgba(31, 111, 235, 0.2);
    color: #1f6feb;
}

/* Discover section specific styling */
QTableWidget#discoverTable {
    background-color: rgba(13, 17, 23, 0.8);
    border: 1px solid rgba(177, 186, 196, 0.2);
}

QTableWidget#discoverTable::item {
    padding: 16px 12px;
    border-bottom: 1px solid rgba(177, 186, 196, 0.08);
}

QTableWidget#discoverTable::item:hover {
    background-color: rgba(177, 186, 196, 0.05);
}

/* Progress bar styling */
QProgressBar {
    border: 2px solid rgba(177, 186, 196, 0.2);
    border-radius: 4px;
    text-align: center;
    background-color: rgba(177, 186, 196, 0.1);
}

QProgressBar::chunk {
    background-color: #1f6feb;
    border-radius: 2px;
}
"""

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
    search_timer = QTimer()
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Aurora - Package Manager")
        self.setGeometry(100, 100, 1600, 900)  # Increased width to accommodate sidebar
        self.setMinimumSize(1200, 700)  # Set minimum size
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet(DARK_STYLESHEET)
        # self.set_minimal_icon()
        
        self.current_view = "updates"
        self.updating = False
        self.all_packages = []
        self.search_results = []
        self.packages_per_page = 10
        self.current_page = 0
        self.loader_thread = None
        self.packages_ready.connect(self.on_packages_loaded)
        self.discover_results_ready.connect(self.display_discover_results)
        self.show_message.connect(self._show_message)
        self.log_signal.connect(self.log)
        self.setup_ui()
        self.center_window()
        self.update_toolbar()
        
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
        sidebar.setObjectName("sidebar")
        
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(15, 30, 15, 30)
        layout.setSpacing(20)  # Increased spacing between cards
        
        # Header
        header = QLabel("AURORA")
        header.setObjectName("sidebarHeader")
        layout.addWidget(header)
        
        # Spacer
        layout.addSpacing(20)  # Reduced spacing
        
        # Navigation buttons with icons
        nav_items = [
            (os.path.join(os.path.dirname(__file__), "assets", "icons", "discover.svg"), "Discover", "discover"),
            (os.path.join(os.path.dirname(__file__), "assets", "icons", "updates.svg"), "Updates", "updates"), 
            (os.path.join(os.path.dirname(__file__), "assets", "icons", "installed.svg"), "Installed", "installed"),
            (os.path.join(os.path.dirname(__file__), "assets", "icons", "local.svg"), "Bundles", "bundles")
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
        settings_btn = self.create_bottom_card_button("/home/alexa/StudioProjects/orca/assets/icons/settings.svg", "Settings", self.show_settings)
        bottom_layout.addWidget(settings_btn)
        
        # About button - card style
        about_btn = self.create_bottom_card_button("/home/alexa/StudioProjects/orca/assets/icons/about.svg", "About", self.show_about)
        bottom_layout.addWidget(about_btn)
        
        layout.addLayout(bottom_layout)
        
        return sidebar
    
    def create_nav_button(self, icon_path, text, view_id):
        btn = QPushButton()
        btn.setObjectName("navBtn")
        btn.setProperty("view_id", view_id)
        
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
            from PyQt6.QtSvg import QSvgRenderer
            from PyQt6.QtGui import QPainter
            
            svg_renderer = QSvgRenderer(icon_path)
            if svg_renderer.isValid():
                # Create pixmap and render SVG in white
                pixmap = QPixmap(50, 50)
                pixmap.fill(Qt.GlobalColor.transparent)
                
                painter = QPainter(pixmap)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
                
                # Set composition mode and color for white rendering
                from PyQt6.QtCore import QRectF
                svg_renderer.render(painter, QRectF(pixmap.rect()))
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                painter.fillRect(pixmap.rect(), QColor("#e1e5e9"))  # Light gray color
                painter.end()
                
                icon_label.setPixmap(pixmap)
            else:
                # Fallback to emoji if SVG is invalid
                emoji = self.get_fallback_icon(icon_path)
                icon_label.setText(emoji)
        except ImportError:
            # Fallback if SVG support not available
            try:
                pixmap = QPixmap(icon_path)
                if not pixmap.isNull():
                    scaled_pixmap = pixmap.scaled(40, 40, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    icon_label.setPixmap(scaled_pixmap)
                else:
                    emoji = self.get_fallback_icon(icon_path)
                    icon_label.setText(emoji)
            except:
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
            from PyQt6.QtSvg import QSvgRenderer
            from PyQt6.QtGui import QPainter
            
            svg_renderer = QSvgRenderer(icon_path)
            if svg_renderer.isValid():
                # Create pixmap and render SVG in white
                pixmap = QPixmap(28, 28)  # Match icon size
                pixmap.fill(Qt.GlobalColor.transparent)
                
                painter = QPainter(pixmap)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
                
                # Set composition mode and color for white rendering
                from PyQt6.QtCore import QRectF
                svg_renderer.render(painter, QRectF(pixmap.rect()))
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                painter.fillRect(pixmap.rect(), QColor("#e1e5e9"))  # Light gray color
                painter.end()
                
                icon_label.setPixmap(pixmap)
            else:
                # Fallback to emoji
                emoji = "⚙️" if "settings" in icon_path else "ℹ️"
                icon_label.setText(emoji)
        except ImportError:
            # Fallback if SVG support not available
            try:
                pixmap = QPixmap(icon_path)
                if not pixmap.isNull():
                    scaled_pixmap = pixmap.scaled(20, 20, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)  # Smaller scaling
                    icon_label.setPixmap(scaled_pixmap)
                else:
                    emoji = "⚙️" if "settings" in icon_path else "ℹ️"
                    icon_label.setText(emoji)
            except:
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
        splitter.setSizes([250, 900])
        
        layout.addWidget(splitter, 1)
        
        return content
    
    def create_header(self):
        header = QFrame()
        header.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 #1a1a1a, stop:1 #1a1a1a);
                border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            }
        """)
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
        
        refresh_btn = QPushButton("🔄")
        refresh_btn.setFixedSize(36, 36)
        refresh_btn.clicked.connect(self.refresh_packages)
        layout.addWidget(refresh_btn)
        
        return header
    
    def create_filters_panel(self):
        panel = QFrame()
        panel.setStyleSheet("""
            QFrame {
                background-color: #0f0f0f;
                border-right: 1px solid rgba(255, 255, 255, 0.1);
            }
        """)
        
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
        filters_layout = QVBoxLayout(self.filters_section)
        filters_layout.setContentsMargins(0, 0, 0, 0)
        filters_layout.setSpacing(8)
        
        filters_label = QLabel("Filters")
        filters_label.setObjectName("sectionLabel")
        filters_layout.addWidget(filters_label)
        
        filter_options = ["Updates available", "Installed"]
        self.filter_checkboxes = {}
        for option in filter_options:
            checkbox = QCheckBox(option)
            checkbox.setChecked(True)
            self.filter_checkboxes[option] = checkbox
            filters_layout.addWidget(checkbox)
        
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
        self.package_table.verticalHeader().setDefaultSectionSize(36)
        self.package_table.setAlternatingRowColors(True)
        self.package_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.package_table.setSelectionMode(QTableWidget.SelectionMode.MultiSelection)
        layout.addWidget(self.package_table, 1)
        
        # Load More Button
        self.load_more_btn = QPushButton("📥 Load More Packages")
        self.load_more_btn.setFixedHeight(36)
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
            layout.setSpacing(12)
            
            uninstall_btn = QPushButton("🗑️  Uninstall selected packages")
            uninstall_btn.setMinimumHeight(36)
            uninstall_btn.clicked.connect(self.uninstall_selected)
            layout.addWidget(uninstall_btn)
            
            update_btn = QPushButton("⬆️  Update selected packages")
            update_btn.setMinimumHeight(36)
            update_btn.clicked.connect(self.update_selected)
            layout.addWidget(update_btn)
            
            layout.addStretch()
            self.toolbar_layout.addLayout(layout)
        elif self.current_view == "discover":
            layout = QHBoxLayout()
            layout.setSpacing(12)
            
            install_btn = QPushButton("⬇️  Install selected packages")
            install_btn.setMinimumHeight(36)
            install_btn.clicked.connect(self.install_selected)
            layout.addWidget(install_btn)
            
            layout.addStretch()
            self.toolbar_layout.addLayout(layout)
        # For bundles, no toolbar
    
    def switch_view(self, view_id):
        self.current_view = view_id
        
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
        
        header_text, info_text = headers.get(view_id, ("Aurora", ""))
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
        if view_id == "installed":
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
        
        sources = ["pacman", "AUR", "Flatpak"]
        self.source_checkboxes = {}
        for source in sources:
            checkbox = QCheckBox(source)
            checkbox.setChecked(True)
            checkbox.stateChanged.connect(self.apply_source_filter)
            self.source_checkboxes[source] = checkbox
            self.sources_layout.addWidget(checkbox)
    
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
            self.package_table.setColumnCount(7)
            self.package_table.setHorizontalHeaderLabels(["", "Package Name", "Package ID", "Version", "Description", "Source", "Tags"])
            self.package_table.setObjectName("discoverTable")  # Apply special styling
            self.package_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            self.package_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            self.package_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
            self.package_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
            self.package_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
            self.package_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
            self.package_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
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
        
        def load_in_thread():
            try:
                result = subprocess.run(["pacman", "-Qu"], capture_output=True, text=True, timeout=60)
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
                self.log(f"Error: {str(e)}")
        
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
        
        Thread(target=load_in_thread, daemon=True).start()
    
    def on_packages_loaded(self, packages):
        self.all_packages = packages
        self.current_page = 0
        self.packages_per_page = 10
        self.package_table.setRowCount(0)
        self.display_page()
        self.log(f"Loaded {len(packages)} packages total. Showing first 10...")
    
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
            self.load_more_btn.setText(f"📥 Load More ({remaining} remaining)")
    
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
            self.load_more_btn.setText(f"📥 Load More ({remaining} remaining)")
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
        
        self.package_table.setItem(row, 1, QTableWidgetItem(pkg['name']))
        self.package_table.setItem(row, 2, QTableWidgetItem(pkg['id']))
        self.package_table.setItem(row, 3, QTableWidgetItem(pkg['version']))
        self.package_table.setItem(row, 4, QTableWidgetItem(pkg.get('description', '')))
        self.package_table.setItem(row, 5, QTableWidgetItem(pkg['source']))
        self.package_table.setItem(row, 6, QTableWidgetItem(pkg.get('tags', '')))
    
    def add_package_row(self, name, pkg_id, version, new_version, source, pkg_data=None):
        row = self.package_table.rowCount()
        self.package_table.insertRow(row)
        
        checkbox = QCheckBox()
        checkbox.setChecked(True)
        self.package_table.setCellWidget(row, 0, checkbox)
        
        self.package_table.setItem(row, 1, QTableWidgetItem(name))
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
            self.package_table.setItem(row, 4, QTableWidgetItem(new_version))
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
            self.load_more_btn.setText(f"📥 Load More ({remaining} remaining)")
        
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
    
    def update_selected(self):
        selected_rows = self.package_table.selectionModel().selectedRows()
        if not selected_rows:
            self.log("No packages selected for update")
            # QMessageBox.warning(self, "No Selection", "Please select packages to update")
            return
        
        packages = []
        for row in selected_rows:
            pkg_name = self.package_table.item(row.row(), 1).text()
            packages.append(pkg_name.lower())
        
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
        selected_rows = self.package_table.selectionModel().selectedRows()
        if not selected_rows:
            self.log_signal.emit("No packages selected for installation")
            return
        
        packages_by_source = {}
        for row in selected_rows:
            pkg_name = self.package_table.item(row.row(), 1).text().lower()
            source = self.package_table.item(row.row(), 5).text()
            if source not in packages_by_source:
                packages_by_source[source] = []
            packages_by_source[source].append(pkg_name)
        
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
            self.load_more_btn.setText(f"📥 Load More ({remaining} remaining)")
        
        self.log(f"Showing {len(filtered[:10])} of {len(filtered)} packages")

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
    
    def show_about(self):
        QMessageBox.information(self, "About Aurora", 
                              "Aurora - Modern Arch Package Manager\nVersion 1.0\n\nBuilt with PyQt6")
    
    def log(self, message):
        self.console.append(message)

def main():
    if len(sys.argv) > 1:
        if sys.argv[1] in ["--help", "-h"]:
            print("Aurora - Modern Arch Package Manager")
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
