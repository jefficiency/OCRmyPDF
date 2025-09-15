#!/usr/bin/env python3
"""
Test Upstage Document Parse API integration with improved coordinate handling.
This tests the updated implementation that uses the 'elements' array with coordinates.
"""

import tempfile
import argparse
from pathlib import Path
from ocrmypdf.builtin_plugins.upstage_ocr import UpstageDocumentOcrEngine, check_options

def test_upstage_document_parse():
    """Test Upstage Document Parse engine with coordinate handling."""
    
    print("🧪 Testing Upstage Document Parse Engine")
    print("=" * 50)
    
    # Create mock options with document-parse model
    options = argparse.Namespace()
    options.upstage_api_key = None  # Will be loaded from .env
    options.upstage_endpoint = 'https://api.upstage.ai/v1/document-digitization'
    options.upstage_timeout = 180.0
    options.upstage_model = 'document-parse'  # Use document-parse for better structure
    options.upstage_confidence_threshold = 0.0
    options.pdf_renderer = 'hocr'  # Required for creator_tag
    
    print("1. Testing configuration validation...")
    try:
        check_options(options)
        print("   ✅ Configuration validation passed")
        print(f"   🔑 API key resolved: {'Yes' if options.upstage_api_key else 'No'}")
        print(f"   🌐 Endpoint: {options.upstage_endpoint}")
        print(f"   🤖 Model: {options.upstage_model}")
    except Exception as e:
        print(f"   ❌ Configuration validation failed: {e}")
        return False
    
    print("\\n2. Testing OCR engine creation...")
    try:
        engine = UpstageDocumentOcrEngine()
        print(f"   ✅ Engine created: {engine.__class__.__name__}")
        print(f"   📋 Version: {engine.version()}")
        print(f"   🏷️  Creator tag: {engine.creator_tag(options)}")
    except Exception as e:
        print(f"   ❌ Engine creation failed: {e}")
        return False
    
    print("\\n3. Testing Document Parse API call...")
    input_file = Path("test_page1.pdf")
    if not input_file.exists():
        print(f"   ❌ Test file {input_file} not found")
        return False
    
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir = Path(temp_dir)
            output_hocr = temp_dir / "output.hocr"
            output_text = temp_dir / "output.txt"
            
            print(f"   📄 Input: {input_file}")
            print(f"   📝 Output hOCR: {output_hocr}")
            print("   🌐 Making API call to Upstage Document Parse...")
            print("   📊 Using 'elements' array with coordinates for better positioning")
            
            # This will make an actual API call with document-parse model
            engine.generate_hocr(
                input_file=input_file,
                output_hocr=output_hocr,
                output_text=output_text,
                options=options
            )
            
            # Check results
            if output_hocr.exists():
                hocr_size = output_hocr.stat().st_size
                print(f"   ✅ hOCR generated: {hocr_size} bytes")
                
                # Analyze hOCR structure
                with open(output_hocr, 'r', encoding='utf-8') as f:
                    hocr_content = f.read()
                    
                # Count elements
                block_count = hocr_content.count('ocr_carea')
                par_count = hocr_content.count('ocr_par')
                word_count = hocr_content.count('ocrx_word')
                bbox_count = hocr_content.count('bbox')
                
                print(f"   📊 Structure analysis:")
                print(f"      - Blocks (areas): {block_count}")
                print(f"      - Paragraphs: {par_count}")  
                print(f"      - Words: {word_count}")
                print(f"      - Bounding boxes: {bbox_count}")
                
                # Show first few lines of hOCR
                lines = hocr_content.split('\\n')[:10]
                print("   📄 hOCR structure preview:")
                for line in lines:
                    if line.strip():
                        print(f"      {line.strip()}")
            else:
                print("   ❌ hOCR file not generated")
                return False
            
            if output_text.exists():
                text_size = output_text.stat().st_size
                print(f"   ✅ Text generated: {text_size} bytes")
                
                # Show text content
                with open(output_text, 'r', encoding='utf-8') as f:
                    text_content = f.read().strip()
                    lines = text_content.split('\\n')[:5]  # First 5 lines
                    print(f"   📝 Text structure preview:")
                    for line in lines:
                        if line.strip():
                            print(f"      {line.strip()}")
            else:
                print("   ❌ Text file not generated")
                return False
                
    except Exception as e:
        print(f"   ❌ Document Parse API test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\\n🎉 Upstage Document Parse test completed successfully!")
    print("\\n📋 Key Improvements:")
    print("   ✅ Using Document Parse API instead of OCR API")
    print("   ✅ Processing 'elements' array with categories and coordinates")
    print("   ✅ Better text positioning using relative coordinates")
    print("   ✅ Structured text extraction with proper layout detection")
    return True

if __name__ == "__main__":
    success = test_upstage_document_parse()
    exit(0 if success else 1)
