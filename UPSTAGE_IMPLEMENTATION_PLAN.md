# Upstage OCR Plugin Implementation Plan

## Overview

This document outlines the implementation plan for integrating Upstage Document OCR API into OCRmyPDF as a replacement for Tesseract OCR.

## API Selection: Document OCR vs Document Parsing

### Chosen API: Document OCR (`ocr`)
- **Endpoint**: `https://api.upstage.ai/v1/document-digitization`
- **Model**: `ocr` (alias for latest version)
- **Output**: Word-level bounding boxes with confidence scores
- **Rate Limit**: 1 RPS
- **Max Pages**: 100 (synchronous)

### Why Not Document Parsing?
- Document Parsing focuses on layout detection (tables, figures, equations)
- OCR API provides precise word-level coordinates needed for hOCR conversion
- Simpler integration path for OCRmyPDF's text layer requirements

## Implementation Components

### 1. HTTP Client (`_exec/upstage.py`)

```python
# New file: src/ocrmypdf/_exec/upstage.py
import requests
from pathlib import Path
from typing import Dict, List, Any

class UpstageAPIClient:
    def __init__(self, api_key: str, endpoint: str, timeout: float):
        self.api_key = api_key
        self.endpoint = endpoint
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {api_key}'
        })
    
    def ocr_image(self, image_path: Path) -> Dict[str, Any]:
        """Send image to Upstage OCR API and return response."""
        with open(image_path, 'rb') as f:
            files = {'document': f}
            data = {'model': 'ocr'}
            response = self.session.post(
                self.endpoint,
                files=files,
                data=data,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
```

### 2. Response Format Analysis

#### Upstage OCR Response Structure:
```json
{
  "confidence": 0.9924988460974842,
  "pages": [
    {
      "confidence": 0.9924988460974842,
      "height": 256,
      "width": 786,
      "text": "Print the words \\nhello, world",
      "words": [
        {
          "boundingBox": {
            "vertices": [
              {"x": 65, "y": 52},
              {"x": 221, "y": 55},
              {"x": 221, "y": 104},
              {"x": 64, "y": 101}
            ]
          },
          "confidence": 0.9950619419,
          "text": "Print"
        }
      ]
    }
  ]
}
```

### 3. Coordinate System Conversion

#### Challenge: Coordinate System Differences
- **Upstage API**: Absolute pixel coordinates with top-left origin (0,0)
- **hOCR Format**: Absolute pixel coordinates with top-left origin (0,0) - COMPATIBLE!
- **PDF Coordinates**: Bottom-left origin (0,0) - NEEDS CONVERSION

#### Conversion Functions:
```python
def upstage_to_hocr_bbox(vertices: List[Dict], page_height: int) -> str:
    """Convert Upstage bounding box to hOCR bbox format."""
    # Upstage uses top-left origin, hOCR also uses top-left origin
    # Extract min/max coordinates from vertices
    x_coords = [v['x'] for v in vertices]
    y_coords = [v['y'] for v in vertices]
    
    x1, x2 = min(x_coords), max(x_coords)
    y1, y2 = min(y_coords), max(y_coords)
    
    return f"bbox {x1} {y1} {x2} {y2}"

def upstage_to_pdf_coords(vertices: List[Dict], page_height: int) -> tuple:
    """Convert Upstage coordinates to PDF coordinate system."""
    # PDF uses bottom-left origin, so flip Y coordinates
    x_coords = [v['x'] for v in vertices]
    y_coords = [page_height - v['y'] for v in vertices]  # Flip Y
    
    return (min(x_coords), min(y_coords), max(x_coords), max(y_coords))
```

### 4. hOCR Generation Implementation

