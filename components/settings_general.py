import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QGridLayout,
                             QLabel, QCheckBox, QLineEdit, QPushButton, QFileDialog)
from PyQt6.QtCore import Qt

class GeneralSettingsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.app = parent
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(8, 8, 8, 8)
        self.layout.setSpacing(8)

        self.setup_ui()

    def setup_ui(self):
        # Basic Settings
        basic_box = QGroupBox("Basic Settings")
        grid = QGridLayout(basic_box)
        grid.setContentsMargins(12, 12, 12, 12)
        grid.setSpacing(8)

        # Auto check updates on launch
        self.cb_auto_check = QCheckBox("Auto check updates on launch")
        self.cb_auto_check.setChecked(bool(self.app.settings.get('auto_check_updates', True)))
        self.cb_auto_check.toggled.connect(lambda v: self.app._update_setting('auto_check_updates', v))
        grid.addWidget(self.cb_auto_check, 0, 0, 1, 2)

        # Include Local source
        self.cb_local = QCheckBox("Include Local source (custom scripts)")
        self.cb_local.setChecked(bool(self.app.settings.get('include_local_source', True)))
        self.cb_local.toggled.connect(lambda v: self.app._update_setting('include_local_source', v))
        grid.addWidget(self.cb_local, 1, 0, 1, 2)

        # Use npm user mode
        self.cb_npm = QCheckBox("Use npm user mode for global installs")
        self.cb_npm.setChecked(bool(self.app.settings.get('npm_user_mode', True)))
        self.cb_npm.toggled.connect(lambda v: self.app._update_setting('npm_user_mode', v))
        grid.addWidget(self.cb_npm, 2, 0, 1, 2)

        self.layout.addWidget(basic_box)

        # Bundle Settings
        bundle_box = QGroupBox("Bundle Autosave")
        pgrid = QGridLayout(bundle_box)
        pgrid.setContentsMargins(12, 12, 12, 12)
        pgrid.setSpacing(8)

        self.cb_bsave = QCheckBox("Autosave bundle to file")
        self.cb_bsave.setChecked(bool(self.app.settings.get('bundle_autosave', True)))
        self.cb_bsave.toggled.connect(lambda v: self.app._update_setting('bundle_autosave', v))
        pgrid.addWidget(self.cb_bsave, 0, 0, 1, 3)

        from_path = self.app.settings.get('bundle_autosave_path') or os.path.join(os.path.expanduser('~'), '.config', 'aurora', 'bundles', 'default.json')
        try:
            os.makedirs(os.path.dirname(from_path), exist_ok=True)
        except Exception:
            pass

        self.path_edit = QLineEdit(from_path)
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self.on_browse_bundle_path)
        pgrid.addWidget(QLabel("Autosave path:"), 1, 0)
        pgrid.addWidget(self.path_edit, 1, 1)
        pgrid.addWidget(browse_btn, 1, 2)

        self.layout.addWidget(bundle_box)

        # Import/Export buttons
        btns = QHBoxLayout()
        btn_export = QPushButton("Export Settings")
        btn_export.clicked.connect(self.app.export_settings)
        btn_import = QPushButton("Import Settings")
        btn_import.clicked.connect(self.app.import_settings)
        btns.addWidget(btn_export)
        btns.addWidget(btn_import)
        btns.addStretch()
        self.layout.addLayout(btns)

        self.layout.addStretch()

    def on_browse_bundle_path(self):
        path, _ = QFileDialog.getSaveFileName(self, "Select Bundle Autosave Path",
                                           self.path_edit.text(), "Bundle JSON (*.json)")
        if path:
            self.path_edit.setText(path)
            self.app._update_setting('bundle_autosave_path', path)
