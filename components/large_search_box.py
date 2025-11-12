"""
LargeSearchBox Component - Large search box for package discovery
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel, QPushButton, QFrame, QGridLayout, QProgressBar
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QRectF, QTimer
from PyQt6.QtGui import QPixmap, QPainter, QIcon, QColor, QResizeEvent
from PyQt6.QtSvg import QSvgRenderer
import os


class LargeSearchBox(QWidget):
    """Large search box component for discover page"""

    search_requested = pyqtSignal(str)  # Emits query when search is triggered

    def __init__(self, parent=None):
        super().__init__(parent)
        self.search_timer = QTimer()
        self.search_timer.setInterval(300)  # Faster response
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.on_auto_search)
        self.highlight_widgets = []
        self.compact_mode = False
        self.is_maximized_layout = False
        self.current_width = 0
        self.main_layout = None
        self.hero_card = None
        self.expanded_sections = None
        self.init_ui()

    def init_ui(self):
        """Initialize the large search box UI with responsive design"""
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(20, 30, 20, 30)
        self.main_layout.setSpacing(20)
        
        # Create main hero card
        self.create_hero_card()
        
        # Create expanded sections (initially hidden)
        self.create_expanded_sections()
        
        # Set initial layout - force compact mode initially
        self.current_width = 800  # Start with a typical window width
        self.is_maximized_layout = False
        self.rebuild_layout()
        self.setStyleSheet(self.get_stylesheet())

    def create_hero_card(self):
        """Create the main search card"""
        self.hero_card = QFrame()
        self.hero_card.setObjectName("largeSearchCard")
        card_layout = QVBoxLayout(self.hero_card)
        card_layout.setContentsMargins(36, 40, 36, 40)
        card_layout.setSpacing(24)

        # Title and subtitle
        title_label = QLabel("Discover New Packages")
        title_label.setObjectName("heroTitle")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(title_label)

        subtitle_label = QLabel("Search across pacman, AUR, Flatpak, and npm repositories")
        subtitle_label.setObjectName("heroSubtitle")
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(subtitle_label)

        # Search container
        self.create_search_container(card_layout)
        
        # Highlights container
        self.create_highlights_container(card_layout)

    def create_search_container(self, parent_layout):
        """Create the search input container"""
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
        self.search_input.setFixedHeight(48)
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

        parent_layout.addWidget(search_container)

    def create_highlights_container(self, parent_layout):
        """Create highlights/feature cards container"""
        self.highlights_container = QWidget()
        self.highlights_container.setObjectName("highlightsContainer")
        
        # This will be dynamically set based on layout mode
        self.highlights_layout = QHBoxLayout(self.highlights_container)
        self.highlights_layout.setContentsMargins(0, 0, 0, 0)
        self.highlights_layout.setSpacing(18)

        parent_layout.addWidget(self.highlights_container)
        self.create_highlight_cards()

    def create_highlight_cards(self):
        """Create feature highlight cards"""
        # Clear existing widgets
        for widget in self.highlight_widgets:
            widget["card"].setParent(None)
        self.highlight_widgets.clear()

        # Define highlights based on layout mode
        if self.is_maximized_layout:
            highlights = [
                ("🚀", "Blazing Fast search", "Instant unified search"),
                ("⭕", "Curated Collections", "Instant unified search"),
                ("⭐", "Curated results", "Trusted package picks"),
                ("⚙️", "Advanced User Tools", "Advanced user control")
            ]
        else:
            highlights = [
                ("🚀", "Instant multi repo search", "Instant unified search"),
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
            title_label.setWordWrap(True)
            card_layout_inner.addWidget(title_label)

            description_label = QLabel(description)
            description_label.setObjectName("highlightDescription")
            description_label.setWordWrap(True)
            card_layout_inner.addWidget(description_label)

            self.highlight_widgets.append({
                "card": highlight_card,
                "icon": icon_label,
                "title": title_label,
                "desc": description_label,
            })

            self.highlights_layout.addWidget(highlight_card, 1)

    def create_expanded_sections(self):
        """Create additional sections for maximized layout"""
        self.expanded_sections = QWidget()
        self.expanded_sections.setObjectName("expandedSections")
        expanded_layout = QHBoxLayout(self.expanded_sections)
        expanded_layout.setContentsMargins(0, 20, 0, 0)
        expanded_layout.setSpacing(20)

        # Recent Updates section
        recent_updates = self.create_recent_updates_section()
        expanded_layout.addWidget(recent_updates, 1)

        # System Health section
        system_health = self.create_system_health_section()
        expanded_layout.addWidget(system_health, 1)

        self.expanded_sections.hide()  # Initially hidden

    def create_recent_updates_section(self):
        """Create Recent Updates section"""
        section = QFrame()
        section.setObjectName("expandedSection")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        title = QLabel("Recent Updates")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        # Sample update items
        updates = [
            ("🍽️", "Pacman Tui plates", "SSU saved"),
            ("⚪", "System monitor, auutils, l ar poputils", "10789 at stage"),
            ("🔧", "Docs system Cleansage", "231.83/22-1/712"),
            ("⚪", "Neovim/nvim/neovim/nvim.ly, Tizen 22", "101.3/3 pis Aut/1.83/712")
        ]

        for icon, title_text, status in updates:
            item = QFrame()
            item.setObjectName("updateItem")
            item_layout = QHBoxLayout(item)
            item_layout.setContentsMargins(12, 8, 12, 8)
            item_layout.setSpacing(12)

            icon_label = QLabel(icon)
            icon_label.setObjectName("updateIcon")
            item_layout.addWidget(icon_label)

            text_container = QWidget()
            text_layout = QVBoxLayout(text_container)
            text_layout.setContentsMargins(0, 0, 0, 0)
            text_layout.setSpacing(2)

            title_label = QLabel(title_text)
            title_label.setObjectName("updateTitle")
            text_layout.addWidget(title_label)

            status_label = QLabel(status)
            status_label.setObjectName("updateStatus")
            text_layout.addWidget(status_label)

            item_layout.addWidget(text_container, 1)
            layout.addWidget(item)

        return section

    def create_system_health_section(self):
        """Create System Health section"""
        section = QFrame()
        section.setObjectName("expandedSection")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        title = QLabel("System Health")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        # CPU Load
        cpu_container = QWidget()
        cpu_layout = QVBoxLayout(cpu_container)
        cpu_layout.setContentsMargins(0, 0, 0, 0)
        cpu_layout.setSpacing(8)

        cpu_header = QHBoxLayout()
        cpu_icon = QLabel("🖥️")
        cpu_icon.setObjectName("healthIcon")
        cpu_header.addWidget(cpu_icon)

        cpu_label = QLabel("CPU Load")
        cpu_label.setObjectName("healthLabel")
        cpu_header.addWidget(cpu_label, 1)

        cpu_value = QLabel("1.8-0.7 need")
        cpu_value.setObjectName("healthValue")
        cpu_header.addWidget(cpu_value)

        cpu_layout.addLayout(cpu_header)

        # Memory Usage
        memory_container = QWidget()
        memory_layout = QVBoxLayout(memory_container)
        memory_layout.setContentsMargins(0, 0, 0, 8)
        memory_layout.setSpacing(8)

        memory_header = QHBoxLayout()
        memory_icon = QLabel("💾")
        memory_icon.setObjectName("healthIcon")
        memory_header.addWidget(memory_icon)

        memory_label = QLabel("Memory Usage")
        memory_label.setObjectName("healthLabel")
        memory_header.addWidget(memory_label, 1)

        memory_layout.addLayout(memory_header)

        # Progress bar for memory
        memory_progress = QProgressBar()
        memory_progress.setObjectName("memoryProgress")
        memory_progress.setValue(65)
        memory_progress.setTextVisible(False)
        memory_progress.setFixedHeight(8)
        memory_layout.addWidget(memory_progress)

        layout.addWidget(cpu_container)
        layout.addWidget(memory_container)

        return section

    def showEvent(self, event):
        """Handle widget show events"""
        super().showEvent(event)
        # Ensure layout is properly set when widget becomes visible
        if self.width() > 0:
            self.current_width = self.width()
            self.update_layout_for_size()

    def resizeEvent(self, event: QResizeEvent):
        """Handle window resize events"""
        super().resizeEvent(event)
        new_width = event.size().width()
        
        # Only update if width changed significantly (avoid excessive updates)
        if abs(new_width - self.current_width) > 50:
            self.current_width = new_width
            self.update_layout_for_size()

    def update_layout_for_size(self):
        """Update layout based on current window size"""
        # Get actual widget width if available, fallback to current_width
        actual_width = max(self.width(), self.current_width)
        
        # Determine if we should use maximized layout (wider than 1200px)
        should_be_maximized = actual_width > 1200
        
        if should_be_maximized != self.is_maximized_layout:
            self.is_maximized_layout = should_be_maximized
            self.rebuild_layout()
        
        # Update margins based on width
        if actual_width > 1400:
            margins = (60, 40, 60, 40)
        elif actual_width > 1000:
            margins = (40, 30, 40, 30)
        else:
            margins = (20, 30, 20, 30)
        
        self.main_layout.setContentsMargins(*margins)

    def rebuild_layout(self):
        """Rebuild the layout when switching between modes"""
        # Clear current layout
        while self.main_layout.count():
            child = self.main_layout.takeAt(0)
            if child.widget():
                child.widget().setParent(None)
        
        if self.is_maximized_layout:
            # Maximized layout: hero card + expanded sections
            self.main_layout.addWidget(self.hero_card)
            self.main_layout.addWidget(self.expanded_sections)
            self.expanded_sections.show()
        else:
            # Compact layout: centered hero card
            self.main_layout.addStretch()
            self.main_layout.addWidget(self.hero_card, alignment=Qt.AlignmentFlag.AlignCenter)
            self.main_layout.addStretch()
            self.expanded_sections.hide()
        
        # Recreate highlight cards for new layout
        self.create_highlight_cards()

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

    def set_compact_mode(self, compact: bool):
        self.compact_mode = compact
        for w in self.highlight_widgets:
            try:
                w["icon"].setVisible(not compact)
                w["desc"].setVisible(not compact)
                w["title"].setVisible(True)
            except Exception:
                pass

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
                min-height: 100px;
            }

            QFrame#highlightCard:hover {
                background-color: rgba(22, 26, 34, 0.95);
                border-color: rgba(0, 191, 174, 0.25);
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

            /* Expanded Sections Styles */
            QWidget#expandedSections {
                background-color: transparent;
            }

            QFrame#expandedSection {
                background-color: rgba(28, 30, 36, 0.95);
                border-radius: 20px;
                border: 1px solid rgba(0, 191, 174, 0.12);
            }

            QLabel#sectionTitle {
                color: #F6F7FB;
                font-size: 18px;
                font-weight: 600;
                margin-bottom: 8px;
            }

            /* Recent Updates Styles */
            QFrame#updateItem {
                background-color: rgba(20, 22, 28, 0.7);
                border-radius: 12px;
                border: 1px solid rgba(0, 191, 174, 0.08);
                margin: 2px 0px;
            }

            QFrame#updateItem:hover {
                background-color: rgba(24, 26, 32, 0.9);
                border-color: rgba(0, 191, 174, 0.15);
            }

            QLabel#updateIcon {
                font-size: 16px;
                min-width: 20px;
            }

            QLabel#updateTitle {
                color: #E8F4F3;
                font-size: 13px;
                font-weight: 500;
            }

            QLabel#updateStatus {
                color: #9CA6B4;
                font-size: 11px;
            }

            /* System Health Styles */
            QLabel#healthIcon {
                font-size: 16px;
                min-width: 20px;
            }

            QLabel#healthLabel {
                color: #E8F4F3;
                font-size: 13px;
                font-weight: 500;
            }

            QLabel#healthValue {
                color: #00BFAE;
                font-size: 12px;
                font-weight: 600;
            }

            QProgressBar#memoryProgress {
                background-color: rgba(20, 22, 28, 0.8);
                border-radius: 4px;
                border: none;
            }

            QProgressBar#memoryProgress::chunk {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #00BFAE, stop:0.7 #00D4C1, stop:1 #00E6D6);
                border-radius: 4px;
            }
        """
