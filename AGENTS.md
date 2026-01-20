# AGENTS.md

Codebase guidelines for AI agents working on cash-report project.

## Project Overview
FastAPI application processing financial documents: monthly statements, cash reports, payment forms, and bank data integration (HSBC, Citibank).

---

## Build/Test Commands

### Running Application
```bash
python run.py
```
Default: 0.0.0.0:8000, reload enabled in dev mode.

### Running Tests
```bash
pytest                          # Run all tests
pytest test/file.py              # Run specific file
pytest test/file.py::test_func    # Run specific function
pytest -v                        # Verbose output
```

### Docker Deployment
```bash
docker build -t cash-report .
docker run -p 8000:8000 --env-file .env cash-report
./server-deploy.sh prod [tag]     # Production (uses podman)
./server-deploy.sh dev [tag]      # Development
```

---

## Code Style Guidelines

### Import Patterns
```python
# Standard library
import os, re
from pathlib import Path
from typing import Optional, List, Dict

# Third-party
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

# Local app (absolute from app/)
from app.core.config import settings
from app.utils.logger import logger
```

### Naming Conventions
- Functions: `snake_case` (e.g., `remove_pdf_password`)
- Classes: `PascalCase` (e.g., `ProcessRequest`)
- Variables: `snake_case`
- Constants: `UPPER_CASE`

### Type Hints
Always use type hints:
```python
def process_file(path: str, passwords: Optional[List[str]] = None) -> bool:
    pass

class ResponseModel(BaseModel):
    status: str
    data: Optional[List[Dict[str, Any]]] = None
```

### Pydantic Models
Use Field for all request/response fields:
```python
class ProcessRequest(BaseModel):
    task_id: str = Field(..., description="Unique task identifier")
    file_path: str = Field(..., description="Path to file")
    optional_field: Optional[str] = Field(None, description="Optional")
```

### Async Functions
All API endpoints must be async:
```python
@router.post("/endpoint", response_model=ResponseModel)
async def endpoint_function(request: RequestModel):
    pass
```

### Logging
Use loguru (not print):
```python
logger.debug("Debug info")
logger.info("Info message")
logger.warning("Warning")
logger.error(f"Error: {e}")
logger.exception("Error with traceback")  # Includes stack trace
```

### Error Handling

**API endpoints:**
```python
try:
    return ResponseModel(success=True, message="Success")
except FileNotFoundError as e:
    logger.error(f"File not found: {e}")
    return ResponseModel(success=False, message="File not found", error_code="FILE_NOT_FOUND")
except Exception as e:
    logger.error(f"Unexpected error: {e}", exc_info=True)
    return ResponseModel(success=False, message="Failed", error_details=str(e))
```

**Utility functions:**
```python
def utility(input_data: str) -> Optional[Dict]:
    try:
        return {"result": "success"}
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return None
```

### File Operations
Use pathlib.Path (not os.path for path manipulation):
```python
file_path = Path(settings.TEMP_DIR) / task_id / "file.pdf"
output_dir = Path(settings.TEMP_DIR) / "output"

output_dir.mkdir(parents=True, exist_ok=True)

if file_path.exists():
    size = file_path.stat().st_size

stem = file_path.stem  # filename without extension
suffix = file_path.suffix  # including dot (e.g., '.pdf')
```

### Documentation Strings
```python
def process_pdf(input_path: Path, output_dir: Path) -> List[Dict]:
    """
    Process PDF file.

    Args:
        input_path: Path to input PDF.
        output_dir: Directory for output files.

    Returns:
        List of processed file info.

    Raises:
        FileNotFoundError: If input file missing.
        ValueError: If format invalid.
    """
    pass
```

### FastAPI Router Pattern
```python
router = APIRouter()

@router.post("/endpoint_name")
async def endpoint_function(request: RequestModel):
    pass
```

Register in `app/main.py`:
```python
for router_module in ROUTERS:
    app.include_router(
        router_module.router,
        prefix="/api",
        dependencies=[Depends(verify_api_auth)]
    )
```

### Environment Variables
```python
from app.core.config import settings

temp_dir = settings.TEMP_DIR
debug = settings.DEBUG
environment = settings.ENVIRONMENT
```

Loaded from `.env` file (not in git).

---

## Project Structure

```
cash-report/
├── app/
│   ├── api/endpoints/    # FastAPI route handlers
│   ├── core/             # Config, security, API docs
│   ├── utils/             # Utility functions (filer, logger, downloader)
│   ├── models/            # Pydantic data models
│   ├── templates/         # Jinja2/Typst/LaTeX templates
│   └── r_scripts/        # R scripts for data processing
├── test/                 # Pytest test files
├── resources/fonts/      # Font files for PDF generation
├── temp/                 # Temporary files (gitignored)
└── logs/                 # Log files
```

---

## Testing

```python
import os
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_functionality(tmp_path):
    response = client.post("/endpoint", json={"key": "value"})
    assert response.status_code == 200
    assert response.json()["field"] == expected_value

    if os.path.exists(some_path):
        os.remove(some_path)
```

Test files: `test/` directory, `test_` prefix.

---

## Key Dependencies

- **FastAPI 0.112+**: Web framework
- **Pydantic 2.10+**: Data validation
- **loguru**: Logging (`app.utils.logger`)
- **PyPDF2**: PDF processing
- **pikepdf**: PDF manipulation (passwords, attachments)
- **rpy2**: R integration
- **pytest 8.3.5**: Testing

---

## Important Notes

1. Never suppress type errors - use proper typing or `Optional`/`Union`
2. No `# type: ignore` unless absolutely necessary
3. Always log errors with context
4. Use pathlib for paths, not os.path
5. Use BackgroundTasks for long operations
6. Clean up temp files with background_tasks
7. All endpoints protected by `verify_api_auth` by default
