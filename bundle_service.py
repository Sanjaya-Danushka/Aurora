import os
import json
import subprocess
from threading import Thread
from workers import CommandWorker
from PyQt6.QtWidgets import QFileDialog, QTableWidgetItem, QLabel


def add_selected_to_bundle(app):
    items = []
    for row in range(app.package_table.rowCount()):
        checkbox = app.get_row_checkbox(row)
        if checkbox is not None and checkbox.isChecked():
            info = app.get_row_info(row)
            if info.get("name") and info.get("source"):
                items.append(info)
    if not items:
        app.log("No selected rows to add to bundle")
        return
    existing = {(i.get('source'), i.get('id') or i.get('name')) for i in app.bundle_items}
    added = 0
    for it in items:
        key = (it.get('source'), it.get('id') or it.get('name'))
        if key not in existing:
            app.bundle_items.append(it)
            existing.add(key)
            added += 1
    app.log(f"Added {added} item(s) to bundle")
    if app.current_view == "bundles":
        refresh_bundles_table(app)


def refresh_bundles_table(app):
    if app.current_view != "bundles":
        return
    app.package_table.setRowCount(0)
    app.package_table.setUpdatesEnabled(False)
    for it in app.bundle_items:
        pkg = {
            'name': it.get('name', ''),
            'id': it.get('id') or it.get('name', ''),
            'version': it.get('version', ''),
            'source': it.get('source', ''),
        }
        app.add_discover_row(pkg)
    app.package_table.setUpdatesEnabled(True)
    try:
        app.package_table.clearSelection()
    except Exception:
        pass
    app.load_more_btn.setVisible(False)
    try:
        app.package_table.setVisible(True)
    except Exception:
        pass


def export_bundle(app):
    if not app.bundle_items:
        app._show_message("Export Bundle", "Bundle is empty")
        return
    path, _ = QFileDialog.getSaveFileName(app, "Export Bundle", os.path.expanduser("~"), "Bundle JSON (*.json)")
    if not path:
        return
    data = {"app": "NeoArch", "items": app.bundle_items}
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        app._show_message("Export Bundle", f"Saved {len(app.bundle_items)} items to {path}")
    except Exception as e:
        app._show_message("Export Bundle", f"Failed: {e}")


def import_bundle(app):
    path, _ = QFileDialog.getOpenFileName(app, "Import Bundle", os.path.expanduser("~"), "Bundle JSON (*.json)")
    if not path:
        return
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        items = data.get('items') if isinstance(data, dict) else None
        if not isinstance(items, list):
            app._show_message("Import Bundle", "Invalid bundle file")
            return
        existing = {(i.get('source'), i.get('id') or i.get('name')) for i in app.bundle_items}
        added = 0
        for it in items:
            if not isinstance(it, dict):
                continue
            src = (it.get('source') or '').strip()
            nm = (it.get('name') or '').strip()
            pkg_id = (it.get('id') or nm).strip()
            if not src or not nm:
                continue
            key = (src, pkg_id or nm)
            if key not in existing:
                app.bundle_items.append({
                    'name': nm,
                    'id': pkg_id or nm,
                    'version': (it.get('version') or '').strip(),
                    'source': src,
                })
                existing.add(key)
                added += 1
        app._show_message("Import Bundle", f"Added {added} items")
        if app.current_view == "bundles":
            refresh_bundles_table(app)
    except Exception as e:
        app._show_message("Import Bundle", f"Failed: {e}")


def remove_selected_from_bundle(app):
    if app.current_view != "bundles":
        return
    keys_to_remove = []
    for row in range(app.package_table.rowCount()):
        chk = app.get_row_checkbox(row)
        if chk is not None and chk.isChecked():
            info = app.get_row_info(row, view_id='bundles')
            keys_to_remove.append((info.get('source'), info.get('id') or info.get('name')))
    if not keys_to_remove:
        app.log("No selected items to remove from bundle")
        return
    before = len(app.bundle_items)
    app.bundle_items = [it for it in app.bundle_items if (it.get('source'), it.get('id') or it.get('name')) not in keys_to_remove]
    removed = before - len(app.bundle_items)
    app.log(f"Removed {removed} items from bundle")
    refresh_bundles_table(app)


def clear_bundle(app):
    if not app.bundle_items:
        return
    app.bundle_items = []
    refresh_bundles_table(app)


def install_bundle(app):
    if not app.bundle_items:
        app._show_message("Install Bundle", "Bundle is empty")
        return
    items = list(app.bundle_items)

    def run():
        try:
            by_src = {}
            for it in items:
                src = it.get('source') or 'pacman'
                name = it.get('name') or ''
                pkg_id = it.get('id') or name
                if not name:
                    continue
                by_src.setdefault(src, []).append(pkg_id if src == 'Flatpak' else name)
            for src, lst in by_src.items():
                if not lst:
                    continue
                if src == 'pacman':
                    cmd = ["pacman", "-S", "--noconfirm"] + lst
                    w = CommandWorker(cmd, sudo=True)
                    w.output.connect(app.log); w.error.connect(app.log); w.run()
                elif src == 'AUR':
                    env, _ = app.prepare_askpass_env()
                    cmd = ["yay", "-S", "--noconfirm", "--sudoflags", "-A"] + lst
                    w = CommandWorker(cmd, sudo=False, env=env)
                    w.output.connect(app.log); w.error.connect(app.log); w.run()
                elif src == 'Flatpak':
                    cmd = ["flatpak", "install", "-y", "--noninteractive"] + lst
                    w = CommandWorker(cmd, sudo=False)
                    w.output.connect(app.log); w.error.connect(app.log); w.run()
                elif src == 'npm':
                    env = os.environ.copy()
                    try:
                        npm_prefix = os.path.join(os.path.expanduser('~'), '.npm-global')
                        os.makedirs(npm_prefix, exist_ok=True)
                        env['npm_config_prefix'] = npm_prefix
                        env['NPM_CONFIG_PREFIX'] = npm_prefix
                        env['PATH'] = os.path.join(npm_prefix, 'bin') + os.pathsep + env.get('PATH', '')
                    except Exception:
                        pass
                    cmd = ["npm", "install", "-g"] + lst
                    w = CommandWorker(cmd, sudo=False, env=env)
                    w.output.connect(app.log); w.error.connect(app.log); w.run()
            app.show_message.emit("Install Bundle", f"Installed {sum(len(v) for v in by_src.values())} package(s)")
        except Exception as e:
            app.log(f"Bundle install error: {str(e)}")
    Thread(target=run, daemon=True).start()
