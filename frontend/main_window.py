"""
Main window for DICOM Workstation Lite.
Provides UI for viewing and managing DICOM studies and images.
"""

import sys
from pathlib import Path
from typing import Optional, List, Dict

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QListWidget, QTextEdit,
    QSplitter, QMessageBox, QStatusBar, QListWidgetItem,
    QFileDialog
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QPixmap, QImage

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from frontend.api_client import APIClient


class MainWindow(QMainWindow):
    """
    Main application window for DICOM Workstation Lite.

    Provides interface for:
    - Uploading DICOM files
    - Browsing studies
    - Viewing images with different window/level presets
    - Navigating through image series
    """

    def __init__(self):
        """Initialize the main window and all UI components."""
        super().__init__()

        # Initialize API client
        self.api_client = APIClient()

        # State variables
        self.current_study: Optional[Dict] = None
        self.current_images: List[Dict] = []
        self.current_index: int = 0
        self.current_preset: str = "default"

        # Initialize UI
        self.init_ui()

        # Check backend connection
        self.check_backend_connection()

    def init_ui(self):
        """
        Initialize and layout all UI components.

        Creates a split-panel layout with:
        - Left panel: Study list and controls
        - Right panel: Image viewer and metadata
        """
        # Window properties
        self.setWindowTitle("DICOM Workstation Lite")
        self.resize(1200, 700)

        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QVBoxLayout(central_widget)

        # ====================================================================
        # Main horizontal splitter (30% left panel, 70% right panel)
        # ====================================================================
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ====================================================================
        # LEFT PANEL - Study List
        # ====================================================================
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        # Top section - Action buttons
        self.upload_btn = QPushButton("📁 Upload DICOM Files")
        self.upload_btn.clicked.connect(self.upload_files)
        left_layout.addWidget(self.upload_btn)

        self.refresh_btn = QPushButton("🔄 Refresh Studies")
        self.refresh_btn.clicked.connect(self.refresh_studies)
        left_layout.addWidget(self.refresh_btn)

        # Studies label
        studies_label = QLabel("Studies:")
        studies_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        left_layout.addWidget(studies_label)

        # Studies list widget
        self.studies_list = QListWidget()
        self.studies_list.itemClicked.connect(self.on_study_selected)
        left_layout.addWidget(self.studies_list)

        splitter.addWidget(left_panel)

        # ====================================================================
        # RIGHT PANEL - Image Viewer
        # ====================================================================
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        # Top section - Study information
        self.study_info_label = QLabel("No study selected")
        self.study_info_label.setStyleSheet(
            "padding: 10px; background-color: #f0f0f0; border-radius: 5px;"
        )
        self.study_info_label.setWordWrap(True)
        right_layout.addWidget(self.study_info_label)

        # Image display label
        self.image_label = QLabel("No image loaded")
        self.image_label.setMinimumSize(512, 512)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet(
            "background-color: black; color: white; border: 2px solid #ccc;"
        )
        self.image_label.setScaledContents(False)  # Manual scaling for better control
        right_layout.addWidget(self.image_label)

        # Navigation controls
        nav_layout = QHBoxLayout()

        self.prev_btn = QPushButton("◀ Previous")
        self.prev_btn.clicked.connect(self.previous_image)
        self.prev_btn.setEnabled(False)
        nav_layout.addWidget(self.prev_btn)

        self.position_label = QLabel("Image: 0 / 0")
        self.position_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nav_layout.addWidget(self.position_label)

        self.next_btn = QPushButton("Next ▶")
        self.next_btn.clicked.connect(self.next_image)
        self.next_btn.setEnabled(False)
        nav_layout.addWidget(self.next_btn)

        right_layout.addLayout(nav_layout)

        # Window/Level presets
        preset_layout = QHBoxLayout()

        preset_label = QLabel("Presets:")
        preset_label.setStyleSheet("font-weight: bold;")
        preset_layout.addWidget(preset_label)

        self.default_preset_btn = QPushButton("Default")
        self.default_preset_btn.clicked.connect(lambda: self.apply_preset("default"))
        preset_layout.addWidget(self.default_preset_btn)

        self.lung_preset_btn = QPushButton("Lung")
        self.lung_preset_btn.clicked.connect(lambda: self.apply_preset("lung"))
        preset_layout.addWidget(self.lung_preset_btn)

        self.bone_preset_btn = QPushButton("Bone")
        self.bone_preset_btn.clicked.connect(lambda: self.apply_preset("bone"))
        preset_layout.addWidget(self.bone_preset_btn)

        self.brain_preset_btn = QPushButton("Brain")
        self.brain_preset_btn.clicked.connect(lambda: self.apply_preset("brain"))
        preset_layout.addWidget(self.brain_preset_btn)

        preset_layout.addStretch()
        right_layout.addLayout(preset_layout)

        # Metadata section
        metadata_label = QLabel("Image Metadata:")
        metadata_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        right_layout.addWidget(metadata_label)

        self.metadata_text = QTextEdit()
        self.metadata_text.setReadOnly(True)
        self.metadata_text.setMaximumHeight(150)
        self.metadata_text.setPlaceholderText("Select an image to view metadata")
        right_layout.addWidget(self.metadata_text)

        splitter.addWidget(right_panel)

        # Set splitter proportions (30% left, 70% right)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 7)

        main_layout.addWidget(splitter)

        # ====================================================================
        # Status Bar
        # ====================================================================
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

        # ====================================================================
        # Menu Bar
        # ====================================================================
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        upload_action = QAction("&Upload DICOM Files", self)
        upload_action.setShortcut("Ctrl+O")
        upload_action.triggered.connect(self.upload_files)
        file_menu.addAction(upload_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        about_action = QAction("&About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    # ========================================================================
    # Backend Communication
    # ========================================================================

    def check_backend_connection(self):
        """
        Check if backend is available and show warning if not.
        """
        if not self.api_client.check_connection():
            QMessageBox.warning(
                self,
                "Backend Connection Failed",
                "Cannot connect to the backend server.\n\n"
                "Please make sure the backend is running at:\n"
                "http://localhost:8000\n\n"
                "Start the backend with:\n"
                "python backend/api.py"
            )
            self.status_bar.showMessage("⚠ Backend offline", 0)
        else:
            self.status_bar.showMessage("✓ Backend connected")
            # Auto-refresh studies on startup
            self.refresh_studies()

    # ========================================================================
    # File Operations
    # ========================================================================

    def upload_files(self):
        """Open file dialog and upload selected DICOM files."""
        try:
            # Open file dialog for multiple DICOM files
            file_paths, _ = QFileDialog.getOpenFileNames(
                self,
                "Select DICOM Files",
                "",
                "DICOM Files (*.dcm);;All Files (*)"
            )

            if not file_paths:
                # User cancelled
                return

            # Show uploading message
            self.status_bar.showMessage(f"Uploading {len(file_paths)} file(s)...")

            # Convert to Path objects
            paths = [Path(f) for f in file_paths]

            # Upload files
            results = self.api_client.upload_files(paths)

            # Show success message
            if results:
                result = results[0]  # First study result
                message = (
                    f"Successfully uploaded {result['num_files']} file(s)\n\n"
                    f"Study UID: {result['study_uid']}\n"
                    f"Patient ID: {result['patient_id']}"
                )
                QMessageBox.information(
                    self,
                    "Upload Successful",
                    message
                )

                # Refresh studies list
                self.refresh_studies()

                self.status_bar.showMessage(f"✓ Uploaded {result['num_files']} file(s)")

        except ValueError as e:
            QMessageBox.critical(
                self,
                "Upload Error",
                f"Invalid files:\n{str(e)}"
            )
            self.status_bar.showMessage("✗ Upload failed")

        except RuntimeError as e:
            QMessageBox.critical(
                self,
                "Upload Error",
                f"Upload failed:\n{str(e)}"
            )
            self.status_bar.showMessage("✗ Upload failed")

        except Exception as e:
            QMessageBox.critical(
                self,
                "Unexpected Error",
                f"An unexpected error occurred:\n{str(e)}"
            )
            self.status_bar.showMessage("✗ Upload failed")

    def refresh_studies(self):
        """Refresh the studies list from the backend."""
        try:
            # Get studies from API
            studies = self.api_client.get_studies()

            # Clear current list
            self.studies_list.clear()

            # Populate list with studies
            for study in studies:
                # Format display text
                display_text = (
                    f"Patient: {study['patient_name']} | "
                    f"Date: {study['study_date']} | "
                    f"{study['modality']}"
                )

                # Create list item
                item = QListWidgetItem(display_text)

                # Store full study dict in item data for later retrieval
                item.setData(Qt.ItemDataRole.UserRole, study)

                # Add to list
                self.studies_list.addItem(item)

            # Update status bar
            self.status_bar.showMessage(f"✓ Loaded {len(studies)} study/studies")

        except RuntimeError as e:
            QMessageBox.warning(
                self,
                "Refresh Error",
                f"Failed to refresh studies:\n{str(e)}"
            )
            self.status_bar.showMessage("✗ Refresh failed")

        except Exception as e:
            QMessageBox.critical(
                self,
                "Unexpected Error",
                f"An unexpected error occurred:\n{str(e)}"
            )
            self.status_bar.showMessage("✗ Refresh failed")

    # ========================================================================
    # Study and Image Display
    # ========================================================================

    def on_study_selected(self, item: QListWidgetItem):
        """
        Handle study selection from the list.

        Args:
            item: Selected list widget item containing study data
        """
        try:
            # Get study data from item
            study = item.data(Qt.ItemDataRole.UserRole)
            if not study:
                return

            # Store current study
            self.current_study = study

            # Update study info label
            study_info = (
                f"<b>Patient:</b> {study['patient_name']} "
                f"<b>ID:</b> {study['patient_id']} | "
                f"<b>Date:</b> {study['study_date']} | "
                f"<b>Modality:</b> {study['modality']}"
            )
            self.study_info_label.setText(study_info)

            # Get detailed study information with images
            self.status_bar.showMessage("Loading study details...")
            study_detail = self.api_client.get_study_detail(study['study_uid'])

            # Extract images list
            self.current_images = study_detail.get('images', [])

            # Reset to first image
            self.current_index = 0

            # Update metadata display with study info
            metadata_text = (
                f"Study Information:\n"
                f"Patient ID: {study_detail['patient_id']}\n"
                f"Patient Name: {study_detail['patient_name']}\n"
                f"Study Date: {study_detail['study_date']}\n"
                f"Modality: {study_detail['modality']}\n"
                f"Number of Images: {len(self.current_images)}\n"
            )
            self.metadata_text.setPlainText(metadata_text)

            # Show first image
            if self.current_images:
                self.show_image()
            else:
                self.image_label.setText("No images in study")
                self.position_label.setText("Image: 0 / 0")

        except RuntimeError as e:
            QMessageBox.warning(
                self,
                "Study Load Error",
                f"Failed to load study details:\n{str(e)}"
            )
            self.status_bar.showMessage("✗ Failed to load study")

        except Exception as e:
            QMessageBox.critical(
                self,
                "Unexpected Error",
                f"An unexpected error occurred:\n{str(e)}"
            )
            self.status_bar.showMessage("✗ Failed to load study")

    def show_image(self):
        """Display the current image with the current preset."""
        try:
            # Check if we have images
            if not self.current_images:
                return

            # Get current image metadata
            image = self.current_images[self.current_index]
            sop_uid = image['sop_uid']

            # Update status
            self.status_bar.showMessage(f"Loading image {self.current_index + 1}...")

            # Get image bytes from API
            image_bytes = self.api_client.get_image_bytes(sop_uid, self.current_preset)

            # Convert bytes to QImage then QPixmap
            qimage = QImage.fromData(image_bytes)
            pixmap = QPixmap.fromImage(qimage)

            # Scale to fit label while maintaining aspect ratio
            scaled_pixmap = pixmap.scaled(
                self.image_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )

            # Set pixmap to label
            self.image_label.setPixmap(scaled_pixmap)

            # Update position label
            total = len(self.current_images)
            self.position_label.setText(f"Image: {self.current_index + 1} / {total}")

            # Update metadata display with image info
            metadata_text = (
                f"Study Information:\n"
                f"Patient ID: {self.current_study['patient_id']}\n"
                f"Patient Name: {self.current_study['patient_name']}\n"
                f"Study Date: {self.current_study['study_date']}\n"
                f"Modality: {self.current_study['modality']}\n\n"
                f"Current Image:\n"
                f"Instance Number: {image['instance_number']}\n"
                f"SOP UID: {sop_uid}\n"
                f"Window Preset: {self.current_preset}\n"
            )
            self.metadata_text.setPlainText(metadata_text)

            # Enable/disable navigation buttons based on position
            self.prev_btn.setEnabled(self.current_index > 0)
            self.next_btn.setEnabled(self.current_index < len(self.current_images) - 1)

            # Update status
            self.status_bar.showMessage(
                f"✓ Showing image {self.current_index + 1} of {total} ({self.current_preset})"
            )

        except RuntimeError as e:
            QMessageBox.warning(
                self,
                "Image Load Error",
                f"Failed to load image:\n{str(e)}"
            )
            self.status_bar.showMessage("✗ Failed to load image")

        except Exception as e:
            QMessageBox.critical(
                self,
                "Unexpected Error",
                f"An unexpected error occurred:\n{str(e)}"
            )
            self.status_bar.showMessage("✗ Failed to load image")

    # ========================================================================
    # Navigation
    # ========================================================================

    def next_image(self):
        """Navigate to the next image in the current series."""
        if self.current_images and self.current_index < len(self.current_images) - 1:
            self.current_index += 1
            self.show_image()

    def previous_image(self):
        """Navigate to the previous image in the current series."""
        if self.current_images and self.current_index > 0:
            self.current_index -= 1
            self.show_image()

    def apply_preset(self, preset: str):
        """
        Apply window/level preset to current image.

        Args:
            preset: Preset name (default, lung, bone, brain, liver)
        """
        # Update current preset
        self.current_preset = preset

        # Re-render current image with new preset
        if self.current_images:
            self.show_image()

        # Update status bar
        self.status_bar.showMessage(f"✓ Applied {preset} preset")

    def show_about(self):
        """Show about dialog."""
        QMessageBox.about(
            self,
            "About DICOM Workstation Lite",
            "<h2>DICOM Workstation Lite</h2>"
            "<p>Version 1.0.0</p>"
            "<p>Medical imaging DICOM viewer with FastAPI backend and PyQt6 GUI.</p>"
            "<p><b>Tech Stack:</b></p>"
            "<ul>"
            "<li>Backend: FastAPI, PyDICOM, NumPy</li>"
            "<li>Frontend: PyQt6</li>"
            "<li>Storage: JSON-based metadata</li>"
            "</ul>"
            "<p>For educational and research purposes.</p>"
        )

    def closeEvent(self, event):
        """
        Handle window close event.

        Clean up resources before closing.
        """
        # Close API client session
        self.api_client.close()
        event.accept()


def main():
    """Main entry point for the application."""
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    # Set application properties
    app.setApplicationName("DICOM Workstation Lite")
    app.setOrganizationName("DICOM Workstation")

    # Create and show main window
    window = MainWindow()
    window.show()

    # Start event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
