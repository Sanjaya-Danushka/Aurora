import os
import subprocess
from threading import Thread
from PyQt6.QtCore import QTimer
from workers import CommandWorker


def uninstall_packages(app, packages_by_source: dict):
    def uninstall():
        app.log("Uninstallation thread started")
        try:
            for source, pkgs in packages_by_source.items():
                if not pkgs:
                    continue
                if source in ('pacman', 'AUR'):
                    cmd = ["pacman", "-R", "--noconfirm"] + pkgs
                    app.log(f"Running: {' '.join(cmd)}")
                    worker = CommandWorker(cmd, sudo=True)
                    worker.output.connect(app.log)
                    worker.error.connect(app.log)
                    worker.run()
                elif source == 'Flatpak':
                    cmd = ["flatpak", "uninstall", "-y", "--noninteractive"] + pkgs
                    app.log(f"Running: {' '.join(cmd)}")
                    worker = CommandWorker(cmd, sudo=False)
                    worker.output.connect(app.log)
                    worker.error.connect(app.log)
                    worker.run()
                elif source == 'npm':
                    env = os.environ.copy()
                    try:
                        npm_prefix = os.path.join(os.path.expanduser('~'), '.npm-global')
                        os.makedirs(npm_prefix, exist_ok=True)
                        env['npm_config_prefix'] = npm_prefix
                        env['NPM_CONFIG_PREFIX'] = npm_prefix
                        env['PATH'] = os.path.join(npm_prefix, 'bin') + os.pathsep + env.get('PATH', '')
                    except Exception:
                        pass
                    cmd = ["npm", "uninstall", "-g"] + pkgs
                    app.log(f"Running: {' '.join(cmd)}")
                    worker = CommandWorker(cmd, sudo=False, env=env)
                    worker.output.connect(app.log)
                    worker.error.connect(app.log)
                    worker.run()
            app.show_message.emit("Uninstallation Complete", f"Successfully processed {sum(len(v) for v in packages_by_source.values())} package(s).")
            QTimer.singleShot(0, app.load_installed_packages)
        except Exception as e:
            app.log(f"Error in uninstallation thread: {str(e)}")
    Thread(target=uninstall, daemon=True).start()
