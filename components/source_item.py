"""
SourceItem Component - Individual source selection widget
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QGraphicsDropShadowEffect
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
        self.icon_container.setFixedSize(40, 40)
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

        # Accent and interactivity
        self.accent_hex = self.get_accent_color(self.source_name)
        self.accent_color = QColor(self.accent_hex)
        self.apply_accent_styles()
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setToolTip(f"Search {self.source_name}")

        # Subtle shadow for icon
        try:
            shadow = QGraphicsDropShadowEffect(self.icon_container)
            shadow.setBlurRadius(12)
            shadow.setOffset(0, 2)
            c = QColor(self.accent_color)
            c.setAlpha(80)
            shadow.setColor(c)
            self.icon_container.setGraphicsEffect(shadow)
        except ImportError:
            # Handle missing graphics effect support gracefully
            pass

        # Apply styling
        self.setStyleSheet(self.get_stylesheet())
        self.update_visual_state()

    def set_icon(self, icon_path):
        """Set the icon for this source item"""
        try:
            svg_renderer = QSvgRenderer(icon_path)
            if svg_renderer.isValid():
                pixmap = QPixmap(24, 24)
                if pixmap.isNull():
                    self.icon_label.setText("📦")
                    self.icon_label.setStyleSheet("font-size: 16px; color: white;")
                    return
                pixmap.fill(Qt.GlobalColor.transparent)

                painter = QPainter(pixmap)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

                svg_renderer.render(painter, QRectF(pixmap.rect()))
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                painter.fillRect(pixmap.rect(), QColor("white"))
                painter.end()

                self.icon_label.setPixmap(pixmap)
            else:
                self.icon_label.setText("📦")
                self.icon_label.setStyleSheet("font-size: 16px; color: white;")
        except OSError:
            # Handle file loading or parsing errors with emoji fallback
            emoji_map = {
                "pacman": "📦",
                "aur": "🧡",
                "flatpak": "📱",
                "npm": "📦",
            }
            self.icon_label.setText(emoji_map.get(self.source_name.lower(), "📦"))
            self.icon_label.setStyleSheet("font-size: 16px; color: white;")

    def on_state_changed(self, state):
        """Handle checkbox state changes"""
        self.checked = state == Qt.CheckState.Checked
        self.update_visual_state()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            try:
                pos = event.position().toPoint()
            except AttributeError:
                pos = event.pos()
            # Toggle only when clicking outside the checkbox to avoid double toggles
            if not self.checkbox.geometry().contains(pos):
                self.checkbox.toggle()
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            # Avoid double toggle when the checkbox itself has focus
            if not self.checkbox.hasFocus():
                self.checkbox.toggle()
                return
        super().keyPressEvent(event)

    def get_accent_color(self, name):
        n = name.lower()
        mapping = {
            "pacman": "#4FC3F7",
            "aur": "#FF8A65",
            "flatpak": "#26A69A",
            "npm": "#E53935",
        }
        return mapping.get(n, "#00BFAE")

    def apply_accent_styles(self):
        r, g, b = self.accent_color.red(), self.accent_color.green(), self.accent_color.blue()
        self.checkbox.setStyleSheet(
            f"""
            QCheckBox#sourceCheckbox {{
                color: #F0F0F0;
                font-size: 13px;
                font-weight: 600;
                spacing: 8px;
            }}
            QCheckBox#sourceCheckbox::indicator {{
                width: 20px;
                height: 20px;
                border-radius: 10px;
                border: 2px solid rgba({r}, {g}, {b}, 0.4);
                background-color: rgba(42, 45, 51, 0.8);
            }}
            QCheckBox#sourceCheckbox::indicator:checked {{
                background-color: {self.accent_hex};
                border: 2px solid {self.accent_hex};
            }}
            QCheckBox#sourceCheckbox::indicator:hover {{
                border-color: rgba({r}, {g}, {b}, 0.8);
            }}
            """
        )

    def update_visual_state(self):
        """Update visual appearance based on checked state"""
        if self.checked:
            r, g, b = self.accent_color.red(), self.accent_color.green(), self.accent_color.blue()
            self.icon_container.setStyleSheet(
                f"""
                QWidget#sourceIconContainer {{
                    background-color: rgba({r}, {g}, {b}, 0.14);
                    border: 1px solid rgba({r}, {g}, {b}, 0.4);
                    border-radius: 12px;
                }}
                """
            )
        else:
            self.icon_container.setStyleSheet("""
                QWidget#sourceIconContainer {
                    background-color: rgba(42, 45, 51, 0.3);
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 12px;
                }
            """)

    def get_stylesheet(self):
        """Get stylesheet for this component"""
        return """
            SourceItem {
                background-color: transparent;
                border-radius: 12px;
                margin: 2px 0px;
            }

            SourceItem:hover {
                background-color: rgba(0, 191, 174, 0.05);
                border-radius: 12px;
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
                border-radius: 12px;
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
