import shutil
import os

def cmd_exists(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def get_missing_dependencies() -> list:
    missing = []
    if not cmd_exists("flatpak"):
        missing.append("flatpak")
    if not cmd_exists("git"):
        missing.append("git")
    if not cmd_exists("node"):
        missing.append("nodejs")
    if not cmd_exists("npm"):
        missing.append("npm")
    if not cmd_exists("docker"):
        missing.append("docker")
    if not cmd_exists("yay"):
        missing.append("yay")
    return missing
