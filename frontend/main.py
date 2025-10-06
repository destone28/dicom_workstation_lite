"""
Entry point for the DICOM Workstation Lite GUI application.

This module initializes the PyQt6 application and launches the main window.
"""

import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from frontend.main_window import MainWindow


def main():
    """Initialize and run the DICOM Workstation Lite application."""
    # Create application instance
    app = QApplication(sys.argv)

    # Set modern application style
    app.setStyle("Fusion")

    # Set application metadata
    app.setApplicationName("DICOM Workstation Lite")
    app.setOrganizationName("DICOM Workstation")

    # Create and show main window
    window = MainWindow()
    window.show()

    # Execute application event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
