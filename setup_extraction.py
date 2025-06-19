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
        "opencv-python==4.8.1.78"
    ]
    
    for package in dependencies:
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
            print(f"✅ Installed {package}")
        except subprocess.CalledProcessError:
            print(f"❌ Failed to install {package}")

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

def main():
    print("Setting up PDF Student Information Extraction")
    print("=" * 50)
    
    # Install dependencies
    install_dependencies()
    
    # Check Tesseract
    tesseract_ok = check_tesseract()
    
    # Create test directory
    create_test_directory()
    
    print("\n" + "=" * 50)
    print("Setup Summary:")
    print(f"Python dependencies: ✅ Installed")
    print(f"Tesseract OCR: {'✅ Ready' if tesseract_ok else '❌ Needs installation'}")
    print(f"Test directory: ✅ Created")
    
    if tesseract_ok:
        print("\n🎉 Setup complete! You can now run:")
        print("   python test_pdf_extraction.py <path_to_pdf>")
        print("   or place PDFs in test_pdfs/ directory and run:")
        print("   python test_pdf_extraction.py")
    else:
        print("\n⚠️  Please install Tesseract OCR before proceeding")

if __name__ == "__main__":
    main()
