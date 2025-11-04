import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QGridLayout,
                             QLabel, QCheckBox, QSpinBox, QPushButton)
from PyQt6.QtCore import Qt

class AutoUpdateSettingsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.app = parent
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(8, 8, 8, 8)
        self.layout.setSpacing(8)

        self.setup_ui()

    def setup_ui(self):
        # Auto Update Settings
        update_box = QGroupBox("Auto Update")
        auto_grid = QGridLayout(update_box)
        auto_grid.setContentsMargins(12, 12, 12, 12)
        auto_grid.setSpacing(8)

        self.cb_auto_update = QCheckBox("Enable automatic updates")
        self.cb_auto_update.setChecked(bool(self.app.settings.get('auto_update_enabled', False)))
        self.cb_auto_update.toggled.connect(lambda v: self.app._update_setting('auto_update_enabled', v))
        auto_grid.addWidget(self.cb_auto_update, 0, 0, 1, 2)

        auto_grid.addWidget(QLabel("Update interval (days):"), 1, 0)
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 30)  # 1 day to 30 days
        self.interval_spin.setValue(int(self.app.settings.get('auto_update_interval_days', 1)))
        self.interval_spin.valueChanged.connect(lambda v: self.app._update_setting('auto_update_interval_days', v))
        auto_grid.addWidget(self.interval_spin, 1, 1)

        self.layout.addWidget(update_box)

        # Snapshot Settings
        snapshot_box = QGroupBox("Snapshots")
        snap_grid = QGridLayout(snapshot_box)
        snap_grid.setContentsMargins(12, 12, 12, 12)
        snap_grid.setSpacing(8)

        self.cb_snapshot = QCheckBox("Create snapshot before updates")
        self.cb_snapshot.setChecked(bool(self.app.settings.get('snapshot_before_update', False)))
        self.cb_snapshot.toggled.connect(lambda v: self.app._update_setting('snapshot_before_update', v))
        snap_grid.addWidget(self.cb_snapshot, 0, 0, 1, 2)

        snap_btns = QHBoxLayout()
        create_snap_btn = QPushButton("Create Snapshot")
        create_snap_btn.clicked.connect(self.app.create_snapshot)
        snap_btns.addWidget(create_snap_btn)

        revert_snap_btn = QPushButton("Revert to Snapshot")
        revert_snap_btn.clicked.connect(self.app.revert_to_snapshot)
        snap_btns.addWidget(revert_snap_btn)

        delete_snap_btn = QPushButton("Delete Snapshots")
        delete_snap_btn.clicked.connect(self.app.delete_snapshots)
        snap_btns.addWidget(delete_snap_btn)

        snap_btns.addStretch()
        snap_grid.addLayout(snap_btns, 1, 0, 1, 2)

        self.layout.addWidget(snapshot_box)

        self.layout.addStretch()
