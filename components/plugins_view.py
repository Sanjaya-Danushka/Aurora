from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QFrame, QGridLayout, QSizePolicy, QMenu
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QAction
import os
import shutil
import re
import random


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
        plugins_items_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "assets", "plugins", "plugins-items"))
        self.plugins = [
            {
                'id': 'bleachbit',
                'name': 'BleachBit',
                'desc': 'System cleaner to free disk space and guard your privacy.',
                'pkg': 'bleachbit',
                'cmd': 'bleachbit',
                'icon': os.path.join(plugins_items_dir, 'BleachBit.png'),
                'category': 'Cleaner',
            },
            {
                'id': 'timeshift',
                'name': 'Timeshift',
                'desc': 'System restore utility for Linux.',
                'pkg': 'timeshift',
                'cmd': 'timeshift-gtk',
                'icon': os.path.join(plugins_items_dir, 'timeshift.png'),
                'category': 'Backup',
            },
            {
                'id': 'baobab',
                'name': 'Disk Usage Analyzer',
                'desc': 'Visualize disk usage and identify large folders/files.',
                'pkg': 'baobab',
                'cmd': 'baobab',
                'icon': os.path.join(plugins_items_dir, 'diskusageanalyzer.png'),
                'category': 'Cleaner',
            },
            {
                'id': 'deja-dup',
                'name': 'Déjà Dup (Backups)',
                'desc': 'Simple backups for GNOME with cloud support.',
                'pkg': 'deja-dup',
                'cmd': 'deja-dup',
                'icon': os.path.join(plugins_items_dir, 'DejaDup.png'),
                'category': 'Backup',
            },
            {
                'id': 'gparted',
                'name': 'GParted',
                'desc': 'Partition editor for graphically managing disk partitions.',
                'pkg': 'gparted',
                'cmd': 'gparted',
                'icon': os.path.join(plugins_items_dir, 'gparted.jpeg'),
                'category': 'System',
            },
            {
                'id': 'gnome-disk-utility',
                'name': 'GNOME Disks',
                'desc': 'Manage disks and media — partition, format and benchmark.',
                'pkg': 'gnome-disk-utility',
                'cmd': 'gnome-disks',
                'icon': os.path.join(plugins_items_dir, 'gnomedisk.jpeg'),
                'category': 'System',
            },
            {
                'id': 'pavucontrol',
                'name': 'PulseAudio Volume Control',
                'desc': 'Advanced audio mixer for PulseAudio.',
                'pkg': 'pavucontrol',
                'cmd': 'pavucontrol',
                'icon': os.path.join(plugins_items_dir, 'pulseaudio.png'),
                'category': 'System',
            },
            {
                'id': 'system-config-printer',
                'name': 'Printers',
                'desc': 'Configure printers and manage print jobs.',
                'pkg': 'system-config-printer',
                'cmd': 'system-config-printer',
                'icon': os.path.join(plugins_items_dir, 'printers.png'),
                'category': 'System',
            },
            {
                'id': 'btop',
                'name': 'btop',
                'desc': 'Modern resource monitor for CPU, memory, disks, network.',
                'pkg': 'btop',
                'cmd': 'btop',
                'icon': os.path.join(plugins_items_dir, 'btop.png'),
                'category': 'Monitor',
            },
            {
                'id': 'htop',
                'name': 'htop',
                'desc': 'Interactive process viewer and system monitor.',
                'pkg': 'htop',
                'cmd': 'htop',
                'icon': os.path.join(plugins_items_dir, 'htop.png'),
                'category': 'Monitor',
            },
            {
                'id': 'gnome-system-monitor',
                'name': 'GNOME System Monitor',
                'desc': 'Graphical system monitor for processes and resources.',
                'pkg': 'gnome-system-monitor',
                'cmd': 'gnome-system-monitor',
                'icon': os.path.join(plugins_items_dir, 'gnomesystem.jpeg'),
                'category': 'Monitor',
            },
            {
                'id': 'nvidia-settings',
                'name': 'NVIDIA Settings',
                'desc': 'Configure NVIDIA drivers and GPU options.',
                'pkg': 'nvidia-settings',
                'cmd': 'nvidia-settings',
                'icon': os.path.join(plugins_items_dir, 'nvideasettings.jpeg'),
                'category': 'GPU',
            },
            {
                'id': 'nvtop',
                'name': 'nvtop',
                'desc': 'NVIDIA/AMD Intel GPU process monitor (requires supported GPU).',
                'pkg': 'nvtop',
                'cmd': 'nvtop',
                'icon': os.path.join(plugins_items_dir, 'nvtop.png'),
                'category': 'GPU',
            },
            {
                'id': 'simple-scan',
                'name': 'Document Scanner',
                'desc': 'Scan documents and photos with a simple interface.',
                'pkg': 'simple-scan',
                'cmd': 'simple-scan',
                'icon': os.path.join(plugins_items_dir, 'documentscanner.png'),
                'category': 'Utility',
            },
            {
                'id': 'file-roller',
                'name': 'Archive Manager',
                'desc': 'Create and extract archives (zip, tar, etc.).',
                'pkg': 'file-roller',
                'cmd': 'file-roller',
                'icon': os.path.join(plugins_items_dir, 'achive.png'),
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
        
        # Apps Grid
        self.create_apps_grid(layout)

    def create_popular_slider(self, parent_layout):
        """Create the popular apps slider at the top"""
        slider_container = QWidget()
        slider_container.setFixedHeight(220)  # Increased height for larger cards
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
        scroll_area.setFixedHeight(220)  # Increased height for larger cards
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
        
        # Popular apps data - curated selection with image filenames
        popular_apps = [
            {"name": "Firefox", "desc": "Fast, private & safe web browser", "category": "Internet", "rating": 4.6, "image": "firefox.jpg"},
            {"name": "Visual Studio Code", "desc": "Powerful code editor", "category": "Development", "rating": 4.8, "image": "vscode.jpg"},
            {"name": "Timeshift", "desc": "System restore utility", "category": "System Tools", "rating": 4.5, "image": "timeshift.jpg"},
            {"name": "BleachBit", "desc": "System cleaner & privacy tool", "category": "System Tools", "rating": 4.3, "image": "bleachbit.jpg"},
            {"name": "GIMP", "desc": "GNU Image Manipulation Program", "category": "Graphics", "rating": 4.4, "image": "gimp.jpg"},
            {"name": "VLC Media Player", "desc": "Universal media player", "category": "Multimedia", "rating": 4.7, "image": "vlc.jpg"},
            {"name": "Discord", "desc": "Voice, video and text chat", "category": "Communication", "rating": 4.2, "image": "discode.jpg"},
            {"name": "Krita", "desc": "Digital painting application", "category": "Graphics", "rating": 4.6, "image": "krita.jpg"},
            {"name": "Spotify", "desc": "Music streaming service", "category": "Multimedia", "rating": 4.1, "image": "spotify.jpg"},
            {"name": "Telegram", "desc": "Fast and secure messaging", "category": "Communication", "rating": 4.4, "image": "telegram.jpg"},
            {"name": "Google Chrome", "desc": "Fast and secure web browser", "category": "Internet", "rating": 4.3, "image": "chrome.jpg"},
            {"name": "Kitty", "desc": "Fast, feature-rich terminal", "category": "System Tools", "rating": 4.5, "image": "kitty.jpg"}
        ]
        
        # Shuffle the apps list to randomize the order
        shuffled_apps = popular_apps.copy()
        random.shuffle(shuffled_apps)
        
        for app in shuffled_apps:
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
        """Create a card for the popular apps slider with background image"""
        card = QFrame()
        card.setFixedSize(240, 180)  # Larger size for better visibility
        
        # Get background image path
        image_filename = app_data.get("image", "")
        background_image_path = os.path.join(os.path.dirname(__file__), "..", "assets", "plugins", "slidebar", image_filename)
        
        # Create background image label
        background_label = QLabel(card)
        background_label.setGeometry(0, 0, 240, 180)
        
        # Load and scale the background image
        if os.path.exists(background_image_path):
            pixmap = QPixmap(background_image_path)
            if not pixmap.isNull():
                # Scale the pixmap to cover the entire card while maintaining aspect ratio
                scaled_pixmap = pixmap.scaled(240, 180, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                
                # If the scaled image is larger than the card, crop it to center
                if scaled_pixmap.width() > 240 or scaled_pixmap.height() > 180:
                    x_offset = max(0, (scaled_pixmap.width() - 240) // 2)
                    y_offset = max(0, (scaled_pixmap.height() - 180) // 2)
                    cropped_pixmap = scaled_pixmap.copy(x_offset, y_offset, 240, 180)
                    background_label.setPixmap(cropped_pixmap)
                else:
                    background_label.setPixmap(scaled_pixmap)
        
        # Style the card frame
        card.setStyleSheet("""
            QFrame {
                border-radius: 12px;
                border: none;
            }
        """)
        
        # Create overlay container for text content
        overlay = QWidget(card)
        overlay.setGeometry(0, 0, 240, 180)
        overlay.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(0, 0, 0, 0.1),
                    stop:0.6 rgba(0, 0, 0, 0.3),
                    stop:1 rgba(0, 0, 0, 0.8));
                border: none;
            }
        """)
        
        layout = QVBoxLayout(overlay)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)
        
        # Add stretch to push content to bottom
        layout.addStretch()
        
        # App name
        name_label = QLabel(app_data["name"])
        name_label.setStyleSheet("""
            color: white;
            font-weight: 700;
            font-size: 16px;
            background: transparent;
        """)
        name_label.setWordWrap(True)
        name_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(name_label)
        
        # App description
        desc_label = QLabel(app_data["desc"])
        desc_label.setStyleSheet("""
            color: rgba(255, 255, 255, 0.9);
            font-size: 12px;
            font-weight: 400;
            background: transparent;
        """)
        desc_label.setWordWrap(True)
        desc_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        desc_label.setMaximumHeight(32)
        layout.addWidget(desc_label)
        
        # Bottom row with rating and install button
        bottom_row = QWidget()
        bottom_row.setStyleSheet("background: transparent;")
        bottom_layout = QHBoxLayout(bottom_row)
        bottom_layout.setContentsMargins(0, 8, 0, 0)
        bottom_layout.setSpacing(8)
        
        # Rating
        rating_label = QLabel(f"⭐ {app_data['rating']}")
        rating_label.setStyleSheet("""
            color: #FFD700;
            font-size: 12px;
            font-weight: 600;
            background: transparent;
            border: none;
        """)
        bottom_layout.addWidget(rating_label)
        
        bottom_layout.addStretch()
        
        # Install button
        install_btn = QPushButton("Install")
        install_btn.setFixedSize(80, 32)
        install_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(30, 30, 30, 0.9);
                color: white;
                border: none;
                border-radius: 16px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: rgba(50, 50, 50, 0.9);
            }
            QPushButton:pressed {
                background-color: rgba(20, 20, 20, 0.9);
            }
        """)
        bottom_layout.addWidget(install_btn)
        
        layout.addWidget(bottom_row)
        
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
            
            # Special handling for Categories button
            if filter_name == "Categories":
                # Create dropdown menu for categories
                categories_menu = QMenu(self)
                categories_menu.setStyleSheet("""
                    QMenu {
                        background-color: #1a1a1a;
                        color: #E0E0E0;
                        border: 1px solid rgba(255, 255, 255, 0.2);
                        border-radius: 8px;
                        padding: 4px;
                    }
                    QMenu::item {
                        padding: 8px 16px;
                        border-radius: 4px;
                    }
                    QMenu::item:selected {
                        background-color: rgba(0, 191, 174, 0.2);
                    }
                """)
                
                # Add all categories to the menu
                categories = [
                    "System", "Office", "Development", "Internet", 
                    "Multimedia", "Graphics", "Games", "Education", 
                    "Utilities", "Customization", "Security", "Lifestyle"
                ]
                
                for category in categories:
                    action = QAction(category, self)
                    action.triggered.connect(lambda checked, cat=category: self.filter_by_category(cat))
                    categories_menu.addAction(action)
                
                btn.setMenu(categories_menu)
            
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


    def _get_scrollbar_stylesheet(self):
        """Return beautiful scrollbar stylesheet with rounded corners"""
        return """
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                border: none;
                background: transparent;
                width: 12px;
                margin: 0px 0px 0px 0px;
            }
            QScrollBar::handle:vertical {
                background: rgba(0, 191, 174, 0.6);
                border-radius: 6px;
                min-height: 20px;
                margin: 2px 2px 2px 2px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(0, 191, 174, 0.8);
            }
            QScrollBar::handle:vertical:pressed {
                background: rgba(0, 191, 174, 1);
            }
            QScrollBar::add-line:vertical {
                border: none;
                background: none;
                height: 0px;
            }
            QScrollBar::sub-line:vertical {
                border: none;
                background: none;
                height: 0px;
            }
            QScrollBar::up-arrow:vertical, QScrollBar::down-arrow:vertical {
                border: none;
                width: 0px;
                height: 0px;
                background: none;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """

    def create_apps_grid(self, parent_layout):
        """Create the apps grid section"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(self._get_scrollbar_stylesheet())
        
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(16)
        
        # Create grid container
        grid_container = QWidget()
        self.grid_layout = QGridLayout(grid_container)
        self.grid_layout.setSpacing(20)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setColumnStretch(0, 1)
        self.grid_layout.setColumnStretch(1, 1)
        
        # Add sample app cards
        self.populate_app_cards()
        
        scroll_layout.addWidget(grid_container)
        scroll_layout.addStretch()
        
        scroll.setWidget(scroll_widget)
        parent_layout.addWidget(scroll)

    def populate_app_cards(self):
        """Populate the grid with real plugin cards"""
        cols = 2
        for i, plugin in enumerate(self.plugins):
            row = i // cols
            col = i % cols
            installed = self.is_installed(plugin)
            icon = self._icon_for(plugin)
            card = self.create_app_card(plugin, icon, installed)
            self.grid_layout.addWidget(card, row, col)

    def _get_package_source(self, plugin_spec):
        """Determine package source from plugin spec"""
        pkg = plugin_spec.get('pkg', '').lower()
        if pkg.startswith('npm-') or 'npm' in pkg:
            return 'npm'
        elif pkg.startswith('aur/') or 'aur' in pkg:
            return 'aur'
        elif pkg.endswith('.flatpak') or 'flatpak' in pkg:
            return 'flatpak'
        elif pkg.startswith('brew-') or 'brew' in pkg:
            return 'brew'
        else:
            return 'pacman'

    def create_app_card(self, plugin_spec, icon, installed):
        """Create a medium-sized app card with enhanced styling"""
        card = QFrame()
        card.setFixedSize(340, 140)
        card.setStyleSheet("""
            QFrame {
                background-image: url('/home/dev/Desktop/New Folder1/Neoarch/assets/plugins/cardbackground.jpg');
                background-position: center;
                background-repeat: no-repeat;
                background-attachment: fixed;
                background-color: rgba(15, 20, 30, 0.85);
                border-radius: 14px;
                border: 1px solid rgba(0, 191, 174, 0.15);
            }
            QFrame:hover {
                border: 1px solid rgba(0, 191, 174, 0.4);
                background-color: rgba(20, 25, 35, 0.9);
            }
        """)
        
        layout = QHBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)
        
        # Left side: Icon and text
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)
        
        # Icon and name row
        icon_name_layout = QHBoxLayout()
        icon_name_layout.setContentsMargins(0, 0, 0, 0)
        icon_name_layout.setSpacing(10)
        
        # Icon with shadow effect
        icon_label = QLabel()
        icon_label.setFixedSize(52, 52)
        icon_label.setStyleSheet("""
            QLabel {
                border: none;
                background: rgba(255, 255, 255, 0.05);
                border-radius: 10px;
                padding: 2px;
            }
        """)
        if icon and not icon.isNull():
            icon_label.setPixmap(icon.pixmap(48, 48))
        else:
            icon_label.setText("🧩")
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_label.setStyleSheet("""
                QLabel {
                    font-size: 28px;
                    border: none;
                    background: rgba(255, 255, 255, 0.05);
                    border-radius: 10px;
                }
            """)
        icon_name_layout.addWidget(icon_label)
        
        # Name and source column
        name_source_layout = QVBoxLayout()
        name_source_layout.setContentsMargins(0, 0, 0, 0)
        name_source_layout.setSpacing(2)
        
        # Name
        name_label = QLabel(plugin_spec.get('name', plugin_spec.get('id')))
        name_label.setStyleSheet("""
            QLabel {
                color: #FFFFFF;
                font-weight: 700;
                font-size: 13px;
                border: none;
                background: transparent;
            }
        """)
        name_label.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        name_source_layout.addWidget(name_label)
        
        # Source (package manager)
        source = self._get_package_source(plugin_spec)
        source_label = QLabel(f"📦 {source}")
        source_label.setStyleSheet("""
            QLabel {
                color: #00BFAE;
                font-size: 9px;
                font-weight: 500;
                border: none;
                background: transparent;
            }
        """)
        name_source_layout.addWidget(source_label)
        
        icon_name_layout.addLayout(name_source_layout, 1)
        left_layout.addLayout(icon_name_layout)
        
        # Description
        desc_label = QLabel(plugin_spec.get('desc', ''))
        desc_label.setStyleSheet("""
            QLabel {
                color: #B0B0B0;
                font-size: 10px;
                border: none;
                background: transparent;
                line-height: 1.3;
            }
        """)
        desc_label.setWordWrap(True)
        desc_label.setMaximumHeight(28)
        left_layout.addWidget(desc_label)
        
        left_layout.addStretch()
        layout.addLayout(left_layout, 1)
        
        # Right side: Buttons
        btn_layout = QVBoxLayout()
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(8)
        btn_layout.addStretch()
        
        if installed:
            # Open button (filled white)
            open_btn = QPushButton("Open")
            open_btn.setFixedHeight(34)
            open_btn.setMinimumWidth(85)
            open_btn.setStyleSheet("""
                QPushButton {
                    background-color: #FFFFFF;
                    color: #1a1a1a;
                    border: none;
                    border-radius: 8px;
                    font-weight: 700;
                    font-size: 12px;
                    padding: 0px 12px;
                }
                QPushButton:hover {
                    background-color: #F0F0F0;
                    color: #000000;
                }
                QPushButton:pressed {
                    background-color: #E0E0E0;
                }
            """)
            open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            open_btn.clicked.connect(lambda: self.launch_requested.emit(plugin_spec['id']))
            btn_layout.addWidget(open_btn)
            
            # Uninstall button (outlined)
            uninstall_btn = QPushButton("Uninstall")
            uninstall_btn.setFixedHeight(32)
            uninstall_btn.setMinimumWidth(85)
            uninstall_btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #E0E0E0;
                    border: 1.5px solid rgba(255, 255, 255, 0.25);
                    border-radius: 8px;
                    font-weight: 600;
                    font-size: 11px;
                    padding: 0px 12px;
                }
                QPushButton:hover {
                    border: 1.5px solid rgba(0, 191, 174, 0.7);
                    color: #00BFAE;
                    background-color: rgba(0, 191, 174, 0.08);
                }
                QPushButton:pressed {
                    background-color: rgba(0, 191, 174, 0.15);
                }
            """)
            uninstall_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            uninstall_btn.clicked.connect(lambda: self.uninstall_requested.emit(plugin_spec['id']))
            btn_layout.addWidget(uninstall_btn)
        else:
            # Install button (filled teal)
            install_btn = QPushButton("Install")
            install_btn.setFixedHeight(34)
            install_btn.setMinimumWidth(85)
            install_btn.setStyleSheet("""
                QPushButton {
                    background-color: #00BFAE;
                    color: white;
                    border: none;
                    border-radius: 8px;
                    font-weight: 700;
                    font-size: 12px;
                    padding: 0px 12px;
                }
                QPushButton:hover {
                    background-color: #00D4C4;
                    color: white;
                }
                QPushButton:pressed {
                    background-color: #009080;
                }
            """)
            install_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            install_btn.clicked.connect(lambda: self.install_requested.emit(plugin_spec['id']))
            btn_layout.addWidget(install_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
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
    
    def filter_by_category(self, category):
        """Handle category selection from dropdown menu"""
        print(f"Filtering by category: {category}")
        # TODO: Implement actual filtering logic here
        # This will be connected to your CRUD system later
