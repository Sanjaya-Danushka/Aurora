from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QFrame, QGridLayout, QSizePolicy
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QIcon
import os
import shutil
import re


class ElideLabel(QLabel):
    def __init__(self, text="", parent=None, max_lines=2):
        super().__init__(text, parent)
        self._full_text = text or ""
        self._max_lines = max(1, int(max_lines))
        try:
            self.setWordWrap(True)
            self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        except Exception:
            pass

    def set_max_lines(self, n):
        try:
            self._max_lines = max(1, int(n))
        except Exception:
            self._max_lines = 1
        self._apply_elide()

    def setText(self, text):
        self._full_text = text or ""
        self._apply_elide()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._apply_elide()

    def _apply_elide(self):
        try:
            fm = self.fontMetrics()
            width = max(0, self.width())
            if width <= 0:
                QLabel.setText(self, self._full_text)
                return
            if self._max_lines <= 1:
                el = fm.elidedText(self._full_text, Qt.TextElideMode.ElideRight, width)
                QLabel.setText(self, el)
                return
            words = (self._full_text or "").split()
            lines = []
            current = ""
            i = 0
            while i < len(words):
                w = words[i]
                trial = (current + " " + w).strip()
                if fm.horizontalAdvance(trial) <= width:
                    current = trial
                    i += 1
                else:
                    if current:
                        lines.append(current)
                    else:
                        lines.append(fm.elidedText(w, Qt.TextElideMode.ElideRight, width))
                        i += 1
                    current = ""
                if len(lines) == self._max_lines - 1:
                    remaining = " ".join(words[i:])
                    last = (current + (" " if current and remaining else "") + remaining).strip()
                    el = fm.elidedText(last, Qt.TextElideMode.ElideRight, width)
                    lines.append(el)
                    current = ""
                    break
            if current and len(lines) < self._max_lines:
                lines.append(current)
            QLabel.setText(self, "\n".join(lines[: self._max_lines]))
        except Exception:
            try:
                QLabel.setText(self, self._full_text)
            except Exception:
                pass

class PluginCard(QFrame):
    def __init__(self, spec: dict, icon: QIcon, installed: bool, on_install, on_open, on_uninstall, parent=None):
        super().__init__(parent)
        self.spec = spec
        self.on_install = on_install
        self.on_open = on_open
        self.on_uninstall = on_uninstall
        self.setObjectName("pluginCard")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(self._style())
        # Fix height so all cards are uniform regardless of content/state
        self.setFixedHeight(148)
        # Prevent vertical stretch so grid vertical spacing is visible
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        self.icon_label = QLabel()
        try:
            if icon and not icon.isNull():
                self.icon_label.setPixmap(icon.pixmap(36, 36))
            else:
                self.icon_label.setText("🧩")
        except Exception:
            self.icon_label.setText("🧩")
        layout.addWidget(self.icon_label)

        text_col = QVBoxLayout()
        title_text = spec.get('name', spec.get('id'))
        title = ElideLabel(title_text, self, max_lines=1)
        title.setObjectName("pluginTitle")
        try:
            title.setToolTip(title_text)
        except Exception:
            pass
        desc_text = spec.get('desc', "")
        desc = ElideLabel(desc_text, self, max_lines=2)
        desc.setObjectName("pluginDesc")
        try:
            desc.setToolTip(desc_text)
        except Exception:
            pass
        text_col.addWidget(title)
        text_col.addWidget(desc)
        layout.addLayout(text_col, 1)

        self.action_btn = QPushButton()
        self.status_label = QLabel()
        self.status_label.setObjectName("pluginStatus")
        self.uninstall_btn = QPushButton("Uninstall")
        self.uninstall_btn.setVisible(False)
        btn_col = QVBoxLayout()
        btn_col.addWidget(self.action_btn)
        btn_col.addWidget(self.uninstall_btn)
        btn_col.addWidget(self.status_label)
        btn_col.addStretch()
        layout.addLayout(btn_col)

        self.update_state(installed)

    def update_icon(self, icon: QIcon):
        try:
            if icon and not icon.isNull():
                self.icon_label.setPixmap(icon.pixmap(36, 36))
            else:
                self.icon_label.setText("🧩")
        except Exception:
            try:
                self.icon_label.setText("🧩")
            except Exception:
                pass

    def update_state(self, installed: bool):
        self.status_label.setText("Installed" if installed else "Not installed")
        if installed:
            self.action_btn.setText("Open")
            self.action_btn.clicked.disconnect() if self.action_btn.receivers(self.action_btn.clicked) else None
            self.action_btn.clicked.connect(lambda: self.on_open(self.spec))
            self.uninstall_btn.setVisible(True)
            self.uninstall_btn.clicked.disconnect() if self.uninstall_btn.receivers(self.uninstall_btn.clicked) else None
            self.uninstall_btn.clicked.connect(lambda: self.on_uninstall(self.spec))
        else:
            self.action_btn.setText("Install")
            self.action_btn.clicked.disconnect() if self.action_btn.receivers(self.action_btn.clicked) else None
            self.action_btn.clicked.connect(lambda: self.on_install(self.spec))
            self.uninstall_btn.setVisible(False)

    def set_installing(self, installing: bool):
        try:
            if installing:
                self.action_btn.setEnabled(False)
                self.uninstall_btn.setEnabled(False)
                self.action_btn.setText("Installing…")
                self.status_label.setText("Installing…")
            else:
                self.action_btn.setEnabled(True)
                self.uninstall_btn.setEnabled(True)
                # Restore text based on state
                self.update_state(self.status_label.text().lower().startswith("installed"))
        except Exception:
            pass

    def _style(self):
        return """
        QFrame#pluginCard {
            background-color: #0f0f0f;
            border-radius: 12px;
            border: 1px solid rgba(255,255,255,0.06);
            margin: 10px;
        }
        QLabel#pluginTitle {
            color: #F0F0F0;
            font-size: 13px;
            font-weight: 600;
        }
        QLabel#pluginDesc {
            color: #A0A0A0;
            font-size: 11px;
        }
        QLabel#pluginStatus {
            color: #00BFAE;
            font-size: 10px;
        }
        """


