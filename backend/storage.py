"""
JSON-based storage manager for DICOM metadata.
Provides persistent storage for study and image metadata with file management.
"""

import json
import shutil
from pathlib import Path
from typing import Optional
from datetime import datetime


class JSONStorage:
    """
    Simple JSON-based storage manager for DICOM studies and images metadata.

    Manages study metadata in a JSON file and stores DICOM files in a dedicated directory.
    """

    def __init__(self, json_path: str = "data/studies.json", files_dir: str = "data/dicom_files"):
        """
        Initialize the storage manager.

        Args:
            json_path: Path to the JSON metadata file
            files_dir: Directory where DICOM files will be stored
        """
        self.json_path = Path(json_path)
        self.files_dir = Path(files_dir)

        # Create directories if they don't exist
        self.json_path.parent.mkdir(parents=True, exist_ok=True)
        self.files_dir.mkdir(parents=True, exist_ok=True)

        # Load existing data or initialize empty structure
        self.data = self._load_data()

    def _load_data(self) -> dict:
        """
        Load existing JSON data or create empty structure.

        Returns:
            Dictionary containing studies data
        """
        try:
            if self.json_path.exists():
                with open(self.json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Ensure proper structure
                    if "studies" not in data:
                        data = {"studies": []}
                    return data
            else:
                # Create empty structure
                return {"studies": []}
        except json.JSONDecodeError as e:
            print(f"Error loading JSON data: {e}. Creating new structure.")
            return {"studies": []}
        except Exception as e:
            print(f"Unexpected error loading data: {e}. Creating new structure.")
            return {"studies": []}

    def _save_data(self) -> None:
        """
        Save data to JSON file using atomic write operation.
        Writes to a temporary file first, then renames to prevent corruption.
        """
        try:
            # Write to temporary file first
            temp_path = self.json_path.with_suffix('.json.tmp')
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)

            # Atomic rename (replaces existing file)
            temp_path.replace(self.json_path)
        except Exception as e:
            print(f"Error saving data: {e}")
            # Clean up temp file if it exists
            if temp_path.exists():
                temp_path.unlink()
            raise

    def save_study(self, study_metadata: dict, images_metadata: list[dict]) -> None:
        """
        Append or update study in JSON file.

        Args:
            study_metadata: Dictionary with study information
                Required keys: study_uid, patient_id, patient_name, study_date, modality
            images_metadata: List of dictionaries with image information
                Required keys per image: sop_uid, instance_number, file_path

        Raises:
            ValueError: If required fields are missing
            Exception: If save operation fails
        """
        # Validate study metadata
        required_study_fields = ['study_uid', 'patient_id', 'patient_name', 'study_date', 'modality']
        for field in required_study_fields:
            if field not in study_metadata:
                raise ValueError(f"Missing required field in study metadata: {field}")

        # Validate images metadata
        required_image_fields = ['sop_uid', 'instance_number', 'file_path']
        for img in images_metadata:
            for field in required_image_fields:
                if field not in img:
                    raise ValueError(f"Missing required field in image metadata: {field}")

        try:
            # Check if study already exists
            study_uid = study_metadata['study_uid']
            existing_study_idx = None

            for idx, study in enumerate(self.data['studies']):
                if study['study_uid'] == study_uid:
                    existing_study_idx = idx
                    break

            # Create study entry
            study_entry = {
                'study_uid': study_metadata['study_uid'],
                'patient_id': study_metadata['patient_id'],
                'patient_name': study_metadata['patient_name'],
                'study_date': study_metadata['study_date'],
                'modality': study_metadata['modality'],
                'images': images_metadata
            }

            # Update or append study
            if existing_study_idx is not None:
                # Update existing study
                self.data['studies'][existing_study_idx] = study_entry
            else:
                # Append new study
                self.data['studies'].append(study_entry)

            # Save to file atomically
            self._save_data()

        except Exception as e:
            print(f"Error saving study: {e}")
            raise

    def get_studies(self, modality: Optional[str] = None) -> list[dict]:
        """
        Return list of all studies, optionally filtered by modality.

        Args:
            modality: Optional modality filter (e.g., 'CT', 'MR')

        Returns:
            List of study dictionaries sorted by study_date descending
        """
        try:
            studies = self.data.get('studies', [])

            # Filter by modality if provided
            if modality:
                studies = [s for s in studies if s.get('modality') == modality]

            # Sort by study_date descending (most recent first)
            # Handle cases where study_date might be missing or in different formats
            def get_sort_key(study):
                date_str = study.get('study_date', '')
                try:
                    # Try to parse DICOM date format (YYYYMMDD)
                    return datetime.strptime(date_str, '%Y%m%d')
                except (ValueError, TypeError):
                    # Return minimum date if parsing fails
                    return datetime.min

            studies_sorted = sorted(studies, key=get_sort_key, reverse=True)
            return studies_sorted

        except Exception as e:
            print(f"Error retrieving studies: {e}")
            return []

    def get_image_metadata(self, sop_uid: str) -> Optional[dict]:
        """
        Find and return image metadata by SOP Instance UID.

        Args:
            sop_uid: SOP Instance UID to search for

        Returns:
            Dictionary containing image metadata, or None if not found
        """
        try:
            # Search through all studies and their images
            for study in self.data.get('studies', []):
                for image in study.get('images', []):
                    if image.get('sop_uid') == sop_uid:
                        # Return image metadata with study context
                        return {
                            **image,
                            'study_uid': study.get('study_uid'),
                            'patient_id': study.get('patient_id'),
                            'patient_name': study.get('patient_name')
                        }

            # Not found
            return None

        except Exception as e:
            print(f"Error retrieving image metadata: {e}")
            return None

    def copy_dicom_file(self, source_path: str, sop_uid: str) -> str:
        """
        Copy DICOM file to storage directory with standardized naming.

        Args:
            source_path: Path to the source DICOM file
            sop_uid: SOP Instance UID to use as filename

        Returns:
            Destination path where file was copied

        Raises:
            FileNotFoundError: If source file doesn't exist
            Exception: If copy operation fails
        """
        try:
            source = Path(source_path)

            # Verify source file exists
            if not source.exists():
                raise FileNotFoundError(f"Source file not found: {source_path}")

            # Create destination path with SOP UID as filename
            destination = self.files_dir / f"{sop_uid}.dcm"

            # Copy file
            shutil.copy2(source, destination)

            # Return destination path as string
            return str(destination)

        except FileNotFoundError:
            raise
        except Exception as e:
            print(f"Error copying DICOM file: {e}")
            raise


if __name__ == "__main__":
    # Example usage
    storage = JSONStorage()

    # Example: Save a study
    study_meta = {
        'study_uid': '1.2.3.4.5.6.7.8.9',
        'patient_id': 'PAT001',
        'patient_name': 'Test^Patient',
        'study_date': '20250106',
        'modality': 'CT'
    }

    images_meta = [
        {
            'sop_uid': '1.2.3.4.5.6.7.8.9.1',
            'instance_number': 1,
            'file_path': 'data/dicom_files/1.2.3.4.5.6.7.8.9.1.dcm'
        }
    ]

    print("Storage manager initialized successfully")
    print(f"JSON path: {storage.json_path}")
    print(f"Files directory: {storage.files_dir}")
