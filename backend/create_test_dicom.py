"""
Utility script to generate synthetic DICOM CT images for testing purposes.
"""

import os
from datetime import datetime
import numpy as np
import pydicom
from pydicom.dataset import Dataset, FileDataset
from pydicom.uid import generate_uid, ExplicitVRLittleEndian


def create_synthetic_dicom(output_path, patient_id, study_uid, series_uid, instance_number):
    """
    Create a valid DICOM CT file with synthetic data.

    Args:
        output_path: Path where the DICOM file will be saved
        patient_id: Patient identifier
        study_uid: Study Instance UID
        series_uid: Series Instance UID
        instance_number: Instance number for this image
    """
    # Create file meta information
    file_meta = Dataset()
    file_meta.MediaStorageSOPClassUID = '1.2.840.10008.5.1.4.1.1.2'  # CT Image Storage
    file_meta.MediaStorageSOPInstanceUID = generate_uid()
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    file_meta.ImplementationClassUID = generate_uid()

    # Create the main dataset
    ds = FileDataset(output_path, {}, file_meta=file_meta, preamble=b"\0" * 128)

    # Patient information
    ds.PatientName = f"Test^Patient{patient_id}"
    ds.PatientID = f"PAT{patient_id:03d}"
    ds.PatientBirthDate = '19800101'
    ds.PatientSex = 'M'

    # Study information
    ds.StudyInstanceUID = study_uid
    ds.StudyDate = datetime.now().strftime('%Y%m%d')
    ds.StudyTime = datetime.now().strftime('%H%M%S')
    ds.StudyDescription = f"Test CT Study {patient_id}"
    ds.AccessionNumber = f"ACC{patient_id:05d}"

    # Series information
    ds.SeriesInstanceUID = series_uid
    ds.SeriesNumber = 1
    ds.SeriesDescription = "Test CT Series"
    ds.Modality = "CT"

    # Instance information
    ds.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
    ds.SOPClassUID = file_meta.MediaStorageSOPClassUID
    ds.InstanceNumber = instance_number

    # Image pixel information
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.Rows = 512
    ds.Columns = 512
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 0  # Unsigned

    # CT-specific tags
    ds.RescaleIntercept = -1024
    ds.RescaleSlope = 1
    ds.SliceThickness = 5.0
    ds.KVP = 120

    # Generate random grayscale pixel data (simulating CT hounsfield units)
    # CT values typically range from -1024 (air) to 3071 (bone)
    pixel_array = np.random.randint(0, 4096, size=(512, 512), dtype=np.uint16)
    ds.PixelData = pixel_array.tobytes()

    # Save the DICOM file
    ds.save_as(output_path, write_like_original=False)
    print(f"Created: {output_path}")


def create_test_dataset(output_dir, num_studies=2, images_per_study=5):
    """
    Create a test dataset with multiple studies and images.

    Args:
        output_dir: Directory where test DICOM files will be saved
        num_studies: Number of patient studies to create
        images_per_study: Number of images per study
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    print(f"Generating {num_studies} studies with {images_per_study} images each...")

    # Generate studies for different patients
    for patient_num in range(1, num_studies + 1):
        # Generate unique UIDs for this study
        study_uid = generate_uid()
        series_uid = generate_uid()

        # Create patient directory
        patient_dir = os.path.join(output_dir, f"patient_{patient_num:03d}")
        os.makedirs(patient_dir, exist_ok=True)

        print(f"\nPatient {patient_num}:")

        # Generate multiple images for this study
        for img_num in range(1, images_per_study + 1):
            output_path = os.path.join(patient_dir, f"image_{img_num:03d}.dcm")
            create_synthetic_dicom(
                output_path=output_path,
                patient_id=patient_num,
                study_uid=study_uid,
                series_uid=series_uid,
                instance_number=img_num
            )

    print(f"\n✓ Test dataset created successfully in: {output_dir}")
    print(f"  Total files: {num_studies * images_per_study}")


if __name__ == "__main__":
    # Generate test dataset in data/test_dicom/ directory
    output_directory = os.path.join(os.path.dirname(__file__), "..", "data", "test_dicom")
    create_test_dataset(output_directory, num_studies=2, images_per_study=5)
