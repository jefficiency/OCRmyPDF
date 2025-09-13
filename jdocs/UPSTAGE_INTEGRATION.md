# Upstage Document Parse Engine Integration

This document outlines the integration of Upstage Document Parse Engine as an OCR engine for OCRmyPDF.

## Overview

The Upstage Document Parse Engine integration provides an alternative to Tesseract OCR, leveraging Upstage's cloud-based document AI capabilities for optical character recognition.

## Files Created

### 1. Built-in Plugin Implementation
- **File**: `src/ocrmypdf/builtin_plugins/upstage_ocr.py`
- **Purpose**: Complete built-in plugin implementation with all OCRmyPDF hooks
- **Status**: Placeholder implementation with full interface compliance

### 2. Example External Plugin
- **File**: `misc/upstage_plugin_example.py`
- **Purpose**: Standalone plugin example for external use
- **Status**: Simplified implementation for demonstration

## Interface Implementation

The `UpstageDocumentParseEngine` class implements all required methods from the `OcrEngine` abstract base class:

### Required Methods (Placeholders)

```python
class UpstageDocumentParseEngine(OcrEngine):
    @staticmethod
    def version() -> str:
        # TODO: Query Upstage API for version or return static version
        
    @staticmethod
    def creator_tag(options: Namespace) -> str:
        # TODO: Return proper PDF metadata creator tag
        
    def __str__(self) -> str:
        # TODO: Return human-readable engine name and version
        
    @staticmethod
    def languages(options: Namespace) -> Set[str]:
        # TODO: Return set of supported language codes (ISO 639-2 Alpha-3)
        
    @staticmethod
    def get_orientation(input_file: Path, options: Namespace) -> OrientationConfidence:
        # TODO: Use Upstage API to detect page orientation
        
    @staticmethod
    def get_deskew(input_file: Path, options: Namespace) -> float:
        # TODO: Use Upstage API to detect skew angle
        
    @staticmethod
    def generate_hocr(input_file: Path, output_hocr: Path, output_text: Path, options: Namespace) -> None:
        # TODO: Generate hOCR XML from Upstage API response
        
    @staticmethod
    def generate_pdf(input_file: Path, output_pdf: Path, output_text: Path, options: Namespace) -> None:
        # TODO: Generate text-only PDF from Upstage API response
```

### Plugin Hooks Implemented

```python
@hookimpl
def add_options(parser: ArgumentParser) -> None:
    # Adds Upstage-specific command line options

@hookimpl  
def check_options(options: Namespace) -> None:
    # Validates Upstage configuration options

@hookimpl
def validate(pdfinfo, options: Namespace) -> None:
    # PDF-specific validation for Upstage processing

@hookimpl
def filter_ocr_image(page: PageContext, image) -> None:
    # Image preprocessing for Upstage requirements

@hookimpl
def get_ocr_engine() -> UpstageDocumentParseEngine:
    # Returns the Upstage OCR engine instance
```

## Command Line Options Added

The plugin adds the following command line options:

- `--upstage-api-key KEY`: Upstage API key for authentication
- `--upstage-endpoint URL`: API endpoint URL (default: https://api.upstage.ai/v1/document-ai/ocr)
- `--upstage-timeout SECONDS`: Request timeout (default: 180.0)
- `--upstage-confidence-threshold THRESHOLD`: Minimum confidence threshold (default: 0.5)

## Usage Examples

### As Built-in Plugin
```bash
# If integrated as built-in plugin
ocrmypdf --upstage-api-key YOUR_API_KEY input.pdf output.pdf
```

### As External Plugin
```bash
# Using the example plugin file
ocrmypdf --plugin misc/upstage_plugin_example.py \
         --upstage-api-key YOUR_API_KEY \
         input.pdf output.pdf

# Using environment variable
export UPSTAGE_API_KEY=your_api_key_here
ocrmypdf --plugin misc/upstage_plugin_example.py input.pdf output.pdf
```

## Implementation Tasks

To complete the integration, implement the following TODO items:

### 1. API Integration
- [ ] Implement HTTP client for Upstage Document Parse API
- [ ] Handle authentication with API key
- [ ] Implement request/response parsing
- [ ] Add proper error handling and retries

### 2. Format Conversion
- [ ] **hOCR Generation**: Convert Upstage API response to hOCR XML format
  - Parse bounding boxes and text from API response
  - Generate proper hOCR structure (page → paragraph → line → word)
  - Handle coordinate system conversion (API coordinates → hOCR coordinates)
  
- [ ] **Text-only PDF Generation**: Create invisible text layer PDF
  - Use pikepdf to create PDF structure
  - Position text using coordinates from API
  - Set proper text rendering mode (invisible)
  - Match page dimensions to input image

### 3. Feature Implementation
- [ ] **Orientation Detection**: Use API to detect page rotation
- [ ] **Deskew Detection**: Use API to detect skew angle  
- [ ] **Language Support**: Map Upstage language codes to ISO 639-2 Alpha-3
- [ ] **Version Detection**: Query API for version information

### 4. Error Handling
- [ ] Network connectivity issues
- [ ] API rate limiting
- [ ] Invalid API responses
- [ ] Timeout handling
- [ ] Graceful degradation (empty output on failure)

### 5. Configuration & Validation
- [ ] API key validation
- [ ] Endpoint URL validation
- [ ] File size and format constraints
- [ ] Network connectivity checks

## API Integration Notes

### Expected Upstage API Response Format
The implementation assumes the Upstage Document Parse API returns structured data containing:
- Text content for each detected text region
- Bounding box coordinates (x1, y1, x2, y2)
- Confidence scores
- Language detection results
- Page orientation information

### Coordinate System Conversion
- **Upstage API**: Likely uses top-left origin (0,0) at top-left corner
- **hOCR Format**: Uses top-left origin with bbox format "x1 y1 x2 y2"
- **PDF Coordinates**: Uses bottom-left origin (0,0) at bottom-left corner

Proper coordinate transformation will be needed between these systems.

## Testing

### Unit Tests
Create tests in `tests/` directory:
- `test_upstage_ocr.py`: Test the OCR engine implementation
- Mock API responses for consistent testing
- Test error conditions and edge cases

### Integration Tests  
- Test with real Upstage API (requires API key)
- Validate hOCR output format
- Verify text-only PDF generation
- Test with various image formats and sizes

## Plugin Distribution

For external distribution, create a separate package:
```
ocrmypdf-upstage/
├── pyproject.toml
├── README.md
├── src/
│   └── ocrmypdf_upstage/
│       ├── __init__.py
│       └── plugin.py
└── tests/
    └── test_upstage.py
```

With `pyproject.toml` entry point:
```toml
[project.entry-points."ocrmypdf"]
upstage = "ocrmypdf_upstage.plugin"
```

## Security Considerations

- API keys should be handled securely
- Validate all API responses before processing
- Implement request size limits
- Consider data privacy when sending documents to cloud API
- Add option to disable network requests for sensitive documents

## Performance Considerations

- Implement connection pooling for multiple pages
- Add caching for repeated API calls
- Consider parallel processing limitations (API rate limits)
- Optimize image format/size before sending to API
