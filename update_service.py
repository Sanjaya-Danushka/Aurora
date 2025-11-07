import os
import json
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
                    # Determine where each package is installed and update in that scope
                    env_user = os.environ.copy()
                    try:
                        npm_prefix = os.path.join(os.path.expanduser('~'), '.npm-global')
                        os.makedirs(npm_prefix, exist_ok=True)
                        env_user['npm_config_prefix'] = npm_prefix
                        env_user['NPM_CONFIG_PREFIX'] = npm_prefix
                        env_user['PATH'] = os.path.join(npm_prefix, 'bin') + os.pathsep + env_user.get('PATH', '')
                    except Exception:
                        pass
                    env_sys = os.environ.copy()

                    user_pkgs, sys_pkgs, unknown_pkgs = [], [], []
                    for name in pkgs:
                        placed = False
                        try:
                            r_user = subprocess.run(["npm", "ls", "-g", name, "--depth=0", "--json"], capture_output=True, text=True, env=env_user, timeout=30)
                            if r_user.returncode in (0, 1) and r_user.stdout:
                                try:
                                    data = json.loads(r_user.stdout)
                                    deps = (data.get('dependencies') or {}) if isinstance(data, dict) else {}
                                    if name in deps:
                                        user_pkgs.append(name)
                                        placed = True
                                except Exception:
                                    pass
                        except Exception:
                            pass
                        if placed:
                            continue
                        try:
                            r_sys = subprocess.run(["npm", "ls", "-g", name, "--depth=0", "--json"], capture_output=True, text=True, timeout=30)
                            if r_sys.returncode in (0, 1) and r_sys.stdout:
                                try:
                                    data = json.loads(r_sys.stdout)
                                    deps = (data.get('dependencies') or {}) if isinstance(data, dict) else {}
                                    if name in deps:
                                        sys_pkgs.append(name)
                                        placed = True
                                except Exception:
                                    pass
                        except Exception:
                            pass
                        if not placed:
                            # Default to user scope if location unknown
                            user_pkgs.append(name)

                    if user_pkgs:
                        cmd_u = ["npm", "update", "-g"] + user_pkgs
                        w_u = CommandWorker(cmd_u, sudo=False, env=env_user)
                        w_u.output.connect(app.log)
                        w_u.error.connect(app.log)
                        w_u.run()
                    if sys_pkgs:
                        cmd_s = ["npm", "update", "-g"] + sys_pkgs
                        # Use pkexec (sudo=True) for system-global updates
                        w_s = CommandWorker(cmd_s, sudo=True, env=env_sys)
                        w_s.output.connect(app.log)
                        w_s.error.connect(app.log)
                        w_s.run()
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
            try:
                app.ui_call.emit(app.refresh_packages)
            except Exception:
                pass
        except Exception as e:
            app.log(f"Error in update thread: {str(e)}")
    Thread(target=update, daemon=True).start()


def update_core_tools(app):
    app.loading_widget.setVisible(True)
    app.loading_widget.set_message("Updating tools...")
    app.loading_widget.start_animation()

    def do_update():
        try:
            deps = ["flatpak", "git", "nodejs", "npm", "docker"]
            if app.cmd_exists("pacman"):
                w1 = CommandWorker(["pacman", "-Syu", "--noconfirm"] + deps, sudo=True)
                w1.output.connect(app.log)
                w1.error.connect(app.log)
                w1.run()
            try:
                app.ensure_flathub_user_remote()
            except Exception:
                pass
            try:
                update_ids = set()
                for scope in ([], ["--user"], ["--system"]):
                    cmdu = ["flatpak"] + scope + ["list", "--app", "--updates", "--columns=application,version"]
                    fu = subprocess.run(cmdu, capture_output=True, text=True, timeout=60)
                    if fu.returncode == 0 and fu.stdout:
                        for ln in [x for x in fu.stdout.strip().split('\n') if x.strip()]:
                            cols = ln.split('\t')
                            if cols:
                                update_ids.add(cols[0].strip())
                if update_ids:
                    for pkg in packages:
                        if pkg.get('source') == 'Flatpak' and pkg.get('name') in update_ids:
                            pkg['has_update'] = True
            except Exception:
                pass
            if app.cmd_exists("flatpak"):
                w2 = CommandWorker(["flatpak", "--user", "update", "-y"], sudo=False)
                w2.output.connect(app.log)
                w2.error.connect(app.log)
                w2.run()
            if app.cmd_exists("npm"):
                env = os.environ.copy()
                try:
                    npm_prefix = os.path.join(os.path.expanduser('~'), '.npm-global')
                    os.makedirs(npm_prefix, exist_ok=True)
                    env['npm_config_prefix'] = npm_prefix
                    env['NPM_CONFIG_PREFIX'] = npm_prefix
                    env['PATH'] = os.path.join(npm_prefix, 'bin') + os.pathsep + env.get('PATH', '')
                except Exception:
                    pass
                w3 = CommandWorker(["npm", "update", "-g"], sudo=False, env=env)
                w3.output.connect(app.log)
                w3.error.connect(app.log)
                w3.run()
            if app.cmd_exists("yay"):
                env, _ = app.prepare_askpass_env()
                w4 = CommandWorker(["yay", "-Syu", "--noconfirm", "--sudoflags", "-A"], sudo=False, env=env)
                w4.output.connect(app.log)
                w4.error.connect(app.log)
                w4.run()
            app.show_message.emit("Environment", "Tools updated")
        except Exception as e:
            app.show_message.emit("Environment", f"Update failed: {str(e)}")
        finally:
            try:
                app.ui_call.emit(lambda: app.loading_widget.stop_animation())
                app.ui_call.emit(lambda: app.loading_widget.setVisible(False))
            except Exception:
                pass

    Thread(target=do_update, daemon=True).start()