class PluginsView(QWidget):
    install_requested = pyqtSignal(str)   # plugin id
    launch_requested = pyqtSignal(str)    # plugin id
    uninstall_requested = pyqtSignal(str) # plugin id

    def __init__(self, main_app, get_icon_callback, parent=None):
        super().__init__(parent)
        self.main_app = main_app
        self.get_icon_callback = get_icon_callback
        self._filter_text = ""
        self._installed_only = False
        self._categories = set()
        self._init_specs()
        self._init_ui()

    def _init_specs(self):
        icons_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "assets", "icons", "plugins"))
        base_icon = os.path.join(os.path.dirname(__file__), "..", "assets", "icons", "plugins.svg")
        bb_icon = os.path.join(icons_dir, "bleachbit.svg")
        ts_icon = os.path.join(icons_dir, "timeshift.svg")
        self.plugins = [
            {
                'id': 'bleachbit',
                'name': 'BleachBit',
                'desc': 'System cleaner to free disk space and guard your privacy.',
                'pkg': 'bleachbit',
                'cmd': 'bleachbit',
                'icon': bb_icon,
                'category': 'Cleaner',
            },
            {
                'id': 'timeshift',
                'name': 'Timeshift',
                'desc': 'System restore utility for Linux.',
                'pkg': 'timeshift',
                'cmd': 'timeshift-gtk',
                'icon': ts_icon,
                'category': 'Backup',
            },
            # Cleaners / Storage
            {
                'id': 'baobab',
                'name': 'Disk Usage Analyzer',
                'desc': 'Visualize disk usage and identify large folders/files.',
                'pkg': 'baobab',
                'cmd': 'baobab',
                'icon': os.path.join(icons_dir, 'baobab.svg'),
                'category': 'Cleaner',
            },
            # Backup
            {
                'id': 'deja-dup',
                'name': 'Déjà Dup (Backups)',
                'desc': 'Simple backups for GNOME with cloud support.',
                'pkg': 'deja-dup',
                'cmd': 'deja-dup',
                'icon': os.path.join(icons_dir, 'deja-dup.svg'),
                'category': 'Backup',
            },
            # System tools
            {
                'id': 'gparted',
                'name': 'GParted',
                'desc': 'Partition editor for graphically managing disk partitions.',
                'pkg': 'gparted',
                'cmd': 'gparted',
                'icon': os.path.join(icons_dir, 'gparted.jpeg'),
                'category': 'System',
            },
            {
                'id': 'gnome-disk-utility',
                'name': 'GNOME Disks',
                'desc': 'Manage disks and media — partition, format and benchmark.',
                'pkg': 'gnome-disk-utility',
                'cmd': 'gnome-disks',
                'icon': os.path.join(icons_dir, 'gnomedisk.jpeg'),
                'category': 'System',
            },
            {
                'id': 'pavucontrol',
                'name': 'PulseAudio Volume Control',
                'desc': 'Advanced audio mixer for PulseAudio.',
                'pkg': 'pavucontrol',
                'cmd': 'pavucontrol',
                'icon': os.path.join(icons_dir, 'pavucontrol.svg'),
                'category': 'System',
            },
            {
                'id': 'system-config-printer',
                'name': 'Printers',
                'desc': 'Configure printers and manage print jobs.',
                'pkg': 'system-config-printer',
                'cmd': 'system-config-printer',
                'icon': os.path.join(icons_dir, 'printer.svg'),
                'category': 'System',
            },
            # Monitors
            {
                'id': 'btop',
                'name': 'btop',
                'desc': 'Modern resource monitor for CPU, memory, disks, network.',
                'pkg': 'btop',
                'cmd': 'btop',
                'icon': os.path.join(icons_dir, 'btop.svg'),
                'category': 'Monitor',
            },
            {
                'id': 'htop',
                'name': 'htop',
                'desc': 'Interactive process viewer and system monitor.',
                'pkg': 'htop',
                'cmd': 'htop',
                'icon': os.path.join(icons_dir, 'htop.svg'),
                'category': 'Monitor',
            },
            {
                'id': 'gnome-system-monitor',
                'name': 'GNOME System Monitor',
                'desc': 'Graphical system monitor for processes and resources.',
                'pkg': 'gnome-system-monitor',
                'cmd': 'gnome-system-monitor',
                'icon': os.path.join(icons_dir, 'gnomesystem.jpeg'),
                'category': 'Monitor',
            },
            # GPU
            {
                'id': 'nvidia-settings',
                'name': 'NVIDIA Settings',
                'desc': 'Configure NVIDIA drivers and GPU options.',
                'pkg': 'nvidia-settings',
                'cmd': 'nvidia-settings',
                'icon': os.path.join(icons_dir, 'nvidia.svg'),
                'category': 'GPU',
            },
            {
                'id': 'nvtop',
                'name': 'nvtop',
                'desc': 'NVIDIA/AMD Intel GPU process monitor (requires supported GPU).',
                'pkg': 'nvtop',
                'cmd': 'nvtop',
                'icon': os.path.join(icons_dir, 'nvtop.svg'),
                'category': 'GPU',
            },
            # Utility
            {
                'id': 'simple-scan',
                'name': 'Document Scanner',
                'desc': 'Scan documents and photos with a simple interface.',
                'pkg': 'simple-scan',
                'cmd': 'simple-scan',
                'icon': os.path.join(icons_dir, 'simple-scan.svg'),
                'category': 'Utility',
            },
            {
                'id': 'file-roller',
                'name': 'Archive Manager',
                'desc': 'Create and extract archives (zip, tar, etc.).',
                'pkg': 'file-roller',
                'cmd': 'file-roller',
                'icon': os.path.join(icons_dir, 'archive.svg'),
                'category': 'Utility',
            },
        ]

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(20)

        # Popular Apps Slider Section
        self.create_popular_slider(layout)
        
        # Filter Buttons Row
        self.create_filter_buttons(layout)
        
        # Secondary Filter Row
        self.create_secondary_filters(layout)
        
        # Apps Grid
        self.create_apps_grid(layout)

    def create_popular_slider(self, parent_layout):
        """Create the popular apps slider at the top"""
        slider_container = QWidget()
        slider_container.setFixedHeight(200)
        slider_container.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(20, 25, 35, 0.9),
                    stop:1 rgba(25, 30, 40, 0.9));
                border-radius: 12px;
                border: 1px solid rgba(255, 255, 255, 0.1);
            }
        """)
        
        # Create scroll area for horizontal scrolling
        scroll_area = QScrollArea()
        scroll_area.setFixedHeight(200)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:horizontal {
                border: none;
                background: rgba(255, 255, 255, 0.1);
                height: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:horizontal {
                background: rgba(0, 191, 174, 0.6);
                border-radius: 4px;
                min-width: 20px;
            }
            QScrollBar::handle:horizontal:hover {
                background: rgba(0, 191, 174, 0.8);
            }
        """)
        
        # Create content widget for the scroll area
        scroll_content = QWidget()
        slider_layout = QHBoxLayout(scroll_content)
        slider_layout.setContentsMargins(20, 20, 20, 20)
        slider_layout.setSpacing(16)
        
        # Popular apps data - curated selection
        popular_apps = [
            {"name": "Firefox", "desc": "Fast, private & safe web browser", "category": "Internet", "rating": 4.6},
            {"name": "Visual Studio Code", "desc": "Powerful code editor", "category": "Development", "rating": 4.8},
            {"name": "Timeshift", "desc": "System restore utility", "category": "System Tools", "rating": 4.5},
            {"name": "BleachBit", "desc": "System cleaner & privacy tool", "category": "System Tools", "rating": 4.3},
            {"name": "GIMP", "desc": "GNU Image Manipulation Program", "category": "Graphics", "rating": 4.4},
            {"name": "VLC Media Player", "desc": "Universal media player", "category": "Multimedia", "rating": 4.7},
            {"name": "Discord", "desc": "Voice, video and text chat", "category": "Communication", "rating": 4.2},
            {"name": "Krita", "desc": "Digital painting application", "category": "Graphics", "rating": 4.6},
            {"name": "Spotify", "desc": "Music streaming service", "category": "Multimedia", "rating": 4.1},
            {"name": "Telegram", "desc": "Fast and secure messaging", "category": "Communication", "rating": 4.4},
            {"name": "Google Chrome", "desc": "Fast and secure web browser", "category": "Internet", "rating": 4.3},
            {"name": "Kitty", "desc": "Fast, feature-rich terminal", "category": "System Tools", "rating": 4.5}
        ]
        
        for app in popular_apps:
            card = self.create_slider_card(app)
            slider_layout.addWidget(card)
        
        # Set the content widget to the scroll area
        scroll_area.setWidget(scroll_content)
        
        # Add scroll area to the main container
        container_layout = QVBoxLayout(slider_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.addWidget(scroll_area)
        
        parent_layout.addWidget(slider_container)

    def create_slider_card(self, app_data):
        """Create a card for the popular apps slider"""
        card = QFrame()
        card.setFixedSize(200, 160)  # Increased width from 180 to 200
        
        # Try to load background image for the app
        app_name = app_data["name"].lower().replace(" ", "_")
        icons_dir = os.path.join(os.path.dirname(__file__), "..", "assets", "icons")
        
        # Look for background image files
        background_image = None
        for ext in ['.png', '.jpg', '.jpeg', '.svg']:
            image_path = os.path.join(icons_dir, f"{app_name}{ext}")
            print(f"Looking for image: {image_path}")  # Debug print
            if os.path.exists(image_path):
                background_image = os.path.normpath(image_path)
                print(f"Found background image: {background_image}")  # Debug print
                break
        
        if not background_image:
            print(f"No background image found for {app_name} in {icons_dir}")  # Debug print
        
        # Create stylesheet with or without background image
        if background_image:
            # Use QPixmap to load and scale the image properly
            from PyQt6.QtGui import QPixmap, QPalette, QBrush
            pixmap = QPixmap(background_image)
            if not pixmap.isNull():
                # Scale pixmap to card size
                scaled_pixmap = pixmap.scaled(200, 160, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                
                # Create QBrush from pixmap and set as background
                brush = QBrush(scaled_pixmap)
                palette = card.palette()
                palette.setBrush(QPalette.ColorRole.Window, brush)
                card.setPalette(palette)
                card.setAutoFillBackground(True)
                
            card.setStyleSheet("""
                QFrame {
                    border-radius: 10px;
                    border: 1px solid rgba(0, 191, 174, 0.3);
                }
                QFrame:hover {
                    border: 1px solid rgba(0, 191, 174, 0.6);
                }
            """)
        else:
            # Fallback to gradient if no image found
            card.setStyleSheet("""
                QFrame {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 rgba(30, 35, 45, 0.95),
                        stop:1 rgba(25, 30, 40, 0.95));
                    border-radius: 10px;
                    border: 1px solid rgba(0, 191, 174, 0.3);
                }
                QFrame:hover {
                    border: 1px solid rgba(0, 191, 174, 0.6);
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 rgba(35, 40, 50, 0.95),
                        stop:1 rgba(30, 35, 45, 0.95));
                }
            """)
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)  # Increased horizontal margins
        layout.setSpacing(6)  # Reduced spacing to fit content better
        
        # App icon placeholder
        icon_label = QLabel("📱")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet("font-size: 28px; color: #00BFAE;")  # Slightly smaller icon
        layout.addWidget(icon_label)
        
        # App name
        name_label = QLabel(app_data["name"])
        name_label.setStyleSheet("color: #F0F0F0; font-weight: 600; font-size: 12px;")  # Slightly smaller font
        name_label.setWordWrap(True)
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setMaximumHeight(30)  # Limit height to prevent overflow
        layout.addWidget(name_label)
        
        # App description
        desc_label = QLabel(app_data["desc"])
        desc_label.setStyleSheet("color: #A0A0A0; font-size: 9px;")  # Smaller description font
        desc_label.setWordWrap(True)
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_label.setMaximumHeight(25)  # Limit height to prevent overflow
        layout.addWidget(desc_label)
        
        # Install button
        install_btn = QPushButton("Install")
        install_btn.setFixedHeight(26)  # Slightly smaller button
        install_btn.setStyleSheet("""
            QPushButton {
                background-color: #00BFAE;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: 600;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #00A89A;
            }
        """)
        layout.addWidget(install_btn)
        
        return card

    def create_filter_buttons(self, parent_layout):
        """Create the main filter buttons row"""
        filter_container = QWidget()
        filter_layout = QHBoxLayout(filter_container)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.setSpacing(12)
        
        filters = ["All", "Popular", "Updated", "Categories"]
        
        for i, filter_name in enumerate(filters):
            btn = QPushButton(filter_name)
            btn.setFixedHeight(36)
            
            if i == 0:  # "All" button selected by default
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #00BFAE;
                        color: white;
                        border: none;
                        border-radius: 18px;
                        padding: 0 20px;
                        font-weight: 600;
                        font-size: 13px;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: rgba(255, 255, 255, 0.1);
                        color: #E0E0E0;
                        border: 1px solid rgba(255, 255, 255, 0.2);
                        border-radius: 18px;
                        padding: 0 20px;
                        font-weight: 500;
                        font-size: 13px;
                    }
                    QPushButton:hover {
                        background-color: rgba(0, 191, 174, 0.2);
                        border-color: rgba(0, 191, 174, 0.4);
                    }
                """)
            
            filter_layout.addWidget(btn)
        
        filter_layout.addStretch()
        parent_layout.addWidget(filter_container)

    def create_secondary_filters(self, parent_layout):
        """Create the secondary filter row"""
        secondary_container = QWidget()
        secondary_layout = QHBoxLayout(secondary_container)
        secondary_layout.setContentsMargins(0, 0, 0, 0)
        secondary_layout.setSpacing(8)
        
        secondary_filters = ["New", "Updated", "Upgraded", "Sorts", "Companies"]
        
        for filter_name in secondary_filters:
            btn = QPushButton(filter_name)
            btn.setFixedHeight(32)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(255, 255, 255, 0.05);
                    color: #B0B0B0;
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 16px;
                    padding: 0 16px;
                    font-weight: 500;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: rgba(0, 191, 174, 0.15);
                    border-color: rgba(0, 191, 174, 0.3);
                    color: #E0E0E0;
                }
            """)
            secondary_layout.addWidget(btn)
        
        secondary_layout.addStretch()
        parent_layout.addWidget(secondary_container)

    def create_apps_grid(self, parent_layout):
        """Create the apps grid section"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")
        
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(16)
        
        # Create grid container
        grid_container = QWidget()
        self.grid_layout = QGridLayout(grid_container)
        self.grid_layout.setSpacing(16)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        
        # Add sample app cards
        self.populate_app_cards()
        
        scroll_layout.addWidget(grid_container)
        scroll_layout.addStretch()
        
        scroll.setWidget(scroll_widget)
        parent_layout.addWidget(scroll)

    def populate_app_cards(self):
        """Populate the grid with app cards"""
        apps = [
            {"name": "System Monitor Pro", "desc": "Advanced system monitoring", "category": "System Tools", "rating": 4.5, "downloads": "10K+"},
            {"name": "KDE Plasma Designer", "desc": "Desktop customization", "category": "Desktop", "rating": 4.3, "downloads": "5K+"},
            {"name": "KDE Plasma", "desc": "Desktop environment", "category": "Desktop", "rating": 4.8, "downloads": "50K+"},
            {"name": "KDE Plasma Framework", "desc": "Framework components", "category": "Development", "rating": 4.6, "downloads": "25K+"},
            {"name": "Roxann Government", "desc": "Government tools", "category": "Office", "rating": 3.9, "downloads": "2K+"},
            {"name": "Revival of Khwaja", "desc": "Cultural application", "category": "Education", "rating": 4.1, "downloads": "1K+"},
            {"name": "Flatpak Manager", "desc": "Manage Flatpak apps", "category": "System Tools", "rating": 4.4, "downloads": "15K+"},
            {"name": "Power Manager", "desc": "Advanced power management", "category": "System Tools", "rating": 4.2, "downloads": "8K+"}
        ]
        
        cols = 4
        for i, app in enumerate(apps):
            row = i // cols
            col = i % cols
            card = self.create_app_card(app)
            self.grid_layout.addWidget(card, row, col)

    def create_app_card(self, app_data):
        """Create a modern app card"""
        card = QFrame()
        card.setFixedSize(160, 220)
        card.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(25, 30, 40, 0.9),
                    stop:1 rgba(20, 25, 35, 0.9));
                border-radius: 12px;
                border: 1px solid rgba(255, 255, 255, 0.08);
            }
            QFrame:hover {
                border: 1px solid rgba(0, 191, 174, 0.4);
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(30, 35, 45, 0.9),
                    stop:1 rgba(25, 30, 40, 0.9));
            }
        """)
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        
        # App icon
        icon_container = QWidget()
        icon_container.setFixedSize(48, 48)
        icon_container.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(0, 191, 174, 0.8),
                    stop:1 rgba(0, 150, 140, 0.8));
                border-radius: 12px;
            }
        """)
        icon_layout = QVBoxLayout(icon_container)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_label = QLabel("📱")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet("font-size: 24px; color: white;")
        icon_layout.addWidget(icon_label)
        layout.addWidget(icon_container, 0, Qt.AlignmentFlag.AlignHCenter)
        
        # App name
        name_label = QLabel(app_data["name"])
        name_label.setStyleSheet("color: #F0F0F0; font-weight: 600; font-size: 13px;")
        name_label.setWordWrap(True)
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(name_label)
        
        # App description
        desc_label = QLabel(app_data["desc"])
        desc_label.setStyleSheet("color: #A0A0A0; font-size: 10px;")
        desc_label.setWordWrap(True)
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc_label)
        
        # Rating and downloads
        info_container = QWidget()
        info_layout = QHBoxLayout(info_container)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(4)
        
        # Rating
        rating_label = QLabel(f"⭐ {app_data['rating']}")
        rating_label.setStyleSheet("color: #FFD700; font-size: 10px; font-weight: 500;")
        info_layout.addWidget(rating_label)
        
        info_layout.addStretch()
        
        # Downloads
        downloads_label = QLabel(app_data['downloads'])
        downloads_label.setStyleSheet("color: #A0A0A0; font-size: 10px;")
        info_layout.addWidget(downloads_label)
        
        layout.addWidget(info_container)
        
        # Install button
        install_btn = QPushButton("Install")
        install_btn.setFixedHeight(32)
        install_btn.setStyleSheet("""
            QPushButton {
                background-color: #00BFAE;
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #00A89A;
            }
        """)
        layout.addWidget(install_btn)
        
        layout.addStretch()
        return card

    def _icon_for(self, spec):
        try:
            icons_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "assets", "icons", "plugins"))
            path = spec.get('icon')
            if path and os.path.exists(path):
                return self.get_icon_callback(os.path.normpath(path), 36)

            # Try to resolve using available files (supports svg/png/jpg/jpeg) with aliases
            resolved = self._find_plugin_icon_file(spec)
            if resolved and os.path.exists(resolved):
                return self.get_icon_callback(os.path.normpath(resolved), 36)

            # Fallback to default plugin icon
            fallback = os.path.join(os.path.dirname(__file__), "..", "assets", "icons", "plugins.svg")
            return self.get_icon_callback(os.path.normpath(fallback), 36)
        except Exception:
            return QIcon()

    def _normalize_name(self, s: str) -> str:
        try:
            return re.sub(r'[^a-z0-9]', '', (s or '').lower())
        except Exception:
            s = (s or '').lower()
            return s.replace('-', '').replace('_', '').replace(' ', '')

    def _candidate_aliases(self, spec) -> list:
        pid = (spec.get('id') or '')
        name = (spec.get('name') or '')
        aliases = []

        def add(x):
            if x and x not in aliases:
                aliases.append(x)

        # Base identifiers
        add(pid)
        add(name)
        add(pid.replace('-', ''))
        add(pid.replace('-', '_'))
        add(pid.replace('_', ''))
        add((name or '').replace(' ', ''))
        add((name or '').replace(' ', '-').lower())
        add((name or '').replace(' ', '').lower())

        # Explicit aliases for known mismatches and alt names
        alias_map = {
            'bleachbit': ['BleachBit', 'bleachbit'],
            'timeshift': ['timeshift'],
            'baobab': ['diskusageanalyzer', 'baobab'],
            'deja-dup': ['dejadup', 'DejaDup'],
            'gparted': ['gparted'],
            'gnome-disk-utility': ['gnome-disks', 'gnomedisks', 'gnomeDis'],
            'pavucontrol': ['pavucontrol', 'pulseaudio'],
            'system-config-printer': ['printer', 'printers'],
            'btop': ['btop'],
            'htop': ['htop'],
            'gnome-system-monitor': ['system-monitor', 'gnomesystemmonitor', 'gnomeSystemMonitor'],
            'simple-scan': ['simple-scan', 'documentscanner'],
            'file-roller': ['file-roller', 'archive', 'achive', 'archivemanager', 'archiver'],
            'nvidia-settings': ['nvidia-settings', 'nvidia', 'nvideasettings', 'nvidiasettings'],
            'nvtop': ['nvtop'],
        }
        for a in alias_map.get(pid, []):
            add(a)

        return aliases

    def _find_plugin_icon_file(self, spec):
        icons_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "assets", "icons", "plugins"))
        try:
            files = []
            try:
                files = os.listdir(icons_dir)
            except Exception:
                files = []
            if not files:
                return None

            # Build index by normalized stem per extension, prefer svg, then png, jpeg, jpg
            exts = ['.svg', '.png', '.jpeg', '.jpg']
            index = {e: {} for e in exts}
            for fname in files:
                path = os.path.join(icons_dir, fname)
                if not os.path.isfile(path):
                    continue
                ext = os.path.splitext(fname)[1].lower()
                if ext not in index:
                    continue
                stem = os.path.splitext(fname)[0]
                key = self._normalize_name(stem)
                # Do not overwrite existing mapping for same key/ext to keep first-found
                index[ext].setdefault(key, path)

            candidates = [self._normalize_name(a) for a in self._candidate_aliases(spec) if a]

            # Exact match by preference order
            for ext in exts:
                for key in candidates:
                    if key in index[ext]:
                        return index[ext][key]

            # Fallback: partial contains match (still following ext preference)
            for ext in exts:
                for key in candidates:
                    for k2, p2 in index[ext].items():
                        if key and (k2.startswith(key) or key in k2):
                            return p2
            return None
        except Exception:
            return None

    def is_installed(self, spec):
        cmd = spec.get('cmd')
        pkg = spec.get('pkg')
        # Prefer which on the launch command; fallback to pacman -Qi
        try:
            if cmd and shutil.which(cmd):
                return True
        except Exception:
            pass
        try:
            import subprocess
            r = subprocess.run(["pacman", "-Qi", pkg], capture_output=True, text=True)
            return r.returncode == 0
        except Exception:
            return False

    def refresh_all(self):
        # No plugin cards to refresh in empty view
        pass

    def get_plugin(self, plugin_id):
        for spec in self.plugins:
            if spec['id'] == plugin_id:
                return spec
        return None

    def set_filter(self, text: str, installed_only: bool, categories=None):
        self._filter_text = (text or "").strip().lower()
        self._installed_only = bool(installed_only)
        self._categories = set((categories or []))
        self.apply_filter()

    def apply_filter(self):
        # No plugin cards to filter in empty view
        pass

    def set_installing(self, plugin_id: str, installing: bool):
        # No plugin cards to update in empty view
        pass
