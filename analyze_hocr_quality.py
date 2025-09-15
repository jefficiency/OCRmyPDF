#!/usr/bin/env python3
"""
Analyze the quality of hOCR output from Upstage Document Parse API.
"""

import tempfile
import argparse
from pathlib import Path
from xml.etree import ElementTree as ET
from ocrmypdf.builtin_plugins.upstage_ocr import UpstageDocumentOcrEngine, check_options

def analyze_hocr_structure(hocr_file: Path) -> dict:
    """Analyze hOCR file structure and quality."""
    
    with open(hocr_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Parse XML with namespace handling
    try:
        root = ET.fromstring(content)
    except ET.ParseError as e:
        return {"error": f"Invalid XML: {e}"}
    
    # Handle XHTML namespace
    namespaces = {'html': 'http://www.w3.org/1999/xhtml'} if 'xmlns' in content else {}
    
    # Helper function for finding elements with optional namespace
    def find_elements(xpath):
        if namespaces:
            # Convert xpath to use namespace
            xpath_ns = xpath.replace('//', './/html:').replace('[@class=', '[@class=')
            try:
                return root.findall(xpath_ns, namespaces)
            except:
                pass
        # Fallback: try without namespace
        return root.findall(xpath)
    
    # Count elements
    stats = {
        "total_size_bytes": len(content),
        "pages": len(find_elements(".//div[@class='ocr_page']")),
        "blocks": len(find_elements(".//div[@class='ocr_carea']")),
        "paragraphs": len(find_elements(".//p")),
        "lines": len(find_elements(".//span[@class='ocr_line']")),
        "words": len(find_elements(".//span[@class='ocrx_word']")),
        "headers": len(find_elements(".//p[@class='ocr_header']")),
        "captions": len(find_elements(".//p[@class='ocr_caption']")),
        "textfloats": len(find_elements(".//p[@class='ocr_textfloat']")),
    }
    
    # Check coordinate quality
    bbox_elements = find_elements(".//*[@title]") if namespaces else root.findall(".//*[@title]")
    bbox_count = 0
    valid_bbox_count = 0
    
    for elem in bbox_elements:
        title = elem.get('title', '')
        if 'bbox' in title:
            bbox_count += 1
            # Check if bbox has 4 coordinates
            try:
                bbox_part = title.split('bbox')[1].split(';')[0].strip()
                coords = bbox_part.split()
                if len(coords) == 4 and all(coord.isdigit() for coord in coords):
                    valid_bbox_count += 1
            except:
                pass  # Invalid bbox format
    
    stats["bbox_elements"] = bbox_count
    stats["valid_bboxes"] = valid_bbox_count
    stats["bbox_quality"] = (valid_bbox_count / bbox_count * 100) if bbox_count > 0 else 0
    
    # Check text content quality
    word_elements = find_elements(".//span[@class='ocrx_word']")
    non_empty_words = sum(1 for elem in word_elements if elem.text and elem.text.strip())
    stats["non_empty_words"] = non_empty_words
    stats["text_coverage"] = (non_empty_words / len(word_elements) * 100) if word_elements else 0
    
    return stats

def test_hocr_integration():
    """Test hOCR generation and analyze quality."""
    
    print("🔍 Analyzing Upstage hOCR Quality")
    print("=" * 50)
    
    # Create options
    options = argparse.Namespace()
    options.upstage_api_key = None
    options.upstage_endpoint = 'https://api.upstage.ai/v1/document-digitization'
    options.upstage_timeout = 180.0
    options.upstage_model = 'document-parse'
    options.upstage_confidence_threshold = 0.0
    options.upstage_chart_recognition = True
    options.upstage_merge_tables = True
    options.pdf_renderer = 'hocr'
    
    try:
        check_options(options)
        print("✅ Configuration validated")
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        return False
    
    # Generate hOCR
    input_file = Path("test_page1.pdf")
    if not input_file.exists():
        print(f"❌ Test file {input_file} not found")
        return False
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir = Path(temp_dir)
        output_hocr = temp_dir / "analysis.hocr"
        output_text = temp_dir / "analysis.txt"
        
        print("🌐 Generating hOCR with Upstage Document Parse...")
        
        engine = UpstageDocumentOcrEngine()
        engine.generate_hocr(
            input_file=input_file,
            output_hocr=output_hocr,
            output_text=output_text,
            options=options
        )
        
        if not output_hocr.exists():
            print("❌ hOCR file not generated")
            return False
        
        # Analyze quality
        print("📊 Analyzing hOCR structure and quality...")
        stats = analyze_hocr_structure(output_hocr)
        
        if "error" in stats:
            print(f"❌ Analysis error: {stats['error']}")
            return False
        
        print(f"\n📋 hOCR Quality Report:")
        print(f"   📄 File size: {stats['total_size_bytes']:,} bytes")
        print(f"   📑 Structure:")
        print(f"      - Pages: {stats['pages']}")
        print(f"      - Blocks (areas): {stats['blocks']}")
        print(f"      - Paragraphs: {stats['paragraphs']}")
        print(f"      - Lines: {stats['lines']}")
        print(f"      - Words: {stats['words']}")
        print(f"   🎯 Element Types:")
        print(f"      - Headers: {stats['headers']}")
        print(f"      - Captions: {stats['captions']}")
        print(f"      - Text floats: {stats['textfloats']}")
        print(f"   📐 Coordinate Quality:")
        print(f"      - Elements with bbox: {stats['bbox_elements']}")
        print(f"      - Valid bboxes: {stats['valid_bboxes']}")
        print(f"      - Bbox quality: {stats['bbox_quality']:.1f}%")
        print(f"   📝 Text Quality:")
        print(f"      - Non-empty words: {stats['non_empty_words']}")
        print(f"      - Text coverage: {stats['text_coverage']:.1f}%")
        
        # Quality assessment
        print(f"\n🎯 Quality Assessment:")
        
        quality_score = 0
        max_score = 5
        
        # Structure completeness (0-1 points)
        if stats['pages'] > 0 and stats['blocks'] > 0 and stats['words'] > 0:
            quality_score += 1
            print("   ✅ Structure completeness: GOOD")
        else:
            print("   ❌ Structure completeness: POOR")
        
        # Coordinate quality (0-1 points)
        if stats['bbox_quality'] >= 90:
            quality_score += 1
            print("   ✅ Coordinate quality: EXCELLENT")
        elif stats['bbox_quality'] >= 70:
            quality_score += 0.5
            print("   ⚠️  Coordinate quality: GOOD")
        else:
            print("   ❌ Coordinate quality: POOR")
        
        # Text coverage (0-1 points)
        if stats['text_coverage'] >= 95:
            quality_score += 1
            print("   ✅ Text coverage: EXCELLENT")
        elif stats['text_coverage'] >= 80:
            quality_score += 0.5
            print("   ⚠️  Text coverage: GOOD")
        else:
            print("   ❌ Text coverage: POOR")
        
        # Element diversity (0-1 points)
        element_types = stats['headers'] + stats['captions'] + stats['textfloats']
        if element_types > 0:
            quality_score += 1
            print("   ✅ Element type diversity: GOOD")
        else:
            print("   ⚠️  Element type diversity: LIMITED")
        
        # Size efficiency (0-1 points)
        words_per_kb = stats['words'] / (stats['total_size_bytes'] / 1024)
        if words_per_kb > 20:
            quality_score += 1
            print("   ✅ Size efficiency: GOOD")
        elif words_per_kb > 10:
            quality_score += 0.5
            print("   ⚠️  Size efficiency: ACCEPTABLE")
        else:
            print("   ❌ Size efficiency: POOR")
        
        final_score = (quality_score / max_score) * 100
        print(f"\n🏆 Overall Quality Score: {final_score:.1f}% ({quality_score:.1f}/{max_score})")
        
        if final_score >= 80:
            print("🎉 EXCELLENT - Ready for production use!")
        elif final_score >= 60:
            print("✅ GOOD - Minor improvements possible")
        elif final_score >= 40:
            print("⚠️  FAIR - Some issues need attention")
        else:
            print("❌ POOR - Significant improvements needed")
        
        return True

if __name__ == "__main__":
    success = test_hocr_integration()
    exit(0 if success else 1)
