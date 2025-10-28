#!/usr/bin/env python3
import sys
import os
import subprocess
import json
from threading import Thread
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLineEdit, QTableWidget, QTableWidgetItem, QTextEdit,
                             QLabel, QFileDialog, QMessageBox, QHeaderView, QFrame, QSplitter)
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QThread
from PyQt6.QtGui import QColor, QFont, QIcon
from PyQt6.QtCore import QSize

# Modern Dark Theme
DARK_STYLESHEET = """
QMainWindow {
    background-color: #1a1a1a;
}

QWidget {
    background-color: #1a1a1a;
    color: #e8e8e8;
}

QLineEdit {
    background-color: #252525;
    color: #e8e8e8;
    border: 2px solid #3a3a3a;
    border-radius: 6px;
    padding: 8px;
    font-size: 11px;
}

QLineEdit:focus {
    border: 2px solid #00d4ff;
}

QPushButton {
    background-color: #2d2d2d;
    color: #e8e8e8;
    border: none;
    border-radius: 10px;
    padding: 12px 24px;
    font-weight: bold;
    font-size: 13px;
    font-family: 'Segoe UI', 'Ubuntu', sans-serif;
}

QPushButton:hover {
    background-color: #3a3a3a;
}

QPushButton:pressed {
    background-color: #4a4a4a;
}

QPushButton#installBtn {
    background-color: #10b981;
    color: #ffffff;
    font-weight: bold;
    font-size: 14px;
}

QPushButton#installBtn:hover {
    background-color: #059669;
}

QPushButton#removeBtn {
    background-color: #ef4444;
    color: #ffffff;
    font-weight: bold;
    font-size: 14px;
}

QPushButton#removeBtn:hover {
    background-color: #dc2626;
}

QPushButton#localBtn {
    background-color: #00d4ff;
    color: #1a1a1a;
    font-weight: bold;
    font-size: 14px;
}

QPushButton#localBtn:hover {
    background-color: #00e6ff;
}

QTableWidget {
    background-color: #252525;
    alternate-background-color: #1f2937;
    gridline-color: #3a3a3a;
    border: none;
}

QTableWidget::item {
    padding: 8px;
    border: none;
}

QTableWidget::item:selected {
    background-color: #00d4ff;
    color: #1a1a1a;
}

QHeaderView::section {
    background-color: #2d2d2d;
    color: #00d4ff;
    padding: 8px;
    border: none;
    font-weight: bold;
}

QTextEdit {
    background-color: #252525;
    color: #e8e8e8;
    border: 2px solid #3a3a3a;
    border-radius: 6px;
    font-family: 'Courier New';
    font-size: 10px;
}

QLabel {
    color: #e8e8e8;
}

QLabel#headerLabel {
    color: #00d4ff;
    font-size: 20px;
    font-weight: bold;
}

QLabel#sectionLabel {
    color: #00d4ff;
    font-size: 12px;
    font-weight: bold;
}

QFrame {
    background-color: #1a1a1a;
    border: none;
}
"""

