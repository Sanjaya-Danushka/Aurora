import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
                             QHeaderView, QPushButton)
from PyQt6.QtCore import Qt

class PluginsSettingsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.app = parent
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(8, 8, 8, 8)
        self.layout.setSpacing(8)

        self.setup_ui()

    def setup_ui(self):
        # Plugin Actions
        actions = QHBoxLayout()
        btn_add = QPushButton("Install Plugin")
        btn_add.clicked.connect(self.app.install_plugin)
        btn_remove = QPushButton("Remove Selected")
        btn_remove.clicked.connect(self.app.remove_selected_plugins)
        btn_reload = QPushButton("Reload Plugins")
        btn_reload.clicked.connect(self.app.reload_plugins_and_notify)
        btn_defaults = QPushButton("Install Default Plugins")
        btn_defaults.clicked.connect(self.app.install_default_plugins)

        actions.addWidget(btn_add)
        actions.addWidget(btn_remove)
        actions.addWidget(btn_reload)
        actions.addWidget(btn_defaults)
        actions.addStretch()
        self.layout.addLayout(actions)

        # Plugins Table
        self.plugins_table = QTableWidget()
        self.plugins_table.setColumnCount(3)
        self.plugins_table.setHorizontalHeaderLabels(["Enabled", "Plugin", "Location"])
        self.plugins_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.plugins_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.plugins_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.layout.addWidget(self.plugins_table)

        self.refresh_plugins_table()
        self.plugins_table.itemChanged.connect(self.on_plugin_item_changed)

    def refresh_plugins_table(self):
        self._plugins_populating = True
        plugs = self.app.scan_plugins()
        enabled = set(self.app.settings.get('enabled_plugins') or [])
        self.plugins_table.setRowCount(0)

        for p in plugs:
            row = self.plugins_table.rowCount()
            self.plugins_table.insertRow(row)

            enabled_item = QTableWidgetItem()
            enabled_item.setFlags(enabled_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            enabled_item.setCheckState(Qt.CheckState.Checked if p['name'] in enabled else Qt.CheckState.Unchecked)
            name_item = QTableWidgetItem(p['name'])
            loc_item = QTableWidgetItem(p.get('location', 'User'))

            self.plugins_table.setItem(row, 0, enabled_item)
            self.plugins_table.setItem(row, 1, name_item)
            self.plugins_table.setItem(row, 2, loc_item)

        self._plugins_populating = False

    def on_plugin_item_changed(self, item):
        if getattr(self, '_plugins_populating', False):
            return
        if item.column() != 0:
            return

        row = item.row()
        name_item = self.plugins_table.item(row, 1)
        if not name_item:
            return

        name = name_item.text().strip()
        enabled = set(self.app.settings.get('enabled_plugins') or [])

        if item.checkState() == Qt.CheckState.Checked:
            enabled.add(name)
        else:
            enabled.discard(name)

        self.app.settings['enabled_plugins'] = sorted(enabled)
        self.app.save_settings()