```python
def generate_hocr_from_upstage(upstage_response: Dict, output_hocr: Path, output_text: Path):
    """Convert Upstage OCR response to hOCR format."""
    
    page_data = upstage_response['pages'][0]  # Single page
    page_width = page_data['width']
    page_height = page_data['height']
    words = page_data['words']
    
    # Generate hOCR XML structure
    hocr_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">
<head>
    <title></title>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
    <meta name='ocr-system' content='Upstage Document OCR' />
    <meta name='ocr-capabilities' content='ocr_page ocr_carea ocr_par ocr_line ocrx_word'/>
</head>
<body>
    <div class='ocr_page' id='page_1' title='image ""; bbox 0 0 {page_width} {page_height}; ppageno 0'>
        <div class='ocr_carea' id='block_1_1' title="bbox 0 0 {page_width} {page_height}">
            <p class='ocr_par' dir='ltr' id='par_1' title="bbox 0 0 {page_width} {page_height}">
                <span class='ocr_line' id='line_1' title="bbox 0 0 {page_width} {page_height}">'''
    
    # Add words
    for i, word in enumerate(words):
        bbox = upstage_to_hocr_bbox(word['boundingBox']['vertices'], page_height)
        confidence = int(word['confidence'] * 100)  # Convert to 0-100 scale
        word_text = html.escape(word['text'])
        
        hocr_content += f'''
                    <span class='ocrx_word' id='word_{i+1}' title="{bbox}; x_wconf {confidence}">{word_text}</span>'''
    
    hocr_content += '''
                </span>
            </p>
        </div>
    </div>
</body>
</html>'''
    
    # Write files
    output_hocr.write_text(hocr_content, encoding='utf-8')
    output_text.write_text(page_data['text'], encoding='utf-8')
```

### 5. Text-Only PDF Generation

```python
import pikepdf
from pikepdf import Pdf, Dictionary, Name

def generate_pdf_from_upstage(upstage_response: Dict, output_pdf: Path, output_text: Path):
    """Generate text-only PDF from Upstage OCR response."""
    
    page_data = upstage_response['pages'][0]
    page_width = page_data['width']
    page_height = page_data['height']
    words = page_data['words']
    
    # Create new PDF
    pdf = Pdf.new()
    page_size = (page_width, page_height)  # Points (assuming 72 DPI)
    page = pdf.add_blank_page(page_size=page_size)
    
    # Create content stream for invisible text
    content_parts = [b'BT']  # Begin text
    content_parts.append(b'3 Tr')  # Set text rendering mode to invisible
    content_parts.append(b'/F1 12 Tf')  # Set font (will be added to resources)
    
    for word in words:
        # Convert coordinates to PDF coordinate system
        x1, y1, x2, y2 = upstage_to_pdf_coords(word['boundingBox']['vertices'], page_height)
        
        # Position text at word location
        content_parts.append(f'{x1} {y1} Td'.encode())  # Move to position
        
        # Scale text to fit bounding box width
        text_width = x2 - x1
        if text_width > 0:
            scale = text_width / len(word['text'])  # Rough scaling
            content_parts.append(f'{scale} 0 0 12 {x1} {y1} Tm'.encode())  # Transform matrix
        
        # Show text
        text_escaped = word['text'].replace('(', '\\(').replace(')', '\\)')
        content_parts.append(f'({text_escaped}) Tj'.encode())
    
    content_parts.append(b'ET')  # End text
    
    # Create content stream
    content_stream = b'\\n'.join(content_parts)
    page.Contents = pdf.make_stream(content_stream)
    
    # Add font to resources (simple font for invisible text)
    page.Resources = Dictionary({
        Name.Font: Dictionary({
            Name.F1: Dictionary({
                Name.Type: Name.Font,
                Name.Subtype: Name.Type1,
                Name.BaseFont: Name.Helvetica
            })
        })
    })
    
    # Save PDF
    pdf.save(output_pdf)
    
    # Write text file
    output_text.write_text(page_data['text'], encoding='utf-8')
```

## Plugin Configuration Updates

### Command Line Options
```python
@hookimpl
def add_options(parser: argparse.ArgumentParser) -> None:
    upstage = parser.add_argument_group("Upstage OCR", "Upstage Document OCR API options")
    
    upstage.add_argument(
        '--upstage-api-key',
        metavar='KEY',
        help="Upstage API key (or set UPSTAGE_API_KEY environment variable)",
    )
    upstage.add_argument(
        '--upstage-endpoint',
        metavar='URL',
        default='https://api.upstage.ai/v1/document-digitization',
        help="Upstage API endpoint URL (default: %(default)s)",
    )
    upstage.add_argument(
        '--upstage-timeout',
        type=float,
        default=180.0,
        metavar='SECONDS',
        help="Timeout for Upstage API requests (default: %(default)s)",
    )
    upstage.add_argument(
        '--upstage-confidence-threshold',
        type=float,
        default=0.0,
        metavar='THRESHOLD',
        help="Minimum confidence threshold for OCR results (default: %(default)s)",
    )
    upstage.add_argument(
        '--upstage-model',
        default='ocr',
        metavar='MODEL',
        help="Upstage model to use (default: %(default)s)",
    )
```

