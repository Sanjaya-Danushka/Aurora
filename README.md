# Aurora

A modern, fast, and beautiful Arch Linux Package Manager GUI built with PyQt6.

## Features

- 🎨 **Modern Dark UI** - Professional dark theme with cyan accents
- 🔍 **Smart Search** - Search packages from official repos and AUR
- ⬇️ **Install Packages** - Install from official repositories or AUR
- 🗑️ **Remove Packages** - Easily remove installed packages
- 💾 **Local Installation** - Install packages from local `.tar.gz` or `.pkg.tar.xz` files
- 📦 **Package Management** - Refresh package lists and manage dependencies
- 🖥️ **Responsive UI** - Resizable splitter layout with smooth interactions
- ⚡ **Fast & Stable** - Built with PyQt6 for native performance

## Requirements

- Python 3.8+
- PyQt6
- pacman (Arch Linux)
- Optional: yay (for AUR support)

## Installation

### Install Dependencies

```bash
sudo pacman -S python-pyqt6
```

### Clone Repository

```bash
git clone https://github.com/Sanjaya-Danushka/Aurora.git
cd Aurora
```

## Usage

Run the application:

```bash
python3 archpkg_pyqt.py
```

### Main Features

1. **Search Packages**
   - Enter package name in search box
   - Press Enter or click Search
   - Results from official repos and AUR appear in the table

2. **Install Package**
   - Select a package from the list
   - Click "⬇️ Install Selected"
   - Confirm installation
   - Watch progress in console

3. **Remove Package**
   - Select an installed package
   - Click "🗑️ Remove Selected"
   - Confirm removal

4. **Install Local Package**
   - Click "💾 Install Local"
   - Select a `.pkg.tar.gz` or `.pkg.tar.xz` file
   - Confirm installation

5. **Refresh Package Lists**
   - Click "🔄 Refresh" to update package databases

## UI Layout

```
┌─────────────────────────────────────┐
│  📦 Arch Linux Package Manager      │  ← Header (Cyan)
├─────────────────────────────────────┤
│ Search Packages                     │
│ [Search Input] [Search] [Refresh]   │
├─────────────────────────────────────┤
│ Available Packages                  │
│ ┌─────────────────────────────────┐ │
│ │ Package Name │ Version │ Desc   │ │  ← Resizable
│ │ ─────────────────────────────────│ │
│ │ [Package rows...]               │ │
│ └─────────────────────────────────┘ │
├─────────────────────────────────────┤
│ [⬇️ Install] [🗑️ Remove] [💾 Local] │  ← Action Buttons
├─────────────────────────────────────┤
│ Console Output                      │
│ ┌─────────────────────────────────┐ │
│ │ [Console output...]             │ │  ← Resizable
│ └─────────────────────────────────┘ │
└─────────────────────────────────────┘
```

## Color Scheme

- **Background**: #1a1a1a (Dark)
- **Accent**: #00d4ff (Cyan)
- **Success**: #10b981 (Green)
- **Error**: #ef4444 (Red)
- **Text**: #e8e8e8 (Light Gray)

## Keyboard Shortcuts

- **Enter** in search box: Search packages
- **Ctrl+Q**: Quit application

## Troubleshooting

### "Do not run this application as root"
Aurora must be run as a regular user. Use `pkexec` for privilege escalation when needed.

### "pacman: command not found"
Aurora requires Arch Linux. Install Arch or use a compatible distribution.

### "yay: command not found"
AUR support requires yay. Install with:
```bash
sudo pacman -S yay
```

## Version History

### v1.0 (Initial Release)
- Modern PyQt6 UI with dark theme
- Package search (official + AUR)
- Install/Remove functionality
- Local package installation
- Resizable splitter layout
- Real-time console output

## License

MIT License - Feel free to use and modify

## Contributing

Contributions welcome! Please feel free to submit pull requests.

## Author

Sanjaya Danushka

## Support

For issues and feature requests, visit: https://github.com/Sanjaya-Danushka/Aurora/issues
