# SPDX-FileCopyrightText: 2025 Your Name
# SPDX-License-Identifier: MPL-2.0

"""Interface to Upstage Document OCR API."""

from __future__ import annotations

import html
import logging
import time
from pathlib import Path
from typing import Any, Dict, List

import requests
from packaging.version import Version

from ocrmypdf.exceptions import (
    MissingDependencyError,
    SubprocessOutputError,
    TesseractConfigError,
)
from ocrmypdf.pluginspec import OrientationConfidence

log = logging.getLogger(__name__)


class UpstageAPIClient:
    """HTTP client for Upstage Document OCR API."""
    
    def __init__(self, api_key: str, endpoint: str, timeout: float = 180.0):
        """Initialize Upstage API client.
        
        Args:
            api_key: Upstage API key
            endpoint: API endpoint URL
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.endpoint = endpoint
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {api_key}',
            'User-Agent': 'OCRmyPDF-Upstage/1.0'
        })
        
        # Rate limiting: 1 RPS for OCR API
        self.last_request_time = 0.0
        self.min_request_interval = 1.0  # 1 second between requests
    
    def _rate_limit(self) -> None:
        """Enforce rate limiting to comply with API limits."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last
            log.debug(f"Rate limiting: sleeping {sleep_time:.2f}s")
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def ocr_image(self, image_path: Path, model: str = 'ocr') -> Dict[str, Any]:
        """Send image to Upstage OCR API and return response.
        
        Args:
            image_path: Path to image file
            model: Upstage model to use (default: 'ocr')
            
        Returns:
            API response as dictionary
            
        Raises:
            SubprocessOutputError: On API errors
            MissingDependencyError: On authentication errors
        """
        self._rate_limit()
        
        try:
            with open(image_path, 'rb') as f:
                files = {'document': f}
                data = {'model': model}
                
                log.debug(f"Sending {image_path} to Upstage OCR API")
                response = self.session.post(
                    self.endpoint,
                    files=files,
                    data=data,
                    timeout=self.timeout
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    self._handle_api_error(response, image_path)
                    
        except requests.exceptions.Timeout:
            log.error(f"Upstage API timeout for {image_path}")
            raise SubprocessOutputError(f"Upstage API timeout for {image_path}")
        except requests.exceptions.RequestException as e:
            log.error(f"Upstage API request failed for {image_path}: {e}")
            raise SubprocessOutputError(f"Upstage API request failed: {e}")
    
    def _handle_api_error(self, response: requests.Response, input_file: Path) -> None:
        """Handle Upstage API errors."""
        status_code = response.status_code
        
        try:
            error_data = response.json()
            error_message = error_data.get('message', 'Unknown error')
        except:
            error_message = response.text or 'Unknown error'
        
        if status_code == 400:
            log.error(f"Bad request to Upstage API for {input_file}: {error_message}")
            raise SubprocessOutputError(f"Invalid request: {error_message}")
        elif status_code == 401:
            raise MissingDependencyError("Invalid Upstage API key")
        elif status_code == 413:
            log.error(f"File {input_file} too large for Upstage API (>50MB)")
            raise SubprocessOutputError("File too large (>50MB)")
        elif status_code == 415:
            log.error(f"Unsupported file format for {input_file}")
            raise SubprocessOutputError("Unsupported file format")
        elif status_code == 429:
            log.error("Upstage API rate limit exceeded")
            raise SubprocessOutputError("Rate limit exceeded")
        else:
            log.error(f"Upstage API error {status_code}: {error_message}")
            raise SubprocessOutputError(f"API error {status_code}: {error_message}")


def upstage_to_hocr_bbox(vertices: List[Dict[str, int]], page_height: int) -> str:
    """Convert Upstage bounding box vertices to hOCR bbox format.
    
    Args:
        vertices: List of vertex dictionaries with 'x' and 'y' keys
        page_height: Page height (unused, kept for compatibility)
        
    Returns:
        hOCR bbox string in format "bbox x1 y1 x2 y2"
    """
    if not vertices:
        return "bbox 0 0 0 0"
    
    x_coords = [v['x'] for v in vertices]
    y_coords = [v['y'] for v in vertices]
    
    x1, x2 = min(x_coords), max(x_coords)
    y1, y2 = min(y_coords), max(y_coords)
    
    return f"bbox {x1} {y1} {x2} {y2}"


def upstage_to_pdf_coords(vertices: List[Dict[str, int]], page_height: int) -> tuple[float, float, float, float]:
    """Convert Upstage coordinates to PDF coordinate system.
    
    Args:
        vertices: List of vertex dictionaries with 'x' and 'y' keys
        page_height: Page height for coordinate system conversion
        
    Returns:
        Tuple of (x1, y1, x2, y2) in PDF coordinates
    """
    if not vertices:
        return (0.0, 0.0, 0.0, 0.0)
    
    x_coords = [v['x'] for v in vertices]
    y_coords = [page_height - v['y'] for v in vertices]  # Flip Y for PDF coordinates
    
    return (float(min(x_coords)), float(min(y_coords)), 
            float(max(x_coords)), float(max(y_coords)))


def generate_hocr_from_upstage(
    upstage_response: Dict[str, Any], 
    output_hocr: Path, 
    output_text: Path
) -> None:
    """Convert Upstage OCR response to hOCR format.
    
    Args:
        upstage_response: Response from Upstage OCR API
        output_hocr: Path to write hOCR file
        output_text: Path to write plain text file
    """
    if not upstage_response.get('pages'):
        # Empty response - create minimal hOCR
        _generate_empty_hocr(output_hocr, output_text)
        return
    
    page_data = upstage_response['pages'][0]  # Single page processing
    page_width = page_data['width']
    page_height = page_data['height']
    words = page_data.get('words', [])
    page_text = page_data.get('text', '')
    
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
        confidence = int(word.get('confidence', 0.0) * 100)  # Convert to 0-100 scale
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
    output_text.write_text(page_text, encoding='utf-8')


def generate_pdf_from_upstage(
    upstage_response: Dict[str, Any], 
    output_pdf: Path, 
    output_text: Path
) -> None:
    """Generate text-only PDF from Upstage OCR response.
    
    Args:
        upstage_response: Response from Upstage OCR API
        output_pdf: Path to write PDF file
        output_text: Path to write plain text file
    """
    import pikepdf
    from pikepdf import Pdf, Dictionary, Name
    
    if not upstage_response.get('pages'):
        # Empty response - create empty files
        output_pdf.write_bytes(b'')
        output_text.write_text('', encoding='utf-8')
        return
    
    page_data = upstage_response['pages'][0]
    page_width = page_data['width']
    page_height = page_data['height']
    words = page_data.get('words', [])
    page_text = page_data.get('text', '')
    
    # Create new PDF with invisible text
    pdf = Pdf.new()
    page_size = (page_width, page_height)  # Assuming 72 DPI
    page = pdf.add_blank_page(page_size=page_size)
    
    if words:
        # Create content stream for invisible text
        content_parts = [b'BT']  # Begin text
        content_parts.append(b'3 Tr')  # Set text rendering mode to invisible
        content_parts.append(b'/F1 12 Tf')  # Set font
        
        for word in words:
            # Convert coordinates to PDF coordinate system
            x1, y1, x2, y2 = upstage_to_pdf_coords(word['boundingBox']['vertices'], page_height)
            
            # Position and scale text
            text_width = x2 - x1
            if text_width > 0:
                # Simple horizontal scaling based on bounding box width
                word_text = word['text'].replace('(', '\\(').replace(')', '\\)')
                content_parts.append(f'{x1} {y1} Td'.encode())  # Move to position
                content_parts.append(f'({word_text}) Tj'.encode())  # Show text
        
        content_parts.append(b'ET')  # End text
        
        # Create content stream
        content_stream = b'\\n'.join(content_parts)
        page.Contents = pdf.make_stream(content_stream)
        
        # Add font to resources
        page.Resources = Dictionary({
            Name.Font: Dictionary({
                Name.F1: Dictionary({
                    Name.Type: Name.Font,
                    Name.Subtype: Name.Type1,
                    Name.BaseFont: Name.Helvetica
                })
            })
        })
    
    # Save PDF and text
    pdf.save(output_pdf)
    output_text.write_text(page_text, encoding='utf-8')


def _generate_empty_hocr(output_hocr: Path, output_text: Path) -> None:
    """Generate empty hOCR file for failed OCR."""
    hocr_content = '''<?xml version="1.0" encoding="UTF-8"?>
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
    <div class='ocr_page' id='page_1' title='image ""; bbox 0 0 100 100; ppageno 0'>
    </div>
</body>
</html>'''
    
    output_hocr.write_text(hocr_content, encoding='utf-8')
    output_text.write_text('[OCR failed]', encoding='utf-8')


# API interface functions (similar to tesseract.py)

def version() -> Version:
    """Return version of Upstage OCR (static for now)."""
    return Version("1.0.0")


def get_languages() -> set[str]:
    """Return supported languages."""
    return {
        'eng',      # English (alphanumeric)
        'kor',      # Korean (Hangul + Hanja)
        'chi_sim',  # Chinese Simplified (beta)
        'chi_tra',  # Chinese Traditional (beta)
        'jpn',      # Japanese (beta)
    }


def get_orientation(
    input_file: Path, api_key: str, endpoint: str, timeout: float
) -> OrientationConfidence:
    """Get page orientation (not supported by Upstage OCR API)."""
    # Upstage OCR API doesn't provide orientation detection
    # Return neutral values
    return OrientationConfidence(angle=0, confidence=0.0)


def get_deskew(
    input_file: Path, api_key: str, endpoint: str, timeout: float
) -> float:
    """Get deskew angle (not supported by Upstage OCR API)."""
    # Upstage OCR API doesn't provide deskew detection
    return 0.0


def generate_hocr(
    *,
    input_file: Path,
    output_hocr: Path,
    output_text: Path,
    api_key: str,
    endpoint: str,
    timeout: float,
    model: str = 'ocr',
    confidence_threshold: float = 0.0,
) -> None:
    """Generate hOCR file using Upstage OCR API."""
    client = UpstageAPIClient(api_key, endpoint, timeout)
    
    try:
        response = client.ocr_image(input_file, model)
        
        # Filter words by confidence threshold if specified
        if confidence_threshold > 0.0 and response.get('pages'):
            page_data = response['pages'][0]
            if 'words' in page_data:
                filtered_words = [
                    word for word in page_data['words']
                    if word.get('confidence', 0.0) >= confidence_threshold
                ]
                page_data['words'] = filtered_words
        
        generate_hocr_from_upstage(response, output_hocr, output_text)
        
    except (SubprocessOutputError, MissingDependencyError):
        # Generate empty hOCR on API failure
        log.warning(f"Upstage OCR failed for {input_file}, generating empty hOCR")
        _generate_empty_hocr(output_hocr, output_text)


def generate_pdf(
    *,
    input_file: Path,
    output_pdf: Path,
    output_text: Path,
    api_key: str,
    endpoint: str,
    timeout: float,
    model: str = 'ocr',
    confidence_threshold: float = 0.0,
) -> None:
    """Generate text-only PDF using Upstage OCR API."""
    client = UpstageAPIClient(api_key, endpoint, timeout)
    
    try:
        response = client.ocr_image(input_file, model)
        
        # Filter words by confidence threshold if specified
        if confidence_threshold > 0.0 and response.get('pages'):
            page_data = response['pages'][0]
            if 'words' in page_data:
                filtered_words = [
                    word for word in page_data['words']
                    if word.get('confidence', 0.0) >= confidence_threshold
                ]
                page_data['words'] = filtered_words
        
        generate_pdf_from_upstage(response, output_pdf, output_text)
        
    except (SubprocessOutputError, MissingDependencyError):
        # Generate empty PDF on API failure
        log.warning(f"Upstage OCR failed for {input_file}, generating empty PDF")
        output_pdf.write_bytes(b'')
        output_text.write_text('[OCR failed]', encoding='utf-8')
