"""
LargeSearchBox Component - Large search box for package discovery
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel, QPushButton
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QRectF, QTimer
from PyQt6.QtGui import QPixmap, QPainter, QIcon, QColor
from PyQt6.QtSvg import QSvgRenderer
import os


class LargeSearchBox(QWidget):
    """Large search box component for discover page"""

    search_requested = pyqtSignal(str)  # Emits query when search is triggered

    def __init__(self, parent=None):
        super().__init__(parent)
        self.search_timer = QTimer()
        self.search_timer.setInterval(800)
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.on_auto_search)
        self.init_ui()

    def init_ui(self):
        """Initialize the large search box UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 60, 40, 60)  # Large margins for centering
        layout.setSpacing(20)

        # Main search container
        search_container = QWidget()
        search_container.setObjectName("largeSearchContainer")
        search_layout = QHBoxLayout(search_container)
        search_layout.setContentsMargins(30, 20, 30, 20)
        search_layout.setSpacing(15)

        # Search icon
        self.search_icon = QLabel()
        self.search_icon.setFixedSize(32, 32)
        self.set_search_icon()
        search_layout.addWidget(self.search_icon)

        # Large search input
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search for packages...")
        self.search_input.setObjectName("largeSearchInput")
        self.search_input.returnPressed.connect(self.on_search_triggered)
        self.search_input.textChanged.connect(self.on_text_changed)
        search_layout.addWidget(self.search_input, 1)

        # Search button
        self.search_button = QPushButton()
        self.search_button.setFixedSize(48, 48)
        self.search_button.setObjectName("largeSearchButton")
        self.search_button.clicked.connect(self.on_search_triggered)
        self.set_button_icon()
        search_layout.addWidget(self.search_button)

        layout.addWidget(search_container, alignment=Qt.AlignmentFlag.AlignCenter)

        # Hint text
        hint_label = QLabel("Discover packages from pacman, AUR, Flatpak, npm, and pip")
        hint_label.setObjectName("searchHint")
        hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint_label, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addStretch()  # Push everything to center

        # Apply styling
        self.setStyleSheet(self.get_stylesheet())

    def set_search_icon(self):
        """Set the search icon in the input area"""
        try:
            icon_path = os.path.join(os.path.dirname(__file__), "..", "assets", "icons", "discover", "search.svg")
            if os.path.exists(icon_path):
                svg_renderer = QSvgRenderer(icon_path)
                if svg_renderer.isValid():
                    pixmap = QPixmap(32, 32)
                    pixmap.fill(Qt.GlobalColor.transparent)
                    with QPainter(pixmap) as painter:
                        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                        svg_renderer.render(painter, QRectF(pixmap.rect()))
                        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                        painter.fillRect(pixmap.rect(), QColor("#666666"))
                    self.search_icon.setPixmap(pixmap)
                else:
                    self.search_icon.setText("🔍")
            else:
                self.search_icon.setText("🔍")
        except Exception as e:
            self.search_icon.setText("🔍")

    def set_button_icon(self):
        """Set the search button icon"""
        try:
            icon_path = os.path.join(os.path.dirname(__file__), "..", "assets", "icons", "discover", "search.svg")
            if os.path.exists(icon_path):
                svg_renderer = QSvgRenderer(icon_path)
                if svg_renderer.isValid():
                    pixmap = QPixmap(24, 24)
                    pixmap.fill(Qt.GlobalColor.transparent)
                    with QPainter(pixmap) as painter:
                        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                        svg_renderer.render(painter, QRectF(pixmap.rect()))
                        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                        painter.fillRect(pixmap.rect(), QColor("white"))
                    self.search_button.setIcon(QIcon(pixmap))
                    self.search_button.setIconSize(QSize(24, 24))
                else:
                    self.search_button.setText("🔍")
            else:
                self.search_button.setText("🔍")
        except Exception as e:
            self.search_button.setText("🔍")

    def on_text_changed(self):
        """Start auto-search timer when text changes"""
        self.search_timer.start()

    def on_auto_search(self):
        """Perform auto-search when timer times out"""
        query = self.search_input.text().strip()
        if len(query) >= 3:  # Only search if 3+ characters
            self.search_requested.emit(query)

    def on_search_triggered(self):
        """Handle search trigger (enter or button click)"""
        query = self.search_input.text().strip()
        if query:
            self.search_timer.stop()  # Stop any pending auto-search
            self.search_requested.emit(query)

    def get_stylesheet(self):
        """Get stylesheet for this component"""
        return """
            LargeSearchBox {
                background-color: rgba(42, 45, 51, 0.95);
                border-radius: 12px;
            }

            QWidget#largeSearchContainer {
                background-color: rgba(52, 55, 61, 0.9);
                border: 2px solid rgba(0, 191, 174, 0.3);
                border-radius: 25px;
                min-width: 400px;
                max-width: 600px;
            }

            QWidget#largeSearchContainer:hover {
                border-color: rgba(0, 191, 174, 0.6);
                background-color: rgba(52, 55, 61, 0.95);
            }

            QLineEdit#largeSearchInput {
                background-color: transparent;
                border: none;
                color: #F0F0F0;
                font-size: 18px;
                font-weight: 400;
                padding: 10px 0px;
                selection-background-color: rgba(0, 191, 174, 0.3);
            }

            QLineEdit#largeSearchInput::placeholder {
                color: #888888;
                font-size: 18px;
            }

            QLineEdit#largeSearchInput:focus {
                outline: none;
            }

            QPushButton#largeSearchButton {
                background-color: #00BFAE;
                border: none;
                border-radius: 24px;
                padding: 12px;
            }

            QPushButton#largeSearchButton:hover {
                background-color: #00D4C1;
            }

            QPushButton#largeSearchButton:pressed {
                background-color: #009688;
            }

            QLabel#searchHint {
                color: #A0A0A0;
                font-size: 14px;
                margin-top: 20px;
            }
        """
