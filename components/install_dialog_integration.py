"""
Installation Dialog Integration Helper
Handles showing and updating the installation progress dialog
"""

from PyQt6.QtCore import QTimer
from components.install_progress_dialog import InstallProgressDialog


def show_installation_dialog(app, packages_by_source):
    """Show the installation progress dialog"""
    try:
        dialog = InstallProgressDialog(packages_by_source, app)
        app.install_progress_dialog = dialog
        dialog.cancel_btn.clicked.connect(app.cancel_installation)
        dialog.show()
    except Exception as e:
        app.log_signal.emit(f"Error showing installation dialog: {e}")


def update_installation_progress(app, completed, total, current_package, download_info):
    """Update the installation progress dialog"""
    try:
        if hasattr(app, 'install_progress_dialog') and app.install_progress_dialog:
            app.install_progress_dialog.update_progress(completed, total, current_package, download_info)
    except Exception:
        pass


def close_installation_dialog(app):
    """Close the installation progress dialog"""
    try:
        if hasattr(app, 'install_progress_dialog') and app.install_progress_dialog:
            app.install_progress_dialog.close()
            app.install_progress_dialog = None
    except Exception:
        pass
