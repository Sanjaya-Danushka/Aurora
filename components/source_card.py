"""
SourceCard Component - Card-style container for source selection
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import pyqtSignal
from .source_item import SourceItem


class SourceCard(QWidget):
    """Card component for source selection with select/deselect functionality"""

    source_changed = pyqtSignal(dict)  # Emits dict of source_name -> is_checked

    def __init__(self, parent=None):
        super().__init__(parent)
        self.sources = {}
        self.init_ui()

    def init_ui(self):
        """Initialize the source card UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Header with select/deselect button
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(12, 8, 12, 8)

        title_label = QLabel("Sources")
        title_label.setObjectName("sourceCardTitle")
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.setObjectName("selectAllBtn")
        self.select_all_btn.clicked.connect(self.toggle_select_all)
        header_layout.addWidget(self.select_all_btn)

        layout.addWidget(header_widget)

        # Container for source items
        self.sources_container = QWidget()
        self.sources_layout = QVBoxLayout(self.sources_container)
        self.sources_layout.setContentsMargins(0, 0, 0, 0)
        self.sources_layout.setSpacing(4)

        layout.addWidget(self.sources_container)

        # Apply styling
        self.setStyleSheet(self.get_stylesheet())

    def add_source(self, source_name, icon_path):
        """Add a source to the card"""
        source_item = SourceItem(source_name, icon_path, self)
        source_item.checkbox.stateChanged.connect(lambda: self.on_source_changed())
        self.sources[source_name] = source_item
        self.sources_layout.addWidget(source_item)

        # Initial state change emission
        self.on_source_changed()

    def on_source_changed(self):
        """Handle when any source selection changes"""
        states = {name: item.is_checked() for name, item in self.sources.items()}
        self.source_changed.emit(states)
        self.update_select_all_button()

    def update_select_all_button(self):
        """Update the select all button text based on current state"""
        checked_count = sum(1 for item in self.sources.values() if item.is_checked())
        total_count = len(self.sources)

        if checked_count == total_count:
            self.select_all_btn.setText("Deselect All")
        elif checked_count == 0:
            self.select_all_btn.setText("Select All")
        else:
            self.select_all_btn.setText(f"Selected ({checked_count}/{total_count})")

    def toggle_select_all(self):
        """Toggle select all/deselect all"""
        checked_count = sum(1 for item in self.sources.values() if item.is_checked())
        total_count = len(self.sources)

        if checked_count == total_count:
            # All selected, deselect all
            for item in self.sources.values():
                item.set_checked(False)
        else:
            # Not all selected, select all
            for item in self.sources.values():
                item.set_checked(True)

    def get_selected_sources(self):
        """Return dict of selected sources"""
        return {name: item.is_checked() for name, item in self.sources.items()}

    def set_selected_sources(self, selected_dict):
        """Set which sources are selected"""
        for name, checked in selected_dict.items():
            if name in self.sources:
                self.sources[name].set_checked(checked)

    def get_stylesheet(self):
        """Get stylesheet for this component"""
        return """
            SourceCard {
                background-color: rgba(42, 45, 51, 0.4);
                border-radius: 12px;
                border: 1px solid rgba(0, 191, 174, 0.2);
                margin: 4px 0px;
            }

            QLabel#sourceCardTitle {
                color: #00BFAE;
                font-size: 14px;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }

            QPushButton#selectAllBtn {
                background-color: transparent;
                color: #00BFAE;
                border: 1px solid rgba(0, 191, 174, 0.3);
                border-radius: 6px;
                padding: 4px 12px;
                font-size: 11px;
                font-weight: 500;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }

            QPushButton#selectAllBtn:hover {
                background-color: rgba(0, 191, 174, 0.1);
                border-color: rgba(0, 191, 174, 0.5);
            }

            QPushButton#selectAllBtn:pressed {
                background-color: rgba(0, 191, 174, 0.2);
            }
        """
