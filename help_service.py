import os
import platform
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QWidget,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon


def _make_text_tab(text: str) -> QWidget:
    w = QWidget()
    v = QVBoxLayout(w)
    v.setContentsMargins(12, 12, 12, 12)
    edit = QTextEdit()
    edit.setReadOnly(True)
    edit.setText(text)
    v.addWidget(edit)
    return w


def show_help(parent, current_view: str):
    dlg = QDialog(parent)
    dlg.setWindowTitle("Help & Documentation")
    dlg.setModal(True)
    dlg.setMinimumSize(780, 560)

    icon_path = os.path.join(os.path.dirname(__file__), "assets", "icons", "about.svg")
    if os.path.exists(icon_path):
        dlg.setWindowIcon(QIcon(icon_path))

    root = QVBoxLayout(dlg)
    tabs = QTabWidget()

    overview = (
        "NeoArch helps you search, install, and manage software across multiple sources.\n\n"
        "Use the left sidebar to switch sections. The top titlebar contains actions for each section.\n"
        "The console can be toggled to view logs during operations."
    )
    tabs.addTab(_make_text_tab(overview), "Overview")

    discover = (
        "Discover: Search packages across pacman, AUR, Flatpak and npm.\n\n"
        "- Type at least 3 characters to search.\n"
        "- Select results and click Install selected packages.\n"
        "- Use Add selected to Bundle to curate bundles.\n"
        "- Use Install via GitHub or Docker for alternative sources.\n"
        "- Sudo installs where needed."
    )
    tabs.addTab(_make_text_tab(discover), "Discover")

    updates = (
        "Updates: View and apply available updates.\n\n"
        "- Update Selected to upgrade chosen packages.\n"
        "- Ignore Selected to hide packages from updates.\n"
        "- Manage Ignored to review ignored list."
    )
    tabs.addTab(_make_text_tab(updates), "Updates")

    installed = (
        "Installed: Browse installed packages.\n\n"
        "- Update Selected to upgrade packages with updates.\n"
        "- Uninstall Selected to remove packages.\n"
        "- Add selected to Bundle to create bundles."
    )
    tabs.addTab(_make_text_tab(installed), "Installed")

    bundles = (
        "Bundles: Create, import, export, and install curated package sets.\n\n"
        "- Install Bundle to install all items.\n"
        "- Import/Export for sharing.\n"
        "- Clear or Remove Selected to manage contents."
    )
    tabs.addTab(_make_text_tab(bundles), "Bundles")

    plugins = (
        "Plugins: Discover and manage extensions.\n\n"
        "- Refresh to update list.\n"
        "- Use the sidebar to filter by name, status, or category.\n"
        "- Install/Uninstall and Launch supported tools."
    )
    tabs.addTab(_make_text_tab(plugins), "Plugins")

    settings_help = (
        "Settings: Configure general options and plugins.\n\n"
        "- Auto update checks, snapshots, bundle autosave.\n"
        "- Manage enabled plugins and defaults."
    )
    tabs.addTab(_make_text_tab(settings_help), "Settings")

    if isinstance(current_view, str):
        index_by_name = {
            "discover": 1,
            "updates": 2,
            "installed": 3,
            "bundles": 4,
            "plugins": 5,
            "settings": 6,
        }
        if current_view in index_by_name:
            tabs.setCurrentIndex(index_by_name[current_view])

    root.addWidget(tabs)

    btns = QHBoxLayout()
    btns.addStretch()
    close_btn = QPushButton("Close")
    close_btn.clicked.connect(dlg.accept)
    btns.addWidget(close_btn)
    root.addLayout(btns)

    dlg.exec()


def show_about(parent):
    dlg = QDialog(parent)
    dlg.setWindowTitle("About NeoArch")
    dlg.setModal(True)
    dlg.setMinimumSize(720, 520)

    icon_path = os.path.join(os.path.dirname(__file__), "assets", "icons", "about.svg")
    if os.path.exists(icon_path):
        dlg.setWindowIcon(QIcon(icon_path))

    root = QVBoxLayout(dlg)
    header = QLabel("NeoArch — Elevate Your Arch Experience")
    header.setAlignment(Qt.AlignmentFlag.AlignCenter)
    header.setStyleSheet("font-size: 18px; font-weight: 600;")
    root.addWidget(header)

    tabs = QTabWidget()

    about_text = (
        "NeoArch is a graphical package manager for Arch Linux with AUR support.\n\n"
        "Version: 1.0\n\n"
        "Sources supported include pacman, AUR, Flatpak, npm, and custom Git/Docker installs.\n"
        "Use Bundles to curate sets of packages. Manage extensions via Plugins."
    )
    tabs.addTab(_make_text_tab(about_text), "About")

    sys_text = (
        f"Python: {platform.python_version()}\n"
        f"OS: {platform.system()} {platform.release()}\n"
        f"Machine: {platform.machine()}\n"
    )
    tabs.addTab(_make_text_tab(sys_text), "System")

    license_text = (
        "License: Open source. See project repository for details.\n\n"
        "Acknowledgements: Built with PyQt6 and other open-source components."
    )
    tabs.addTab(_make_text_tab(license_text), "License")

    root.addWidget(tabs)

    btns = QHBoxLayout()
    btns.addStretch()
    ok_btn = QPushButton("OK")
    ok_btn.clicked.connect(dlg.accept)
    btns.addWidget(ok_btn)
    root.addLayout(btns)

    dlg.exec()
