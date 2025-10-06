"""
Comprehensive pytest tests for DICOM Workstation Lite backend.
Tests cover DICOM processing, storage, and API endpoints.
"""

import io
import sys
from pathlib import Path
from datetime import datetime

import pytest
import numpy as np
import pydicom
from pydicom.dataset import Dataset, FileDataset
from pydicom.uid import generate_uid, ExplicitVRLittleEndian
from fastapi.testclient import TestClient

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.storage import JSONStorage
from backend.dicom_processor import (
    extract_metadata,
    get_pixel_array,
    apply_window_level,
    array_to_png_bytes,
    WINDOW_PRESETS
)
from backend.api import app


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sample_dicom():
    """
    Create a synthetic DICOM dataset with all required tags for testing.

    Returns:
        pydicom.Dataset: Complete DICOM dataset with patient, study, and image data
    """
    # Create file meta information
    file_meta = Dataset()
    file_meta.MediaStorageSOPClassUID = '1.2.840.10008.5.1.4.1.1.2'  # CT Image Storage
    file_meta.MediaStorageSOPInstanceUID = generate_uid()
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    file_meta.ImplementationClassUID = generate_uid()

    # Create dataset with file meta
    ds = FileDataset(
        "test.dcm",
        {},
        file_meta=file_meta,
        preamble=b"\0" * 128
    )

    # Patient information
    ds.PatientName = "Test^Patient"
    ds.PatientID = "TEST001"
    ds.PatientBirthDate = "19900101"
    ds.PatientSex = "M"

    # Study information
    ds.StudyInstanceUID = generate_uid()
    ds.StudyDate = datetime.now().strftime('%Y%m%d')
    ds.StudyTime = datetime.now().strftime('%H%M%S')
    ds.StudyDescription = "Test Study"
    ds.AccessionNumber = "ACC001"

    # Series information
    ds.SeriesInstanceUID = generate_uid()
    ds.SeriesNumber = 1
    ds.SeriesDescription = "Test Series"
    ds.Modality = "CT"

    # Instance information
    ds.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
    ds.SOPClassUID = file_meta.MediaStorageSOPClassUID
    ds.InstanceNumber = 1

    # Image information
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.Rows = 512
    ds.Columns = 512
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 0

    # CT-specific tags
    ds.RescaleIntercept = -1024
    ds.RescaleSlope = 1.0
    ds.SliceThickness = 5.0
    ds.KVP = 120

    # Generate pixel data (simple gradient pattern for testing)
    pixel_array = np.arange(512 * 512, dtype=np.uint16).reshape(512, 512)
    ds.PixelData = pixel_array.tobytes()

    return ds


@pytest.fixture
def test_dicom_file(tmp_path, sample_dicom):
    """
    Save sample DICOM dataset to a temporary file.

    Args:
        tmp_path: Pytest temporary directory fixture
        sample_dicom: Sample DICOM dataset fixture

    Returns:
        Path: Path to saved DICOM file
    """
    file_path = tmp_path / "test.dcm"
    sample_dicom.save_as(str(file_path), write_like_original=False)
    return file_path


@pytest.fixture
def test_storage(tmp_path):
    """
    Create JSONStorage instance with temporary directories.

    Args:
        tmp_path: Pytest temporary directory fixture

    Returns:
        JSONStorage: Storage instance for testing
    """
    json_path = tmp_path / "test_studies.json"
    files_dir = tmp_path / "test_dicom_files"
    return JSONStorage(json_path=str(json_path), files_dir=str(files_dir))


@pytest.fixture
def client():
    """
    Create FastAPI TestClient for API endpoint testing.

    Returns:
        TestClient: FastAPI test client
    """
    return TestClient(app)


# ============================================================================
# Tests for dicom_processor.py
# ============================================================================

