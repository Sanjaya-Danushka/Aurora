import os
import re
import subprocess
import time
from threading import Thread, Event
from workers import CommandWorker


def install_packages(app, packages_by_source: dict):
    def install():
        app.install_cancel_event = Event()
        app.installation_progress.emit("start", True)
        app.log_signal.emit("Installation thread started")

        success = True
        current_download_info = ""

        total_packages = sum(len(pkgs) for pkgs in packages_by_source.values())
        total_sources = len(packages_by_source)
        completed_packages = 0
        completed_sources = 0
        force_sudo = bool(getattr(app, 'force_sudo_install', False))

        def update_progress_message(msg: str = ""):
            base_msg = f"Installing: {completed_packages}/{total_packages} packages"
            try:
                if current_download_info and msg:
                    app.ui_call.emit(lambda: app.loading_widget.set_message(f"{base_msg}\n{current_download_info}"))
                elif current_download_info:
                    app.ui_call.emit(lambda: app.loading_widget.set_message(f"{base_msg}\n{current_download_info}"))
                elif msg:
                    app.ui_call.emit(lambda: app.loading_widget.set_message(f"{base_msg}\n{msg}"))
                else:
                    app.ui_call.emit(lambda: app.loading_widget.set_message(base_msg))
            except Exception:
                pass

        def parse_output_line(line: str):
            nonlocal current_download_info
            if "downloading" in line.lower() and ("mib" in line.lower() or "kib" in line.lower() or "gib" in line.lower()):
                size_match = re.search(r'\(([-\d.]+)\s*(MiB|KiB|GiB|B)\)', line)
                if size_match:
                    size, unit = size_match.groups()
                    current_download_info = f"Downloading {size} {unit}"
                    update_progress_message("")
            elif re.search(r'\[.*\]\s*\d+%', line):
                progress_match = re.search(r'(\d+)%', line)
                if progress_match:
                    percentage = progress_match.group(1)
                    if current_download_info:
                        current_download_info = f"{current_download_info} - {percentage}%"
                    else:
                        current_download_info = f"Downloading... {percentage}%"
                    update_progress_message("")
            elif "installed" in line.lower() or "upgraded" in line.lower():
                current_download_info = ""
                update_progress_message("")

        try:
            for source, packages in packages_by_source.items():
                if app.install_cancel_event.is_set():
                    app.log_signal.emit("Installation cancelled by user")
                    app.installation_progress.emit("cancelled", False)
                    return

                update_progress_message(f"Installing from {source}...")

                # Prepare default environment (can be overridden per-source)
                env = os.environ.copy()

                if source == 'pacman':
                    cmd = ["pacman", "-S", "--noconfirm"] + packages
                elif source == 'AUR':
                    cmd = [
                        "yay",
                        "-S", "--noconfirm",
                        "--sudoflags", "-A",
                        "--answerclean", "None",
                        "--answerdiff", "None",
                        "--answeredit", "None"
                    ] + packages
                elif source == 'Flatpak':
                    try:
                        app.ensure_flathub_user_remote()
                    except Exception:
                        pass
                    # In sudo mode install system-wide; otherwise user-scoped
                    if force_sudo:
                        cmd = ["flatpak", "install", "-y", "flathub"] + packages
                    else:
                        cmd = ["flatpak", "--user", "install", "-y", "flathub"] + packages
                elif source == 'npm':
                    if not force_sudo:
                        try:
                            npm_prefix = os.path.join(os.path.expanduser('~'), '.npm-global')
                            os.makedirs(npm_prefix, exist_ok=True)
                            env['npm_config_prefix'] = npm_prefix
                            env['NPM_CONFIG_PREFIX'] = npm_prefix
                            env['PREFIX'] = npm_prefix
                            env['PATH'] = os.path.join(npm_prefix, 'bin') + os.pathsep + env.get('PATH', '')
                        except Exception:
                            pass
                    cmd = ["npm", "install", "-g"] + packages
                else:
                    app.log_signal.emit(f"Unknown source {source} for packages {packages}")
                    continue

                app.log_signal.emit(f"Running command for {source}: {' '.join(cmd)}")

                if app.install_cancel_event.is_set():
                    app.log_signal.emit("Installation cancelled by user")
                    app.installation_progress.emit("cancelled", False)
                    return

                cleanup_path = None
                if source == 'AUR':
                    env, cleanup_path = app.prepare_askpass_env()
                    try:
                        title = "NeoArch - Confirm AUR Install"
                        if len(packages) <= 3:
                            pkg_list = ", ".join(packages)
                        else:
                            pkg_list = ", ".join(packages[:3]) + f" and {len(packages)-3} more"
                        text = (
                            "AUR packages are community-maintained and may be unsafe.\n"
                            f"Packages: {pkg_list}\n\n"
                            "Enter your password to proceed."
                        )
                        env["NEOARCH_ASKPASS_TITLE"] = title
                        env["NEOARCH_ASKPASS_TEXT"] = text
                        env["NEOARCH_ASKPASS_ICON"] = "dialog-password"
                    except Exception:
                        pass
                worker = CommandWorker(cmd, sudo=(source == 'pacman'), env=env)
                worker.output.connect(lambda msg: app.log_signal.emit(msg))
                worker.error.connect(lambda msg: app.log_signal.emit(msg))
                worker.output.connect(parse_output_line)

                try:
                    exec_cmd = worker.command
                    if source == 'pacman' or (force_sudo and source in ('Flatpak', 'npm')):
                        exec_cmd = ["pkexec", "--disable-internal-agent"] + exec_cmd
                    process = subprocess.Popen(
                        exec_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        stdin=subprocess.DEVNULL,
                        text=True,
                        bufsize=1,
                        preexec_fn=os.setsid,
                        env=worker.env
                    )

                    while True:
                        if app.install_cancel_event.is_set():
                            process.terminate()
                            try:
                                process.wait(timeout=5)
                            except subprocess.TimeoutExpired:
                                process.kill()
                            app.log_signal.emit("Installation cancelled by user")
                            app.installation_progress.emit("cancelled", False)
                            return

                        if process.poll() is not None:
                            break

                        if process.stdout:
                            line = process.stdout.readline()
                            if line:
                                line = line.strip()
                                parse_output_line(line)
                                worker.output.emit(line)

                        time.sleep(0.1)

                    if process.returncode == 0:
                        completed_packages += len(packages)
                        completed_sources += 1
                        update_progress_message(f"Completed {source} packages")
                        app.log_signal.emit(f"Successfully installed {len(packages)} {source} package(s)")
                    else:
                        success = False
                        if process.stderr:
                            error_output = process.stderr.read()
                            if error_output:
                                # Check if user cancelled password dialog
                                if source == 'AUR' and ("cancelled" in error_output.lower() or "authentication failed" in error_output.lower() or process.returncode == 1):
                                    app.log_signal.emit("AUR installation cancelled by user")
                                    app.installation_progress.emit("cancelled", False)
                                    return
                                # Fallback: npm EACCES -> try with system privileges (polkit)
                                if source == 'npm' and ("EACCES" in error_output or "permission denied" in error_output.lower()):
                                    try:
                                        app.log_signal.emit("Permission denied installing npm package(s). Retrying with system privileges (polkit)...")
                                        exec_cmd2 = ["pkexec", "--disable-internal-agent", "npm", "install", "-g"] + packages
                                        env2 = os.environ.copy()
                                        process2 = subprocess.Popen(
                                            exec_cmd2,
                                            stdout=subprocess.PIPE,
                                            stderr=subprocess.PIPE,
                                            stdin=subprocess.DEVNULL,
                                            text=True,
                                            bufsize=1,
                                            preexec_fn=os.setsid,
                                            env=env2
                                        )
                                        while True:
                                            if app.install_cancel_event.is_set():
                                                process2.terminate()
                                                try:
                                                    process2.wait(timeout=5)
                                                except subprocess.TimeoutExpired:
                                                    process2.kill()
                                                app.log_signal.emit("Installation cancelled by user")
                                                app.installation_progress.emit("cancelled", False)
                                                return
                                            if process2.poll() is not None:
                                                break
                                            if process2.stdout:
                                                line2 = process2.stdout.readline()
                                                if line2:
                                                    line2 = line2.strip()
                                                    parse_output_line(line2)
                                                    worker.output.emit(line2)
                                            time.sleep(0.1)
                                        if process2.returncode == 0:
                                            success = True
                                            completed_packages += len(packages)
                                            completed_sources += 1
                                            update_progress_message(f"Completed {source} packages (elevated)")
                                            app.log_signal.emit(f"Successfully installed {len(packages)} {source} package(s) with system privileges")
                                        else:
                                            err2 = process2.stderr.read() if process2.stderr else ''
                                            worker.error.emit(f"Error: {err2 or error_output}")
                                        continue
                                    except Exception as _e:
                                        worker.error.emit(f"Error: {str(_e)}")
                                
                                error_text = f"Error: {error_output}"
                                if "Cannot change ownership" in error_output and "Value too large for defined data type" in error_output:
                                    error_text += "\n\nThis error occurs when tar tries to set file ownership to UIDs/GIDs that don't exist in the current environment.\n"
                                    error_text += "To fix this, you can modify the PKGBUILD to add '--no-same-owner' to the tar command.\n"
                                    error_text += "For example, change 'tar -xzf file.tar.gz' to 'tar -xzf file.tar.gz --no-same-owner'"
                                worker.error.emit(error_text)
                finally:
                    if source == 'AUR' and cleanup_path and os.path.exists(cleanup_path):
                        try:
                            os.remove(cleanup_path)
                        except Exception:
                            pass

            if success and not app.install_cancel_event.is_set():
                update_progress_message("Installation complete!")
                app.log_signal.emit("Install completed")
                app.show_message.emit("Installation Complete", f"Successfully installed {total_packages} package(s).")
                app.installation_progress.emit("success", False)
            elif not success and not app.install_cancel_event.is_set():
                app.log_signal.emit("Install failed")
                app.installation_progress.emit("failed", False)

        except Exception as e:
            app.log_signal.emit(f"Error in installation thread: {str(e)}")
            app.installation_progress.emit("failed", False)
        finally:
            try:
                # Reset sudo mode flag if set by caller
                if hasattr(app, 'force_sudo_install'):
                    app.force_sudo_install = False
            except Exception:
                pass
            if hasattr(app, 'install_cancel_event'):
                delattr(app, 'install_cancel_event')

    Thread(target=install, daemon=True).start()
