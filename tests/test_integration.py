"""
Integration tests for DICOM Workstation Lite.
Tests the complete workflow from backend API to data storage.

RUNNING INTEGRATION TESTS:
==========================

Option 1: With automatic server startup (recommended)
------------------------------------------------------
pytest tests/test_integration.py -v -m integration

Option 2: With manually started server
---------------------------------------
1. Start the backend server in one terminal:
   python backend/api.py

2. Run integration tests in another terminal:
   pytest tests/test_integration.py -v -m integration_manual

Option 3: Run all integration tests
------------------------------------
pytest tests/test_integration.py -v

NOTES:
- Automatic tests start/stop the server automatically
- Manual tests require the server to be running at http://localhost:8000
- Tests use data/test_dicom/ directory for test DICOM files
- Make sure test DICOM files exist (run backend/create_test_dicom.py if needed)
"""

import sys
import time
import threading
from pathlib import Path

import pytest
import uvicorn

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from frontend.api_client import APIClient
from backend.storage import JSONStorage


# ============================================================================
# Helper Functions
# ============================================================================

def start_server_thread(port=8000):
    """
    Start FastAPI server in background thread.

    Args:
        port: Port number for server

    Returns:
        Thread: Running server thread
    """
    from backend.api import app

    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="error"  # Reduce noise in test output
    )
    server = uvicorn.Server(config)

    def run_server():
        server.run()

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()

    return thread, server


def wait_for_server(base_url="http://localhost:8000", timeout=10):
    """
    Poll server until it's ready or timeout.

    Args:
        base_url: Server base URL
        timeout: Maximum wait time in seconds

    Returns:
        bool: True if server is ready, False if timeout
    """
    import requests

    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = requests.get(f"{base_url}/health", timeout=1)
            if response.status_code == 200:
                return True
        except requests.RequestException:
            pass
        time.sleep(0.5)

    return False


def get_test_dicom_files():
    """
    Get list of test DICOM files.

    Returns:
        list[Path]: List of DICOM file paths
    """
    test_dicom_dir = Path(__file__).parent.parent / "data" / "test_dicom"

    if not test_dicom_dir.exists():
        raise FileNotFoundError(
            f"Test DICOM directory not found: {test_dicom_dir}\n"
            "Run 'python backend/create_test_dicom.py' to generate test data"
        )

    # Find all .dcm files
    dicom_files = list(test_dicom_dir.rglob("*.dcm"))

    if not dicom_files:
        raise FileNotFoundError(
            f"No DICOM files found in {test_dicom_dir}\n"
            "Run 'python backend/create_test_dicom.py' to generate test data"
        )

    return dicom_files


# ============================================================================
# Integration Tests with Automatic Server
# ============================================================================

