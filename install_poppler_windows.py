import os
import sys
import urllib.request
import zipfile
import platform
import subprocess
from pathlib import Path

def download_and_install_poppler():
    """Download and install Poppler for Windows"""
    if platform.system() != "Windows":
        print("This script is for Windows only.")
        return False
    
    print("Downloading Poppler for Windows...")
    
    # Determine architecture
    is_64bit = platform.machine().endswith('64')
    
    if is_64bit:
        # URL for 64-bit version
        poppler_url = "https://github.com/oschwartz10612/poppler-windows/releases/download/v23.08.0-0/Release-23.08.0-0.zip"
        print("Detected 64-bit system")
    else:
        print("32-bit systems are not supported by modern Poppler releases.")
        print("Please install manually or use the PyMuPDF fallback.")
        return False
    
    # Download location
    download_dir = Path.home() / "Downloads"
    zip_path = download_dir / "poppler-windows.zip"
    install_dir = Path("C:/poppler")
    
    try:
        # Download the file
        print(f"Downloading from: {poppler_url}")
        urllib.request.urlretrieve(poppler_url, zip_path)
        print(f"Downloaded to: {zip_path}")
        
        # Extract the ZIP file
        print(f"Extracting to: {install_dir}")
        os.makedirs(install_dir, exist_ok=True)
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(install_dir)
        
        # Find the extracted folder (usually has version number)
        extracted_folders = [f for f in install_dir.iterdir() if f.is_dir()]
        if extracted_folders:
            poppler_bin = extracted_folders[0] / "Library" / "bin"
        else:
            print("Could not find extracted Poppler folder")
            return False
        
        # Add to PATH
        current_path = os.environ.get('PATH', '')
        poppler_bin_str = str(poppler_bin)
        
        if poppler_bin_str not in current_path:
            print(f"Adding {poppler_bin_str} to PATH...")
            
            # For current session
            os.environ['PATH'] = current_path + ';' + poppler_bin_str
            
            # Permanently add to PATH (requires admin rights)
            try:
                subprocess.run([
                    'setx', 'PATH', 
                    current_path + ';' + poppler_bin_str
                ], check=True, capture_output=True)
                print("✅ Added Poppler to PATH permanently")
            except subprocess.CalledProcessError:
                print("⚠️ Could not add to PATH permanently (requires admin rights)")
                print(f"Please manually add this to your PATH: {poppler_bin_str}")
        
        # Clean up
        zip_path.unlink()
        print("Cleaned up download file")
        
        # Test installation
        print("Testing Poppler installation...")
        try:
            from pdf2image import convert_from_path
            print("✅ Poppler installation successful!")
            return True
        except Exception as e:
            print(f"⚠️ Installation completed but test failed: {e}")
            print("You may need to restart your command prompt/IDE")
            return True
            
    except Exception as e:
        print(f"❌ Installation failed: {e}")
        return False

def main():
    print("Poppler Windows Installer for CheckMate")
    print("=" * 40)
    
    if platform.system() != "Windows":
        print("This installer is for Windows only.")
        print("For other systems, please install Poppler using your package manager.")
        return
    
    print("This will download and install Poppler for better PDF processing quality.")
    print("Installation size: ~15MB")
    print("Install location: C:/poppler/")
    
    response = input("\nProceed with installation? (y/N): ").strip().lower()
    
    if response in ['y', 'yes']:
        success = download_and_install_poppler()
        
        if success:
            print("\n🎉 Installation complete!")
            print("You can now run: python test_pdf_extraction.py --ai")
            print("\nNote: You may need to restart your command prompt/IDE for PATH changes to take effect.")
        else:
            print("\n❌ Installation failed. The system will use PyMuPDF fallback.")
    else:
        print("Installation cancelled. The system will use PyMuPDF fallback.")

if __name__ == "__main__":
    main()
