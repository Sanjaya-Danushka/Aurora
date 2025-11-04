# Aurora - Package Manager for Arch Linux

Aurora is a modern, user-friendly package manager designed specifically for Arch Linux. It provides an intuitive graphical interface for managing packages from multiple sources including pacman, AUR, Flatpak, and npm.

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

### Install Dependencies

```bash
# Install system dependencies
sudo pacman -S python python-pip git flatpak nodejs npm

# Install Python dependencies
pip install -r requirements_pyqt.txt
```

### Run Aurora

```bash
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

This project does not use the MIT license. All rights reserved. No copying, modification, distribution, or redistribution is permitted for security reasons. This software is proprietary and intended solely for authorized use within the whale lab.
