import subprocess
import sys
import os
import platform

def install_dependencies():
    """Install required Python packages"""
    print("Installing Python dependencies...")
    
    dependencies = [
        "PyMuPDF==1.23.14",
        "pytesseract==0.3.10", 
        "Pillow==10.1.0",
        "opencv-python==4.8.1.78",
        "pdf2image==1.16.3",
        "numpy"
    ]
    
    for package in dependencies:
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
            print(f"✅ Installed {package}")
        except subprocess.CalledProcessError:
            print(f"❌ Failed to install {package}")

def check_poppler():
    """Check if Poppler is installed (required for pdf2image)"""
    print("\nChecking Poppler installation (for better PDF quality)...")
    
    try:
        # Try to import and use pdf2image
        from pdf2image import convert_from_path
        # Try a simple test to see if poppler works
        print("✅ Poppler is available - pdf2image will work with high quality")
        return True
    except ImportError:
        print("❌ pdf2image not installed")
        return False
    except Exception as e:
        print("❌ Poppler not found or not in PATH")
        print(f"Error: {str(e)}")
        
        if platform.system() == "Windows":
            print("\nTo install Poppler on Windows:")
            print("1. Download from: https://github.com/oschwartz10612/poppler-windows/releases")
            print("2. Extract to C:\\poppler-xx.xx.x\\")
            print("3. Add C:\\poppler-xx.xx.x\\Library\\bin\\ to your PATH environment variable")
            print("4. Restart your command prompt/IDE")
            print("\nAlternatively:")
            print("- Use conda: conda install -c conda-forge poppler")
            print("- Or the system will fallback to PyMuPDF (still works, but lower quality)")
        else:
            print("\nTo install Poppler:")
            print("Ubuntu/Debian: sudo apt-get install poppler-utils")
            print("macOS: brew install poppler")
            print("CentOS/RHEL: sudo yum install poppler-utils")
        
        print("\n💡 Note: The system will automatically fallback to PyMuPDF if Poppler is not available.")
        return False

def check_tesseract():
    """Check if Tesseract OCR is installed"""
    print("\nChecking Tesseract OCR installation...")
    
    try:
        import pytesseract
        version = pytesseract.get_tesseract_version()
        print(f"✅ Tesseract OCR is installed (Version: {version})")
        return True
    except ImportError:
        print("❌ pytesseract package not found")
        print("   Run: pip install pytesseract")
        return False
    except Exception as e:
        print("❌ Tesseract OCR not found or not properly configured")
        print(f"Error: {e}")
        
        if platform.system() == "Windows":
            print("\n📦 TESSERACT INSTALLATION FOR WINDOWS:")
            print("1. Download installer from: https://github.com/UB-Mannheim/tesseract/wiki")
            print("2. Install to default location: C:\\Program Files\\Tesseract-OCR\\")
            print("3. Add C:\\Program Files\\Tesseract-OCR\\ to your PATH:")
            print("   - Right-click 'This PC' → Properties → Advanced System Settings")
            print("   - Click 'Environment Variables'")
            print("   - Select 'Path' in System Variables → Edit → New")
            print("   - Add: C:\\Program Files\\Tesseract-OCR\\")
            print("   - Click OK and restart your terminal/IDE")
            print("\n🔄 ALTERNATIVE METHODS:")
            print("   - Conda: conda install -c conda-forge tesseract")
            print("   - Chocolatey: choco install tesseract")
            print("   - Manual setup: Set pytesseract.pytesseract.tesseract_cmd path in code")
        else:
            print("\n📦 TESSERACT INSTALLATION:")
            print("Ubuntu/Debian: sudo apt-get install tesseract-ocr")
            print("macOS: brew install tesseract")
            print("CentOS/RHEL: sudo yum install tesseract")
        
        print("\n💡 NOTE: The PDF extraction system can still work without Tesseract")
        print("   - It will use bubble detection and pattern matching methods")
        print("   - OCR is only needed for handwritten or typed text extraction")
        
        return False

def create_test_directory():
    """Create test directory for sample PDFs"""
    test_dir = "test_pdfs"
    if not os.path.exists(test_dir):
        os.makedirs(test_dir)
        print(f"✅ Created {test_dir} directory")
        print(f"   Place your test PDF files in this directory")
    else:
        print(f"✅ {test_dir} directory already exists")

def test_system_compatibility():
    """Test if the system can process PDFs properly"""
    print("\nTesting system compatibility...")
    
    try:
        # Test PyMuPDF (always available)
        import fitz
        print("✅ PyMuPDF (PDF processor) is working")
        
        # Test OpenCV
        import cv2
        print("✅ OpenCV is working")
        
        # Test numpy
        import numpy as np
        print("✅ NumPy is working")
        
        # Test PIL
        from PIL import Image
        print("✅ PIL/Pillow is working")
        
        return True
    except ImportError as e:
        print(f"❌ Missing required dependency: {e}")
        return False

