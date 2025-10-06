"""
FastAPI REST API for DICOM Workstation Lite.
Provides endpoints for uploading, retrieving, and viewing DICOM studies and images.
"""

from typing import List, Optional
from pathlib import Path
import tempfile
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import pydicom
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import io

from backend.storage import JSONStorage
from backend.dicom_processor import (
    extract_metadata,
    get_pixel_array,
    apply_window_level,
    array_to_png_bytes
)


# FastAPI application setup
app = FastAPI(
    title="DICOM Workstation Lite API",
    version="1.0.0",
    description="REST API for medical DICOM image management and viewing"
)

# CORS middleware for development (allow frontend to make requests)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic models for request/response validation
class UploadResponse(BaseModel):
    """Response model for file upload endpoint."""
    study_uid: str
    patient_id: str
    num_files: int
    message: str


class StudySummary(BaseModel):
    """Summary model for study list (without images)."""
    study_uid: str
    patient_id: str
    patient_name: str
    study_date: str
    modality: str
    num_images: int


class ImageMetadata(BaseModel):
    """Model for image metadata."""
    sop_uid: str
    instance_number: int
    file_path: str


class StudyDetail(BaseModel):
    """Detailed study model with images."""
    study_uid: str
    patient_id: str
    patient_name: str
    study_date: str
    modality: str
    images: List[ImageMetadata]


# Dependency injection for storage
def get_storage() -> JSONStorage:
    """
    Dependency that returns a JSONStorage instance.

    Returns:
        JSONStorage instance for data persistence
    """
    return JSONStorage()


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "DICOM Workstation Lite API",
        "version": "1.0.0",
        "endpoints": {
            "upload": "POST /upload",
            "studies": "GET /studies",
            "study_detail": "GET /studies/{study_uid}",
            "image": "GET /image/{sop_uid}?preset=default"
        }
    }


@app.post("/upload", response_model=List[UploadResponse])
async def upload_dicom_files(
    files: List[UploadFile] = File(...),
    storage: JSONStorage = Depends(get_storage)
):
    """
    Upload multiple DICOM files.

    Files are parsed, validated, and stored with their metadata.
    Images are automatically grouped by study.

    Args:
        files: List of DICOM files to upload
        storage: JSONStorage instance (injected)

    Returns:
        List of upload responses, one per study

    Raises:
        HTTPException: If files are invalid or upload fails
    """
    try:
        # Dictionary to group images by study
        studies_data = {}

        # Process each uploaded file
        for file in files:
            try:
                # Read file content
                content = await file.read()

                # Create temporary file for pydicom
                with tempfile.NamedTemporaryFile(delete=False, suffix='.dcm') as tmp_file:
                    tmp_file.write(content)
                    tmp_path = tmp_file.name

                # Parse DICOM file
                try:
                    ds = pydicom.dcmread(tmp_path)
                except Exception as e:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid DICOM file '{file.filename}': {str(e)}"
                    )

                # Extract metadata
                metadata = extract_metadata(ds)

                # Validate required fields
                if not metadata.get('study_uid'):
                    raise HTTPException(
                        status_code=400,
                        detail=f"Missing StudyInstanceUID in '{file.filename}'"
                    )
                if not metadata.get('sop_uid'):
                    raise HTTPException(
                        status_code=400,
                        detail=f"Missing SOPInstanceUID in '{file.filename}'"
                    )

                # Copy file to storage
                sop_uid = metadata['sop_uid']
                destination = storage.copy_dicom_file(tmp_path, sop_uid)

                # Group by study
                study_uid = metadata['study_uid']
                if study_uid not in studies_data:
                    studies_data[study_uid] = {
                        'study_metadata': {
                            'study_uid': study_uid,
                            'patient_id': metadata.get('patient_id', 'UNKNOWN'),
                            'patient_name': metadata.get('patient_name', 'Unknown'),
                            'study_date': metadata.get('study_date', ''),
                            'modality': metadata.get('modality', 'OT'),
                        },
                        'images': []
                    }

                # Add image metadata
                studies_data[study_uid]['images'].append({
                    'sop_uid': sop_uid,
                    'instance_number': metadata.get('instance_number', 0),
                    'file_path': destination
                })

                # Clean up temporary file
                Path(tmp_path).unlink(missing_ok=True)

            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Error processing file '{file.filename}': {str(e)}"
                )

        # Save all studies to storage
        responses = []
        for study_uid, study_data in studies_data.items():
            try:
                storage.save_study(
                    study_data['study_metadata'],
                    study_data['images']
                )

                responses.append(UploadResponse(
                    study_uid=study_uid,
                    patient_id=study_data['study_metadata']['patient_id'],
                    num_files=len(study_data['images']),
                    message=f"Successfully uploaded {len(study_data['images'])} images"
                ))
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Error saving study {study_uid}: {str(e)}"
                )

        return responses

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Upload failed: {str(e)}"
        )


