#!/usr/bin/env python3
"""
Direct test of Upstage OCR engine functionality.
This bypasses OCRmyPDF's plugin selection and tests Upstage directly.
"""

import tempfile
import argparse
from pathlib import Path
from ocrmypdf.builtin_plugins.upstage_ocr import UpstageDocumentOcrEngine, check_options

def test_upstage_ocr():
    """Test Upstage OCR engine directly."""
    
    print("🧪 Testing Upstage OCR Engine Directly")
    print("=" * 50)
    
    # Create mock options
    options = argparse.Namespace()
    options.upstage_api_key = None  # Will be loaded from .env
    options.upstage_endpoint = 'https://api.upstage.ai/v1/document-digitization'
    options.upstage_timeout = 180.0
    options.upstage_model = 'ocr'
    options.upstage_confidence_threshold = 0.0
    options.pdf_renderer = 'hocr'  # Required for creator_tag
    
    print("1. Testing configuration validation...")
    try:
        check_options(options)
        print("   ✅ Configuration validation passed")
        print(f"   🔑 API key resolved: {'Yes' if options.upstage_api_key else 'No'}")
        print(f"   🌐 Endpoint: {options.upstage_endpoint}")
    except Exception as e:
        print(f"   ❌ Configuration validation failed: {e}")
        return False
    
    print("\n2. Testing OCR engine creation...")
    try:
        engine = UpstageDocumentOcrEngine()
        print(f"   ✅ Engine created: {engine.__class__.__name__}")
        print(f"   📋 Version: {engine.version()}")
        print(f"   🏷️  Creator tag: {engine.creator_tag(options)}")
    except Exception as e:
        print(f"   ❌ Engine creation failed: {e}")
        return False
    
    print("\n3. Testing hOCR generation...")
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
            print("   🌐 Making API call to Upstage...")
            
            # This will make an actual API call
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
                
                # Show first few lines of hOCR
                with open(output_hocr, 'r', encoding='utf-8') as f:
                    lines = f.readlines()[:5]
                    print("   📄 hOCR preview:")
                    for line in lines:
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
                    preview = text_content[:200] + "..." if len(text_content) > 200 else text_content
                    print(f"   📝 Text preview: {preview}")
            else:
                print("   ❌ Text file not generated")
                return False
                
    except Exception as e:
        print(f"   ❌ hOCR generation failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n🎉 Upstage OCR test completed successfully!")
    return True

if __name__ == "__main__":
    success = test_upstage_ocr()
    exit(0 if success else 1)
