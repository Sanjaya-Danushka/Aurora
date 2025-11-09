import shutil
import os

def cmd_exists(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def get_available_aur_helpers() -> list:
    """Get list of available AUR helpers in order of preference."""
    helpers = ['yay', 'paru', 'trizen', 'pikaur']
    return [h for h in helpers if cmd_exists(h)]


def get_aur_helper(preferred: str = None) -> str:
    """Get the AUR helper to use.
    
    Args:
        preferred: Preferred AUR helper name. If None or not available,
                   will return the first available helper.
    
    Returns:
        Name of the AUR helper to use, or None if none available.
    """
    available = get_available_aur_helpers()
    if not available:
        return None
    
    # If preferred is specified and available, use it
    if preferred and preferred in available:
        return preferred
    
    # Otherwise return the first available
    return available[0]


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
    # Check if any AUR helper is available
    if not get_available_aur_helpers():
        missing.append("yay or paru")
    return missing