@app.get("/studies", response_model=List[StudySummary])
async def get_studies(
    modality: Optional[str] = Query(None, description="Filter by modality (e.g., 'CT', 'MR')"),
    storage: JSONStorage = Depends(get_storage)
):
    """
    Get list of all studies, optionally filtered by modality.

    Returns summary information without full image list for performance.

    Args:
        modality: Optional modality filter (CT, MR, etc.)
        storage: JSONStorage instance (injected)

    Returns:
        List of study summaries
    """
    try:
        # Get studies from storage
        studies = storage.get_studies(modality=modality)

        # Convert to summary format (exclude full image list)
        summaries = []
        for study in studies:
            summaries.append(StudySummary(
                study_uid=study['study_uid'],
                patient_id=study['patient_id'],
                patient_name=study['patient_name'],
                study_date=study['study_date'],
                modality=study['modality'],
                num_images=len(study.get('images', []))
            ))

        return summaries

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving studies: {str(e)}"
        )


@app.get("/studies/{study_uid}", response_model=StudyDetail)
async def get_study_detail(
    study_uid: str,
    storage: JSONStorage = Depends(get_storage)
):
    """
    Get detailed information for a specific study, including all images.

    Args:
        study_uid: Study Instance UID
        storage: JSONStorage instance (injected)

    Returns:
        Complete study details with image list

    Raises:
        HTTPException 404: If study not found
    """
    try:
        # Get all studies and find the requested one
        studies = storage.get_studies()

        for study in studies:
            if study['study_uid'] == study_uid:
                # Convert images to Pydantic models
                images = [
                    ImageMetadata(**img)
                    for img in study.get('images', [])
                ]

                return StudyDetail(
                    study_uid=study['study_uid'],
                    patient_id=study['patient_id'],
                    patient_name=study['patient_name'],
                    study_date=study['study_date'],
                    modality=study['modality'],
                    images=images
                )

        # Study not found
        raise HTTPException(
            status_code=404,
            detail=f"Study with UID '{study_uid}' not found"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving study: {str(e)}"
        )


@app.get("/image/{sop_uid}")
async def get_image(
    sop_uid: str,
    preset: str = Query("default", description="Window/level preset: default, lung, bone, brain, liver"),
    storage: JSONStorage = Depends(get_storage)
):
    """
    Get DICOM image as PNG with window/level applied.

    Args:
        sop_uid: SOP Instance UID of the image
        preset: Window/level preset name
        storage: JSONStorage instance (injected)

    Returns:
        StreamingResponse with PNG image

    Raises:
        HTTPException 404: If image not found
        HTTPException 500: If image processing fails
    """
    try:
        # Get image metadata from storage
        image_metadata = storage.get_image_metadata(sop_uid)

        if not image_metadata:
            raise HTTPException(
                status_code=404,
                detail=f"Image with SOP UID '{sop_uid}' not found"
            )

        # Get file path
        file_path = image_metadata.get('file_path')
        if not file_path or not Path(file_path).exists():
            raise HTTPException(
                status_code=404,
                detail=f"Image file not found: {file_path}"
            )

        # Load DICOM file
        try:
            ds = pydicom.dcmread(file_path)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error reading DICOM file: {str(e)}"
            )

        # Process image
        try:
            # Extract pixel array
            pixel_array = get_pixel_array(ds)

            # Apply window/level
            windowed = apply_window_level(pixel_array, preset=preset)

            # Convert to PNG bytes
            png_bytes = array_to_png_bytes(windowed)

        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error processing image: {str(e)}"
            )

        # Return as streaming response
        return StreamingResponse(
            io.BytesIO(png_bytes),
            media_type="image/png",
            headers={
                "Content-Disposition": f"inline; filename={sop_uid}.png"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving image: {str(e)}"
        )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "DICOM Workstation Lite API"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