### Validation and Error Handling
```python
@hookimpl
def check_options(options: argparse.Namespace) -> None:
    """Validate Upstage options."""
    import os
    
    # Get API key from options or environment
    api_key = getattr(options, 'upstage_api_key', None) or os.environ.get('UPSTAGE_API_KEY')
    if not api_key:
        raise MissingDependencyError(
            "Upstage API key is required. Use --upstage-api-key or set UPSTAGE_API_KEY environment variable."
        )
    
    # Store resolved API key back to options
    options.upstage_api_key = api_key
    
    # Validate endpoint URL
    if not options.upstage_endpoint.startswith(('http://', 'https://')):
        raise BadArgsError("Upstage endpoint must be a valid HTTP/HTTPS URL")

@hookimpl
def validate(pdfinfo, options: argparse.Namespace) -> None:
    """Validate PDF compatibility with Upstage API."""
    
    # Check page count limits
    page_count = len(pdfinfo)
    if page_count > 100:
        log.warning(f"PDF has {page_count} pages, but Upstage OCR API supports max 100 pages. "
                   f"Only first 100 pages will be processed.")
    
    # Check file size (would need to be implemented at file level)
    # Note: Individual page images should be well under 50MB limit
```

## Error Handling Strategy

### API Error Mapping
```python
def handle_upstage_api_error(response: requests.Response, input_file: Path):
    """Handle Upstage API errors gracefully."""
    
    if response.status_code == 400:
        log.error(f"Bad request to Upstage API for {input_file}: {response.text}")
        return "empty"  # Return empty OCR result
    elif response.status_code == 401:
        raise MissingDependencyError("Invalid Upstage API key")
    elif response.status_code == 413:
        log.error(f"File {input_file} too large for Upstage API (>50MB)")
        return "empty"
    elif response.status_code == 415:
        log.error(f"Unsupported file format for {input_file}")
        return "empty"
    elif response.status_code == 429:
        log.error("Upstage API rate limit exceeded")
        raise SubprocessOutputError("Rate limit exceeded")
    else:
        log.error(f"Upstage API error {response.status_code}: {response.text}")
        return "empty"
```

## Language Support

### Supported Languages (from API docs)
- **Alphanumeric**: English and numbers
- **Hangul**: Korean
- **Hanja**: Traditional Chinese characters used in Korean
- **Hanzi/Kanji**: Chinese/Japanese (beta)

### Language Mapping
```python
@staticmethod
def languages(options: argparse.Namespace) -> Set[str]:
    """Return languages supported by Upstage OCR."""
    return {
        'eng',  # English (alphanumeric)
        'kor',  # Korean (Hangul + Hanja)
        'chi_sim',  # Chinese Simplified (beta)
        'chi_tra',  # Chinese Traditional (beta)
        'jpn',  # Japanese (beta)
    }
```

## Performance Considerations

### Rate Limiting
- **1 RPS limit**: Implement request throttling
- **Retry logic**: Handle temporary failures
- **Concurrent processing**: Serialize API calls across pages

### Optimization
- **Image preprocessing**: Ensure optimal image quality for API
- **Caching**: Consider caching API responses for debugging
- **Timeout handling**: Graceful degradation on timeouts

## Testing Strategy

### Unit Tests
- Mock API responses for consistent testing
- Test coordinate conversion functions
- Test hOCR generation with various inputs
- Test error handling scenarios

### Integration Tests
- Test with real Upstage API (requires API key)
- Validate hOCR output format compliance
- Test text-only PDF generation
- Performance testing with rate limits

## Implementation Priority

1. **Phase 1**: Basic API integration and hOCR generation
2. **Phase 2**: Text-only PDF generation (sandwich mode)
3. **Phase 3**: Error handling and validation
4. **Phase 4**: Performance optimization and rate limiting
5. **Phase 5**: Testing and documentation

## Dependencies

### New Dependencies
```python
# Add to existing imports in upstage_ocr.py
import html
import os
import requests
import time
from typing import Dict, List, Any

# Existing OCRmyPDF dependencies
import pikepdf
from ocrmypdf.exceptions import MissingDependencyError, BadArgsError, SubprocessOutputError
```

### File Structure
```
src/ocrmypdf/
├── _exec/
│   ├── upstage.py          # New: Upstage API client
│   └── ...
├── builtin_plugins/
│   ├── upstage_ocr.py      # Updated: Main plugin
│   └── ...
```

This implementation plan provides a comprehensive roadmap for integrating Upstage OCR API into OCRmyPDF while maintaining compatibility with the existing plugin architecture.