def test_extract_metadata(sample_dicom):
    """
    Test metadata extraction from DICOM dataset.
    Verifies that all essential DICOM tags are correctly extracted.
    """
    metadata = extract_metadata(sample_dicom)

    # Verify patient information
    assert metadata['patient_id'] == "TEST001"
    assert metadata['patient_name'] == "Test^Patient"

    # Verify study information
    assert metadata['study_uid'] == sample_dicom.StudyInstanceUID
    assert metadata['study_date'] == sample_dicom.StudyDate
    assert metadata['study_time'] == sample_dicom.StudyTime

    # Verify modality and instance info
    assert metadata['modality'] == "CT"
    assert metadata['sop_uid'] == sample_dicom.SOPInstanceUID
    assert metadata['instance_number'] == 1

    # Verify image dimensions
    assert metadata['rows'] == 512
    assert metadata['columns'] == 512


def test_extract_metadata_missing_tags():
    """
    Test metadata extraction with missing optional tags.
    Verifies graceful handling of incomplete DICOM data.
    """
    # Create minimal dataset
    ds = Dataset()
    ds.PatientID = "TEST002"
    # Missing most tags

    metadata = extract_metadata(ds)

    # Should still return structure with None values
    assert metadata['patient_id'] == "TEST002"
    assert metadata['study_uid'] is None
    assert metadata['modality'] is None


def test_get_pixel_array(sample_dicom):
    """
    Test pixel data extraction and rescale transformation.
    Verifies that RescaleSlope and RescaleIntercept are applied correctly.
    """
    pixel_array = get_pixel_array(sample_dicom)

    # Verify array properties
    assert pixel_array.dtype == np.float32
    assert pixel_array.shape == (512, 512)

    # Verify rescale was applied (CT Hounsfield Units)
    # Original pixel values: arange creates 0 to 262143, but uint16 wraps at 65536
    # So actual max value stored is (262143 % 65536) = 65535
    # After rescale: value * 1.0 + (-1024)
    assert pixel_array.min() == -1024.0  # First pixel: 0 * 1.0 - 1024
    expected_max = 65535.0 - 1024.0  # Max uint16 value after rescale
    assert pixel_array.max() == pytest.approx(expected_max)


def test_get_pixel_array_no_rescale(tmp_path):
    """
    Test pixel array extraction without rescale parameters.
    """
    # Create a minimal DICOM file with pixel data but no rescale
    file_meta = Dataset()
    file_meta.MediaStorageSOPClassUID = '1.2.840.10008.5.1.4.1.1.2'
    file_meta.MediaStorageSOPInstanceUID = generate_uid()
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    file_meta.ImplementationClassUID = generate_uid()

    ds = FileDataset("test.dcm", {}, file_meta=file_meta, preamble=b"\0" * 128)
    ds.SOPClassUID = file_meta.MediaStorageSOPClassUID
    ds.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
    ds.Rows = 10
    ds.Columns = 10
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.PixelRepresentation = 0
    pixel_data = np.ones((10, 10), dtype=np.uint16) * 100
    ds.PixelData = pixel_data.tobytes()

    # Save and reload to properly initialize pixel_array
    temp_file = tmp_path / "temp_no_rescale.dcm"
    ds.save_as(str(temp_file), write_like_original=False)
    ds_loaded = pydicom.dcmread(str(temp_file))

    pixel_array = get_pixel_array(ds_loaded)

    # Should return array without rescale transformation
    assert pixel_array.dtype == np.float32
    assert np.all(pixel_array == 100.0)


def test_get_pixel_array_missing_data():
    """
    Test error handling when pixel data is missing.
    """
    ds = Dataset()
    # No pixel data

    with pytest.raises(ValueError, match="does not contain pixel data"):
        get_pixel_array(ds)


def test_apply_window_level_default():
    """
    Test window/level transformation with default preset.
    Verifies soft tissue window (W=400, L=40) is applied correctly.
    """
    # Create test pixel array with known values
    pixel_array = np.array([
        [-1024, -160, 40, 240, 3071]  # Air, fat, soft tissue, contrast, bone
    ], dtype=np.float32)

    windowed = apply_window_level(pixel_array, preset="default")

    # Verify output is uint8
    assert windowed.dtype == np.uint8

    # Window center=40, width=400 means range [-160, 240]
    # Values outside this range should be clipped
    assert windowed[0, 0] == 0    # -1024 < -160 → clipped to 0
    assert windowed[0, 1] == 0    # -160 = lower bound → 0
    assert windowed[0, 2] == 127  # 40 = center → ~127
    assert windowed[0, 3] == 255  # 240 = upper bound → 255
    assert windowed[0, 4] == 255  # 3071 > 240 → clipped to 255


