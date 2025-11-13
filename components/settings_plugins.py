import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
                             QHeaderView, QPushButton, QLabel)
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
        # Add title with subtitle
        title = QLabel("Plugins")
        title.setStyleSheet("""
            font-size: 28px; 
            font-weight: 700; 
            color: #ffffff; 
            margin-bottom: 4px;
            letter-spacing: -0.5px;
        """)
        self.layout.addWidget(title)
        
        subtitle = QLabel("Manage installed plugins and extensions")
        subtitle.setStyleSheet("""
            font-size: 13px;
            color: #888;
            margin-bottom: 20px;
        """)
        self.layout.addWidget(subtitle)
        
        # Plugin Actions
        actions = QHBoxLayout()
        btn_add = QPushButton("Install Plugin")
        btn_add.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                background-color: #0d7377;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0a5c5f;
            }
        """)
        btn_add.clicked.connect(self.app.install_plugin)
        btn_remove = QPushButton("Remove Selected")
        btn_remove.clicked.connect(self.app.remove_selected_plugins)
        btn_reload = QPushButton("Reload Plugins")
        btn_reload.clicked.connect(self.app.reload_plugins_and_notify)
        btn_go_plugins = QPushButton("Manage Plugins")
        btn_go_plugins.clicked.connect(self.go_to_plugins_page)

        actions.addWidget(btn_add)
        actions.addWidget(btn_remove)
        actions.addWidget(btn_reload)
        actions.addWidget(btn_go_plugins)
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

    def remove_selected_plugins(self):
        """Remove selected plugins from the table and filesystem"""
        rows = self.plugins_table.selectionModel().selectedRows()
        if not rows:
            return
        
        removed = 0
        for mi in rows:
            r = mi.row()
            name_item = self.plugins_table.item(r, 1)
            if not name_item:
                continue
            name = name_item.text().strip()
            path = os.path.join(self.app.get_user_plugins_dir(), name + '.py')
            try:
                if os.path.exists(path):
                    os.remove(path)
                    removed += 1
                enabled = set(self.app.settings.get('enabled_plugins') or [])
                enabled.discard(name)
                self.app.settings['enabled_plugins'] = sorted(enabled)
            except Exception:
                pass
        
        self.app.save_settings()
        self.refresh_plugins_table()
        if removed > 0:
            self.app._show_message("Remove Plugins", f"Removed {removed} plugin(s)")

    def go_to_plugins_page(self):
        """Switch to the main plugins page"""
        try:
            self.app.switch_view("plugins")
        except Exception as e:
            print(f"Could not switch to plugins page: {e}")
