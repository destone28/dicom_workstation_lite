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
from PyQt6.QtGui import QAction, QPixmap

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
    # Placeholder Methods (to be implemented)
    # ========================================================================

    def upload_files(self):
        """Open file dialog and upload selected DICOM files."""
        pass

    def refresh_studies(self):
        """Refresh the studies list from the backend."""
        pass

    def on_study_selected(self, item: QListWidgetItem):
        """
        Handle study selection from the list.

        Args:
            item: Selected list widget item containing study data
        """
        pass

    def next_image(self):
        """Navigate to the next image in the current series."""
        pass

    def previous_image(self):
        """Navigate to the previous image in the current series."""
        pass

    def apply_preset(self, preset: str):
        """
        Apply window/level preset to current image.

        Args:
            preset: Preset name (default, lung, bone, brain, liver)
        """
        pass

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
