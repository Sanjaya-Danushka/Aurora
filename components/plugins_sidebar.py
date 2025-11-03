from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QRadioButton, QButtonGroup, QListWidget, QPushButton
from PyQt6.QtCore import pyqtSignal


class PluginsSidebar(QWidget):
    filter_changed = pyqtSignal(str, bool)  # search_text, installed_only
    install_requested = pyqtSignal(str)     # plugin_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self.plugins = []
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
        
        self.list = QListWidget()
        self.list.currentTextChanged.connect(self._on_select)
        layout.addWidget(self.list)
        
        self.install_btn = QPushButton("Install Selected")
        self.install_btn.clicked.connect(self._install_selected)
        layout.addWidget(self.install_btn)
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
