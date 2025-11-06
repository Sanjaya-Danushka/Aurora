import os
import shutil
import tempfile


def get_sudo_askpass():
    candidates = [
        "ksshaskpass",
        "ssh-askpass",
        "qt5-askpass",
        "lxqt-openssh-askpass",
    ]
    for c in candidates:
        p = shutil.which(c)
        if p:
            return p
    return None


def prepare_askpass_env():
    env = os.environ.copy()
    cleanup_path = None
    try:
        script = """#!/bin/sh
# Single-attempt password dialog - no retries
title=${NEOARCH_ASKPASS_TITLE:-"NeoArch - AUR Install"}
text=${NEOARCH_ASKPASS_TEXT:-"AUR packages are community-maintained and may be unsafe.\nEnter your password to proceed."}
icon=${NEOARCH_ASKPASS_ICON:-"dialog-password"}

# Try different dialog tools, exit immediately on cancellation
if command -v kdialog >/dev/null 2>&1; then
  result=$(kdialog --title "$title" --icon "$icon" --password "$text" 2>/dev/null)
  exit_code=$?
elif command -v zenity >/dev/null 2>&1; then
  result=$(zenity --password --title="$title" --text="$text" --window-icon="$icon" 2>/dev/null)
  exit_code=$?
elif command -v yad >/dev/null 2>&1; then
  result=$(yad --title="$title" --text="$text" --entry --hide-text --window-icon="$icon" 2>/dev/null)
  exit_code=$?
else
  exit 1
fi

# If cancelled or failed, exit with error code
if [ $exit_code -ne 0 ] || [ -z "$result" ]; then
  exit 1
fi

# Output the password and exit successfully
echo "$result"
exit 0
"""
        fd, path = tempfile.mkstemp(prefix="neoarch-askpass-", suffix=".sh")
        with os.fdopen(fd, "w") as f:
            f.write(script)
        os.chmod(path, 0o700)
        cleanup_path = path
        env["SUDO_ASKPASS"] = path
        env["SSH_ASKPASS"] = path
        env["SUDO_ASKPASS_REQUIRE"] = "force"
    except Exception:
        pass
    return env, cleanup_path
