from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QFrame, QGridLayout, QSizePolicy
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QIcon
import os
import shutil
import re


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
        self.setMinimumHeight(128)
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
        title = QLabel(spec.get('name', spec.get('id')))
        title.setObjectName("pluginTitle")
        desc = QLabel(spec.get('desc', ""))
        desc.setObjectName("pluginDesc")
        desc.setWordWrap(True)
        try:
            desc.setMaximumHeight(48)
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
        self.cards = {}
        self._filter_text = ""
        self._installed_only = False
        self._categories = set()
        self._init_specs()
        self._init_ui()

    def _init_specs(self):
        icons_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "assets", "icons", "plugins"))
        base_icon = os.path.join(icons_dir, "plugins.svg")
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
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        title = QLabel("Plugins")
        title.setObjectName("sectionLabel")
        layout.addWidget(title)

        grid_container = QWidget()
        self.grid = QGridLayout(grid_container)
        self.grid.setContentsMargins(12, 12, 12, 12)
        self.grid.setHorizontalSpacing(12)
        self.grid.setVerticalSpacing(48)
        try:
            grid_container.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        except Exception:
            pass

        col_count = 3
        for idx, spec in enumerate(self.plugins):
            installed = self.is_installed(spec)
            icon = self._icon_for(spec)
            card = PluginCard(
                spec,
                icon,
                installed,
                on_install=lambda s, self=self: self.install_requested.emit(s['id']),
                on_open=lambda s, self=self: self.launch_requested.emit(s['id']),
                on_uninstall=lambda s, self=self: self.uninstall_requested.emit(s['id']),
                parent=self,
            )
            row = idx // col_count
            col = idx % col_count
            self.grid.addWidget(card, row, col)
            self.cards[spec['id']] = card

        layout.addWidget(grid_container)
        layout.addStretch()

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
            fallback = os.path.join(icons_dir, "plugins.svg")
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
        for spec in self.plugins:
            card = self.cards.get(spec['id'])
            if not card:
                continue
            try:
                new_icon = self._icon_for(spec)
                card.update_icon(new_icon)
            except Exception:
                pass
            card.update_state(self.is_installed(spec))
        self.apply_filter()

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
        txt = self._filter_text
        only = self._installed_only
        for spec in self.plugins:
            card = self.cards.get(spec['id'])
            if not card:
                continue
            name = (spec.get('name') or spec.get('id') or "").lower()
            desc = (spec.get('desc') or "").lower()
            cat = (spec.get('category') or "").lower()
            matches_txt = (not txt) or (txt in name) or (txt in desc)
            if only:
                is_inst = self.is_installed(spec)
            else:
                is_inst = True
            matches_cat = (not self._categories) or (cat in {c.lower() for c in self._categories})
            card.setVisible(matches_txt and is_inst and matches_cat)

    def set_installing(self, plugin_id: str, installing: bool):
        card = self.cards.get(plugin_id)
        if card:
            card.set_installing(installing)
