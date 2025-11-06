import subprocess
from PyQt6.QtCore import QTimer
from threading import Thread
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit, QTableWidget, QHeaderView,
    QWidget, QHBoxLayout, QCheckBox, QPushButton, QTableWidgetItem
)


def ignore_selected(app):
    items = []
    for row in range(app.package_table.rowCount()):
        checkbox = app.get_row_checkbox(row)
        if checkbox is not None and checkbox.isChecked():
            name_item = app.package_table.item(row, 1)
            if name_item:
                items.append(name_item.text().strip())
    if not items:
        app.log("No packages selected to ignore")
        return
    ignored = app.load_ignored_updates()
    for n in items:
        ignored.add(n)
    app.save_ignored_updates(ignored)
    app.log(f"Ignored {len(items)} package(s)")
    if app.current_view == "updates":
        app.load_updates()


def manage_ignored(app):
    ignored = sorted(app.load_ignored_updates())
    dlg = QDialog(app)
    dlg.setWindowTitle("Manage Ignored Updates")
    v = QVBoxLayout()
    hdr = QLabel(f"Ignored packages: {len(ignored)}")
    v.addWidget(hdr)
    search = QLineEdit()
    search.setPlaceholderText("Filter packages...")
    v.addWidget(search)
    tbl = QTableWidget()
    tbl.setColumnCount(5)
    tbl.setHorizontalHeaderLabels(["", "Package", "Source", "Installed", "Available"])
    tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
    tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
    tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
    tbl.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
    tbl.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
    tbl.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
    v.addWidget(tbl)
    row = QWidget()
    h = QHBoxLayout(row)
    btn_unignore = QPushButton("Unignore Selected")
    btn_unall = QPushButton("Unignore All")
    btn_close = QPushButton("Close")
    h.addWidget(btn_unignore)
    h.addWidget(btn_unall)
    h.addStretch()
    h.addWidget(btn_close)
    v.addWidget(row)

    tbl.setRowCount(len(ignored))
    for i, name in enumerate(ignored):
        cb = QCheckBox()
        cb.setObjectName("tableCheckbox")
        w = QWidget()
        l = QHBoxLayout(w)
        l.setContentsMargins(0,0,0,0)
        l.addWidget(cb)
        l.addStretch()
        tbl.setCellWidget(i, 0, w)
        tbl.setItem(i, 1, QTableWidgetItem(name))
        tbl.setItem(i, 2, QTableWidgetItem(""))
        tbl.setItem(i, 3, QTableWidgetItem(""))
        tbl.setItem(i, 4, QTableWidgetItem(""))

    def finalize(installed, aur_set, new_versions):
        for i, name in enumerate(ignored):
            src = "AUR" if name in aur_set else "pacman"
            tbl.setItem(i, 2, QTableWidgetItem(src))
            tbl.setItem(i, 3, QTableWidgetItem(installed.get(name, "")))
            tbl.setItem(i, 4, QTableWidgetItem(new_versions.get(name, "")))

    def load_data():
        installed = {}
        try:
            r = subprocess.run(["pacman", "-Q"], capture_output=True, text=True, timeout=20)
            if r.returncode == 0 and r.stdout:
                for ln in r.stdout.strip().split('\n'):
                    ps = ln.split()
                    if len(ps) >= 2:
                        installed[ps[0]] = ps[1]
        except Exception:
            pass
        aur_set = set()
        try:
            r = subprocess.run(["pacman", "-Qm"], capture_output=True, text=True, timeout=10)
            if r.returncode == 0 and r.stdout:
                for ln in r.stdout.strip().split('\n'):
                    ps = ln.split()
                    if ps:
                        aur_set.add(ps[0])
        except Exception:
            pass
        new_versions = {}
        try:
            r = subprocess.run(["pacman", "-Qu"], capture_output=True, text=True, timeout=20)
            if r.returncode == 0 and r.stdout:
                for ln in r.stdout.strip().split('\n'):
                    if ' -> ' in ln:
                        left, nv = ln.split(' -> ', 1)
                        nm = left.split()[0]
                        new_versions[nm] = nv.strip()
        except Exception:
            pass
        try:
            r = subprocess.run(["yay", "-Qua"], capture_output=True, text=True, timeout=20)
            if r.returncode == 0 and r.stdout:
                for ln in r.stdout.strip().split('\n'):
                    if ' -> ' in ln:
                        left, nv = ln.split(' -> ', 1)
                        nm = left.split()[0]
                        new_versions[nm] = nv.strip()
        except Exception:
            pass
        QTimer.singleShot(0, lambda: finalize(installed, aur_set, new_versions))

    Thread(target=load_data, daemon=True).start()

    def apply_filter(text):
        t = text.strip().lower()
        for r in range(tbl.rowCount()):
            nm = tbl.item(r,1).text().lower() if tbl.item(r,1) else ""
            tbl.setRowHidden(r, t not in nm)
    search.textChanged.connect(apply_filter)

    def unignore_selected():
        sel = []
        for r in range(tbl.rowCount()):
            w = tbl.cellWidget(r, 0)
            if not w:
                continue
            chks = w.findChildren(QCheckBox)
            if chks and chks[0].isChecked():
                nm = tbl.item(r,1).text()
                sel.append(nm)
        if sel:
            s = app.load_ignored_updates()
            for nm in sel:
                s.discard(nm)
            app.save_ignored_updates(s)
            for r in reversed(range(tbl.rowCount())):
                w = tbl.cellWidget(r,0)
                if not w:
                    continue
                chks = w.findChildren(QCheckBox)
                if chks and chks[0].isChecked():
                    tbl.removeRow(r)
            QTimer.singleShot(0, app.refresh_packages)
    btn_unignore.clicked.connect(unignore_selected)

    def unignore_all():
        app.save_ignored_updates(set())
        tbl.setRowCount(0)
        QTimer.singleShot(0, app.refresh_packages)
    btn_unall.clicked.connect(unignore_all)

    btn_close.clicked.connect(dlg.accept)
    dlg.setLayout(v)
    dlg.resize(820, 520)
    dlg.exec()
