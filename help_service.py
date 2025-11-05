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
        "NeoArch is a comprehensive package manager for Arch Linux with multi-source support.\n\n"
        "Key features:\n"
        "- Unified search and management across pacman, AUR, Flatpak, and npm.\n"
        "- One-click installs with progress display and cancel support.\n"
        "- Bundles for curating and sharing sets of packages.\n"
        "- Plugins panel for extensions and system tools (e.g., BleachBit, Timeshift).\n"
        "- GitHub and Docker install helpers for alternative sources.\n"
        "- Snapshot integration via Timeshift (manual and pre-update).\n"
        "- Auto update checks and scheduled update workflow.\n"
        "- Source and status filters to focus results.\n\n"
        "Use the left sidebar to switch sections; the top titlebar shows actions for each section.\n"
        "Toggle the console from the bottom-right to see logs during operations."
    )
    tabs.addTab(_make_text_tab(overview), "Overview")

    discover = (
        "Discover: Search packages across pacman, AUR, Flatpak, and npm.\n\n"
        "- Type at least 3 characters to search; results span all enabled sources.\n"
        "- Select results and click \"Install selected packages\".\n"
        "- \"Add selected to Bundle\" to curate a bundle for later.\n"
        "- \"Install via GitHub\" and \"Install via Docker\" support alternative sources.\n"
        "- Use \"Install with Sudo Privileges\" when elevated rights are required (polkit/askpass handled automatically)."
    )
    tabs.addTab(_make_text_tab(discover), "Discover")

    updates = (
        "Updates: Review and apply updates across sources.\n\n"
        "- \"Update Selected\" to upgrade chosen packages.\n"
        "- \"Ignore Selected\" to hide packages from future update lists.\n"
        "- \"Manage Ignored\" to review and restore items.\n"
        "- Snapshot support: optionally create a Timeshift snapshot before updating (see Settings).\n"
        "- \"Update Tools\" refreshes system tooling (pacman/yay, Flatpak, npm)."
    )
    tabs.addTab(_make_text_tab(updates), "Updates")

    installed = (
        "Installed: Browse and act on installed software.\n\n"
        "- \"Update Selected\" to upgrade packages with available updates.\n"
        "- \"Uninstall Selected\" to remove packages.\n"
        "- \"Add selected to Bundle\" to curate bundles.\n"
        "- Filter by source and status to narrow the list."
    )
    tabs.addTab(_make_text_tab(installed), "Installed")

    bundles = (
        "Bundles: Create, import, export, and install curated sets of packages.\n\n"
        "- \"Install Bundle\" installs all items in the bundle.\n"
        "- \"Import\"/\"Export\" to share bundles.\n"
        "- \"Clear\" or \"Remove Selected\" to manage contents.\n"
        "- Optional autosave path can be configured in Settings."
    )
    tabs.addTab(_make_text_tab(bundles), "Bundles")

    plugins = (
        "Plugins: Discover and manage extensions and system tools.\n\n"
        "- Use \"Refresh\" to update the list.\n"
        "- Filter by name, status, or category from the left sidebar.\n"
        "- Install/Uninstall and Launch supported tools (e.g., BleachBit, Timeshift)."
    )
    tabs.addTab(_make_text_tab(plugins), "Plugins")

    settings_help = (
        "Settings: Configure global behavior and plugins.\n\n"
        "- General: auto update checks, number of minutes between refreshes.\n"
        "- Snapshots: enable pre-update Timeshift snapshots; manual create/revert/delete.\n"
        "- Bundles: enable autosave and configure default path.\n"
        "- Plugins: manage enabled plugins and defaults."
    )
    tabs.addTab(_make_text_tab(settings_help), "Settings")

    advanced = (
        "Advanced:\n\n"
        "- Console: toggle from the bottom-right to see real-time logs.\n"
        "- Cancel installation: available while installs are running.\n"
        "- Flathub: user remote ensured automatically for Flatpak operations.\n"
        "- Privileges: pacman uses pkexec; AUR operations use askpass when needed.\n"
        "- Scheduled updates: background workflow can prompt updates and create snapshots if enabled."
    )
    tabs.addTab(_make_text_tab(advanced), "Advanced")

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

    features_text = (
        "Features:\n\n"
        "- Unified package management across pacman, AUR, Flatpak, and npm.\n"
        "- Discover view with GitHub/Docker install helpers and sudo install option.\n"
        "- Rich update workflow with Ignore/Manage Ignored and Tools update.\n"
        "- Bundles: create, import/export, install, and manage curated sets.\n"
        "- Plugins: discover, filter, install/uninstall, and launch tools.\n"
        "- Snapshots via Timeshift: manual create/revert/delete and pre-update integration.\n"
        "- Console with real-time logs and cancel installation support.\n"
        "- Flatpak Flathub user remote ensured automatically.\n"
        "- Scheduled updates workflow with optional snapshot creation.\n"
    )
    tabs.addTab(_make_text_tab(features_text), "Features")

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