def test_apply_window_level_lung():
    """
    Test window/level transformation with lung preset.
    Verifies lung window (W=1500, L=-600) for viewing lung parenchyma.
    """
    # Create test array with lung-relevant values
    pixel_array = np.array([[-1024, -600, 0, 500]], dtype=np.float32)

    windowed = apply_window_level(pixel_array, preset="lung")

    # Verify transformation applied
    assert windowed.dtype == np.uint8
    # Lung window: center=-600, width=1500 → range [-1350, 150]
    assert windowed[0, 1] == 127  # -600 is center → ~127


def test_apply_window_level_custom():
    """
    Test window/level transformation with custom values.
    """
    pixel_array = np.array([[0, 500, 1000]], dtype=np.float32)

    windowed = apply_window_level(
        pixel_array,
        custom_window=1000,
        custom_level=500
    )

    assert windowed.dtype == np.uint8
    # Custom window: center=500, width=1000 → range [0, 1000]
    assert windowed[0, 1] == 127  # 500 is center → ~127


def test_array_to_png_bytes():
    """
    Test conversion of numpy array to PNG bytes.
    Verifies that output is valid PNG format.
    """
    # Create simple test array
    pixel_array = np.random.randint(0, 256, (100, 100), dtype=np.uint8)

    png_bytes = array_to_png_bytes(pixel_array)

    # Verify output is bytes
    assert isinstance(png_bytes, bytes)

    # Verify PNG signature (first 8 bytes)
    assert png_bytes[:8] == b'\x89PNG\r\n\x1a\n'

    # Verify reasonable size
    assert len(png_bytes) > 100


def test_array_to_png_bytes_float_conversion():
    """
    Test PNG conversion with float array (should be normalized).
    """
    # Create float array
    pixel_array = np.random.random((50, 50)).astype(np.float32)

    png_bytes = array_to_png_bytes(pixel_array)

    # Should successfully convert
    assert isinstance(png_bytes, bytes)
    assert png_bytes[:8] == b'\x89PNG\r\n\x1a\n'


# ============================================================================
# Tests for storage.py
# ============================================================================

def test_save_and_get_studies(test_storage):
    """
    Test saving a study and retrieving it from storage.
    Verifies data persistence and retrieval.
    """
    # Prepare test data
    study_metadata = {
        'study_uid': '1.2.3.4.5',
        'patient_id': 'PAT001',
        'patient_name': 'Test^Patient',
        'study_date': '20250106',
        'modality': 'CT'
    }

    images_metadata = [
        {
            'sop_uid': '1.2.3.4.5.1',
            'instance_number': 1,
            'file_path': '/path/to/image1.dcm'
        },
        {
            'sop_uid': '1.2.3.4.5.2',
            'instance_number': 2,
            'file_path': '/path/to/image2.dcm'
        }
    ]

    # Save study
    test_storage.save_study(study_metadata, images_metadata)

    # Retrieve studies
    studies = test_storage.get_studies()

    # Verify study was saved
    assert len(studies) == 1
    assert studies[0]['study_uid'] == '1.2.3.4.5'
    assert studies[0]['patient_id'] == 'PAT001'
    assert studies[0]['modality'] == 'CT'
    assert len(studies[0]['images']) == 2


def test_filter_studies_by_modality(test_storage):
    """
    Test filtering studies by modality.
    Verifies that modality filter returns only matching studies.
    """
    # Save CT study
    ct_study = {
        'study_uid': '1.2.3.1',
        'patient_id': 'PAT001',
        'patient_name': 'Test^Patient1',
        'study_date': '20250106',
        'modality': 'CT'
    }
    test_storage.save_study(ct_study, [
        {'sop_uid': '1.2.3.1.1', 'instance_number': 1, 'file_path': '/path/ct.dcm'}
    ])

    # Save MR study
    mr_study = {
        'study_uid': '1.2.3.2',
        'patient_id': 'PAT002',
        'patient_name': 'Test^Patient2',
        'study_date': '20250107',
        'modality': 'MR'
    }
    test_storage.save_study(mr_study, [
        {'sop_uid': '1.2.3.2.1', 'instance_number': 1, 'file_path': '/path/mr.dcm'}
    ])

    # Test CT filter
    ct_studies = test_storage.get_studies(modality='CT')
    assert len(ct_studies) == 1
    assert ct_studies[0]['modality'] == 'CT'

    # Test MR filter
    mr_studies = test_storage.get_studies(modality='MR')
    assert len(mr_studies) == 1
    assert mr_studies[0]['modality'] == 'MR'

    # Test no filter (all studies)
    all_studies = test_storage.get_studies()
    assert len(all_studies) == 2


