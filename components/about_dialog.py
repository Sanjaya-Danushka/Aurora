import os
import platform
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QWidget,
    QFrame,
    QGridLayout,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QPixmap


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About NeoArch")
        self.setModal(True)
        self.setMinimumSize(720, 560)

        icon_path = os.path.join(os.path.dirname(__file__), "..", "assets", "icons", "about.svg")
        icon_path = os.path.normpath(icon_path)
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        root = QVBoxLayout(self)
        header = QLabel("NeoArch")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet("font-size: 22px; font-weight: 700;")
        sub = QLabel("Developed by Whale Lab")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet("color: #9CA6B4; font-size: 13px;")
        root.addWidget(header)
        root.addWidget(sub)

        tabs = QTabWidget()
        tabs.addTab(self._make_about_tab(), "About")
        tabs.addTab(self._make_system_tab(), "System")
        tabs.addTab(self._make_license_tab(), "License")
        root.addWidget(tabs)

        btns = QHBoxLayout()
        btns.addStretch()
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        btns.addWidget(ok_btn)
        root.addLayout(btns)

    def _make_about_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        desc = QLabel(
            "NeoArch is a graphical package manager for Arch Linux with AUR support.\n\n"
            "Search and manage packages from pacman, AUR, Flatpak, npm, and more.\n"
            "Create bundles, manage plugins, and streamline your setup."
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)

        row = QHBoxLayout()
        row.setSpacing(16)

        left = QFrame()
        left.setObjectName("aboutLeftCard")
        left.setFrameShape(QFrame.Shape.NoFrame)
        left_l = QVBoxLayout(left)
        left_l.setContentsMargins(16, 16, 16, 16)
        left_l.setSpacing(10)

        dev_title = QLabel("Developer")
        dev_title.setStyleSheet("font-weight: 600;")
        left_l.addWidget(dev_title)

        dev_row = QHBoxLayout()
        dev_img = QLabel()
        user_img_path = os.path.join(os.path.dirname(__file__), "..", "assets", "about", "user.jpg")
        user_img_path = os.path.normpath(user_img_path)
        if os.path.exists(user_img_path):
            pm = QPixmap(user_img_path)
            if not pm.isNull():
                dev_img.setPixmap(pm.scaled(96, 96, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        dev_img.setFixedSize(96, 96)
        dev_img.setStyleSheet("border-radius: 8px;")
        dev_row.addWidget(dev_img)

        dev_info = QVBoxLayout()
        name = QLabel("Sanjaya Danushka")
        name.setStyleSheet("font-size: 15px; font-weight: 600;")
        dev_info.addWidget(name)

        links = QLabel(
            '<a href="https://github.com/Sanjaya-Danushka">GitHub</a>  |  '
            '<a href="https://www.linkedin.com/in/sanjaya-danushka-4484292a0">LinkedIn</a>  |  '
            '<a href="https://www.facebook.com/sanjaya.danushka.186">Facebook</a>'
        )
        links.setTextFormat(Qt.TextFormat.RichText)
        links.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        links.setOpenExternalLinks(True)
        dev_info.addWidget(links)
        dev_info.addStretch()
        dev_row.addLayout(dev_info)

        left_l.addLayout(dev_row)

        sponsor_title = QLabel("Sponsor — Buy Me a Coffee")
        sponsor_title.setStyleSheet("font-weight: 600;")
        left_l.addWidget(sponsor_title)

        qr_label = QLabel()
        qr_path = os.path.join(os.path.dirname(__file__), "..", "assets", "about", "sponsor.png")
        qr_path = os.path.normpath(qr_path)
        if os.path.exists(qr_path):
            qr_pm = QPixmap(qr_path)
            if not qr_pm.isNull():
                qr_label.setPixmap(qr_pm.scaled(180, 180, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        qr_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        left_l.addWidget(qr_label)

        row.addWidget(left, 1)

        right = QFrame()
        right.setObjectName("aboutRightCard")
        right_l = QVBoxLayout(right)
        right_l.setContentsMargins(16, 16, 16, 16)
        right_l.setSpacing(8)

        highlights = QLabel(
            "• Unified package search across pacman, AUR, Flatpak, npm\n"
            "• One‑click installs with progress tracking\n"
            "• Bundle creation and plugin ecosystem\n"
            "• Snapshot support for safe updates"
        )
        highlights.setWordWrap(True)
        right_l.addWidget(highlights)
        right_l.addStretch()

        row.addWidget(right, 1)

        layout.addLayout(row)

        w.setStyleSheet(
            "QFrame#aboutLeftCard, QFrame#aboutRightCard {"
            "  border: 1px solid rgba(0, 191, 174, 0.18);"
            "  border-radius: 12px;"
            "  background: rgba(32,34,40,0.08);"
            "}"
        )

        return w

    def _make_system_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(16, 16, 16, 16)
        sys_text = (
            f"Python: {platform.python_version()}\n"
            f"OS: {platform.system()} {platform.release()}\n"
            f"Machine: {platform.machine()}\n"
        )
        lbl = QLabel(sys_text)
        lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        v.addWidget(lbl)
        v.addStretch()
        return w

    def _make_license_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(16, 16, 16, 16)
        lbl = QLabel(
            "License: Open source. See project repository for details.\n\n"
            "Acknowledgements: Built with PyQt6 and other open-source components."
        )
        lbl.setWordWrap(True)
        v.addWidget(lbl)
        v.addStretch()
        return w