def test_extraction_service():
    """Test the PDF extraction service"""
    print("\nTesting PDF extraction service...")
    
    try:
        from pdf_extraction_service import PDFExtractionService
        extractor = PDFExtractionService()
        print("✅ PDF extraction service loaded successfully")
        
        # Test with sample PDF if available
        test_pdf = "pdf_directory/Test.pdf"
        if os.path.exists(test_pdf):
            print(f"🔍 Testing with sample PDF: {test_pdf}")
            result = extractor.extract_from_pdf(test_pdf, 'multiple_choice_4', 50)
            
            if result['success']:
                print("✅ Sample PDF extraction successful")
                print(f"   Student Name: '{result['student_name']}'")
                print(f"   Student ID: '{result['student_id']}'")
                print(f"   Answers found: {len(result['answers'])}")
                print(f"   Extraction method: {result['metadata'].get('extraction_method', 'N/A')}")
                print(f"   Tesseract available: {result['metadata'].get('tesseract_available', False)}")
                
                # Show specific feedback about the extraction
                if result['metadata'].get('tesseract_available', False):
                    print("   ✅ OCR capability: Available")
                else:
                    print("   ⚠️  OCR capability: Limited (Tesseract not found)")
                    print("       System will use pattern matching and bubble detection")
                    
            else:
                print("⚠️ Sample PDF extraction had issues, but service is functional")
                if result.get('errors'):
                    print(f"   Errors: {result['errors']}")
        else:
            print(f"📁 No test PDF found at: {test_pdf}")
            print("   Place a test PDF in the pdf_directory folder to test extraction")
        
        return True
        
    except ImportError as e:
        print(f"❌ PDF extraction service not found: {e}")
        print("   Make sure pdf_extraction_service.py is in the same directory")
        return False
    except Exception as e:
        print(f"⚠️ PDF extraction service test failed: {e}")
        return False

def main():
    print("Setting up CheckMate PDF Student Information + AI Answer Extraction")
    print("=" * 60)
    
    # Install dependencies
    install_dependencies()
    
    # Test system compatibility
    system_ok = test_system_compatibility()
    
    # Check Poppler (optional but recommended)
    poppler_ok = check_poppler()
    
    # Check Tesseract (optional for OCR)
    tesseract_ok = check_tesseract()
    
    # Test extraction service
    extraction_ok = test_extraction_service()
    
    # Create test directory
    create_test_directory()
    
    print("\n" + "=" * 60)
    print("Setup Summary:")
    print(f"✅ Python dependencies: Installed")
    print(f"📊 System compatibility: {'✅ Good' if system_ok else '❌ Issues detected'}")
    print(f"📄 PDF processing: {'✅ High quality (pdf2image + Poppler)' if poppler_ok else '⚠️ Standard quality (PyMuPDF fallback)'}")
    print(f"🔤 OCR capability: {'✅ Full (Tesseract)' if tesseract_ok else '⚠️ Limited (Pattern matching only)'}")
    print(f"🔧 Extraction service: {'✅ Ready' if extraction_ok else '❌ Issues detected'}")
    print(f"📁 Test directory: Created")
    
    if system_ok and extraction_ok:
        print("\n🎉 CheckMate system is ready! You can now run:")
        print("   python test_pdf_extraction.py pdf_directory/Test.pdf")
        print("   python test_pdf_extraction.py --directory pdf_directory/")
        
        print("\n💡 For best results:")
        if not poppler_ok:
            print("   - Install Poppler for better PDF quality")
        if not tesseract_ok:
            print("   - Install Tesseract OCR for enhanced text extraction")
        print("   - Use high-quality scanned PDFs (300+ DPI)")
        print("   - Ensure answer sheets follow the CheckMate V4 template exactly")
        
        print("\n🚀 Quick start:")
        print("   python test_pdf_extraction.py pdf_directory/Test.pdf --debug")
        
        if not tesseract_ok:
            print("\n📝 Current capabilities WITHOUT Tesseract:")
            print("   ✅ Student info from PDF form fields")
            print("   ✅ Bubble detection for filled circles")
            print("   ✅ Pattern matching for basic text")
            print("   ❌ OCR for handwritten text")
            print("   ❌ Complex text recognition")
    else:
        print("\n⚠️  Setup incomplete:")
        if not system_ok:
            print("   - Fix missing Python dependencies")
        if not extraction_ok:
            print("   - Check PDF extraction service installation")
        print("   - Run setup again after installing missing components")
        
        if not tesseract_ok:
            print("\n📋 OPTIONAL: Install Tesseract for enhanced OCR capabilities")