def test_get_image_metadata(test_storage):
    """
    Test retrieving specific image metadata by SOP UID.
    """
    # Save study with images
    study_metadata = {
        'study_uid': '1.2.3.4',
        'patient_id': 'PAT001',
        'patient_name': 'Test^Patient',
        'study_date': '20250106',
        'modality': 'CT'
    }
    images_metadata = [
        {
            'sop_uid': '1.2.3.4.1',
            'instance_number': 1,
            'file_path': '/path/to/image1.dcm'
        }
    ]
    test_storage.save_study(study_metadata, images_metadata)

    # Retrieve image metadata
    image = test_storage.get_image_metadata('1.2.3.4.1')

    # Verify image data
    assert image is not None
    assert image['sop_uid'] == '1.2.3.4.1'
    assert image['instance_number'] == 1
    assert image['file_path'] == '/path/to/image1.dcm'
    assert image['study_uid'] == '1.2.3.4'
    assert image['patient_id'] == 'PAT001'


def test_get_image_metadata_not_found(test_storage):
    """
    Test retrieving non-existent image metadata returns None.
    """
    image = test_storage.get_image_metadata('non.existent.uid')
    assert image is None


def test_copy_dicom_file(test_storage, test_dicom_file):
    """
    Test copying DICOM file to storage directory.
    Verifies file is copied and renamed correctly.
    """
    sop_uid = '1.2.3.4.5.6.7'

    # Copy file
    destination = test_storage.copy_dicom_file(str(test_dicom_file), sop_uid)

    # Verify destination path
    assert destination.endswith(f"{sop_uid}.dcm")

    # Verify file exists
    assert Path(destination).exists()

    # Verify file content matches
    original_size = test_dicom_file.stat().st_size
    copied_size = Path(destination).stat().st_size
    assert original_size == copied_size


def test_copy_dicom_file_not_found(test_storage):
    """
    Test error handling when source file doesn't exist.
    """
    with pytest.raises(FileNotFoundError):
        test_storage.copy_dicom_file('/nonexistent/file.dcm', 'some.uid')


def test_storage_persistence(tmp_path):
    """
    Test that storage data persists across instances.
    """
    json_path = tmp_path / "persist_test.json"
    files_dir = tmp_path / "persist_files"

    # Create storage and save data
    storage1 = JSONStorage(json_path=str(json_path), files_dir=str(files_dir))
    study = {
        'study_uid': '1.2.3',
        'patient_id': 'PAT001',
        'patient_name': 'Test',
        'study_date': '20250106',
        'modality': 'CT'
    }
    storage1.save_study(study, [
        {'sop_uid': '1.2.3.1', 'instance_number': 1, 'file_path': '/test.dcm'}
    ])

    # Create new storage instance with same path
    storage2 = JSONStorage(json_path=str(json_path), files_dir=str(files_dir))

    # Verify data was loaded
    studies = storage2.get_studies()
    assert len(studies) == 1
    assert studies[0]['study_uid'] == '1.2.3'


# ============================================================================
# Tests for api.py
# ============================================================================

def test_api_root(client):
    """
    Test API root endpoint returns information.
    """
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data['name'] == "DICOM Workstation Lite API"
    assert 'endpoints' in data


def test_health_check(client):
    """
    Test health check endpoint.
    """
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()['status'] == "healthy"


def test_upload_dicom_files(client, test_dicom_file):
    """
    Test uploading DICOM files via API.
    Verifies file upload, processing, and storage.
    """
    # Read DICOM file
    with open(test_dicom_file, 'rb') as f:
        file_content = f.read()

    # Upload file
    files = {
        'files': ('test.dcm', file_content, 'application/dicom')
    }
    response = client.post("/upload", files=files)

    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]['num_files'] == 1
    assert 'study_uid' in data[0]
    assert 'Successfully uploaded' in data[0]['message']


