import os
import subprocess
from threading import Thread
from PyQt6.QtCore import QTimer
from workers import CommandWorker


def update_packages(app, packages_by_source: dict):
    def update():
        try:
            for source, pkgs in packages_by_source.items():
                if source == 'pacman':
                    cmd = ["pacman", "-S", "--noconfirm"] + pkgs
                    worker = CommandWorker(cmd, sudo=True)
                    worker.output.connect(app.log)
                    worker.error.connect(app.log)
                    worker.run()
                elif source == 'AUR':
                    env, _ = app.prepare_askpass_env()
                    cmd = ["yay", "-S", "--noconfirm"] + pkgs
                    worker = CommandWorker(cmd, sudo=False, env=env)
                    worker.output.connect(app.log)
                    worker.error.connect(app.log)
                    worker.run()
                elif source == 'Flatpak':
                    cmd = ["flatpak", "update", "-y", "--noninteractive"] + pkgs
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
                    cmd = ["npm", "update", "-g"] + pkgs
                    worker = CommandWorker(cmd, sudo=False, env=env)
                    worker.output.connect(app.log)
                    worker.error.connect(app.log)
                    worker.run()
                elif source == 'Local':
                    entries = { (e.get('id') or e.get('name')): e for e in app.load_local_update_entries() }
                    for token in pkgs:
                        e = entries.get(token) or entries.get(token.strip())
                        if not e:
                            continue
                        upd = e.get('update_cmd')
                        if not upd:
                            continue
                        try:
                            process = subprocess.Popen(["bash", "-lc", upd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                            while True:
                                line = process.stdout.readline() if process.stdout else ""
                                if not line and process.poll() is not None:
                                    break
                                if line:
                                    app.log(line.strip())
                            _, stderr = process.communicate()
                            if process.returncode != 0 and stderr:
                                app.log(f"Error: {stderr}")
                        except Exception as ex:
                            app.log(str(ex))
            app.show_message.emit("Update Complete", f"Successfully updated {sum(len(v) for v in packages_by_source.values())} package(s).")
            QTimer.singleShot(0, app.refresh_packages)
        except Exception as e:
            app.log(f"Error in update thread: {str(e)}")
    Thread(target=update, daemon=True).start()
