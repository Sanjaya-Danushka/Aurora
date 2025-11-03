from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QRadioButton, QButtonGroup, QListWidget, QPushButton
from PyQt6.QtCore import pyqtSignal


class PluginsSidebar(QWidget):
    filter_changed = pyqtSignal(str, bool)  # search_text, installed_only
    install_requested = pyqtSignal(str)     # plugin_id
    uninstall_requested = pyqtSignal(str)   # plugin_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self.plugins = []
        self._category_buttons = []
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        title = QLabel("Extensions")
        title.setObjectName("sectionLabel")
        layout.addWidget(title)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search extensions")
        self.search.textChanged.connect(self._emit)
        layout.addWidget(self.search)

        self.group = QButtonGroup(self)
        self.rb_all = QRadioButton("All")
        self.rb_installed = QRadioButton("Installed")
        self.group.addButton(self.rb_all, 0)
        self.group.addButton(self.rb_installed, 1)
        self.rb_all.setChecked(True)
        self.group.buttonClicked.connect(lambda _: self._emit())

        row = QHBoxLayout()
        row.addWidget(self.rb_all)
        row.addWidget(self.rb_installed)
        row.addStretch()
        layout.addLayout(row)
        
        # Category chips row
        self.cat_row = QHBoxLayout()
        self.cat_row.setSpacing(6)
        layout.addLayout(self.cat_row)

        self.list = QListWidget()
        self.list.currentTextChanged.connect(self._on_select)
        layout.addWidget(self.list)
        
        self.install_btn = QPushButton("Install Selected")
        self.install_btn.clicked.connect(self._install_selected)
        layout.addWidget(self.install_btn)
        self.uninstall_btn = QPushButton("Uninstall Selected")
        self.uninstall_btn.clicked.connect(self._uninstall_selected)
        layout.addWidget(self.uninstall_btn)
        layout.addStretch()

    def set_plugins(self, plugins):
        self.plugins = plugins or []
        try:
            self.list.blockSignals(True)
            self.list.clear()
            for p in self.plugins:
                name = p.get('name') or p.get('id')
                self.list.addItem(name)
        finally:
            self.list.blockSignals(False)
    
    def set_categories(self, categories):
        # Clear existing buttons
        for i in reversed(range(self.cat_row.count())):
            item = self.cat_row.takeAt(i)
            if item and item.widget():
                item.widget().deleteLater()
        self._category_buttons = []
        if not categories:
            return
        for cat in categories:
            btn = QPushButton(cat)
            btn.setCheckable(True)
            btn.setObjectName("chip")
            btn.toggled.connect(lambda _v, self=self: self._emit())
            self.cat_row.addWidget(btn)
            self._category_buttons.append(btn)
        self.cat_row.addStretch()
    
    def get_selected_categories(self):
        selected = []
        for btn in self._category_buttons:
            if btn.isChecked():
                selected.append(btn.text())
        return selected

    def _emit(self):
        text = self.search.text().strip()
        installed_only = self.group.checkedId() == 1
        self.filter_changed.emit(text, installed_only)
    
    def _on_select(self, text):
        # Selecting an item narrows the filter to that name
        self.filter_changed.emit(text or "", self.group.checkedId() == 1)
    
    def _install_selected(self):
        item = self.list.currentItem()
        if not item:
            return
        name = item.text()
        # Map back to id
        pid = None
        for p in self.plugins:
            n = p.get('name') or p.get('id')
            if n == name:
                pid = p.get('id')
                break
        if pid:
            self.install_requested.emit(pid)
    
    def _uninstall_selected(self):
        item = self.list.currentItem()
        if not item:
            return
        name = item.text()
        pid = None
        for p in self.plugins:
            n = p.get('name') or p.get('id')
            if n == name:
                pid = p.get('id')
                break
        if pid:
            self.uninstall_requested.emit(pid)
