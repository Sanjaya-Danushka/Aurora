"""
Beautiful Installation Progress Dialog with detailed information
"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, 
                             QScrollArea, QWidget, QPushButton, QFrame)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor


class InstallProgressDialog(QDialog):
    """Beautiful installation progress dialog with package list and download info"""
    
    def __init__(self, packages_by_source, parent=None):
        super().__init__(parent)
        self.packages_by_source = packages_by_source
        self.total_packages = sum(len(pkgs) for pkgs in packages_by_source.values())
        self.completed_packages = 0
        self.current_source = ""
        self.current_download_info = ""
        
        self.setWindowTitle("Installing Packages")
        self.setGeometry(100, 100, 600, 500)
        self.setModal(True)
        self.setStyleSheet(self._get_stylesheet())
        
        self.init_ui()
    
    def init_ui(self):
        """Initialize the UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        
        # Title
        title = QLabel("Installing Packages")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color: #F0F0F0;")
        layout.addWidget(title)
        
        # Overall progress
        progress_layout = QHBoxLayout()
        self.progress_label = QLabel(f"0/{self.total_packages} packages")
        self.progress_label.setStyleSheet("color: #A0A0A0; font-size: 12px;")
        progress_layout.addWidget(self.progress_label)
        progress_layout.addStretch()
        layout.addLayout(progress_layout)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(self.total_packages)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 6px;
                background-color: rgba(255, 255, 255, 0.05);
                height: 24px;
            }
            QProgressBar::chunk {
                background-color: #00BFAE;
                border-radius: 5px;
            }
        """)
        layout.addWidget(self.progress_bar)
        
        # Download info
        self.download_info_label = QLabel("Preparing installation...")
        self.download_info_label.setStyleSheet("color: #808080; font-size: 11px;")
        layout.addWidget(self.download_info_label)
        
        # Current package info
        current_frame = QFrame()
        current_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(0, 191, 174, 0.1);
                border: 1px solid rgba(0, 191, 174, 0.2);
                border-radius: 8px;
            }
        """)
        current_layout = QVBoxLayout(current_frame)
        current_layout.setContentsMargins(12, 12, 12, 12)
        current_layout.setSpacing(6)
        
        current_label = QLabel("Current Package:")
        current_label.setStyleSheet("color: #A0A0A0; font-size: 10px; font-weight: 600;")
        current_layout.addWidget(current_label)
        
        self.current_package_label = QLabel("Waiting to start...")
        self.current_package_label.setStyleSheet("color: #00BFAE; font-size: 12px; font-weight: 500;")
        self.current_package_label.setWordWrap(True)
        current_layout.addWidget(self.current_package_label)
        
        layout.addWidget(current_frame)
        
        # Package list
        list_label = QLabel("Packages to Install:")
        list_label.setStyleSheet("color: #A0A0A0; font-size: 11px; font-weight: 600;")
        layout.addWidget(list_label)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                background-color: rgba(255, 255, 255, 0.02);
                border: 1px solid rgba(255, 255, 255, 0.05);
                border-radius: 6px;
            }
            QScrollBar:vertical {
                width: 8px;
            }
            QScrollBar::handle:vertical {
                background: rgba(0, 191, 174, 0.5);
                border-radius: 4px;
            }
        """)
        
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(4)
        
        # Add packages to list
        for source, packages in self.packages_by_source.items():
            source_label = QLabel(f"📦 {source}")
            source_label.setStyleSheet("color: #00BFAE; font-size: 11px; font-weight: 600; margin-top: 6px;")
            scroll_layout.addWidget(source_label)
            
            for pkg in packages:
                pkg_label = QLabel(f"  • {pkg}")
                pkg_label.setStyleSheet("color: #D0D0D0; font-size: 10px;")
                scroll_layout.addWidget(pkg_label)
        
        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.cancel_btn = QPushButton("Cancel Installation")
        self.cancel_btn.setFixedHeight(36)
        self.cancel_btn.setMinimumWidth(140)
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 100, 100, 0.2);
                color: #FF6464;
                border: 1px solid rgba(255, 100, 100, 0.4);
                border-radius: 6px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: rgba(255, 100, 100, 0.3);
                border: 1px solid rgba(255, 100, 100, 0.6);
            }
        """)
        btn_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(btn_layout)
    
    def update_progress(self, completed, total, current_package, download_info):
        """Update the progress display"""
        self.completed_packages = completed
        self.progress_bar.setValue(completed)
        self.progress_label.setText(f"{completed}/{total} packages")
        self.current_package_label.setText(current_package)
        
        if download_info:
            self.download_info_label.setText(download_info)
    
    def _get_stylesheet(self):
        """Get the dialog stylesheet"""
        return """
            InstallProgressDialog {
                background-color: #1a1a1a;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 12px;
            }
            QLabel {
                background-color: transparent;
            }
            QPushButton {
                background-color: #00BFAE;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: 600;
                font-size: 12px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #00A89A;
            }
            QPushButton:pressed {
                background-color: #009080;
            }
        """
