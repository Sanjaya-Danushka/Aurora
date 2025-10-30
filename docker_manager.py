# docker_manager.py - Docker container management component for Aurora

import os
import subprocess
from threading import Thread
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                             QListWidget, QListWidgetItem, QDialog, QLineEdit, QMessageBox)
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QTimer
from PyQt6.QtGui import QPixmap, QPainter, QIcon, QColor
from PyQt6.QtSvg import QSvgRenderer


class DockerManager(QObject):
    """Docker container management component for Aurora"""

    def __init__(self, log_signal, show_message_signal, sources_layout, parent=None):
        super().__init__()
        self.log_signal = log_signal
        self.show_message = show_message_signal
        self.sources_layout = sources_layout
        self.parent = parent  # Reference to main window

        # UI elements that will be created
        self.docker_section = None  # Reference to the docker section widget
        self.recent_containers_label = None
        self.recent_containers_list = None

        # Initialize the Docker section UI
        self.create_docker_section()

    def create_docker_section(self):
        """Create and add the Docker section to the sources layout"""
        self.docker_section = QWidget()
        docker_layout = QVBoxLayout(self.docker_section)
        docker_layout.setContentsMargins(0, 8, 0, 0)  # Add top margin for spacing
        docker_layout.setSpacing(10)  # Increase spacing between elements

        # Docker section label
        docker_label = QLabel("Docker Containers")
        docker_label.setObjectName("sectionLabel")
        docker_label.setStyleSheet("font-size: 11px; margin-bottom: 4px;")
        docker_layout.addWidget(docker_label)

        # Docker buttons container - now horizontal layout like other sources
        docker_buttons_widget = QWidget()
        docker_buttons_layout = QHBoxLayout(docker_buttons_widget)
        docker_buttons_layout.setContentsMargins(0, 0, 0, 0)
        docker_buttons_layout.setSpacing(8)

        # Install from Docker button (with icon)
        install_docker_container = QWidget()
        install_docker_layout = QHBoxLayout(install_docker_container)
        install_docker_layout.setContentsMargins(0, 0, 0, 0)
        install_docker_layout.setSpacing(8)

        # Docker icon
        docker_icon_label = QLabel()
        docker_icon_path = os.path.join(os.path.dirname(__file__), "assets", "icons", "discover", "docker.svg")
        try:
            svg_renderer = QSvgRenderer(docker_icon_path)
            if svg_renderer.isValid():
                pixmap = QPixmap(20, 20)
                pixmap.fill(Qt.GlobalColor.transparent)
                painter = QPainter(pixmap)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                from PyQt6.QtCore import QRectF
                svg_renderer.render(painter, QRectF(pixmap.rect()))
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                painter.fillRect(pixmap.rect(), QColor("white"))
                painter.end()
                docker_icon_label.setPixmap(pixmap)
            else:
                docker_icon_label.setText("🐳")
        except:
            docker_icon_label.setText("🐳")

        install_docker_layout.addWidget(docker_icon_label)

        # Install button
        install_docker_btn = QPushButton("Run from Docker")
        install_docker_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 191, 174, 0.8);
                color: #1E1E1E;
                border: 1px solid rgba(0, 191, 174, 0.3);
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 11px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: rgba(0, 191, 174, 0.9);
                border-color: rgba(0, 191, 174, 0.5);
            }
            QPushButton:pressed {
                background-color: rgba(0, 191, 174, 0.7);
            }
        """)
        install_docker_btn.clicked.connect(self.install_from_docker)
        install_docker_layout.addWidget(install_docker_btn)

        docker_buttons_layout.addWidget(install_docker_container)

        # Secondary buttons widget
        secondary_buttons_widget = QWidget()
        secondary_layout = QHBoxLayout(secondary_buttons_widget)
        secondary_layout.setContentsMargins(0, 0, 0, 0)
        secondary_layout.setSpacing(4)

        # List containers button
        list_containers_btn = QPushButton("📋 List")
        list_containers_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(42, 45, 51, 0.5);
                color: #F0F0F0;
                border: 1px solid rgba(0, 191, 174, 0.15);
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 10px;
                text-align: center;
            }
            QPushButton:hover {
                background-color: rgba(42, 45, 51, 0.7);
                border-color: rgba(0, 191, 174, 0.35);
                color: #00BFAE;
            }
        """)
        list_containers_btn.clicked.connect(self.list_docker_containers)
        secondary_layout.addWidget(list_containers_btn)

        # Stop containers button
        stop_containers_btn = QPushButton("⏹️ Stop")
        stop_containers_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(42, 45, 51, 0.5);
                color: #F0F0F0;
                border: 1px solid rgba(0, 191, 174, 0.15);
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 10px;
                text-align: center;
            }
            QPushButton:hover {
                background-color: rgba(42, 45, 51, 0.7);
                border-color: rgba(0, 191, 174, 0.35);
                color: #FF6B6B;
            }
        """)
        stop_containers_btn.clicked.connect(self.stop_docker_containers)
        secondary_layout.addWidget(stop_containers_btn)

        # Clean containers button
        clean_containers_btn = QPushButton("🗑️ Clean")
        clean_containers_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(42, 45, 51, 0.5);
                color: #F0F0F0;
                border: 1px solid rgba(0, 191, 174, 0.15);
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 10px;
                text-align: center;
            }
            QPushButton:hover {
                background-color: rgba(42, 45, 51, 0.7);
                border-color: rgba(0, 191, 174, 0.35);
                color: #FF6B6B;
            }
        """)
        clean_containers_btn.clicked.connect(self.clean_docker_containers)
        secondary_layout.addWidget(clean_containers_btn)

        docker_buttons_layout.addWidget(secondary_buttons_widget)

        docker_layout.addWidget(docker_buttons_widget)

        # Recent containers list (compact)
        self.recent_containers_label = QLabel("Running:")
        self.recent_containers_label.setStyleSheet("color: #C9C9C9; font-size: 10px; margin-top: 4px;")
        docker_layout.addWidget(self.recent_containers_label)

        self.recent_containers_list = QListWidget()
        self.recent_containers_list.setStyleSheet("""
            QListWidget {
                background-color: rgba(42, 45, 51, 0.4);
                border: 1px solid rgba(0, 191, 174, 0.15);
                color: #F0F0F0;
                font-size: 10px;
                max-height: 85px;
            }
            QListWidget::item:hover {
                background-color: rgba(0, 191, 174, 0.15);
            }
            QListWidget::item:selected {
                background-color: rgba(0, 191, 174, 0.25);
            }
        """)
        self.recent_containers_list.itemDoubleClicked.connect(self.open_container_logs)
        self.recent_containers_list.setVisible(False)  # Initially hidden
        docker_layout.addWidget(self.recent_containers_list)

        self.sources_layout.addWidget(self.docker_section)

        # Load running containers on startup
        self.load_running_containers()

    def install_from_docker(self):
        """Create a dialog to ask for Docker image name/tag"""
        dialog = QDialog()
        dialog.setWindowTitle("Run Container from Docker Image")
        dialog.setModal(True)
        dialog.setStyleSheet("""
            QDialog {
                background-color: #1E1E1E;
                color: #F0F0F0;
                border: 1px solid rgba(0, 191, 174, 0.2);
            }
        """)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Title
        title = QLabel("Run Application from Docker Image")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #00BFAE;")
        layout.addWidget(title)

        # Description
        desc = QLabel("Enter the Docker image name and tag to run the container:")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Image input
        image_input = QLineEdit()
        image_input.setPlaceholderText("nginx:latest or user/myapp:v1.0")
        image_input.setStyleSheet("""
            QLineEdit {
                background-color: rgba(42, 45, 51, 0.8);
                color: #F0F0F0;
                border: 2px solid rgba(0, 191, 174, 0.2);
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border-color: #00BFAE;
            }
        """)
        layout.addWidget(image_input)

        # Port mapping input
        port_layout = QHBoxLayout()
        port_layout.addWidget(QLabel("Port mapping (optional):"))
        port_input = QLineEdit()
        port_input.setPlaceholderText("8080:80")
        port_input.setStyleSheet("""
            QLineEdit {
                background-color: rgba(42, 45, 51, 0.8);
                color: #F0F0F0;
                border: 2px solid rgba(0, 191, 174, 0.2);
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
            }
            QLineEdit:focus {
                border-color: #00BFAE;
            }
        """)
        port_layout.addWidget(port_input)
        layout.addLayout(port_layout)

        # Buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(dialog.reject)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(42, 45, 51, 0.6);
                color: #F0F0F0;
                border: 1px solid rgba(0, 191, 174, 0.2);
                border-radius: 4px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: rgba(42, 45, 51, 0.8);
            }
        """)
        buttons_layout.addWidget(cancel_btn)

        run_btn = QPushButton("Run Container")
        run_btn.setDefault(True)
        run_btn.clicked.connect(lambda: self.proceed_docker_run(image_input.text().strip(), port_input.text().strip(), dialog))
        run_btn.setStyleSheet("""
            QPushButton {
                background-color: #00BFAE;
                color: #1E1E1E;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #00C4B0;
            }
        """)
        buttons_layout.addWidget(run_btn)

        layout.addLayout(buttons_layout)

        dialog.exec()

    def proceed_docker_run(self, image_name, port_mapping, dialog):
        """Handle the actual Docker container running process"""
        if not image_name:
            QMessageBox.warning(None, "Invalid Image", "Please enter a valid Docker image name.")
            return

        dialog.accept()

        self.log_signal.emit(f"Starting Docker container from image: {image_name}")

        def run_docker_thread():
            try:
                # Build the docker run command
                cmd = ["docker", "run", "-d", "--name", f"aurora-{image_name.replace('/', '-').replace(':', '-')}-{os.urandom(4).hex()}"]

                # Add port mapping if specified
                if port_mapping:
                    cmd.extend(["-p", port_mapping])

                cmd.append(image_name)

                self.log_signal.emit(f"Running command: {' '.join(cmd)}")
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

                if result.returncode == 0:
                    container_id = result.stdout.strip()
                    self.log_signal.emit(f"Container started successfully with ID: {container_id}")
                    self.show_message.emit("Container Started", f"Successfully started container from {image_name}")
                    # Refresh the running containers list
                    self.load_running_containers()
                else:
                    self.log_signal.emit(f"Failed to start container: {result.stderr}")
                    self.show_message.emit("Container Start Failed", f"Failed to start container: {result.stderr}")

            except Exception as e:
                self.log_signal.emit(f"Error running Docker container: {str(e)}")
                self.show_message.emit("Container Start Failed", f"Error: {str(e)}")

        Thread(target=run_docker_thread, daemon=True).start()

    def list_docker_containers(self):
        """List all Docker containers"""
        try:
            result = subprocess.run(["docker", "ps", "-a", "--format", "table {{.Names}}\\t{{.Image}}\\t{{.Status}}"],
                                  capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                self.log_signal.emit("Docker containers:")
                for line in result.stdout.strip().split('\n'):
                    if line.strip():
                        self.log_signal.emit(f"  {line}")
            else:
                self.log_signal.emit(f"Failed to list containers: {result.stderr}")
        except Exception as e:
            self.log_signal.emit(f"Error listing containers: {str(e)}")

    def stop_docker_containers(self):
        """Stop running Docker containers"""
        try:
            # Get running containers
            result = subprocess.run(["docker", "ps", "-q"], capture_output=True, text=True, timeout=30)
            if result.returncode == 0 and result.stdout.strip():
                containers = result.stdout.strip().split('\n')
                self.log_signal.emit(f"Stopping {len(containers)} containers...")

                for container_id in containers:
                    stop_result = subprocess.run(["docker", "stop", container_id], capture_output=True, text=True, timeout=30)
                    if stop_result.returncode == 0:
                        self.log_signal.emit(f"Stopped container: {container_id}")
                    else:
                        self.log_signal.emit(f"Failed to stop container {container_id}: {stop_result.stderr}")

                self.show_message.emit("Containers Stopped", f"Stopped {len(containers)} containers")
                # Refresh the running containers list
                self.load_running_containers()
                # Remove the Docker section from the UI after stopping containers
                self.remove_docker_section()
        except Exception as e:
            self.log_signal.emit(f"Error stopping containers: {str(e)}")

    def remove_docker_section(self):
        """Remove the Docker section from the sources layout"""
        if self.docker_section and self.sources_layout:
            self.sources_layout.removeWidget(self.docker_section)
            self.docker_section.setParent(None)
            self.docker_section.deleteLater()
            self.docker_section = None
            self.log_signal.emit("Docker section removed from sources panel")
            # Clear the reference in parent so it can be recreated
            if self.parent:
                self.parent.docker_manager = None

    def clean_docker_containers(self):
        """Clean up Docker containers and images"""
        try:
            # Ask for confirmation
            reply = QMessageBox.question(
                None, "Clean Docker",
                "This will remove stopped containers and unused images.\n\nAre you sure you want to continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )

            if reply != QMessageBox.StandardButton.Yes:
                return

            self.log_signal.emit("Cleaning Docker containers and images...")

            # Remove stopped containers
            clean_result = subprocess.run(["docker", "container", "prune", "-f"], capture_output=True, text=True, timeout=60)
            if clean_result.returncode == 0:
                self.log_signal.emit("Removed stopped containers")
            else:
                self.log_signal.emit(f"Failed to clean containers: {clean_result.stderr}")

            # Remove unused images
            image_result = subprocess.run(["docker", "image", "prune", "-f"], capture_output=True, text=True, timeout=60)
            if image_result.returncode == 0:
                self.log_signal.emit("Removed unused images")
            else:
                self.log_signal.emit(f"Failed to clean images: {image_result.stderr}")

            self.show_message.emit("Docker Clean Complete", "Cleaned containers and images")

        except Exception as e:
            self.log_signal.emit(f"Error cleaning Docker: {str(e)}")

    def load_running_containers(self):
        """Load and display running Docker containers"""
        try:
            result = subprocess.run(["docker", "ps", "--format", "{{.Names}}|{{.Image}}|{{.Ports}}"],
                                  capture_output=True, text=True, timeout=30)

            if result.returncode == 0 and result.stdout.strip():
                containers = []
                for line in result.stdout.strip().split('\n'):
                    if line.strip():
                        parts = line.split('|')
                        if len(parts) >= 2:
                            name = parts[0]
                            image = parts[1]
                            ports = parts[2] if len(parts) > 2 else ""
                            containers.append((name, image, ports))

                if containers and self.recent_containers_list:
                    self.recent_containers_list.clear()
                    for name, image, ports in containers:
                        port_info = f" ({ports})" if ports else ""
                        item = QListWidgetItem(f"🐳 {name} - {image}{port_info}")
                        item.setToolTip(f"Container: {name}\nImage: {image}\nPorts: {ports}")
                        item.setData(Qt.ItemDataRole.UserRole, name)
                        self.recent_containers_list.addItem(item)

                    if self.recent_containers_label:
                        self.recent_containers_label.setVisible(True)
                    self.recent_containers_list.setVisible(True)
                else:
                    if self.recent_containers_label:
                        self.recent_containers_label.setVisible(False)
                    if self.recent_containers_list:
                        self.recent_containers_list.setVisible(False)
            else:
                if self.recent_containers_label:
                    self.recent_containers_label.setVisible(False)
                if self.recent_containers_list:
                    self.recent_containers_list.setVisible(False)

        except Exception as e:
            self.log_signal.emit(f"Error loading running containers: {e}")
            if self.recent_containers_label:
                self.recent_containers_label.setVisible(False)
            if self.recent_containers_list:
                self.recent_containers_list.setVisible(False)

    def open_container_logs(self, item):
        """Show logs for the selected container"""
        container_name = item.data(Qt.ItemDataRole.UserRole)
        if container_name:
            try:
                result = subprocess.run(["docker", "logs", "--tail", "50", container_name],
                                      capture_output=True, text=True, timeout=30)
                if result.returncode == 0:
                    self.log_signal.emit(f"Logs for container '{container_name}':")
                    for line in result.stdout.split('\n'):
                        if line.strip():
                            self.log_signal.emit(f"  {line}")
                    if result.stderr:
                        for line in result.stderr.split('\n'):
                            if line.strip():
                                self.log_signal.emit(f"  [ERR] {line}")
                else:
                    self.log_signal.emit(f"Failed to get logs for {container_name}: {result.stderr}")
            except Exception as e:
                self.log_signal.emit(f"Error getting container logs: {str(e)}")
