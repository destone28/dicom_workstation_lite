# 🏥 DICOM Workstation Lite

> Professional medical imaging viewer with FastAPI backend and PyQt6 GUI

![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Tests](https://img.shields.io/badge/tests-51%20passing-brightgreen.svg)
![Coverage](https://img.shields.io/badge/coverage-58%25-yellow.svg)

A lightweight, cross-platform DICOM medical image viewer designed for educational purposes and rapid prototyping. Features a modern FastAPI backend with a responsive PyQt6 desktop interface.

---

## ✨ Features

### Backend Capabilities
- 🔌 **RESTful API** with FastAPI and automatic OpenAPI documentation
- 📁 **DICOM File Processing** using PyDICOM for metadata extraction
- 🖼️ **Image Processing** with configurable window/level presets
- 💾 **JSON-based Storage** for study metadata and file management
- 🔄 **Real-time Image Conversion** to PNG with multiple viewing presets
- ✅ **Comprehensive Validation** for DICOM file integrity

### Frontend Features
- 🖥️ **Modern PyQt6 Interface** with resizable split panels
- 📋 **Study Management** with filtering and search capabilities
- 🎨 **Multiple Window/Level Presets** (Soft Tissue, Lung, Bone, Brain, Liver)
- ⏭️ **Image Series Navigation** with Previous/Next controls
- 📊 **Metadata Display** showing patient and study information
- 🔍 **Real-time Preview** with instant preset switching

### Medical Imaging Capabilities
- ✅ CT (Computed Tomography) image support
- ✅ Hounsfield Unit (HU) rescaling for accurate display
- ✅ Clinical window/level presets for different tissue types
- ✅ DICOM metadata preservation and display
- ✅ Multi-instance series support

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    DICOM Workstation Lite                   │
└─────────────────────────────────────────────────────────────┘

    ┌──────────────┐         ┌──────────────┐         ┌──────────────┐
    │              │  HTTP   │              │  JSON   │              │
    │   PyQt6 GUI  │ ◄─────► │ FastAPI REST │ ◄─────► │   Storage    │
    │   Frontend   │  REST   │   Backend    │  Files  │   Layer      │
    │              │         │              │         │              │
    └──────────────┘         └──────────────┘         └──────────────┘
         ▲                          ▲                        ▲
         │                          │                        │
    User Actions              DICOM Processing          Persistence
    - Upload files           - Metadata extraction     - studies.json
    - Browse studies         - Pixel processing        - DICOM files
    - View images            - Window/Level apply      - File management
    - Navigate series        - PNG conversion
```

### Design Patterns
- **Repository Pattern** for data access abstraction
- **MVC-like Architecture** separating UI, business logic, and data
- **Dependency Injection** for testability and modularity
- **RESTful Design** for clean API architecture

### Tech Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| Backend Framework | FastAPI | Latest |
| Web Server | Uvicorn | Latest |
| DICOM Processing | PyDICOM | Latest |
| Image Processing | NumPy, Pillow | Latest |
| Frontend GUI | PyQt6 | 6.9+ |
| HTTP Client | Requests | Latest |
| Testing | Pytest, pytest-cov | Latest |
| Storage | JSON + Filesystem | - |

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.10 or higher**
- **pip** package manager
- **git** (optional, for cloning)

### Installation

```bash
# Clone the repository
git clone https://github.com/destone28/dicom-workstation-lite.git
cd dicom-workstation-lite

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### Generate Test Data

```bash
# Create synthetic DICOM files for testing
python backend/create_test_dicom.py
```

This generates 10 test CT DICOM images in `data/test_dicom/`.

### Running the Application

#### Start the Backend Server

```bash
# Terminal 1
source venv/bin/activate
python backend/api.py
```

Server will start at `http://0.0.0.0:8000`

- API Documentation: http://localhost:8000/docs
- Health Check: http://localhost:8000/health

#### Start the Frontend GUI

```bash
# Terminal 2
source venv/bin/activate
python frontend/main.py
```

### First Steps

1. **Upload DICOM Files**
   - Click "📁 Upload DICOM Files"
   - Navigate to `data/test_dicom/patient_001/`
   - Select one or more `.dcm` files
   - Click "Open"

2. **Browse Studies**
   - Studies appear in the left panel
   - Click on a study to view details

3. **View Images**
   - Select a study to load its images
   - Use "◀ Previous" and "Next ▶" to navigate
   - Try different presets: Default, Lung, Bone, Brain

4. **Explore Metadata**
   - Patient information displayed at the top
   - Image metadata shown at the bottom
   - Status bar shows current operation

---

## 📡 API Documentation

### Endpoints Overview

| Endpoint | Method | Description | Parameters |
|----------|--------|-------------|------------|
| `/upload` | POST | Upload DICOM files | `files`: multipart/form-data |
| `/studies` | GET | List all studies | `modality`: CT, MR, etc. (optional) |
| `/studies/{study_uid}` | GET | Get study details | `study_uid`: Study Instance UID |
| `/image/{sop_uid}` | GET | Get image as PNG | `sop_uid`: SOP Instance UID<br>`preset`: default, lung, bone, brain, liver |
| `/health` | GET | Health check | - |

### Example Usage

#### Upload Files
```bash
curl -X POST "http://localhost:8000/upload" \
  -F "files=@image1.dcm" \
  -F "files=@image2.dcm"
```

#### Get Studies
```bash
# All studies
curl "http://localhost:8000/studies"

# Filter by modality
curl "http://localhost:8000/studies?modality=CT"
```

#### Get Study Details
```bash
curl "http://localhost:8000/studies/1.2.3.4.5.6.7.8.9"
```

#### Get Image with Preset
```bash
curl "http://localhost:8000/image/1.2.3.4.5.6.7.8.9.1?preset=lung" \
  --output lung_view.png
```

### Interactive API Documentation

Visit **http://localhost:8000/docs** for:
- Interactive API testing (Swagger UI)
- Automatic request/response examples
- Schema documentation
- Try-it-out functionality

---

## 💻 Development

### Project Structure

```
dicom_workstation_lite/
│
├── backend/                      # Backend application
│   ├── __init__.py
│   ├── api.py                   # FastAPI endpoints (85% coverage)
│   ├── dicom_processor.py       # DICOM processing (51% coverage)
│   ├── storage.py               # Data persistence (69% coverage)
│   └── create_test_dicom.py     # Test data generator
│
├── frontend/                     # Frontend application
│   ├── __init__.py
│   ├── main.py                  # Application entry point
│   ├── main_window.py           # Main window UI (59% coverage)
│   └── api_client.py            # API client (61% coverage)
│
├── tests/                        # Test suite
│   ├── __init__.py
│   ├── test_backend.py          # Backend unit tests (28 tests)
│   ├── test_frontend.py         # Frontend tests (20 tests)
│   ├── test_integration.py      # Integration tests (3 tests)
│   ├── coverage_report.md       # Coverage analysis
│   └── TEST_RESULTS.md          # Test results summary
│
├── data/                         # Data directory
│   ├── test_dicom/              # Test DICOM files
│   ├── dicom_files/             # Uploaded files (gitignored)
│   └── studies.json             # Study metadata (gitignored)
│
├── requirements.txt              # Python dependencies
├── pytest.ini                   # Pytest configuration
├── .gitignore                   # Git ignore rules
├── README.md                    # This file
└── PROJECT_SUMMARY.md           # Detailed project documentation
```

### Running Tests

```bash
# All tests with coverage
pytest tests/ -v --cov=backend --cov=frontend --cov-report=html

# Backend tests only
pytest tests/test_backend.py -v

# Frontend tests only
pytest tests/test_frontend.py -v

# Integration tests (automatic server)
pytest tests/test_integration.py -v -m integration

# Integration tests (manual server - backend must be running)
pytest tests/test_integration.py -v -m integration_manual

# View coverage report
xdg-open htmlcov/index.html  # Linux
open htmlcov/index.html       # Mac
start htmlcov/index.html      # Windows
```

### Test Results

- ✅ **51 tests** - All passing
- ✅ **58% overall coverage** (85% on critical API endpoints)
- ⚡ **~9 seconds** execution time
- 📊 Detailed results in `tests/TEST_RESULTS.md`

### Adding New Features

1. **New API Endpoint**
   ```python
   # backend/api.py
   @app.get("/new-endpoint")
   async def new_endpoint():
       return {"message": "Hello"}
   ```

2. **New Window/Level Preset**
   ```python
   # backend/dicom_processor.py
   WINDOW_PRESETS = {
       "custom": {"window": 1000, "level": 50}
   }
   ```

3. **New GUI Feature**
   ```python
   # frontend/main_window.py
   def new_feature(self):
       # Implementation
       pass
   ```

4. **Write Tests**
   ```python
   # tests/test_backend.py
   def test_new_feature():
       assert True
   ```

---

## 🧪 Testing

### Test Strategy

The project uses a comprehensive testing approach:

- **Unit Tests** - Test individual functions and methods
- **Integration Tests** - Test end-to-end workflows
- **Component Tests** - Test GUI components
- **Mocked Tests** - Isolate dependencies for reliable testing

### Test Coverage by Module

| Module | Tests | Coverage | Status |
|--------|-------|----------|--------|
| Backend API | 11 | 85% | ✅ Excellent |
| Storage | 7 | 69% | ✅ Good |
| DICOM Processor | 10 | 51% | ✅ Acceptable |
| API Client | 10 | 61% | ✅ Acceptable |
| Main Window | 10 | 59% | ✅ Acceptable |

### Test Data

Synthetic DICOM files are generated using `backend/create_test_dicom.py`:

- **2 patients** with realistic metadata
- **5 images per study** (CT modality)
- **512x512 pixels** with random Hounsfield values
- **Fully DICOM-compliant** files for testing

---

## 🎯 Design Decisions

### JSON Storage
**Decision:** Use JSON for metadata storage instead of a database.

**Rationale:**
- ✅ Simple to implement and debug
- ✅ No database setup required
- ✅ Easy to migrate to PostgreSQL/MongoDB later
- ✅ Human-readable for development
- ⚠️ Not suitable for large-scale production

**Migration Path:** Switch to SQLAlchemy ORM for easy database migration.

### PyQt6 over PySide6
**Decision:** Use PyQt6 for GUI development.

**Rationale:**
- ✅ Better documentation and community support
- ✅ More stable releases
- ✅ Familiar API for Qt developers
- ⚠️ Commercial licensing for closed-source apps (use PySide6 if needed)

### Window/Level Presets
**Decision:** Include 5 clinical presets (Default, Lung, Bone, Brain, Liver).

**Rationale:**
- ✅ Cover most common CT viewing scenarios
- ✅ Based on standard clinical practice
- ✅ Easy to extend with custom presets
- ✅ Improve diagnostic workflow

| Preset | Clinical Use | Window | Level |
|--------|-------------|--------|-------|
| Default | Soft tissue | 400 | 40 |
| Lung | Lung parenchyma | 1500 | -600 |
| Bone | Skeletal structures | 2000 | 300 |
| Brain | Brain tissue | 80 | 40 |
| Liver | Liver parenchyma | 150 | 30 |

### Flat Image Structure
**Decision:** Store images as flat list without series hierarchy.

**Rationale:**
- ✅ Simpler data model for MVP
- ✅ Easier to query and display
- ✅ Sufficient for single-series studies
- ⚠️ Series hierarchy can be added later if needed

---

## 🔮 Future Enhancements

### Short-term (Next Release)
- [ ] **Series Hierarchy** - Group images by series
- [ ] **Drag-and-Drop Upload** - Easier file management
- [ ] **Keyboard Shortcuts** - Navigate with arrow keys
- [ ] **Export Images** - Save processed images to PNG/JPEG
- [ ] **Dark Mode** - Eye-friendly theme for long viewing sessions

### Medium-term
- [ ] **Database Migration** - PostgreSQL for production scalability
- [ ] **Measurement Tools** - Distance, angle, ROI measurements
- [ ] **Thumbnail View** - Grid view of all images in series
- [ ] **Multi-modality Support** - MR, US, CR, DX support

### Long-term
- [ ] **3D Volume Rendering** - Using VTK or Three.js
- [ ] **Web-based Viewer** - Browser-based interface with WebGL
- [ ] **AI Integration** - Auto-segmentation, lesion detection
- [ ] **DICOM Structured Reports** - SR creation and display

---

## 📸 Screenshots

> Screenshots will be added after visual testing

Planned screenshots:
- Main window with loaded study
- Image viewer with different presets
- Upload dialog
- Study list view
- Metadata panel

Create folder structure:
```bash
mkdir -p docs/screenshots
# Add screenshots:
# - main_window.png
# - image_viewer.png
# - upload_dialog.png
# - study_list.png
# - metadata_panel.png
```

---

## 🤝 Contributing

Contributions are welcome! Please follow these guidelines:

### Code Style
- Follow **PEP 8** for Python code
- Use **type hints** for function signatures
- Write **docstrings** for all public functions
- Keep functions **focused and small** (<50 lines)

### Pull Request Process

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Write tests** for new functionality
4. **Ensure tests pass** (`pytest tests/ -v`)
5. **Update documentation** as needed
6. **Commit** changes (`git commit -m 'Add amazing feature'`)
7. **Push** to branch (`git push origin feature/amazing-feature`)
8. **Open** a Pull Request

### Development Setup

```bash
# Install development dependencies
pip install -r requirements.txt

# Install pre-commit hooks (optional)
pip install pre-commit
pre-commit install

# Run linters
flake8 backend/ frontend/
black --check backend/ frontend/

# Run type checker
mypy backend/ frontend/
```

---

## 📄 License

This project is licensed under the **MIT License** - see below for details:

```
MIT License

Copyright (c) 2025 DICOM Workstation Lite Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## 🙏 Acknowledgments

This project builds upon excellent open-source libraries:

- **[PyDICOM](https://pydicom.github.io/)** - Pure Python DICOM library
- **[FastAPI](https://fastapi.tiangolo.com/)** - Modern Python web framework
- **[PyQt6](https://pypi.org/project/PyQt6/)** - Python bindings for Qt
- **[Pytest](https://pytest.org/)** - Testing framework
- **[NumPy](https://numpy.org/)** - Numerical computing
- **[Pillow](https://python-pillow.org/)** - Image processing

---

## 📚 Additional Resources

- **[Project Summary](PROJECT_SUMMARY.md)** - Detailed architecture and design
- **[Coverage Report](tests/coverage_report.md)** - Detailed coverage metrics
- **[API Documentation](http://localhost:8000/docs)** - Interactive API docs (when server is running)

---

## 📞 Support

- **Issues:** [GitHub Issues](https://github.com/destone28/dicom-workstation-lite/issues)
- **Discussions:** [GitHub Discussions](https://github.com/destone28/dicom-workstation-lite/discussions)
- **Email:** emilio.destratis@gmail.com

---

**Made with ❤️ for the medical imaging community**

*DICOM Workstation Lite - Making medical imaging accessible*
