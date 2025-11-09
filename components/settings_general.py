import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QGridLayout,
                             QLabel, QCheckBox, QLineEdit, QPushButton, QFileDialog, QComboBox)
from PyQt6.QtCore import Qt
import sys_utils

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

        # AUR Helper selection
        grid.addWidget(QLabel("AUR Helper:"), 3, 0)
        self.aur_helper_combo = QComboBox()
        
        # Get available AUR helpers
        available_helpers = sys_utils.get_available_aur_helpers()
        
        # Add auto option first
        self.aur_helper_combo.addItem("Auto (detect available)", "auto")
        
        # Add all supported helpers (mark unavailable ones)
        for helper in ['yay', 'paru', 'trizen', 'pikaur']:
            if helper in available_helpers:
                self.aur_helper_combo.addItem(helper, helper)
            else:
                self.aur_helper_combo.addItem(f"{helper} (not installed)", helper)
        
        # Set current selection
        current_helper = self.app.settings.get('aur_helper', 'auto')
        index = self.aur_helper_combo.findData(current_helper)
        if index >= 0:
            self.aur_helper_combo.setCurrentIndex(index)
        
        self.aur_helper_combo.currentIndexChanged.connect(self.on_aur_helper_changed)
        grid.addWidget(self.aur_helper_combo, 3, 1)
        
        # Show currently detected helper
        detected_helper = sys_utils.get_aur_helper()
        if detected_helper:
            helper_status = QLabel(f"Currently using: {detected_helper}")
            helper_status.setStyleSheet("color: #888; font-size: 11px;")
            grid.addWidget(helper_status, 4, 1)
        else:
            helper_status = QLabel("No AUR helper detected")
            helper_status.setStyleSheet("color: #d9534f; font-size: 11px;")
            grid.addWidget(helper_status, 4, 1)

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
    
    def on_aur_helper_changed(self, index):
        helper = self.aur_helper_combo.itemData(index)
        self.app._update_setting('aur_helper', helper)
        self.app.log(f"AUR helper preference set to: {helper}")
