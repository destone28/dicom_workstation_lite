"""
DICOM file processing and image manipulation utilities.
Provides functions for extracting metadata, processing pixel data, and applying imaging transformations.
"""

import io
from typing import Dict, Optional
import numpy as np
import pydicom
from PIL import Image


# Window/Level presets for different tissue types
WINDOW_PRESETS = {
    "default": {"window": 400, "level": 40},      # Soft tissue
    "lung": {"window": 1500, "level": -600},      # Lung parenchyma
    "bone": {"window": 2000, "level": 300},       # Bone
    "brain": {"window": 80, "level": 40},         # Brain tissue
    "liver": {"window": 150, "level": 30},        # Liver
}


def extract_metadata(dicom_dataset: pydicom.Dataset) -> Dict[str, Optional[str]]:
    """
    Extract essential DICOM tags from a dataset.

    Args:
        dicom_dataset: PyDICOM Dataset object

    Returns:
        Dictionary containing essential metadata with keys:
            - patient_id: Patient identifier
            - patient_name: Patient name
            - study_uid: Study Instance UID
            - study_date: Study date (YYYYMMDD format)
            - study_time: Study time (HHMMSS format)
            - modality: Imaging modality (CT, MR, etc.)
            - series_uid: Series Instance UID
            - sop_uid: SOP Instance UID
            - instance_number: Instance number

    Example:
        >>> import pydicom
        >>> ds = pydicom.dcmread('image.dcm')
        >>> metadata = extract_metadata(ds)
        >>> print(metadata['patient_id'])
        'PAT001'
    """
    try:
        metadata = {
            # Patient information
            'patient_id': getattr(dicom_dataset, 'PatientID', None),
            'patient_name': str(getattr(dicom_dataset, 'PatientName', 'Unknown')),

            # Study information
            'study_uid': getattr(dicom_dataset, 'StudyInstanceUID', None),
            'study_date': getattr(dicom_dataset, 'StudyDate', None),
            'study_time': getattr(dicom_dataset, 'StudyTime', None),
            'study_description': getattr(dicom_dataset, 'StudyDescription', None),

            # Series information
            'modality': getattr(dicom_dataset, 'Modality', None),
            'series_uid': getattr(dicom_dataset, 'SeriesInstanceUID', None),
            'series_number': getattr(dicom_dataset, 'SeriesNumber', None),
            'series_description': getattr(dicom_dataset, 'SeriesDescription', None),

            # Instance information
            'sop_uid': getattr(dicom_dataset, 'SOPInstanceUID', None),
            'instance_number': getattr(dicom_dataset, 'InstanceNumber', None),

            # Image information
            'rows': getattr(dicom_dataset, 'Rows', None),
            'columns': getattr(dicom_dataset, 'Columns', None),
        }

        return metadata

    except Exception as e:
        print(f"Error extracting metadata: {e}")
        # Return minimal structure on error
        return {
            'patient_id': None,
            'patient_name': 'Unknown',
            'study_uid': None,
            'study_date': None,
            'study_time': None,
            'modality': None,
            'series_uid': None,
            'sop_uid': None,
            'instance_number': None,
        }


def get_pixel_array(dicom_dataset: pydicom.Dataset) -> np.ndarray:
    """
    Extract and process pixel data from DICOM dataset.

    Applies RescaleSlope and RescaleIntercept transformations if present
    (commonly used in CT images to convert to Hounsfield Units).

    Args:
        dicom_dataset: PyDICOM Dataset object containing pixel data

    Returns:
        numpy.ndarray: Float32 array containing processed pixel values

    Raises:
        ValueError: If pixel data is missing or cannot be accessed

    Example:
        >>> import pydicom
        >>> ds = pydicom.dcmread('ct_image.dcm')
        >>> pixels = get_pixel_array(ds)
        >>> print(f"Pixel range: {pixels.min()} to {pixels.max()}")
        Pixel range: -1024.0 to 3071.0
    """
    try:
        # Extract raw pixel array
        if not hasattr(dicom_dataset, 'pixel_array'):
            raise ValueError("DICOM dataset does not contain pixel data")

        pixel_array = dicom_dataset.pixel_array.astype(np.float32)

        # Apply rescale transformation if present (CT Hounsfield Units)
        # Formula: HU = pixel_value * RescaleSlope + RescaleIntercept
        rescale_slope = getattr(dicom_dataset, 'RescaleSlope', 1.0)
        rescale_intercept = getattr(dicom_dataset, 'RescaleIntercept', 0.0)

        if rescale_slope != 1.0 or rescale_intercept != 0.0:
            pixel_array = pixel_array * rescale_slope + rescale_intercept

        return pixel_array

    except AttributeError as e:
        raise ValueError(f"Cannot access pixel data: {e}")
    except Exception as e:
        raise ValueError(f"Error processing pixel data: {e}")