@pytest.mark.integration
def test_full_workflow_with_test_server():
    """
    Full end-to-end integration test with automatic server startup.

    Tests the complete workflow:
    1. Start server
    2. Upload DICOM files
    3. Retrieve studies
    4. Get study details
    5. Fetch images
    6. Verify all operations
    """
    server_thread = None
    server = None
    test_port = 8001  # Use different port to avoid conflicts

    try:
        # ====================================================================
        # Phase 1: Start server
        # ====================================================================
        print("\n[Phase 1] Starting test server...")
        server_thread, server = start_server_thread(port=test_port)

        # Wait for server to be ready
        base_url = f"http://localhost:{test_port}"
        server_ready = wait_for_server(base_url, timeout=10)

        assert server_ready, "Server failed to start within timeout"
        print(f"✓ Server started at {base_url}")

        # ====================================================================
        # Phase 2: Initialize client
        # ====================================================================
        print("\n[Phase 2] Initializing API client...")
        client = APIClient(base_url=base_url)

        # Verify connection
        assert client.check_connection(), "Failed to connect to server"
        print("✓ Client connected to server")

        # ====================================================================
        # Phase 3: Upload test DICOM files
        # ====================================================================
        print("\n[Phase 3] Uploading test DICOM files...")
        test_files = get_test_dicom_files()

        # Upload first 3 files for speed
        files_to_upload = test_files[:3]
        print(f"Uploading {len(files_to_upload)} files...")

        upload_results = client.upload_files(files_to_upload)

        # Verify upload response
        assert len(upload_results) > 0, "Upload returned no results"
        result = upload_results[0]

        assert 'study_uid' in result, "Upload result missing study_uid"
        assert 'patient_id' in result, "Upload result missing patient_id"
        assert result['num_files'] > 0, "No files were uploaded"

        study_uid = result['study_uid']
        print(f"✓ Uploaded {result['num_files']} files to study {study_uid}")

        # ====================================================================
        # Phase 4: Get studies list
        # ====================================================================
        print("\n[Phase 4] Retrieving studies list...")
        studies = client.get_studies()

        # Verify studies list
        assert len(studies) > 0, "No studies found after upload"
        assert any(s['study_uid'] == study_uid for s in studies), \
            "Uploaded study not found in studies list"

        print(f"✓ Found {len(studies)} study/studies")

        # ====================================================================
        # Phase 5: Get study detail
        # ====================================================================
        print("\n[Phase 5] Retrieving study details...")
        study_detail = client.get_study_detail(study_uid)

        # Verify study detail
        assert study_detail['study_uid'] == study_uid, "Study UID mismatch"
        assert 'images' in study_detail, "Study detail missing images"
        assert len(study_detail['images']) > 0, "Study has no images"

        print(f"✓ Study has {len(study_detail['images'])} images")

        # ====================================================================
        # Phase 6: Get image bytes
        # ====================================================================
        print("\n[Phase 6] Fetching image as PNG...")
        first_image = study_detail['images'][0]
        sop_uid = first_image['sop_uid']

        # Test default preset
        image_bytes = client.get_image_bytes(sop_uid, preset='default')

        # Verify PNG format
        assert len(image_bytes) > 0, "Image bytes are empty"
        assert image_bytes[:8] == b'\x89PNG\r\n\x1a\n', "Image is not valid PNG"

        print(f"✓ Retrieved image ({len(image_bytes)} bytes, PNG format)")

        # Test different preset
        image_bytes_lung = client.get_image_bytes(sop_uid, preset='lung')
        assert len(image_bytes_lung) > 0, "Lung preset image is empty"
        assert image_bytes_lung[:8] == b'\x89PNG\r\n\x1a\n', \
            "Lung preset image is not valid PNG"

        print(f"✓ Retrieved image with lung preset ({len(image_bytes_lung)} bytes)")

        # ====================================================================
        # Phase 7: Test modality filter
        # ====================================================================
        print("\n[Phase 7] Testing modality filter...")
        ct_studies = client.get_studies(modality='CT')

        # Verify filter works
        assert all(s['modality'] == 'CT' for s in ct_studies), \
            "Modality filter returned non-CT studies"

        print(f"✓ Modality filter works ({len(ct_studies)} CT studies)")

        # ====================================================================
        # Success
        # ====================================================================
        print("\n" + "=" * 70)
        print("✓ ALL INTEGRATION TESTS PASSED")
        print("=" * 70)

    except Exception as e:
        print(f"\n✗ Integration test failed: {e}")
        raise

    finally:
        # ====================================================================
        # Cleanup
        # ====================================================================
        print("\n[Cleanup] Shutting down test server...")

        if server:
            server.should_exit = True

        if client:
            client.close()

        # Give server time to shut down
        time.sleep(1)

        print("✓ Cleanup complete")


# ============================================================================
# Integration Tests with Manual Server
# ============================================================================

