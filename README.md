# Aurora - Package Manager for Arch Linux

Aurora is a modern, user-friendly package manager designed specifically for Arch Linux. It provides an intuitive graphical interface for managing packages from multiple sources including pacman, AUR, Flatpak, and npm.


<img width="1236" height="851" alt="Screenshot" src="https://github.com/user-attachments/assets/fd068b88-d104-4145-a6ab-1769a2fa4d68" />


## Features

- **Multi-source package management**: Support for pacman, AUR, Flatpak, and npm packages
- **Graphical user interface**: Built with PyQt6 for a smooth desktop experience
- **Plugin system**: Extensible with plugins for additional tools and utilities
- **Bundle management**: Create and manage package bundles for easy deployment
- **Security-focused**: Requires appropriate privileges for package installation to maintain system security

## Installation

### Prerequisites

- Python 3.8+
- PyQt6
- Arch Linux system
- Administrative privileges (sudo) for package management

### Install Dependencies wz

Option A — Recommended (Aur)

```bash
# Install system packages from official repos
sudo pacman -S --needed python python-pyqt6 python-requests qt6-svg git flatpak nodejs npm docker
yay -S neoarch-git 

```

Option B — Use a Python virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements_pyqt.txt
```

Note: On Arch, using system `pip` often triggers the "externally-managed-environment" error. Prefer Option A (pacman) or install into a virtual environment (Option B). Alternatively, you can install apps with `pipx` (`sudo pacman -S python-pipx`) which manages a dedicated venv for each app.

### Run Aurora

```bash
# If you created a virtual environment
source .venv/bin/activate  # skip if not using a venv

python aurora_home.py
```

## Security Notice

As a package manager, Aurora requires administrative privileges to install, update, and remove system packages. This is essential for maintaining system security and integrity. The application will prompt for authentication when performing privileged operations.

## Usage

1. **Discover Packages**: Search and browse available packages from multiple repositories
2. **Install Packages**: Select and install packages with a single click
3. **Manage Updates**: View and install available system updates
4. **Plugins**: Access additional tools and utilities through the plugin system
5. **Bundles**: Create package bundles for consistent deployments

## Contributing

Contributions are welcome! Please ensure all changes maintain the security and stability requirements of a system package manager.

## License

This project is now open-source 
--developed by Whale Lab
