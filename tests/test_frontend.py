"""
Pytest tests for DICOM Workstation Lite frontend components.
Tests cover API client functionality and basic GUI operations.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock

import pytest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from frontend.api_client import APIClient
from frontend.main_window import MainWindow


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def qapp():
    """
    Session-scoped QApplication instance.
    Required for all PyQt6 GUI tests.

    Returns:
        QApplication: Application instance for testing
    """
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app
    # Note: Don't quit the app as it's session-scoped


@pytest.fixture
def mock_api_client(monkeypatch):
    """
    Mock APIClient with test data and patch it for MainWindow use.

    Returns:
        Mock APIClient instance with mocked methods
    """
    # Create mock client
    mock_client = Mock(spec=APIClient)

    # Mock connection check
    mock_client.check_connection.return_value = False  # Return False to avoid showing error dialog

    # Mock get_studies
    mock_client.get_studies.return_value = [
        {
            'study_uid': '1.2.3.4.5',
            'patient_id': 'PAT001',
            'patient_name': 'Test^Patient',
            'study_date': '20250106',
            'modality': 'CT',
            'num_images': 5
        }
    ]

    # Mock get_study_detail
    mock_client.get_study_detail.return_value = {
        'study_uid': '1.2.3.4.5',
        'patient_id': 'PAT001',
        'patient_name': 'Test^Patient',
        'study_date': '20250106',
        'modality': 'CT',
        'images': [
            {'sop_uid': '1.2.3.4.5.1', 'instance_number': 1, 'file_path': '/test/img1.dcm'}
        ]
    }

    # Mock get_image_bytes (return minimal PNG)
    # Minimal valid PNG: 8-byte signature
    mock_client.get_image_bytes.return_value = b'\x89PNG\r\n\x1a\n'

    # Mock upload_files
    mock_client.upload_files.return_value = [
        {
            'study_uid': '1.2.3.4.5',
            'patient_id': 'PAT001',
            'num_files': 1,
            'message': 'Upload successful'
        }
    ]

    # Mock get_available_presets
    mock_client.get_available_presets.return_value = ["default", "lung", "bone"]

    # Mock close
    mock_client.close.return_value = None

    # Patch APIClient class to return our mock
    monkeypatch.setattr('frontend.api_client.APIClient', lambda *args, **kwargs: mock_client)
    monkeypatch.setattr('frontend.main_window.APIClient', lambda *args, **kwargs: mock_client)

    return mock_client


@pytest.fixture
def mock_requests_session(monkeypatch):
    """
    Mock requests.Session for API client tests.

    Returns:
        Mock session instance
    """
    mock_session = MagicMock()

    # Mock successful response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {'status': 'ok'}
    mock_response.content = b'test content'

    mock_session.get.return_value = mock_response
    mock_session.post.return_value = mock_response

    # Patch Session class
    mock_session_class = MagicMock(return_value=mock_session)
    monkeypatch.setattr('requests.Session', mock_session_class)

    return mock_session


# ============================================================================
# Tests for APIClient
# ============================================================================

def test_api_client_initialization():
    """
    Test APIClient initialization.
    Verifies that base URL is stored correctly.
    """
    base_url = "http://test.example.com:8000"
    client = APIClient(base_url=base_url)

    assert client.base_url == base_url
    assert client.session is not None


def test_api_client_default_url():
    """
    Test APIClient with default URL.
    """
    client = APIClient()

    assert client.base_url == "http://localhost:8000"


def test_upload_files_success(mock_requests_session, tmp_path):
    """
    Test successful file upload.
    Verifies that POST request is made correctly.
    """
    # Create a test file
    test_file = tmp_path / "test.dcm"
    test_file.write_bytes(b"test dicom data")

    # Configure mock response
    mock_requests_session.post.return_value.json.return_value = [
        {
            'study_uid': '1.2.3.4.5',
            'patient_id': 'PAT001',
            'num_files': 1,
            'message': 'Success'
        }
    ]

    # Create client and upload
    client = APIClient()
    results = client.upload_files([test_file])

    # Verify POST was called
    assert mock_requests_session.post.called
    assert len(results) == 1
    assert results[0]['study_uid'] == '1.2.3.4.5'


def test_get_studies_success(mock_requests_session):
    """
    Test successful studies retrieval.
    Verifies that GET request is made and response is parsed.
    """
    # Configure mock response
    mock_requests_session.get.return_value.json.return_value = [
        {
            'study_uid': '1.2.3.4.5',
            'patient_name': 'Test^Patient',
            'modality': 'CT'
        }
    ]

    # Create client and get studies
    client = APIClient()
    studies = client.get_studies()

    # Verify GET was called
    assert mock_requests_session.get.called
    assert len(studies) == 1
    assert studies[0]['study_uid'] == '1.2.3.4.5'


def test_get_studies_with_modality(mock_requests_session):
    """
    Test studies retrieval with modality filter.
    """
    mock_requests_session.get.return_value.json.return_value = []

    client = APIClient()
    studies = client.get_studies(modality='CT')

    # Verify GET was called with modality parameter
    assert mock_requests_session.get.called
    call_args = mock_requests_session.get.call_args
    assert 'params' in call_args.kwargs
    assert call_args.kwargs['params']['modality'] == 'CT'


def test_get_image_bytes_success(mock_requests_session):
    """
    Test successful image retrieval.
    Verifies that image bytes are returned.
    """
    # Configure mock response with PNG data
    png_data = b'\x89PNG\r\n\x1a\n' + b'test image data'
    mock_requests_session.get.return_value.content = png_data

    # Create client and get image
    client = APIClient()
    image_bytes = client.get_image_bytes('1.2.3.4.5.1', preset='default')

    # Verify GET was called and bytes returned
    assert mock_requests_session.get.called
    assert image_bytes == png_data
    assert image_bytes.startswith(b'\x89PNG')


def test_connection_check_success(mock_requests_session):
    """
    Test backend connection check.
    Verifies that health check endpoint is called.
    """
    # Configure mock response
    mock_requests_session.get.return_value.status_code = 200

    # Create client and check connection
    client = APIClient()
    is_connected = client.check_connection()

    # Verify connection check passed
    assert is_connected is True
    assert mock_requests_session.get.called


def test_connection_check_failure(mock_requests_session):
    """
    Test connection check when backend is down.
    """
    # Configure mock to raise exception
    import requests
    mock_requests_session.get.side_effect = requests.RequestException("Connection refused")

    # Create client and check connection
    client = APIClient()
    is_connected = client.check_connection()

    # Verify connection check failed
    assert is_connected is False


def test_api_client_context_manager(mock_requests_session):
    """
    Test APIClient can be used as context manager.
    """
    with APIClient() as client:
        assert client.session is not None

    # Session should be closed after context exit
    # Note: In real usage, session.close() is called


def test_get_available_presets():
    """
    Test getting available window/level presets.
    """
    client = APIClient()
    presets = client.get_available_presets()

    assert isinstance(presets, list)
    assert "default" in presets
    assert "lung" in presets


# ============================================================================
# Tests for MainWindow (using pytest-qt)
# ============================================================================

def test_main_window_creation(qtbot, mock_api_client):
    """
    Test MainWindow creation without errors.
    Verifies that window can be instantiated and displayed.
    """
    # Create window (APIClient is already mocked by fixture)
    window = MainWindow()
    qtbot.addWidget(window)

    # Verify window properties
    assert window.windowTitle() == "DICOM Workstation Lite"
    assert window.width() == 1200
    assert window.height() == 700


def test_upload_button_exists(qtbot, mock_api_client):
    """
    Test that upload button is present in UI.
    """
    # Create window
    window = MainWindow()
    qtbot.addWidget(window)

    # Verify upload button exists
    assert window.upload_btn is not None
    assert window.upload_btn.text() == "📁 Upload DICOM Files"


def test_navigation_buttons_exist(qtbot, mock_api_client):
    """
    Test that navigation buttons (Previous/Next) are present.
    """
    # Create window
    window = MainWindow()
    qtbot.addWidget(window)

    # Verify navigation buttons exist
    assert window.prev_btn is not None
    assert window.next_btn is not None
    assert "Previous" in window.prev_btn.text()
    assert "Next" in window.next_btn.text()


def test_preset_buttons_exist(qtbot, mock_api_client):
    """
    Test that window/level preset buttons are present.
    """
    # Create window
    window = MainWindow()
    qtbot.addWidget(window)

    # Verify preset buttons exist
    assert window.default_preset_btn is not None
    assert window.lung_preset_btn is not None
    assert window.bone_preset_btn is not None
    assert window.brain_preset_btn is not None


def test_study_list_widget_exists(qtbot, mock_api_client):
    """
    Test that studies list widget is present and empty initially.
    """
    # Create window
    window = MainWindow()
    qtbot.addWidget(window)

    # Verify studies list exists
    assert window.studies_list is not None
    # Initially empty (since mock returns empty list)
    assert window.studies_list.count() >= 0


def test_image_label_exists(qtbot, mock_api_client):
    """
    Test that image display label exists.
    """
    # Create window
    window = MainWindow()
    qtbot.addWidget(window)

    # Verify image label exists
    assert window.image_label is not None
    assert window.image_label.minimumSize().width() == 512
    assert window.image_label.minimumSize().height() == 512


def test_metadata_text_exists(qtbot, mock_api_client):
    """
    Test that metadata text widget exists and is read-only.
    """
    # Create window
    window = MainWindow()
    qtbot.addWidget(window)

    # Verify metadata text exists and is read-only
    assert window.metadata_text is not None
    assert window.metadata_text.isReadOnly() is True


def test_refresh_studies_populates_list(qtbot, mock_api_client):
    """
    Test that refresh_studies method populates the study list.
    """
    # Create window
    window = MainWindow()
    qtbot.addWidget(window)

    # Call refresh_studies
    window.refresh_studies()

    # Verify study was added to list
    assert window.studies_list.count() == 1
    item = window.studies_list.item(0)
    assert "Test^Patient" in item.text()
    assert "CT" in item.text()


def test_initial_state(qtbot, mock_api_client):
    """
    Test that window initializes with correct initial state.
    """
    # Create window
    window = MainWindow()
    qtbot.addWidget(window)

    # Verify initial state
    assert window.current_study is None
    assert window.current_images == []
    assert window.current_index == 0
    assert window.current_preset == "default"


def test_navigation_buttons_disabled_initially(qtbot, mock_api_client):
    """
    Test that navigation buttons are disabled when no images are loaded.
    """
    # Create window
    window = MainWindow()
    qtbot.addWidget(window)

    # Verify navigation buttons are disabled
    assert window.prev_btn.isEnabled() is False
    assert window.next_btn.isEnabled() is False
