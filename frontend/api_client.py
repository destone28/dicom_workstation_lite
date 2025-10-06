"""
REST API client for communicating with the DICOM Workstation Lite backend.
Provides methods for uploading files, retrieving studies, and fetching images.
"""

from pathlib import Path
from typing import List, Dict, Optional
import requests


class APIClient:
    """
    Client for interacting with the DICOM Workstation Lite REST API.

    Manages HTTP connections and provides convenient methods for all API endpoints.
    """

    def __init__(self, base_url: str = "http://localhost:8000"):
        """
        Initialize the API client.

        Args:
            base_url: Base URL of the backend API (default: http://localhost:8000)
        """
        self.base_url = base_url.rstrip('/')
        # Use session for connection pooling and performance
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'DICOM-Workstation-Lite-Frontend/1.0'
        })

    def upload_files(self, file_paths: List[Path]) -> List[Dict]:
        """
        Upload multiple DICOM files to the backend.

        Args:
            file_paths: List of Path objects pointing to DICOM files

        Returns:
            List of dictionaries containing upload results:
                [{study_uid, patient_id, num_files, message}, ...]

        Raises:
            ValueError: If file_paths is empty or files don't exist
            requests.RequestException: If upload fails
            RuntimeError: If server returns an error response

        Example:
            >>> client = APIClient()
            >>> files = [Path('image1.dcm'), Path('image2.dcm')]
            >>> results = client.upload_files(files)
            >>> print(results[0]['study_uid'])
        """
        if not file_paths:
            raise ValueError("No files provided for upload")

        # Verify all files exist
        for file_path in file_paths:
            if not file_path.exists():
                raise ValueError(f"File not found: {file_path}")

        try:
            # Prepare multipart form data
            files = []
            for file_path in file_paths:
                files.append(
                    ('files', (file_path.name, open(file_path, 'rb'), 'application/dicom'))
                )

            # Upload files
            url = f"{self.base_url}/upload"
            response = self.session.post(url, files=files, timeout=30)

            # Close all file handles
            for _, (_, file_handle, _) in files:
                file_handle.close()

            # Check response status
            if response.status_code == 200:
                return response.json()
            else:
                error_detail = response.json().get('detail', 'Unknown error')
                raise RuntimeError(f"Upload failed: {error_detail}")

        except requests.RequestException as e:
            raise RuntimeError(f"Network error during upload: {str(e)}")

    def get_studies(self, modality: Optional[str] = None) -> List[Dict]:
        """
        Retrieve list of all studies, optionally filtered by modality.

        Args:
            modality: Optional modality filter (e.g., 'CT', 'MR', 'US')

        Returns:
            List of study summary dictionaries:
                [{study_uid, patient_id, patient_name, study_date, modality, num_images}, ...]

        Raises:
            requests.RequestException: If request fails
            RuntimeError: If server returns an error response

        Example:
            >>> client = APIClient()
            >>> ct_studies = client.get_studies(modality='CT')
            >>> for study in ct_studies:
            ...     print(f"{study['patient_name']} - {study['study_date']}")
        """
        try:
            url = f"{self.base_url}/studies"
            params = {}
            if modality:
                params['modality'] = modality

            response = self.session.get(url, params=params, timeout=10)

            if response.status_code == 200:
                return response.json()
            else:
                error_detail = response.json().get('detail', 'Unknown error')
                raise RuntimeError(f"Failed to retrieve studies: {error_detail}")

        except requests.RequestException as e:
            raise RuntimeError(f"Network error retrieving studies: {str(e)}")

    def get_study_detail(self, study_uid: str) -> Dict:
        """
        Retrieve detailed information for a specific study.

        Args:
            study_uid: Study Instance UID

        Returns:
            Dictionary containing complete study information:
                {study_uid, patient_id, patient_name, study_date, modality,
                 images: [{sop_uid, instance_number, file_path}, ...]}

        Raises:
            ValueError: If study_uid is empty
            requests.RequestException: If request fails
            RuntimeError: If study not found or server error

        Example:
            >>> client = APIClient()
            >>> study = client.get_study_detail('1.2.3.4.5.6')
            >>> print(f"Study has {len(study['images'])} images")
        """
        if not study_uid:
            raise ValueError("study_uid cannot be empty")

        try:
            url = f"{self.base_url}/studies/{study_uid}"
            response = self.session.get(url, timeout=10)

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                raise RuntimeError(f"Study not found: {study_uid}")
            else:
                error_detail = response.json().get('detail', 'Unknown error')
                raise RuntimeError(f"Failed to retrieve study detail: {error_detail}")

        except requests.RequestException as e:
            raise RuntimeError(f"Network error retrieving study detail: {str(e)}")

    def get_image_bytes(self, sop_uid: str, preset: str = "default") -> bytes:
        """
        Retrieve DICOM image as PNG bytes with window/level preset applied.

        Args:
            sop_uid: SOP Instance UID of the image
            preset: Window/level preset name (default, lung, bone, brain, liver)

        Returns:
            PNG image data as bytes

        Raises:
            ValueError: If sop_uid is empty
            requests.RequestException: If request fails
            RuntimeError: If image not found or server error

        Example:
            >>> client = APIClient()
            >>> png_data = client.get_image_bytes('1.2.3.4.5.6.7', preset='lung')
            >>> with open('image.png', 'wb') as f:
            ...     f.write(png_data)
        """
        if not sop_uid:
            raise ValueError("sop_uid cannot be empty")

        try:
            url = f"{self.base_url}/image/{sop_uid}"
            params = {'preset': preset}

            response = self.session.get(url, params=params, timeout=15)

            if response.status_code == 200:
                # Return raw bytes
                return response.content
            elif response.status_code == 404:
                raise RuntimeError(f"Image not found: {sop_uid}")
            else:
                # Try to get error detail from JSON
                try:
                    error_detail = response.json().get('detail', 'Unknown error')
                except Exception:
                    error_detail = f"HTTP {response.status_code}"
                raise RuntimeError(f"Failed to retrieve image: {error_detail}")

        except requests.RequestException as e:
            raise RuntimeError(f"Network error retrieving image: {str(e)}")

    def check_connection(self) -> bool:
        """
        Check if the backend API is accessible.

        Returns:
            True if backend is reachable and responding, False otherwise

        Example:
            >>> client = APIClient()
            >>> if client.check_connection():
            ...     print("Backend is online")
            ... else:
            ...     print("Cannot connect to backend")
        """
        try:
            # Try to get studies list (lightweight operation)
            url = f"{self.base_url}/health"
            response = self.session.get(url, timeout=5)
            return response.status_code == 200

        except requests.RequestException:
            # Connection failed
            return False

    def get_available_presets(self) -> List[str]:
        """
        Get list of available window/level presets.

        Returns:
            List of preset names

        Note:
            This is a client-side method returning known presets.
            Actual presets are defined in backend/dicom_processor.py
        """
        return ["default", "lung", "bone", "brain", "liver"]

    def close(self):
        """
        Close the HTTP session.

        Should be called when done using the client to free resources.
        """
        if self.session:
            self.session.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - close session."""
        self.close()


if __name__ == "__main__":
    # Example usage
    import sys

    print("DICOM Workstation Lite - API Client")
    print("=" * 50)

    # Initialize client
    client = APIClient()

    # Check connection
    print("\nChecking backend connection...")
    if client.check_connection():
        print("✓ Backend is online")

        # Get studies
        try:
            studies = client.get_studies()
            print(f"\n✓ Found {len(studies)} studies")

            if studies:
                print("\nFirst study:")
                study = studies[0]
                print(f"  Patient: {study['patient_name']}")
                print(f"  Date: {study['study_date']}")
                print(f"  Modality: {study['modality']}")
                print(f"  Images: {study['num_images']}")

        except Exception as e:
            print(f"✗ Error retrieving studies: {e}")

    else:
        print("✗ Cannot connect to backend")
        print("  Make sure the backend is running at http://localhost:8000")
        sys.exit(1)

    # Available presets
    print(f"\nAvailable window presets: {', '.join(client.get_available_presets())}")

    client.close()
