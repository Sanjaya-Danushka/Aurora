"""
LoadingSpinner Component - Reusable loading spinner widget
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import QTimer, Qt, QRectF
from PyQt6.QtGui import QPixmap, QPainter, QFont, QColor, QPen


class LoadingSpinner(QWidget):
    """Reusable loading spinner component"""

    def __init__(self, parent=None, message="Loading..."):
        super().__init__(parent)
        self.message = message
        self.spinner_angle = 0
        self.init_ui()

    def init_ui(self):
        """Initialize the loading spinner UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 20, 0, 20)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Spinner label - will be replaced with custom drawing
        self.spinner_label = QLabel()
        self.spinner_label.setFixedSize(48, 48)
        layout.addWidget(self.spinner_label, alignment=Qt.AlignmentFlag.AlignCenter)

        # Set up timer for animation
        self.spinner_timer = QTimer()
        self.spinner_timer.timeout.connect(self.animate_spinner)

        # Loading text
        self.loading_label = QLabel(self.message)
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.loading_label)

        # Apply styling
        self.setStyleSheet("""
            LoadingSpinner {
                background-color: transparent;
                border: none;
            }

            LoadingSpinner QLabel {
                background-color: transparent;
                color: #00BFAE;
                font-size: 14px;
                font-weight: 500;
            }
        """)

    def animate_spinner(self):
        """Animate the spinner with a beautiful cycling effect"""
        self.spinner_angle = (self.spinner_angle + 15) % 360
        
        pixmap = QPixmap(48, 48)
        if pixmap.isNull():
            return
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        if not painter.isActive():
            return
            
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Center of the spinner
        center = pixmap.rect().center()
        
        # Draw the cycling spinner
        for i in range(8):  # 8 segments
            angle = (self.spinner_angle + i * 45) % 360
            # Calculate opacity based on position in cycle
            # Segments fade in and out in a wave pattern
            progress = (angle / 360.0)
            opacity = 0.3 + 0.7 * (1 - abs(progress - 0.5) * 2)  # Peak at 0.5, fade to 0.3
            
            # Set color with opacity
            color = QColor("#00BFAE")
            color.setAlphaF(opacity)
            
            painter.setPen(QPen(color, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            
            # Draw arc segment
            start_angle = angle * 16  # Qt uses 1/16th degrees
            span_angle = 30 * 16  # 30 degree arc
            
            # Rectangle for the arc (slightly inset from edges)
            rect = QRectF(6, 6, 36, 36)  # 48-12=36 diameter
            painter.drawArc(rect, start_angle, span_angle)
        
        painter.end()
        self.spinner_label.setPixmap(pixmap)

    def start_animation(self, message=None):
        """Start the spinner animation"""
        if message:
            self.loading_label.setText(message)
        self.spinner_timer.start(100)  # Update every 100ms

    def stop_animation(self):
        """Stop the spinner animation"""
        self.spinner_timer.stop()

    def set_message(self, message):
        """Set the loading message"""
        self.loading_label.setText(message)

    def is_animating(self):
        """Check if the spinner is currently animating"""
        return self.spinner_timer.isActive()
