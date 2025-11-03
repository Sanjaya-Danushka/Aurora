from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QFrame, QGridLayout
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QIcon
import os
import shutil


class PluginCard(QFrame):
    def __init__(self, spec: dict, icon: QIcon, installed: bool, on_install, on_open, parent=None):
        super().__init__(parent)
        self.spec = spec
        self.on_install = on_install
        self.on_open = on_open
        self.setObjectName("pluginCard")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(self._style())

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        icon_label = QLabel()
        try:
            if icon and not icon.isNull():
                icon_label.setPixmap(icon.pixmap(36, 36))
            else:
                icon_label.setText("🧩")
        except Exception:
            icon_label.setText("🧩")
        layout.addWidget(icon_label)

        text_col = QVBoxLayout()
        title = QLabel(spec.get('name', spec.get('id')))
        title.setObjectName("pluginTitle")
        desc = QLabel(spec.get('desc', ""))
        desc.setObjectName("pluginDesc")
        desc.setWordWrap(True)
        text_col.addWidget(title)
        text_col.addWidget(desc)
        layout.addLayout(text_col, 1)

        self.action_btn = QPushButton()
        self.status_label = QLabel()
        self.status_label.setObjectName("pluginStatus")
        btn_col = QVBoxLayout()
        btn_col.addWidget(self.action_btn)
        btn_col.addWidget(self.status_label)
        btn_col.addStretch()
        layout.addLayout(btn_col)

        self.update_state(installed)

    def update_state(self, installed: bool):
        self.status_label.setText("Installed" if installed else "Not installed")
        if installed:
            self.action_btn.setText("Open")
            self.action_btn.clicked.disconnect() if self.action_btn.receivers(self.action_btn.clicked) else None
            self.action_btn.clicked.connect(lambda: self.on_open(self.spec))
        else:
            self.action_btn.setText("Install")
            self.action_btn.clicked.disconnect() if self.action_btn.receivers(self.action_btn.clicked) else None
            self.action_btn.clicked.connect(lambda: self.on_install(self.spec))

    def _style(self):
        return """
        QFrame#pluginCard {
            background-color: #0f0f0f;
            border-radius: 12px;
            border: 1px solid rgba(255,255,255,0.06);
        }
        QLabel#pluginTitle {
            color: #F0F0F0;
            font-size: 14px;
            font-weight: 600;
        }
        QLabel#pluginDesc {
            color: #A0A0A0;
            font-size: 12px;
        }
        QLabel#pluginStatus {
            color: #00BFAE;
            font-size: 11px;
        }
        """


class PluginsView(QWidget):
    install_requested = pyqtSignal(str)  # plugin id
    launch_requested = pyqtSignal(str)   # plugin id

    def __init__(self, main_app, get_icon_callback, parent=None):
        super().__init__(parent)
        self.main_app = main_app
        self.get_icon_callback = get_icon_callback
        self.cards = {}
        self._init_specs()
        self._init_ui()

    def _init_specs(self):
        base_icon = os.path.join(os.path.dirname(__file__), "..", "assets", "icons", "plugins", "plugins.svg")
        base_icon = os.path.normpath(base_icon)
        self.plugins = [
            {
                'id': 'bleachbit',
                'name': 'BleachBit',
                'desc': 'System cleaner to free disk space and guard your privacy.',
                'pkg': 'bleachbit',
                'cmd': 'bleachbit',
                'icon': base_icon,
            },
            {
                'id': 'timeshift',
                'name': 'Timeshift',
                'desc': 'System restore utility for Linux.',
                'pkg': 'timeshift',
                'cmd': 'timeshift-gtk',
                'icon': base_icon,
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
        grid = QGridLayout(grid_container)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)

        for idx, spec in enumerate(self.plugins):
            installed = self.is_installed(spec)
            icon = self._icon_for(spec)
            card = PluginCard(
                spec,
                icon,
                installed,
                on_install=lambda s, self=self: self.install_requested.emit(s['id']),
                on_open=lambda s, self=self: self.launch_requested.emit(s['id']),
                parent=self,
            )
            row = idx // 2
            col = idx % 2
            grid.addWidget(card, row, col)
            self.cards[spec['id']] = card

        layout.addWidget(grid_container)
        layout.addStretch()

    def _icon_for(self, spec):
        try:
            return self.get_icon_callback(spec.get('icon'), 24)
        except Exception:
            return QIcon()

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
            card.update_state(self.is_installed(spec))

    def get_plugin(self, plugin_id):
        for spec in self.plugins:
            if spec['id'] == plugin_id:
                return spec
        return None