class CommandWorker(QObject):
    finished = pyqtSignal()
    output = pyqtSignal(str)
    error = pyqtSignal(str)
    
    def __init__(self, command, sudo=False):
        super().__init__()
        self.command = command
        self.sudo = sudo
    
    def run(self):
        try:
            if self.sudo:
                self.command = ["pkexec", "--disable-internal-agent"] + self.command
            
            process = subprocess.Popen(
                self.command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                if line:
                    self.output.emit(line.strip())
            
            _, stderr = process.communicate()
            if stderr and process.returncode != 0:
                self.error.emit(f"Error: {stderr}")
            
            self.finished.emit()
        except Exception as e:
            self.error.emit(f"Error running command: {str(e)}")
            self.finished.emit()

class ArchPkgManagerPyQt(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Arch Linux Package Manager")
        self.setGeometry(100, 100, 1200, 800)
        self.setStyleSheet(DARK_STYLESHEET)
        
        self.updating = False
        self.setup_ui()
        self.center_window()
    
    def center_window(self):
        screen = QApplication.primaryScreen()
        screen_geometry = screen.geometry()
        x = (screen_geometry.width() - self.width()) // 2
        y = (screen_geometry.height() - self.height()) // 2
        self.move(x, y)
    
    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Header
        header = self.create_header()
        main_layout.addWidget(header)
        
        # Content container
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(16, 16, 16, 16)
        content_layout.setSpacing(12)
        
        # Search section (top)
        search_layout = self.create_search_section()
        content_layout.addLayout(search_layout)
        
        # Splitter: [Packages], [Buttons], [Console]
        splitter = QSplitter()
        splitter.setOrientation(Qt.Orientation.Vertical)
        
        # Upper: Packages panel (label + table)
        pkg_panel = QWidget()
        pkg_layout = QVBoxLayout(pkg_panel)
        pkg_layout.setContentsMargins(0, 0, 0, 0)
        pkg_layout.setSpacing(8)
        list_label = QLabel("Available Packages")
        list_label.setObjectName("sectionLabel")
        pkg_layout.addWidget(list_label)
        
        self.package_table = QTableWidget()
        self.package_table.setColumnCount(3)
        self.package_table.setHorizontalHeaderLabels(["Package Name", "Version", "Description"])
        self.package_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.package_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.package_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.package_table.verticalHeader().setDefaultSectionSize(36)
        self.package_table.setAlternatingRowColors(True)
        self.package_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.package_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        pkg_layout.addWidget(self.package_table)
        
        # Middle: Buttons panel
        btn_panel = QWidget()
        btn_layout = QHBoxLayout(btn_panel)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(12)
        buttons_layout = self.create_buttons_section()
        btn_layout.addLayout(buttons_layout)
        btn_panel.setMaximumHeight(84)
        
        # Lower: Console panel (label + text edit)
        console_panel = QWidget()
        console_layout = QVBoxLayout(console_panel)
        console_layout.setContentsMargins(0, 0, 0, 0)
        console_layout.setSpacing(8)
        console_label = QLabel("Console Output")
        console_label.setObjectName("sectionLabel")
        console_layout.addWidget(console_label)
        
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        console_layout.addWidget(self.console)
        
        splitter.addWidget(pkg_panel)
        splitter.addWidget(btn_panel)
        splitter.addWidget(console_panel)
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        splitter.setCollapsible(2, False)
        splitter.setSizes([520, 90, 260])
        
        content_layout.addWidget(splitter)
        main_layout.addWidget(content, 1)
    
    def create_header(self):
        header = QFrame()
        header.setStyleSheet("background-color: #00d4ff;")
        header.setFixedHeight(70)
        
        layout = QVBoxLayout(header)
        layout.setContentsMargins(16, 0, 16, 0)
        
        title = QLabel("📦  Arch Linux Package Manager")
        title.setObjectName("headerLabel")
        title.setStyleSheet("color: #1a1a1a; font-size: 20px; font-weight: bold;")
        layout.addWidget(title, alignment=Qt.AlignmentFlag.AlignCenter)
        
        return header
    
    def create_search_section(self):
        layout = QVBoxLayout()
        layout.setSpacing(10)
        
        label = QLabel("Search Packages")
        label.setObjectName("sectionLabel")
        layout.addWidget(label)
        
        search_layout = QHBoxLayout()
        search_layout.setSpacing(12)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter package name...")
        self.search_input.returnPressed.connect(self.search_packages)
        self.search_input.setMinimumHeight(40)
        search_layout.addWidget(self.search_input)
        
        search_btn = QPushButton("\ud83d\udd0d  Search")
        search_btn.clicked.connect(self.search_packages)
        search_btn.setFixedWidth(140)
        search_btn.setMinimumHeight(40)
        search_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        search_layout.addWidget(search_btn)
        
        refresh_btn = QPushButton("\ud83d\udd04  Refresh")
        refresh_btn.clicked.connect(self.update_package_list)
        refresh_btn.setFixedWidth(140)
        refresh_btn.setMinimumHeight(40)
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        search_layout.addWidget(refresh_btn)
        
        layout.addLayout(search_layout)
        return layout
    
    def create_buttons_section(self):
        layout = QHBoxLayout()
        layout.setSpacing(16)
        
        install_btn = QPushButton("\u2b07\ufe0f  Install Selected")
        install_btn.setObjectName("installBtn")
        install_btn.clicked.connect(self.install_package)
        install_btn.setMinimumHeight(56)
        install_btn.setMinimumWidth(240)
        install_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(install_btn)
        
        remove_btn = QPushButton("\ud83d\uddd1\ufe0f  Remove Selected")
        remove_btn.setObjectName("removeBtn")
        remove_btn.clicked.connect(self.remove_package)
        remove_btn.setMinimumHeight(56)
        remove_btn.setMinimumWidth(240)
        remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(remove_btn)
        
        local_btn = QPushButton("\ud83d\udcbe  Install Local")
        local_btn.setObjectName("localBtn")
        local_btn.clicked.connect(self.install_local_package)
        local_btn.setMinimumHeight(56)
        local_btn.setMinimumWidth(240)
        local_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(local_btn)
        
        layout.addStretch()
        return layout
    
    def log(self, message):
        self.console.append(message)
    
    def search_packages(self):
        query = self.search_input.text().strip()
        if not query:
            return
        
        self.log(f"Searching for: {query}")
        self.package_table.setRowCount(0)
        
        def search_thread():
            try:
                # Search official repos
                try:
                    result = subprocess.run(["pacman", "-Ss", query], 
                                          capture_output=True, text=True, timeout=10)
                    if result.stdout:
                        self.parse_pacman_search(result.stdout)
                except Exception as e:
                    self.log(f"Error searching official repos: {str(e)}")
                
                # Search AUR
                try:
                    import urllib.request
                    import urllib.parse
                    
                    url = f"https://aur.archlinux.org/rpc/?v=5&type=search&arg={urllib.parse.quote(query)}"
                    with urllib.request.urlopen(url, timeout=10) as response:
                        data = json.loads(response.read().decode())
                    
                    if data.get('resultcount', 0) > 0:
                        self.parse_aur_results(data['results'])
                except Exception as e:
                    self.log(f"Error searching AUR: {str(e)}")
            
            except Exception as e:
                self.log(f"Search error: {str(e)}")
        
        Thread(target=search_thread, daemon=True).start()
    
    def parse_pacman_search(self, output):
        current_pkg = {}
        for line in output.split('\n'):
            if line.startswith(('core/', 'extra/', 'community/')):
                if current_pkg:
                    self.add_table_row(current_pkg['name'], current_pkg['version'], 
                                     current_pkg['desc'], 'official')
                
                parts = line.split()
                current_pkg = {
                    'name': parts[0].split('/')[-1],
                    'version': parts[1] if len(parts) > 1 else '',
                    'desc': ' '.join(parts[2:]) if len(parts) > 2 else ''
                }
            elif line.strip() and ':' not in line and current_pkg:
                current_pkg['desc'] = line.strip()
        
        if current_pkg:
            self.add_table_row(current_pkg['name'], current_pkg['version'], 
                             current_pkg['desc'], 'official')
    
    def parse_aur_results(self, packages):
        for pkg in packages:
            name = pkg.get('Name', '')
            version = pkg.get('Version', '')
            desc = pkg.get('Description', '')
            votes = pkg.get('NumVotes', 0)
            
            desc = f"{desc} (Votes: {votes})"
            self.add_table_row(name, version, desc, 'aur')
    
    def add_table_row(self, name, version, desc, pkg_type):
        row = self.package_table.rowCount()
        self.package_table.insertRow(row)
        
        self.package_table.setItem(row, 0, QTableWidgetItem(name))
        self.package_table.setItem(row, 1, QTableWidgetItem(version))
        self.package_table.setItem(row, 2, QTableWidgetItem(desc))
        
        # Store package type in first column
        self.package_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, pkg_type)
    
    def install_package(self):
        current_row = self.package_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "No Selection", "Please select a package to install")
            return
        
        pkg_name = self.package_table.item(current_row, 0).text()
        pkg_type = self.package_table.item(current_row, 0).data(Qt.ItemDataRole.UserRole)
        
        reply = QMessageBox.question(self, "Confirm Install", f"Install {pkg_name}?")
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        self.log(f"Installing {pkg_name}...")
        
        def install():
            try:
                if pkg_type == 'aur':
                    cmd = ["yay", "-S", "--noconfirm", pkg_name]
                else:
                    cmd = ["pacman", "-S", "--noconfirm", pkg_name]
                
                worker = CommandWorker(cmd, sudo=True)
                worker.output.connect(self.log)
                worker.error.connect(self.log)
                worker.run()
                
                self.log(f"Successfully installed {pkg_name}")
            except Exception as e:
                self.log(f"Error: {str(e)}")
        
        Thread(target=install, daemon=True).start()
    
    def remove_package(self):
        current_row = self.package_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "No Selection", "Please select a package to remove")
            return
        
        pkg_name = self.package_table.item(current_row, 0).text()
        
        reply = QMessageBox.question(self, "Confirm Removal", f"Remove {pkg_name}?")
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        self.log(f"Removing {pkg_name}...")
        
        def remove():
            try:
                cmd = ["pacman", "-R", "--noconfirm", pkg_name]
                worker = CommandWorker(cmd, sudo=True)
                worker.output.connect(self.log)
                worker.error.connect(self.log)
                worker.run()
                
                self.log(f"Successfully removed {pkg_name}")
            except Exception as e:
                self.log(f"Error: {str(e)}")
        
        Thread(target=remove, daemon=True).start()
    
    def install_local_package(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Package File",
            "",
            "Arch Packages (*.pkg.tar.gz *.pkg.tar.xz *.tar.gz *.tar.xz);;All Files (*)"
        )
        
        if not file_path:
            return
        
        reply = QMessageBox.question(self, "Confirm Install", 
                                    f"Install {os.path.basename(file_path)}?")
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        self.log(f"Installing local package: {os.path.basename(file_path)}...")
        
        def install():
            try:
                cmd = ["pacman", "-U", "--noconfirm", file_path]
                worker = CommandWorker(cmd, sudo=True)
                worker.output.connect(self.log)
                worker.error.connect(self.log)
                worker.run()
                
                self.log(f"Successfully installed {os.path.basename(file_path)}")
            except Exception as e:
                self.log(f"Error: {str(e)}")
        
        Thread(target=install, daemon=True).start()
    
    def update_package_list(self):
        if self.updating:
            self.log("Update already in progress...")
            return
        
        self.updating = True
        self.log("Updating package lists...")
        
        def update():
            try:
                cmd = ["pacman", "-Syy"]
                worker = CommandWorker(cmd, sudo=True)
                worker.output.connect(self.log)
                worker.error.connect(self.log)
                worker.run()
                
                self.log("Package lists updated successfully")
            except Exception as e:
                self.log(f"Error: {str(e)}")
            finally:
                self.updating = False
        
        Thread(target=update, daemon=True).start()

def main():
    if os.geteuid() == 0:
        print("Do not run this application as root.")
        sys.exit(1)
    
    app = QApplication(sys.argv)
    window = ArchPkgManagerPyQt()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