@pytest.mark.integration_manual
def test_full_workflow_manual_server():
    """
    Full end-to-end integration test assuming server is already running.

    PREREQUISITE: Server must be running at http://localhost:8000

    Start server with: python backend/api.py

    Tests the complete workflow:
    1. Connect to server
    2. Upload DICOM files
    3. Retrieve studies
    4. Get study details
    5. Fetch images
    """
    client = None

    try:
        # ====================================================================
        # Phase 1: Connect to server
        # ====================================================================
        print("\n[Phase 1] Connecting to server...")
        client = APIClient(base_url="http://localhost:8000")

        # Verify server is running
        if not client.check_connection():
            pytest.skip(
                "Server is not running at http://localhost:8000\n"
                "Start server with: python backend/api.py"
            )

        print("✓ Connected to server")

        # ====================================================================
        # Phase 2: Upload test DICOM files
        # ====================================================================
        print("\n[Phase 2] Uploading test DICOM files...")
        test_files = get_test_dicom_files()

        # Upload first 5 files
        files_to_upload = test_files[:5]
        print(f"Uploading {len(files_to_upload)} files...")

        upload_results = client.upload_files(files_to_upload)

        assert len(upload_results) > 0
        result = upload_results[0]
        study_uid = result['study_uid']

        print(f"✓ Uploaded {result['num_files']} files to study {study_uid}")

        # ====================================================================
        # Phase 3: Retrieve and verify studies
        # ====================================================================
        print("\n[Phase 3] Retrieving studies...")
        studies = client.get_studies()

        assert len(studies) > 0
        assert any(s['study_uid'] == study_uid for s in studies)

        print(f"✓ Found {len(studies)} study/studies")

        # ====================================================================
        # Phase 4: Get study detail
        # ====================================================================
        print("\n[Phase 4] Getting study details...")
        study_detail = client.get_study_detail(study_uid)

        assert study_detail['study_uid'] == study_uid
        assert len(study_detail['images']) > 0

        print(f"✓ Study has {len(study_detail['images'])} images")

        # ====================================================================
        # Phase 5: Test all presets
        # ====================================================================
        print("\n[Phase 5] Testing all window/level presets...")
        first_image = study_detail['images'][0]
        sop_uid = first_image['sop_uid']

        presets = client.get_available_presets()
        for preset in presets:
            image_bytes = client.get_image_bytes(sop_uid, preset=preset)
            assert len(image_bytes) > 0
            assert image_bytes[:8] == b'\x89PNG\r\n\x1a\n'
            print(f"  ✓ {preset}: {len(image_bytes)} bytes")

        print(f"✓ All {len(presets)} presets work")

        # ====================================================================
        # Success
        # ====================================================================
        print("\n" + "=" * 70)
        print("✓ ALL MANUAL INTEGRATION TESTS PASSED")
        print("=" * 70)

    finally:
        if client:
            client.close()


@pytest.mark.integration_manual
def test_error_handling():
    """
    Test error handling in integration scenarios.

    PREREQUISITE: Server must be running at http://localhost:8000
    """
    client = None

    try:
        client = APIClient(base_url="http://localhost:8000")

        if not client.check_connection():
            pytest.skip("Server is not running")

        # ====================================================================
        # Test 1: Invalid study UID
        # ====================================================================
        print("\n[Test 1] Testing invalid study UID...")
        try:
            client.get_study_detail("invalid.study.uid")
            assert False, "Expected RuntimeError for invalid study UID"
        except RuntimeError as e:
            assert "not found" in str(e).lower()
            print("✓ Invalid study UID handled correctly")

        # ====================================================================
        # Test 2: Invalid image UID
        # ====================================================================
        print("\n[Test 2] Testing invalid image UID...")
        try:
            client.get_image_bytes("invalid.image.uid")
            assert False, "Expected RuntimeError for invalid image UID"
        except RuntimeError as e:
            assert "not found" in str(e).lower()
            print("✓ Invalid image UID handled correctly")

        # ====================================================================
        # Test 3: Empty file list
        # ====================================================================
        print("\n[Test 3] Testing empty file list...")
        try:
            client.upload_files([])
            assert False, "Expected ValueError for empty file list"
        except ValueError as e:
            assert "no files" in str(e).lower()
            print("✓ Empty file list handled correctly")

        print("\n✓ All error handling tests passed")

    finally:
        if client:
            client.close()


# ============================================================================
# Cleanup Utility
# ============================================================================

def cleanup_test_data():
    """
    Cleanup test data from storage.

    WARNING: This will delete all studies from the test database!
    """
    storage = JSONStorage()
    storage.data = {"studies": []}
    storage._save_data()
    print("Test data cleaned up")


if __name__ == "__main__":
    """
    Run integration tests directly.
    """
    print("DICOM Workstation Lite - Integration Tests")
    print("=" * 70)
    print("\nRunning full workflow with automatic server...")

    test_full_workflow_with_test_server()

    print("\n" + "=" * 70)
    print("Integration tests completed successfully!")
