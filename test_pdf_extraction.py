import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import re
import io
import os
import sys

class StudentInfoExtractor:
    def __init__(self):
        # Set up Tesseract path (adjust if needed)
        pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
        
        # Regex patterns for student information
        self.student_id_patterns = [
            r'Student\s*ID[:\s]*([A-Z0-9\-]+)',
            r'ID[:\s]*([A-Z0-9\-]+)',
            r'Student\s*Number[:\s]*([A-Z0-9\-]+)',
            r'(\d{4}-\d{5}-[A-Z]{2}-\d)',  # Format like 2024-05529-CM-0
            r'Student\s*No[.:\s]*([A-Z0-9\-]+)',  # Added for "Student No."
            r'ID\s*No[.:\s]*([A-Z0-9\-]+)',       # Added for "ID No."
        ]
        
        self.student_name_patterns = [
            r'Name[:\s]*([A-Za-z\s,]+?)(?:\s*Student|$)',
            r'Student\s*Name[:\s]*([A-Za-z\s,]+?)(?:\s*Student|$)',
            r'STUDENT\s*INFORMATION[^:]*Name[:\s]*([A-Za-z\s,]+)',
            r'Name[:\s]*([A-Za-z\s,\.]+?)(?:\s*ID|$)',  # Added to catch name before ID
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',       # Pattern for proper names
        ]

    def pdf_to_images(self, pdf_path, dpi=300):
        """Convert PDF pages to images for OCR processing"""
        try:
            doc = fitz.open(pdf_path)
            images = []
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                
                # Convert page to image
                mat = fitz.Matrix(dpi/72, dpi/72)  # Scale factor for DPI
                pix = page.get_pixmap(matrix=mat)
                img_data = pix.tobytes("png")
                
                # Convert to PIL Image
                img = Image.open(io.BytesIO(img_data))
                images.append(img)
                
                print(f"Converted page {page_num + 1} to image (Size: {img.size})")
            
            doc.close()
            return images
            
        except Exception as e:
            print(f"Error converting PDF to images: {e}")
            return []

    def extract_text_from_image(self, image):
        """Extract text from image using OCR"""
        try:
            # Try different OCR configurations
            configs = [
                '--psm 6',  # Uniform block of text
                '--psm 4',  # Single column of text
                '--psm 3',  # Default
            ]
            
            best_text = ""
            best_confidence = 0
            
            for config in configs:
                try:
                    # Extract text with confidence scores
                    data = pytesseract.image_to_data(image, config=config, output_type=pytesseract.Output.DICT)
                    
                    # Calculate average confidence
                    confidences = [int(conf) for conf in data['conf'] if int(conf) > 0]
                    avg_confidence = sum(confidences) / len(confidences) if confidences else 0
                    
                    if avg_confidence > best_confidence:
                        best_confidence = avg_confidence
                        best_text = pytesseract.image_to_string(image, config=config)
                    
                    print(f"OCR Config '{config}': Avg confidence = {avg_confidence:.1f}%")
                    
                except Exception as e:
                    print(f"OCR config '{config}' failed: {e}")
                    continue
            
            print(f"Best OCR result: {best_confidence:.1f}% confidence")
            return best_text, best_confidence
            
        except Exception as e:
            print(f"Error during OCR: {e}")
            return "", 0

    def extract_student_info(self, text):
        """Extract student ID and name from text using regex patterns"""
        student_id = None
        student_name = None
        
        print("\n=== EXTRACTED TEXT ===")
        print(text)
        print("======================\n")
        
        # Clean up text
        text = re.sub(r'\s+', ' ', text.strip())
        
        # Extract Student ID
        for i, pattern in enumerate(self.student_id_patterns):
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                student_id = match.group(1).strip()
                print(f"Found Student ID with pattern #{i+1} '{pattern}': {student_id}")
                break
        
        # Extract Student Name
        for i, pattern in enumerate(self.student_name_patterns):
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                student_name = match.group(1).strip()
                # Clean up name (remove extra spaces, trailing punctuation)
                student_name = re.sub(r'[,._]+$', '', student_name)
                student_name = re.sub(r'\s+', ' ', student_name)
                print(f"Found Student Name with pattern #{i+1} '{pattern}': {student_name}")
                break
        
        # Additional cleanup and validation
        if student_name:
            # Remove common OCR artifacts and clean up
            student_name = re.sub(r'\b(Student|ID|Name|Information)\b', '', student_name, flags=re.IGNORECASE).strip()
            student_name = re.sub(r'[^A-Za-z\s]', ' ', student_name)  # Remove non-letter chars except spaces
            student_name = re.sub(r'\s+', ' ', student_name).strip()   # Normalize spaces
            
            # Validate name (should have at least 2 words)
            if len(student_name.split()) < 2:
                print(f"Invalid name (too short): '{student_name}' - trying other patterns...")
                student_name = None
        
        return student_id, student_name

    def save_debug_images(self, pdf_path, images):
        """Save debug images to help with OCR troubleshooting"""
        debug_dir = os.path.join(os.path.dirname(pdf_path), 'debug_images')
        os.makedirs(debug_dir, exist_ok=True)
        
        base_name = os.path.splitext(os.path.basename(pdf_path))[0]
        
        for i, img in enumerate(images):
            # Save full page
            full_path = os.path.join(debug_dir, f"{base_name}_page_{i+1}_full.png")
            img.save(full_path)
            print(f"Saved debug image: {full_path}")
            
            # Save cropped top section for student info
            width, height = img.size
            top_section = img.crop((0, 0, width, height // 3))
            crop_path = os.path.join(debug_dir, f"{base_name}_page_{i+1}_student_info.png")
            top_section.save(crop_path)
            print(f"Saved student info section: {crop_path}")

    def process_pdf(self, pdf_path, save_debug=False):
        """Main function to process a PDF and extract student information"""
        print(f"\n{'='*60}")
        print(f"Processing: {os.path.basename(pdf_path)}")
        print(f"Full path: {pdf_path}")
        print("Mode: Extract student info only")
        print(f"{'='*60}")
        
        if not os.path.exists(pdf_path):
            print(f"Error: File not found - {pdf_path}")
            return None
        
        # Convert PDF to images
        images = self.pdf_to_images(pdf_path)
        if not images:
            print("Failed to convert PDF to images")
            return None
        
        # Save debug images if requested
        if save_debug:
            self.save_debug_images(pdf_path, images)
        
        # Process only the first page
        first_page = images[0]
        
        # Extract student information from top section
        width, height = first_page.size
        print(f"Original image size: {width}x{height}")
        
        # Focus on top section where student info is typically located
        top_section = first_page.crop((0, 0, width, height // 3))
        print(f"Student info section size: {top_section.size}")
        
        text, confidence = self.extract_text_from_image(top_section)
        student_id, student_name = self.extract_student_info(text)
        
        result = {
            'file': os.path.basename(pdf_path),
            'student_id': student_id,
            'student_name': student_name,
            'ocr_confidence': confidence,
            'raw_text': text[:500] + "..." if len(text) > 500 else text,
            'full_path': pdf_path
        }
        
        return result

    def process_multiple_files(self, pdf_directory):
        """Process multiple PDF files for student information extraction"""
        results = []
        
        pdf_files = [f for f in os.listdir(pdf_directory) if f.lower().endswith('.pdf')]
        
        if not pdf_files:
            print(f"No PDF files found in {pdf_directory}")
            return results
        
        print(f"Found {len(pdf_files)} PDF files to process")
        
        for pdf_file in pdf_files:
            pdf_path = os.path.join(pdf_directory, pdf_file)
            result = self.process_pdf(pdf_path)
            if result:
                results.append(result)
        
        return results

def main():
    """Main function to test the extraction"""
    extractor = StudentInfoExtractor()
    
    # Default test file path
    default_pdf_path = r"D:\YUKI\ADET\Checkmate\pdf_directory\Test.pdf"
    
    # Check command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == '--help' or sys.argv[1] == '-h':
            print("Usage:")
            print(f"  python {sys.argv[0]}                    # Use default test file")
            print(f"  python {sys.argv[0]} <path_to_pdf>      # Use specific PDF file")
            print(f"  python {sys.argv[0]} --debug            # Use default file with debug images")
            print(f"  python {sys.argv[0]} --batch <directory> # Process all PDFs in directory")
            print(f"\nDefault test file: {default_pdf_path}")
            return
        
        elif sys.argv[1] == '--debug':
            pdf_path = default_pdf_path
            save_debug = True
        elif sys.argv[1] == '--batch':
            if len(sys.argv) > 2:
                directory = sys.argv[2]
                save_debug = '--debug' in sys.argv
                
                results = extractor.process_multiple_files(directory)
                
                print(f"\n{'='*60}")
                print("BATCH PROCESSING RESULTS")
                print(f"{'='*60}")
                
                successful = 0
                for result in results:
                    success_indicators = []
                    if result['student_id']: success_indicators.append("ID")
                    if result['student_name']: success_indicators.append("Name")
                    
                    status = f"[{', '.join(success_indicators) if success_indicators else 'No Info'}]"
                    print(f"{status:<15} {result['file']}")
                    
                    if result['student_id'] or result['student_name']:
                        successful += 1
                        if result['student_id']: print(f"                Student ID: {result['student_id']}")
                        if result['student_name']: print(f"                Student Name: {result['student_name']}")
                        print(f"                OCR Confidence: {result['ocr_confidence']:.1f}%")
                        print()
                
                print(f"Summary: {successful}/{len(results)} files processed successfully")
                return
            else:
                print("Error: --batch requires a directory path")
                return
        else:
            pdf_path = sys.argv[1]
            save_debug = '--debug' in sys.argv
    else:
        pdf_path = default_pdf_path
        save_debug = False
    
    print(f"Testing PDF extraction with: {pdf_path}")
    if save_debug:
        print("Debug mode: Will save cropped images for analysis")
    
    # Process the PDF
    result = extractor.process_pdf(pdf_path, save_debug=save_debug)
    
    if result:
        print(f"\n{'='*60}")
        print("EXTRACTION RESULTS")
        print(f"{'='*60}")
        print(f"File: {result['file']}")
        print(f"Student ID: {result['student_id'] or 'Not found'}")
        print(f"Student Name: {result['student_name'] or 'Not found'}")
        print(f"OCR Confidence: {result['ocr_confidence']:.1f}%")
        
        print(f"\nRaw Text Preview:")
        print("-" * 40)
        print(result['raw_text'])
        print("-" * 40)
        
        # Summary
        success_rate = 0
        if result['student_id']: success_rate += 50
        if result['student_name']: success_rate += 50
        
        print(f"\nExtraction Success Rate: {success_rate}%")
        
        if success_rate >= 75:
            print("✅ Extraction successful!")
        elif success_rate >= 50:
            print("⚠️ Partial extraction - some information missing")
        else:
            print("❌ Extraction failed - no student information found")
            
        if save_debug:
            debug_dir = os.path.join(os.path.dirname(pdf_path), 'debug_images')
            print(f"\n📁 Debug images saved to: {debug_dir}")
            print("   Review these images to troubleshoot OCR issues")
    else:
        print("❌ Failed to process PDF file")
    
    # Additional testing suggestions
    print(f"\n{'='*60}")
    print("USAGE EXAMPLES")
    print(f"{'='*60}")
    print("1. Process single file with debug:")
    print(f"   python {sys.argv[0]} --debug")
    print("\n2. Process specific file:")
    print(f"   python {sys.argv[0]} path/to/your/file.pdf")
    print("\n3. Batch process directory:")
    print(f"   python {sys.argv[0]} --batch path/to/pdf/directory")
    print("\n4. If OCR confidence is low, try:")
    print("   - Better quality PDF scan")
    print("   - Adjusting DPI in pdf_to_images() method")
    print("   - Different OCR page segmentation modes")

if __name__ == "__main__":
    main()


