"""
LargeSearchBox Component - Large search box for package discovery
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel, QPushButton, QFrame
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
        layout.setContentsMargins(32, 48, 32, 48)
        layout.setSpacing(24)

        hero_card = QFrame()
        hero_card.setObjectName("largeSearchCard")
        card_layout = QVBoxLayout(hero_card)
        card_layout.setContentsMargins(36, 40, 36, 40)
        card_layout.setSpacing(24)

        title_label = QLabel("Discover New Packages")
        title_label.setObjectName("heroTitle")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(title_label)

        subtitle_label = QLabel("Search across pacman, AUR, Flatpak, and npm repositories")
        subtitle_label.setObjectName("heroSubtitle")
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(subtitle_label)

        search_container = QWidget()
        search_container.setObjectName("largeSearchContainer")
        search_layout = QHBoxLayout(search_container)
        search_layout.setContentsMargins(24, 18, 24, 18)
        search_layout.setSpacing(16)

        self.search_icon = QLabel()
        self.search_icon.setFixedSize(40, 40)
        self.search_icon.setObjectName("searchIconBubble")
        self.set_search_icon()
        search_layout.addWidget(self.search_icon)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Try \"system monitor\" or \"AUR helpers\"")
        self.search_input.setObjectName("largeSearchInput")
        self.search_input.returnPressed.connect(self.on_search_triggered)
        self.search_input.textChanged.connect(self.on_text_changed)
        search_layout.addWidget(self.search_input, 1)

        self.search_button = QPushButton("Search")
        self.search_button.setMinimumWidth(110)
        self.search_button.setFixedHeight(48)
        self.search_button.setObjectName("largeSearchButton")
        self.search_button.clicked.connect(self.on_search_triggered)
        self.set_button_icon()
        search_layout.addWidget(self.search_button)

        card_layout.addWidget(search_container)

        highlights_container = QWidget()
        highlights_container.setObjectName("highlightsContainer")
        highlights_layout = QHBoxLayout(highlights_container)
        highlights_layout.setContentsMargins(0, 0, 0, 0)
        highlights_layout.setSpacing(18)

        highlights = [
            ("🚀", "Instant multi-repo search", "Instant unified search"),
            ("⭐", "Curated results", "Trusted package picks"),
            ("⚙️", "Power user ready", "Advanced user control")
        ]

        for emoji, title, description in highlights:
            highlight_card = QFrame()
            highlight_card.setObjectName("highlightCard")
            card_layout_inner = QVBoxLayout(highlight_card)
            card_layout_inner.setContentsMargins(18, 18, 18, 18)
            card_layout_inner.setSpacing(6)

            icon_label = QLabel(emoji)
            icon_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            icon_label.setObjectName("highlightIcon")
            card_layout_inner.addWidget(icon_label)

            title_label = QLabel(title)
            title_label.setObjectName("highlightTitle")
            card_layout_inner.addWidget(title_label)

            description_label = QLabel(description)
            description_label.setObjectName("highlightDescription")
            description_label.setWordWrap(False)
            card_layout_inner.addWidget(description_label)

            highlights_layout.addWidget(highlight_card, 1)

        card_layout.addWidget(highlights_container)

        layout.addStretch()
        layout.addWidget(hero_card, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addStretch()

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
                background-color: transparent;
            }

            QFrame#largeSearchCard {
                background-color: rgba(32, 34, 40, 0.95);
                border-radius: 28px;
                border: 1px solid rgba(0, 191, 174, 0.18);
            }

            QLabel#heroTitle {
                color: #F6F7FB;
                font-size: 28px;
                font-weight: 600;
                letter-spacing: 0.6px;
            }

            QLabel#heroSubtitle {
                color: #AEB4C2;
                font-size: 16px;
            }

            QWidget#largeSearchContainer {
                background-color: rgba(20, 22, 28, 0.9);
                border-radius: 28px;
                border: 1px solid rgba(0, 191, 174, 0.35);
            }

            QWidget#largeSearchContainer:hover {
                border-color: rgba(0, 230, 214, 0.65);
                background-color: rgba(22, 26, 34, 0.95);
            }

            QLabel#searchIconBubble {
                background-color: rgba(0, 191, 174, 0.12);
                border-radius: 20px;
                padding: 4px;
            }

            QLineEdit#largeSearchInput {
                background-color: transparent;
                border: none;
                color: #F0F3F5;
                font-size: 18px;
                font-weight: 400;
                padding: 8px 0px;
                selection-background-color: rgba(0, 191, 174, 0.3);
            }

            QLineEdit#largeSearchInput::placeholder {
                color: #8C94A4;
                font-size: 17px;
            }

            QLineEdit#largeSearchInput:focus {
                outline: none;
            }

            QPushButton#largeSearchButton {
                background-color: #00BFAE;
                border: none;
                border-radius: 24px;
                padding: 0 24px;
                color: #081017;
                font-size: 17px;
                font-weight: 600;
            }

            QPushButton#largeSearchButton:hover {
                background-color: #00D4C1;
            }

            QPushButton#largeSearchButton:pressed {
                background-color: #009688;
            }

            QWidget#highlightsContainer {
                background-color: transparent;
            }

            QFrame#highlightCard {
                background-color: rgba(18, 21, 27, 0.9);
                border-radius: 18px;
                border: 1px solid rgba(0, 191, 174, 0.14);
            }

            QLabel#highlightIcon {
                font-size: 24px;
            }

            QLabel#highlightTitle {
                color: #EAF6F5;
                font-size: 15px;
                font-weight: 600;
            }

            QLabel#highlightDescription {
                color: #9CA6B4;
                font-size: 11px;
                line-height: 1.4em;
            }
        """
