"""
SourceItem Component - Individual source selection widget
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox
from PyQt6.QtGui import QPixmap, QPainter, QColor
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtSvg import QSvgRenderer


class SourceItem(QWidget):
    """Component for individual source selection with icon and checkbox"""

    def __init__(self, source_name, icon_path, parent=None):
        super().__init__(parent)
        self.source_name = source_name
        self.icon_path = icon_path
        self.checked = True
        self.init_ui()

    def init_ui(self):
        """Initialize the source item UI"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        # Icon container with better styling
        self.icon_container = QWidget()
        self.icon_container.setFixedSize(36, 36)
        self.icon_container.setObjectName("sourceIconContainer")

        icon_layout = QVBoxLayout(self.icon_container)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.icon_label = QLabel()
        self.icon_label.setFixedSize(24, 24)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.set_icon(self.icon_path)
        icon_layout.addWidget(self.icon_label)

        # Checkbox with better styling
        self.checkbox = QCheckBox(self.source_name)
        self.checkbox.setChecked(self.checked)
        self.checkbox.setObjectName("sourceCheckbox")

        layout.addWidget(self.icon_container)
        layout.addWidget(self.checkbox, 1)

        # Connect signals
        self.checkbox.stateChanged.connect(self.on_state_changed)

        # Apply styling
        self.setStyleSheet(self.get_stylesheet())

    def set_icon(self, icon_path):
        """Set the icon for this source item"""
        try:
            svg_renderer = QSvgRenderer(icon_path)
            if svg_renderer.isValid():
                pixmap = QPixmap(24, 24)
                pixmap.fill(Qt.GlobalColor.transparent)

                painter = QPainter(pixmap)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

                svg_renderer.render(painter, QRectF(pixmap.rect()))
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                painter.fillRect(pixmap.rect(), QColor("#00BFAE"))
                painter.end()

                self.icon_label.setPixmap(pixmap)
            else:
                self.icon_label.setText("📦")
                self.icon_label.setStyleSheet("font-size: 16px; color: #00BFAE;")
        except:
            emoji_map = {
                "pacman": "📦",
                "AUR": "🧡",
                "Flatpak": "📱",
                "npm": "📦",
                "pip": "🐍"
            }
            self.icon_label.setText(emoji_map.get(self.source_name.lower(), "📦"))
            self.icon_label.setStyleSheet("font-size: 16px; color: #00BFAE;")

    def on_state_changed(self, state):
        """Handle checkbox state changes"""
        self.checked = state == Qt.CheckState.Checked
        self.update_visual_state()

    def update_visual_state(self):
        """Update visual appearance based on checked state"""
        if self.checked:
            self.icon_container.setStyleSheet("""
                QWidget#sourceIconContainer {
                    background-color: rgba(0, 191, 174, 0.1);
                    border: 1px solid rgba(0, 191, 174, 0.3);
                    border-radius: 8px;
                }
            """)
        else:
            self.icon_container.setStyleSheet("""
                QWidget#sourceIconContainer {
                    background-color: rgba(42, 45, 51, 0.3);
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 8px;
                }
            """)

    def get_stylesheet(self):
        """Get stylesheet for this component"""
        return """
            SourceItem {
                background-color: transparent;
                border-radius: 8px;
                margin: 2px 0px;
            }

            SourceItem:hover {
                background-color: rgba(0, 191, 174, 0.05);
                border-radius: 8px;
            }

            QCheckBox#sourceCheckbox {
                color: #F0F0F0;
                font-size: 13px;
                font-weight: 500;
                spacing: 8px;
            }

            QCheckBox#sourceCheckbox::indicator {
                width: 20px;
                height: 20px;
                border-radius: 10px;
                border: 2px solid rgba(0, 191, 174, 0.4);
                background-color: rgba(42, 45, 51, 0.8);
            }

            QCheckBox#sourceCheckbox::indicator:checked {
                background-color: #00BFAE;
                border: 2px solid #00BFAE;
            }

            QCheckBox#sourceCheckbox::indicator:unchecked {
                background-color: rgba(42, 45, 51, 0.8);
            }

            QCheckBox#sourceCheckbox::indicator:hover {
                border-color: rgba(0, 191, 174, 0.8);
            }

            QWidget#sourceIconContainer {
                background-color: rgba(0, 191, 174, 0.1);
                border: 1px solid rgba(0, 191, 174, 0.3);
                border-radius: 8px;
            }
        """

    def is_checked(self):
        """Return whether this source is checked"""
        return self.checked

    def set_checked(self, checked):
        """Set the checked state"""
        self.checked = checked
        self.checkbox.setChecked(checked)
        self.update_visual_state()
