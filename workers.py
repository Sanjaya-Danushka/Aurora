import os
import subprocess
from PyQt6.QtCore import QObject, pyqtSignal


def get_auth_command(env=None):
    """Get the appropriate authentication command based on desktop environment"""
    if env is None:
        env = os.environ
    
    desktop = env.get('XDG_CURRENT_DESKTOP', '').lower()
    session_type = env.get('XDG_SESSION_TYPE', '').lower()
    
    # Check if polkit agent is running
    try:
        polkit_agent_running = subprocess.run(['pgrep', '-f', 'polkit.*agent'], capture_output=True).returncode == 0
    except Exception:
        polkit_agent_running = False
    
    # For Hyprland and other minimal Wayland compositors
    if 'hyprland' in desktop or (session_type == 'wayland' and not polkit_agent_running):
        # Prefer sudo with askpass for Hyprland
        if 'SUDO_ASKPASS' in env:
            return ["sudo", "-A"]
        else:
            return ["pkexec"]
    
    # For GNOME, KDE, XFCE with polkit agents
    elif polkit_agent_running:
        if desktop in ['gnome', 'kde', 'xfce']:
            return ["pkexec"]
        else:
            return ["pkexec", "--disable-internal-agent"]
    
    # Fallback: try sudo with askpass if available
    elif 'SUDO_ASKPASS' in env:
        return ["sudo", "-A"]
    
    # Final fallback
    else:
        return ["pkexec"]


class PackageLoaderWorker(QObject):
    packages_loaded = pyqtSignal(list)
    error_occurred = pyqtSignal(str)
    finished = pyqtSignal()
    
    def __init__(self, command):
        super().__init__()
        self.command = command
    
    def run(self):
        try:
            result = subprocess.run(self.command, capture_output=True, text=True, timeout=60)
            packages = []
            if result.returncode == 0 and result.stdout:
                for line in result.stdout.strip().split('\n'):
                    if line.strip():
                        parts = line.split()
                        if len(parts) >= 2:
                            packages.append({
                                'name': parts[0],
                                'version': parts[1],
                                'id': parts[0]
                            })
            self.packages_loaded.emit(packages)
        except Exception as e:
            self.error_occurred.emit(f"Error: {str(e)}")
        finally:
            self.finished.emit()


class CommandWorker(QObject):
    finished = pyqtSignal()
    output = pyqtSignal(str)
    error = pyqtSignal(str)
    
    def __init__(self, command, sudo=False, env=None):
        super().__init__()
        self.command = command
        self.sudo = sudo
        self.env = env if env is not None else os.environ.copy()
    
    def run(self):
        try:
            if self.sudo:
                auth_cmd = get_auth_command(self.env)
                self.command = auth_cmd + self.command
            
            process = subprocess.Popen(
                self.command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                text=True,
                bufsize=1,
                preexec_fn=os.setsid,
                env=self.env
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
    
    def _command_exists(self, cmd):
        """Check if a command exists in PATH"""
        return subprocess.run(['which', cmd], capture_output=True).returncode == 0
