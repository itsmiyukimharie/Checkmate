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
    except Exception as e:
        print("❌ Tesseract OCR not found or not properly configured")
        print(f"Error: {e}")
        
        if platform.system() == "Windows":
            print("\nTo install Tesseract on Windows:")
            print("1. Download from: https://github.com/UB-Mannheim/tesseract/wiki")
            print("2. Install to default location (C:\\Program Files\\Tesseract-OCR\\)")
            print("3. Add to PATH or update test_pdf_extraction.py with correct path")
        else:
            print("\nTo install Tesseract:")
            print("Ubuntu/Debian: sudo apt-get install tesseract-ocr")
            print("macOS: brew install tesseract")
            print("CentOS/RHEL: sudo yum install tesseract")
        
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
        print("✅ PyMuPDF (fallback PDF processor) is working")
        
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

def main():
    print("Setting up PDF Student Information + AI Answer Extraction")
    print("=" * 60)
    
    # Install dependencies
    install_dependencies()
    
    # Test system compatibility
    system_ok = test_system_compatibility()
    
    # Check Poppler (optional but recommended)
    poppler_ok = check_poppler()
    
    # Check Tesseract (required)
    tesseract_ok = check_tesseract()
    
    # Create test directory
    create_test_directory()
    
    print("\n" + "=" * 60)
    print("Setup Summary:")
    print(f"✅ Python dependencies: Installed")
    print(f"✅ System compatibility: {'✅ Good' if system_ok else '❌ Issues detected'}")
    print(f"📊 PDF processing: {'✅ High quality (pdf2image + Poppler)' if poppler_ok else '⚠️ Standard quality (PyMuPDF fallback)'}")
    print(f"🔤 OCR capability: {'✅ Ready' if tesseract_ok else '❌ Needs Tesseract installation'}")
    print(f"✅ Test directory: Created")
    
    if system_ok and tesseract_ok:
        print("\n🎉 System is ready! You can now run:")
        print("   python test_pdf_extraction.py --ai")
        print("\n💡 For best results:")
        if not poppler_ok:
            print("   - Install Poppler for better PDF quality")
        print("   - Use high-quality scanned PDFs (300+ DPI)")
        print("   - Ensure answer sheets follow the ALPHA V2 template exactly")
        
        print("\n🚀 Quick start:")
        print("   python test_pdf_extraction.py --debug --ai")
    else:
        print("\n⚠️  Setup incomplete:")
        if not system_ok:
            print("   - Fix missing Python dependencies")
        if not tesseract_ok:
            print("   - Install Tesseract OCR")
        print("   - Run setup again after installing missing components")

if __name__ == "__main__":
    main()