def test_upload_invalid_file(client):
    """
    Test uploading non-DICOM file returns error.
    """
    # Create fake file
    files = {
        'files': ('test.txt', b'This is not a DICOM file', 'text/plain')
    }
    response = client.post("/upload", files=files)

    # Should return error
    assert response.status_code == 400
    assert 'Invalid DICOM' in response.json()['detail']


def test_get_studies_list(client, test_dicom_file):
    """
    Test retrieving list of studies.
    """
    # First upload a study
    with open(test_dicom_file, 'rb') as f:
        files = {'files': ('test.dcm', f.read(), 'application/dicom')}
    client.post("/upload", files=files)

    # Get studies list
    response = client.get("/studies")
    assert response.status_code == 200

    studies = response.json()
    assert len(studies) >= 1
    assert 'study_uid' in studies[0]
    assert 'patient_id' in studies[0]
    assert 'num_images' in studies[0]


def test_get_studies_filter_modality(client, test_dicom_file):
    """
    Test filtering studies by modality.
    """
    # Upload CT study
    with open(test_dicom_file, 'rb') as f:
        files = {'files': ('test.dcm', f.read(), 'application/dicom')}
    client.post("/upload", files=files)

    # Filter by CT
    response = client.get("/studies?modality=CT")
    assert response.status_code == 200
    studies = response.json()
    assert all(s['modality'] == 'CT' for s in studies)

    # Filter by MR (should be empty)
    response = client.get("/studies?modality=MR")
    assert response.status_code == 200
    assert len(response.json()) == 0


def test_get_study_detail(client, test_dicom_file):
    """
    Test retrieving detailed study information.
    """
    # Upload study
    with open(test_dicom_file, 'rb') as f:
        files = {'files': ('test.dcm', f.read(), 'application/dicom')}
    upload_response = client.post("/upload", files=files)
    study_uid = upload_response.json()[0]['study_uid']

    # Get study detail
    response = client.get(f"/studies/{study_uid}")
    assert response.status_code == 200

    study = response.json()
    assert study['study_uid'] == study_uid
    assert 'images' in study
    assert len(study['images']) >= 1


def test_get_study_detail_not_found(client):
    """
    Test retrieving non-existent study returns 404.
    """
    response = client.get("/studies/nonexistent.uid")
    assert response.status_code == 404


def test_get_image_png(client, test_dicom_file):
    """
    Test retrieving image as PNG with window/level preset.
    """
    # Upload study
    with open(test_dicom_file, 'rb') as f:
        files = {'files': ('test.dcm', f.read(), 'application/dicom')}
    upload_response = client.post("/upload", files=files)
    study_uid = upload_response.json()[0]['study_uid']

    # Get study to find SOP UID
    study_response = client.get(f"/studies/{study_uid}")
    sop_uid = study_response.json()['images'][0]['sop_uid']

    # Get image as PNG
    response = client.get(f"/image/{sop_uid}?preset=default")
    assert response.status_code == 200
    assert response.headers['content-type'] == 'image/png'

    # Verify PNG signature
    content = response.content
    assert content[:8] == b'\x89PNG\r\n\x1a\n'


def test_get_image_png_lung_preset(client, test_dicom_file):
    """
    Test retrieving image with lung window preset.
    """
    # Upload and get SOP UID
    with open(test_dicom_file, 'rb') as f:
        files = {'files': ('test.dcm', f.read(), 'application/dicom')}
    upload_response = client.post("/upload", files=files)
    study_uid = upload_response.json()[0]['study_uid']
    study_response = client.get(f"/studies/{study_uid}")
    sop_uid = study_response.json()['images'][0]['sop_uid']

    # Get image with lung preset
    response = client.get(f"/image/{sop_uid}?preset=lung")
    assert response.status_code == 200
    assert response.headers['content-type'] == 'image/png'


def test_get_image_not_found(client):
    """
    Test retrieving non-existent image returns 404.
    """
    response = client.get("/image/nonexistent.uid")
    assert response.status_code == 404
