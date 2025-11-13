import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
                             QHeaderView, QPushButton, QLabel, QTabWidget, QScrollArea, QFrame, 
                             QMessageBox, QGridLayout, QCheckBox)
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
        
        # Create tab widget for Core Plugins and Community Hub
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid rgba(255, 255, 255, 0.06);
                border-radius: 8px;
                background-color: rgba(255, 255, 255, 0.02);
                margin-top: 8px;
            }
            QTabBar::tab {
                background-color: transparent;
                color: #a0a0a0;
                padding: 12px 24px;
                margin-right: 4px;
                border-radius: 6px 6px 0 0;
                font-weight: 500;
                font-size: 13px;
            }
            QTabBar::tab:selected {
                background-color: rgba(13, 115, 119, 0.15);
                color: #0d7377;
                font-weight: 600;
            }
            QTabBar::tab:hover:!selected {
                background-color: rgba(255, 255, 255, 0.05);
                color: #d0d0d0;
            }
        """)
        
        # Core Plugins Tab
        core_tab = QWidget()
        core_layout = QVBoxLayout(core_tab)
        core_layout.setContentsMargins(16, 16, 16, 16)
        core_layout.setSpacing(12)
        
        # Core plugins actions
        core_actions = QHBoxLayout()
        btn_reload = QPushButton("Reload Plugins")
        btn_reload.setStyleSheet("""
            QPushButton {
                padding: 10px 20px;
                background-color: transparent;
                color: #0d7377;
                border: 1px solid rgba(13, 115, 119, 0.3);
                border-radius: 4px;
                font-weight: 500;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: rgba(13, 115, 119, 0.1);
                border-color: #0d7377;
            }
        """)
        btn_reload.clicked.connect(self.app.reload_plugins_and_notify)
        core_actions.addWidget(btn_reload)
        core_actions.addStretch()
        core_layout.addLayout(core_actions)
        
        # Core Plugins Table
        self.core_plugins_table = QTableWidget()
        self.core_plugins_table.setColumnCount(3)
        self.core_plugins_table.setHorizontalHeaderLabels(["Enabled", "Plugin", "Location"])
        self.core_plugins_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.core_plugins_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.core_plugins_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.core_plugins_table.setStyleSheet("""
            QTableWidget {
                background-color: #2a2a2a;
                border: 1px solid #4a4a4a;
                border-radius: 6px;
                gridline-color: #3a3a3a;
                color: #d0d0d0;
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #3a3a3a;
            }
            QTableWidget::item:selected {
                background-color: rgba(13, 115, 119, 0.2);
            }
            QHeaderView::section {
                background-color: #333;
                color: #fff;
                padding: 8px;
                border: none;
                font-weight: 600;
            }
        """)
        core_layout.addWidget(self.core_plugins_table)
        
        # Community Hub Tab
        community_tab = QWidget()
        community_layout = QVBoxLayout(community_tab)
        community_layout.setContentsMargins(16, 16, 16, 16)
        community_layout.setSpacing(12)
        
        # Community hub actions
        community_actions = QHBoxLayout()
        btn_add = QPushButton("Upload Plugin")
        btn_add.setStyleSheet("""
            QPushButton {
                padding: 10px 20px;
                background-color: #0d7377;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: 500;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #0a5c5f;
            }
        """)
        btn_add.clicked.connect(self.show_upload_plugin_form)
        btn_remove = QPushButton("Remove Selected")
        btn_remove.setStyleSheet("""
            QPushButton {
                padding: 10px 20px;
                background-color: transparent;
                color: #d9534f;
                border: 1px solid rgba(217, 83, 79, 0.3);
                border-radius: 4px;
                font-weight: 500;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: rgba(217, 83, 79, 0.1);
                border-color: #d9534f;
            }
        """)
        btn_remove.clicked.connect(self.app.remove_selected_plugins)
        btn_go_plugins = QPushButton("Browse Community")
        btn_go_plugins.setStyleSheet("""
            QPushButton {
                padding: 10px 20px;
                background-color: transparent;
                color: #0d7377;
                border: 1px solid rgba(13, 115, 119, 0.3);
                border-radius: 4px;
                font-weight: 500;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: rgba(13, 115, 119, 0.1);
                border-color: #0d7377;
            }
        """)
        btn_go_plugins.clicked.connect(self.go_to_plugins_page)
        
        community_actions.addWidget(btn_add)
        community_actions.addWidget(btn_remove)
        community_actions.addWidget(btn_go_plugins)
        community_actions.addStretch()
        community_layout.addLayout(community_actions)
        
        # Community Packages Table (repurpose the existing table)
        self.community_plugins_table = QTableWidget()
        self.community_plugins_table.setColumnCount(3)
        self.community_plugins_table.setHorizontalHeaderLabels(["Select", "Package Name", "Source"])
        self.community_plugins_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.community_plugins_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.community_plugins_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.community_plugins_table.setStyleSheet("""
            QTableWidget {
                background-color: #2a2a2a;
                border: 1px solid #4a4a4a;
                border-radius: 6px;
                gridline-color: #3a3a3a;
                color: #d0d0d0;
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #3a3a3a;
            }
            QTableWidget::item:selected {
                background-color: rgba(13, 115, 119, 0.2);
            }
            QHeaderView::section {
                background-color: #333;
                color: #fff;
                padding: 8px;
                border: none;
                font-weight: 600;
            }
        """)
        
        community_layout.addWidget(self.community_plugins_table)
        
        # Add tabs to tab widget
        self.tabs.addTab(core_tab, "Core Plugins")
        self.tabs.addTab(community_tab, "Community Hub")
        
        self.layout.addWidget(self.tabs)
        
        # Initialize tables
        self.refresh_plugins_table()
        self.core_plugins_table.itemChanged.connect(self.on_plugin_item_changed)
        
        # Initialize community bundles
        self.refresh_community_bundles()

    def refresh_plugins_table(self):
        self._plugins_populating = True
        plugs = self.app.scan_plugins()
        enabled = set(self.app.settings.get('enabled_plugins') or [])
        self.core_plugins_table.setRowCount(0)

        for p in plugs:
            row = self.core_plugins_table.rowCount()
            self.core_plugins_table.insertRow(row)

            enabled_item = QTableWidgetItem()
            enabled_item.setFlags(enabled_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            enabled_item.setCheckState(Qt.CheckState.Checked if p['name'] in enabled else Qt.CheckState.Unchecked)
            name_item = QTableWidgetItem(p['name'])
            loc_item = QTableWidgetItem(p.get('location', 'Core'))

            self.core_plugins_table.setItem(row, 0, enabled_item)
            self.core_plugins_table.setItem(row, 1, name_item)
            self.core_plugins_table.setItem(row, 2, loc_item)

        self._plugins_populating = False

    def on_plugin_item_changed(self, item):
        if getattr(self, '_plugins_populating', False):
            return
        if item.column() != 0:
            return

        row = item.row()
        name_item = self.core_plugins_table.item(row, 1)
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

    def refresh_community_bundles(self):
        """Refresh the community packages display"""
        try:
            from services.bundle_service import list_community_bundles
            from PyQt6.QtWidgets import QCheckBox
            
            # Clear existing packages
            self.community_plugins_table.setRowCount(0)
            
            # Load community bundles and extract all packages
            bundles = list_community_bundles()
            all_packages = []
            
            # Extract all packages from all bundles
            for bundle_data in bundles:
                items = bundle_data.get('items', [])
                for item in items:
                    if isinstance(item, dict) and item.get('name') and item.get('source'):
                        all_packages.append(item)
            
            if not all_packages:
                # Add a single row with message
                self.community_plugins_table.setRowCount(1)
                message_item = QTableWidgetItem("No community packages found. Share bundles from the Bundle page to see them here!")
                message_item.setFlags(message_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.community_plugins_table.setItem(0, 1, message_item)
                self.community_plugins_table.setSpan(0, 1, 1, 2)  # Span across remaining columns
                return
            
            # Remove duplicates while preserving order
            seen = set()
            unique_packages = []
            for pkg in all_packages:
                key = (pkg.get('name'), pkg.get('source'))
                if key not in seen:
                    seen.add(key)
                    unique_packages.append(pkg)
            
            # Populate table with packages
            self.community_plugins_table.setRowCount(len(unique_packages))
            
            for row, package in enumerate(unique_packages):
                # Checkbox column
                checkbox = QCheckBox()
                checkbox.setObjectName("packageCheckbox")
                cb_container = QWidget()
                cb_container.setStyleSheet("background: transparent;")
                cb_layout = QHBoxLayout(cb_container)
                cb_layout.setContentsMargins(0, 0, 0, 0)
                cb_layout.addStretch()
                cb_layout.addWidget(checkbox)
                cb_layout.addStretch()
                self.community_plugins_table.setCellWidget(row, 0, cb_container)
                
                # Package name
                name_item = QTableWidgetItem(package.get('name', 'Unknown Package'))
                name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.community_plugins_table.setItem(row, 1, name_item)
                
                # Source
                source_item = QTableWidgetItem(package.get('source', 'Unknown'))
                source_item.setFlags(source_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.community_plugins_table.setItem(row, 2, source_item)
                
        except Exception as e:
            # Show error in table
            self.community_plugins_table.setRowCount(1)
            error_item = QTableWidgetItem(f"Error loading community packages: {str(e)}")
            error_item.setFlags(error_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.community_plugins_table.setItem(0, 1, error_item)
            self.community_plugins_table.setSpan(0, 1, 1, 2)