def apply_window_level(
    pixel_array: np.ndarray,
    preset: str = "default",
    custom_window: Optional[int] = None,
    custom_level: Optional[int] = None
) -> np.ndarray:
    """
    Apply window/level (width/center) transformation for image display.

    Window/level transformation maps the full range of pixel values to a displayable
    range (0-255), enhancing contrast for specific tissue types.

    Args:
        pixel_array: Input numpy array with pixel values
        preset: Preset name from WINDOW_PRESETS ('default', 'lung', 'bone', 'brain', 'liver')
        custom_window: Custom window width (overrides preset)
        custom_level: Custom window center/level (overrides preset)

    Returns:
        numpy.ndarray: Uint8 array with values in range [0, 255] suitable for display

    Example:
        >>> pixels = get_pixel_array(ds)
        >>> # Apply lung window for CT
        >>> lung_view = apply_window_level(pixels, preset='lung')
        >>> # Or use custom values
        >>> custom_view = apply_window_level(pixels, custom_window=500, custom_level=50)
    """
    try:
        # Determine window and level values
        if custom_window is not None and custom_level is not None:
            window = custom_window
            level = custom_level
        elif preset in WINDOW_PRESETS:
            window = WINDOW_PRESETS[preset]["window"]
            level = WINDOW_PRESETS[preset]["level"]
        else:
            # Fallback to default preset
            print(f"Unknown preset '{preset}', using 'default'")
            window = WINDOW_PRESETS["default"]["window"]
            level = WINDOW_PRESETS["default"]["level"]

        # Apply window/level transformation
        # Formula: normalized = (pixel - (level - window/2)) / window
        # This maps the window range [level - window/2, level + window/2] to [0, 1]

        # Calculate window bounds
        lower_bound = level - (window / 2.0)
        upper_bound = level + (window / 2.0)

        # Normalize pixel values to [0, 1] range
        windowed = (pixel_array - lower_bound) / window

        # Clip to [0, 1] range (values outside window become black or white)
        windowed = np.clip(windowed, 0.0, 1.0)

        # Scale to [0, 255] for 8-bit display
        windowed = (windowed * 255.0).astype(np.uint8)

        return windowed

    except Exception as e:
        print(f"Error applying window/level: {e}")
        # Return normalized array as fallback
        normalized = ((pixel_array - pixel_array.min()) /
                     (pixel_array.max() - pixel_array.min()) * 255)
        return normalized.astype(np.uint8)


def array_to_png_bytes(pixel_array: np.ndarray) -> bytes:
    """
    Convert numpy array to PNG image bytes.

    Args:
        pixel_array: Numpy array containing image data (should be uint8)

    Returns:
        bytes: PNG image data suitable for HTTP response or file writing

    Raises:
        ValueError: If array cannot be converted to image

    Example:
        >>> pixels = get_pixel_array(ds)
        >>> windowed = apply_window_level(pixels, preset='lung')
        >>> png_bytes = array_to_png_bytes(windowed)
        >>> # Can be sent as HTTP response or saved to file
        >>> with open('output.png', 'wb') as f:
        ...     f.write(png_bytes)
    """
    try:
        # Convert to uint8 if not already
        if pixel_array.dtype != np.uint8:
            # Normalize to 0-255 range
            pixel_min = pixel_array.min()
            pixel_max = pixel_array.max()
            if pixel_max > pixel_min:
                pixel_array = ((pixel_array - pixel_min) /
                              (pixel_max - pixel_min) * 255).astype(np.uint8)
            else:
                pixel_array = np.zeros_like(pixel_array, dtype=np.uint8)

        # Create PIL Image from array (grayscale mode 'L')
        image = Image.fromarray(pixel_array, mode='L')

        # Convert to PNG bytes
        byte_io = io.BytesIO()
        image.save(byte_io, format='PNG')
        png_bytes = byte_io.getvalue()

        return png_bytes

    except Exception as e:
        raise ValueError(f"Error converting array to PNG: {e}")


def resize_image_array(pixel_array: np.ndarray, target_size: tuple[int, int]) -> np.ndarray:
    """
    Resize image array to target dimensions.

    Args:
        pixel_array: Input numpy array
        target_size: Tuple of (width, height)

    Returns:
        numpy.ndarray: Resized array

    Example:
        >>> pixels = get_pixel_array(ds)
        >>> thumbnail = resize_image_array(pixels, (256, 256))
    """
    try:
        # Ensure uint8 for PIL
        if pixel_array.dtype != np.uint8:
            pixel_min = pixel_array.min()
            pixel_max = pixel_array.max()
            pixel_array = ((pixel_array - pixel_min) /
                          (pixel_max - pixel_min) * 255).astype(np.uint8)

        # Use PIL for high-quality resizing
        image = Image.fromarray(pixel_array, mode='L')
        resized = image.resize(target_size, Image.Resampling.LANCZOS)

        return np.array(resized)

    except Exception as e:
        print(f"Error resizing image: {e}")
        raise


if __name__ == "__main__":
    # Example usage with test DICOM files
    import pydicom
    from pathlib import Path

    print("DICOM Processor Module")
    print("=" * 50)

    # Try to load a test DICOM file
    test_dicom_path = Path(__file__).parent.parent / "data" / "test_dicom" / "patient_001" / "image_001.dcm"

    if test_dicom_path.exists():
        print(f"\nLoading test DICOM: {test_dicom_path}")

        # Read DICOM
        ds = pydicom.dcmread(str(test_dicom_path))

        # Extract metadata
        metadata = extract_metadata(ds)
        print("\nMetadata:")
        for key, value in metadata.items():
            print(f"  {key}: {value}")

        # Get pixel array
        pixels = get_pixel_array(ds)
        print(f"\nPixel array shape: {pixels.shape}")
        print(f"Pixel value range: [{pixels.min():.1f}, {pixels.max():.1f}]")

        # Apply different window presets
        print("\nApplying window/level presets:")
        for preset_name in WINDOW_PRESETS:
            windowed = apply_window_level(pixels, preset=preset_name)
            print(f"  {preset_name}: output range [{windowed.min()}, {windowed.max()}]")

        # Convert to PNG
        windowed = apply_window_level(pixels, preset="default")
        png_data = array_to_png_bytes(windowed)
        print(f"\nPNG size: {len(png_data)} bytes")

    else:
        print(f"\nTest DICOM not found at: {test_dicom_path}")
        print("Run backend/create_test_dicom.py first to generate test data")
