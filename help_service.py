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
        "🚀 Welcome to NeoArch - Your All-in-One Package Manager!\n\n"
        "NeoArch simplifies software management on Arch Linux by bringing everything into one place:\n\n"
        "📦 WHAT YOU CAN DO:\n"
        "• Search and install from multiple sources (official repos, AUR, Flatpak, npm) in one search\n"
        "• Create bundles of your favorite apps to install on new systems\n"
        "• Keep everything updated with one click\n"
        "• Install system tools and utilities from the Plugins section\n"
        "• Install from GitHub repos or Docker containers directly\n"
        "• Create system snapshots before major updates (requires Timeshift)\n\n"
        "🎯 HOW TO GET STARTED:\n"
        "1. Click 'Discover' in the left sidebar to search for software\n"
        "2. Type what you want (e.g., 'firefox', 'discord', 'code editor')\n"
        "3. Select packages and click 'Install selected packages'\n"
        "4. Use 'Updates' to keep your system current\n\n"
        "💡 TIP: Click the terminal icon (bottom-right) to see what's happening behind the scenes!"
    )
    tabs.addTab(_make_text_tab(overview), "Overview")

    discover = (
        "🔍 Discover - Find and Install Software\n\n"
        "This is where you find new software for your system. It searches across:\n"
        "• Official Arch repositories (pacman) - Core system software\n"
        "• AUR (Arch User Repository) - Community packages\n"
        "• Flatpak - Sandboxed applications\n"
        "• npm - Node.js packages and tools\n\n"
        "📝 HOW TO USE:\n"
        "1. Type at least 3 characters of what you want (e.g., 'chrom' for Chrome)\n"
        "2. Browse results from all sources in one list\n"
        "3. Check boxes next to packages you want\n"
        "4. Click 'Install selected packages' - we handle passwords and permissions\n\n"
        "🎁 SPECIAL FEATURES:\n"
        "• 'Add selected to Bundle' - Save packages to install later or on other computers\n"
        "• 'Install via GitHub' - Install directly from GitHub repositories\n"
        "• 'Install via Docker' - Set up Docker containers\n"
        "• 'Install with Sudo Privileges' - For packages needing admin rights\n\n"
        "✨ The search is smart - try terms like 'photo editor', 'music player', or 'development tools'!"
    )
    tabs.addTab(_make_text_tab(discover), "Discover")

    updates = (
        "🔄 Updates - Keep Your System Current\n\n"
        "Stay secure and get new features by keeping your software updated.\n\n"
        "📋 WHAT YOU'LL SEE:\n"
        "• All available updates from all sources in one place\n"
        "• Current version vs. new version for each package\n"
        "• Source (pacman, AUR, Flatpak, npm) for each update\n\n"
        "⚡ QUICK ACTIONS:\n"
        "• 'Update Selected' - Choose which packages to update\n"
        "• 'Ignore Selected' - Hide updates you don't want (like beta versions)\n"
        "• 'Manage Ignored' - See and restore previously ignored updates\n"
        "• 'Update Tools' - Update the update tools themselves (yay, flatpak, npm)\n\n"
        "🛡️ SAFETY FIRST:\n"
        "• Enable snapshots in Settings to auto-backup before updates\n"
        "• Updates are applied safely with proper dependency handling\n"
        "• You can cancel running updates if needed\n\n"
        "💡 TIP: Run updates regularly (weekly) to stay secure and get bug fixes!"
    )
    tabs.addTab(_make_text_tab(updates), "Updates")

    installed = (
        "📦 Installed - Manage Your Software\n\n"
        "See everything installed on your system and manage it easily.\n\n"
        "👀 WHAT YOU CAN VIEW:\n"
        "• All installed packages from all sources (pacman, AUR, Flatpak, npm)\n"
        "• Which packages have updates available (highlighted)\n"
        "• Package versions, descriptions, and installation source\n\n"
        "🔧 MANAGEMENT ACTIONS:\n"
        "• 'Update Selected' - Update specific packages that have newer versions\n"
        "• 'Uninstall Selected' - Safely remove packages you no longer need\n"
        "• 'Add selected to Bundle' - Create a list of your favorite packages\n\n"
        "🎯 SMART FILTERING:\n"
        "• Filter by source: See only AUR packages, only Flatpaks, etc.\n"
        "• Filter by status: Show only packages with updates, or only up-to-date ones\n"
        "• Search by name to quickly find specific software\n\n"
        "💡 TIP: Use bundles to recreate your setup on a new computer - just export and import!"
    )
    tabs.addTab(_make_text_tab(installed), "Installed")

    bundles = (
        "🎁 Bundles - Your Personal Software Collections\n\n"
        "Think of bundles as shopping lists for software - perfect for setting up new computers or sharing your favorite apps with friends!\n\n"
        "✨ WHAT ARE BUNDLES FOR:\n"
        "• Setting up a new computer with all your favorite software\n"
        "• Sharing your developer setup with teammates\n"
        "• Creating themed collections (e.g., 'Photo Editing', 'Gaming', 'Programming')\n"
        "• Backing up your software choices\n\n"
        "🔨 HOW TO USE BUNDLES:\n"
        "1. Go to Discover or Installed and click 'Add selected to Bundle'\n"
        "2. Build your collection by adding more packages\n"
        "3. Click 'Install Bundle' to install everything at once\n"
        "4. Use 'Export Bundle' to save/share your bundle as a file\n"
        "5. Use 'Import Bundle' to load someone else's bundle\n\n"
        "🎯 BUNDLE MANAGEMENT:\n"
        "• 'Remove Selected' - Take items out of your current bundle\n"
        "• 'Clear Bundle' - Start fresh with an empty bundle\n"
        "• Auto-save (Settings) - Automatically save your bundle as you build it\n\n"
        "💡 EXAMPLE: Create a 'New Developer Setup' bundle with VS Code, Git, Node.js, and Docker!"
    )
    tabs.addTab(_make_text_tab(bundles), "Bundles")

    plugins = (
        "🔌 Plugins - System Tools and Utilities\n\n"
        "Pre-configured system tools and utilities that you can install and launch directly.\n\n"
        "🛠️ WHAT YOU'LL FIND:\n"
        "• System cleaners (BleachBit) - Free up disk space\n"
        "• Backup tools (Timeshift) - Create system snapshots\n"
        "• Development tools - IDEs, editors, and utilities\n"
        "• System utilities - File managers, terminals, monitors\n\n"
        "🎮 HOW TO USE:\n"
        "1. Browse available plugins or use the search filter (left sidebar)\n"
        "2. Filter by category (Cleaner, Backup, Development, etc.)\n"
        "3. Click 'Install' on plugins you want\n"
        "4. Once installed, click 'Launch' to run the tool\n"
        "5. Use 'Uninstall' to remove plugins you no longer need\n\n"
        "🎯 SMART FEATURES:\n"
        "• Filter by installation status (installed/not installed)\n"
        "• Search by name to find specific tools\n"
        "• Category filtering to browse by purpose\n"
        "• One-click launch for installed tools\n\n"
        "💡 TIP: Try BleachBit to clean up disk space and Timeshift for system backups!"
    )
    tabs.addTab(_make_text_tab(plugins), "Plugins")

    settings_help = (
        "⚙️ Settings - Customize Your Experience\n\n"
        "Make NeoArch work exactly how you want it.\n\n"
        "🔄 AUTO-UPDATE SETTINGS:\n"
        "• Enable automatic update checks - NeoArch will check for updates in the background\n"
        "• Set check interval - How often to look for updates (in minutes)\n"
        "• Scheduled updates - Get prompted to update your system regularly\n\n"
        "🛡️ SNAPSHOT SETTINGS (Safety First!):\n"
        "• 'Create snapshot before updates' - Auto-backup before any system changes\n"
        "• Manual snapshot controls - Create, restore, or delete system snapshots\n"
        "• Requires Timeshift to be installed (available in Plugins section)\n\n"
        "🎁 BUNDLE SETTINGS:\n"
        "• Auto-save bundles - Automatically save your bundle as you build it\n"
        "• Default save location - Where to save your bundle files\n\n"
        "🔌 PLUGIN MANAGEMENT:\n"
        "• View and manage installed plugins\n"
        "• Enable/disable specific plugins\n"
        "• Reset to default plugin set\n\n"
        "💡 RECOMMENDED: Enable snapshots and auto-update checks for the best experience!"
    )
    tabs.addTab(_make_text_tab(settings_help), "Settings")

    advanced = (
        "🔧 Advanced Features\n\n"
        "Power user features and behind-the-scenes functionality.\n\n"
        "📺 CONSOLE (Debug & Monitoring):\n"
        "• Click the terminal icon (bottom-right) to show/hide the console\n"
        "• See real-time logs of installations, updates, and operations\n"
        "• Debug issues by checking console output\n"
        "• Copy error messages for troubleshooting\n\n"
        "⏹️ INSTALLATION CONTROL:\n"
        "• Cancel button appears during installations - stop anytime\n"
        "• Progress bars show download progress and installation status\n"
        "• Safe cancellation won't leave your system in a broken state\n\n"
        "🔐 PERMISSION HANDLING (Automatic):\n"
        "• System packages (pacman): Uses pkexec for secure admin access\n"
        "• AUR packages: Uses askpass for user authentication\n"
        "• No need to run NeoArch as root - we handle permissions properly\n\n"
        "🌐 FLATPAK INTEGRATION:\n"
        "• Flathub repository automatically configured for your user account\n"
        "• No manual setup needed for Flatpak applications\n\n"
        "⏰ SCHEDULED UPDATES:\n"
        "• Background service can remind you to update regularly\n"
        "• Automatic snapshot creation before scheduled updates\n"
        "• Configurable update intervals and notification preferences"
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
        "🌟 Key Features That Make NeoArch Special\n\n"
        "📦 UNIFIED PACKAGE MANAGEMENT:\n"
        "• Search across pacman, AUR, Flatpak, and npm in one interface\n"
        "• No need to remember different commands for different sources\n"
        "• Smart search that understands what you're looking for\n\n"
        "🚀 EASY INSTALLATION:\n"
        "• One-click installs with progress tracking\n"
        "• Install from GitHub repositories directly\n"
        "• Docker container setup made simple\n"
        "• Automatic permission handling (no sudo needed)\n\n"
        "🎁 BUNDLE SYSTEM:\n"
        "• Create collections of your favorite software\n"
        "• Share setups with friends or across computers\n"
        "• Perfect for developers, gamers, or any themed setup\n\n"
        "🔄 SMART UPDATE MANAGEMENT:\n"
        "• See all updates from all sources in one place\n"
        "• Ignore unwanted updates (beta versions, etc.)\n"
        "• Automatic snapshots before major updates\n\n"
        "🔌 PLUGIN ECOSYSTEM:\n"
        "• Pre-configured system tools and utilities\n"
        "• One-click install and launch\n"
        "• BleachBit, Timeshift, and many more\n\n"
        "🛡️ SAFETY & RELIABILITY:\n"
        "• Timeshift integration for system snapshots\n"
        "• Cancel installations safely anytime\n"
        "• Detailed logs for troubleshooting\n"
        "• Automatic Flatpak repository setup"
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
