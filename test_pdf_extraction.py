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
                for pos in question_bubbles:
                    print(f"  Expected {pos['choice']}: ({pos['x']}, {pos['y']})")
            
            # Check each choice for this question
            for bubble_pos in question_bubbles:
                expected_x = bubble_pos['x']
                expected_y = bubble_pos['y']
                choice = bubble_pos['choice']
                
                # Look for filled bubbles near this position
                for filled_bubble in filled_bubbles:
                    distance = ((filled_bubble['x'] - expected_x) ** 2 + (filled_bubble['y'] - expected_y) ** 2) ** 0.5
                    
                    if distance <= search_radius:
                        # Only take the first match per question to avoid duplicates
                        if question_num not in answers:
                            answers[question_num] = choice
                            
                            if debug:
                                print(f"  MATCH! Question {question_num}: {choice}")
                                print(f"    Expected: ({expected_x}, {expected_y})")
                                print(f"    Found: ({filled_bubble['x']}, {filled_bubble['y']})")
                                print(f"    Distance: {distance:.1f}")
                                print(f"    Fill ratio: {filled_bubble['fill_ratio']:.2f}")
                                
                                # Draw on debug image
                                cv2.circle(debug_img, (expected_x, expected_y), search_radius, (255, 0, 0), 2)
                                cv2.line(debug_img, (expected_x, expected_y), (filled_bubble['x'], filled_bubble['y']), (255, 255, 0), 2)
                                cv2.putText(debug_img, f"Q{question_num}:{choice}", (expected_x-20, expected_y-25), 
                                          cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 0, 0), 1)
                            break
        
        if debug:
            cv2.imwrite(os.path.join(debug_dir, 'corrected_position_mapping.png'), debug_img)
            
            # Draw the expected grid overlay
            grid_img = cv_image.copy()
            for q in range(1, 51):
                positions = get_question_bubble_positions(q)
                for pos in positions:
                    # Draw expected positions as red circles
                    cv2.circle(grid_img, (pos['x'], pos['y']), bubble_radius, (0, 0, 255), 1)
                    if q <= 10:  # Label first 10 questions for reference
                        cv2.putText(grid_img, f"{q}{pos['choice']}", 
                                  (pos['x']-8, pos['y']+20), 
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.25, (0, 0, 255), 1)
            
            cv2.imwrite(os.path.join(debug_dir, 'expected_grid_overlay.png'), grid_img)
        
        # Fill in null for unanswered questions
        for q in range(1, 51):
            if q not in answers:
                answers[q] = None
        
        if debug:
            answered_questions = [q for q, ans in answers.items() if ans is not None]
            print(f"\nFinal detected answers: {answered_questions}")
            for q in answered_questions:
                print(f"  Question {q}: {answers[q]}")
        
        return answers

    def extract_answers_from_bubbles(self, bubbles, debug=False):
        """Extract answers from detected bubbles using improved ALPHA V2 layout detection"""
        if not bubbles:
            return {}
        
        # Filter only filled bubbles for answer extraction
        filled_bubbles = [b for b in bubbles if b['filled']]
        
        if debug:
            print(f"Processing {len(filled_bubbles)} filled bubbles out of {len(bubbles)} total")
            print("Filled bubble positions:")
            for i, bubble in enumerate(filled_bubbles):
                print(f"  Bubble {i}: x={bubble['center_x']}, y={bubble['center_y']}, area={bubble['area']:.0f}")
        
        # Use a grid-based approach to identify the answer sheet layout
        answers = {}
        
        # Determine the layout by analyzing bubble positions
        if filled_bubbles:
            # Find the approximate grid structure
            x_positions = [b['center_x'] for b in bubbles]
            y_positions = [b['center_y'] for b in bubbles]
            
            # Find column positions (A, B, C, D for each question)
            x_sorted = sorted(set(x_positions))
            y_sorted = sorted(set(y_positions))
            
            if debug:
                print(f"Unique X positions (first 20): {x_sorted[:20]}")
                print(f"Unique Y positions (first 20): {y_sorted[:20]}")
            
            # Group X positions into columns
            columns = self._group_positions(x_sorted, tolerance=30)
            rows = self._group_positions(y_sorted, tolerance=15)
            
            if debug:
                print(f"Identified {len(columns)} column groups")
                print(f"Identified {len(rows)} row groups")
            
            # Map filled bubbles to grid positions
            for bubble in filled_bubbles:
                col_index = self._find_position_group(bubble['center_x'], columns, tolerance=30)
                row_index = self._find_position_group(bubble['center_y'], rows, tolerance=15)
                
                if col_index is not None and row_index is not None:
                    # Calculate question number based on position
                    question_num = self._calculate_question_number(row_index, col_index, len(columns), debug)
                    
                    if 1 <= question_num <= 50:
                        # Determine answer letter (A, B, C, D)
                        answer_letter = self._get_answer_letter(col_index, len(columns), debug)
                        
                        if answer_letter:
                            if question_num in answers:
                                if debug:
                                    print(f"  WARNING: Multiple answers for question {question_num}: existing={answers[question_num]}, new={answer_letter}")
                            else:
                                answers[question_num] = answer_letter
                                if debug:
                                    print(f"  Question {question_num}: {answer_letter} (row={row_index}, col={col_index})")
        
        # Fill in null for questions without answers (1-50)
        for q in range(1, 51):
            if q not in answers:
                answers[q] = None
        
        if debug:
            answered_questions = [q for q, ans in answers.items() if ans is not None]
            print(f"\nFinal answers for questions: {answered_questions}")
            for q in answered_questions:
                print(f"  Question {q}: {answers[q]}")
        
        return answers

    def _group_positions(self, positions, tolerance=20):
        """Group similar positions together"""
        if not positions:
            return []
        
        groups = []
        current_group = [positions[0]]
        
        for pos in positions[1:]:
            if abs(pos - current_group[-1]) <= tolerance:
                current_group.append(pos)
            else:
                groups.append(current_group)
                current_group = [pos]
        
        groups.append(current_group)
        
        # Return the average position for each group
        return [sum(group) / len(group) for group in groups]

    def _find_position_group(self, position, groups, tolerance=20):
        """Find which group a position belongs to"""
        for i, group_center in enumerate(groups):
            if abs(position - group_center) <= tolerance:
                return i
        return None

    def _calculate_question_number(self, row_index, col_index, total_cols, debug=False):
        """Calculate question number based on grid position"""
        # ALPHA V2 layout has two columns of questions
        # Left column: questions 1-33, Right column: questions 34-50
        # Each question has 4 answer choices (A, B, C, D)
        
        if total_cols >= 8:  # Two columns of 4 choices each
            questions_per_column = 4  # A, B, C, D
            if col_index < total_cols // 2:
                # Left column
                question_num = row_index + 1
            else:
                # Right column
                question_num = row_index + 34
        else:
            # Single column or different layout
            questions_per_column = min(4, total_cols)
            question_num = (row_index * total_cols // questions_per_column) + 1
        
        if debug:
            print(f"    Row {row_index}, Col {col_index} -> Question {question_num}")
        
        return question_num

    def _get_answer_letter(self, col_index, total_cols, debug=False):
        """Get answer letter (A, B, C, D) based on column position"""
        if total_cols >= 8:  # Two columns of questions
            # Each question has 4 choices
            choice_index = col_index % 4
        else:
            choice_index = col_index % 4
        
        if 0 <= choice_index <= 3:
            answer = chr(65 + choice_index)  # A=65, B=66, C=67, D=68
            if debug:
                print(f"    Col {col_index} -> Choice {choice_index} -> {answer}")
            return answer
        
        return None

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
            
            # Save cropped top section
            width, height = img.size
            top_section = img.crop((0, 0, width, height // 3))
            crop_path = os.path.join(debug_dir, f"{base_name}_page_{i+1}_top_crop.png")
            top_section.save(crop_path)
            print(f"Saved cropped image: {crop_path}")
            
            # Save cropped answer section
            answer_section = img.crop((0, height // 3, width, height))
            answer_path = os.path.join(debug_dir, f"{base_name}_page_{i+1}_answers.png")
            answer_section.save(answer_path)
            print(f"Saved answer section: {answer_path}")

    def process_pdf(self, pdf_path, save_debug=False, extract_answers=False):
        """Main function to process a PDF and extract student information and answers"""
        print(f"\n{'='*60}")
        print(f"Processing: {os.path.basename(pdf_path)}")
        print(f"Full path: {pdf_path}")
        if extract_answers:
            print("Mode: Extract student info + answers (Position-based)")
        else:
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
        
        # Extract student information (keep existing OCR approach)
        width, height = first_page.size
        print(f"Original image size: {width}x{height}")
        
        # Top section for student info (works perfectly)
        top_section = first_page.crop((0, 0, width, height // 3))
        print(f"Top section crop size: {top_section.size}")
        
        text, confidence = self.extract_text_from_image(top_section)
        student_id, student_name = self.extract_student_info(text)
        
        # Extract answers if requested
        answers = {}
        if extract_answers:
            print("\nExtracting answer bubbles using position-based detection...")
            # Use the answer section for position-based detection
            answer_section = first_page.crop((0, height // 4, width, height - 50))
            print(f"Answer section crop size: {answer_section.size}")
            
            answers = self.extract_answers_from_position(answer_section, debug=save_debug)
            
            # Count non-null answers
            answered_questions = sum(1 for ans in answers.values() if ans is not None)
            print(f"Position-based detection found answers for {answered_questions} out of 50 questions")
        
        result = {
            'file': os.path.basename(pdf_path),
            'student_id': student_id,
            'student_name': student_name,
            'ocr_confidence': confidence,
            'raw_text': text[:500] + "..." if len(text) > 500 else text,
            'full_path': pdf_path,
            'answers': answers,
            'total_answers': sum(1 for ans in answers.values() if ans is not None) if answers else 0,
            'answered_questions': [q for q, ans in answers.items() if ans is not None] if answers else []
        }
        
        return result

    def test_multiple_files(self, pdf_directory):
        """Test extraction on multiple PDF files"""
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
            print(f"  python {sys.argv[0]} --answers          # Extract answers too")
            print(f"  python {sys.argv[0]} <path_to_pdf> --debug --answers  # Full extraction with debug")
            print(f"\nDefault test file: {default_pdf_path}")
            return
        
        elif sys.argv[1] == '--debug':
            pdf_path = default_pdf_path
            save_debug = True
            extract_answers = '--answers' in sys.argv
        elif sys.argv[1] == '--answers':
            pdf_path = default_pdf_path
            save_debug = '--debug' in sys.argv
            extract_answers = True
        else:
            pdf_path = sys.argv[1]
            save_debug = '--debug' in sys.argv
            extract_answers = '--answers' in sys.argv
    else:
        pdf_path = default_pdf_path
        save_debug = False
        extract_answers = False
    
    print(f"Testing PDF extraction with: {pdf_path}")
    if save_debug:
        print("Debug mode: Will save cropped images for analysis")
    if extract_answers:
        print("Answer extraction: Will detect filled bubbles")
    
    # Process the PDF
    result = extractor.process_pdf(pdf_path, save_debug=save_debug, extract_answers=extract_answers)
    
    if result:
        print(f"\n{'='*60}")
        print("EXTRACTION RESULTS")
        print(f"{'='*60}")
        print(f"File: {result['file']}")
        print(f"Student ID: {result['student_id'] or 'Not found'}")
        print(f"Student Name: {result['student_name'] or 'Not found'}")
        print(f"OCR Confidence: {result['ocr_confidence']:.1f}%")
        
        if extract_answers:
            print(f"Total Answers Detected: {result['total_answers']}")
            print(f"Answered Questions: {result['answered_questions']}")
            
            if result['answers']:
                print("\nDetected Answers (showing only answered questions):")
                for q_num in sorted(result['answers'].keys()):
                    if result['answers'][q_num] is not None:
                        print(f"  Question {q_num}: {result['answers'][q_num]}")
                
                print(f"\nUnanswered Questions: {[q for q in range(1, 51) if result['answers'].get(q) is None]}")
        
        print(f"\nRaw Text Preview:")
        print("-" * 40)
        print(result['raw_text'])
        print("-" * 40)
        
        # Summary
        success_rate = 0
        if result['student_id']: success_rate += 40
        if result['student_name']: success_rate += 40
        if extract_answers and result['total_answers'] > 0: success_rate += 20
        
        print(f"\nExtraction Success Rate: {success_rate}%")
        
        if success_rate >= 80:
            print("✅ Complete extraction successful!")
        elif success_rate >= 60:
            print("⚠️ Good extraction - minor information missing")
        elif success_rate >= 40:
            print("⚠️ Partial extraction - some information missing")
        else:
            print("❌ Extraction failed - limited information found")
            
        if save_debug:
            debug_dir = os.path.join(os.path.dirname(pdf_path), 'debug_images')
            print(f"\n📁 Debug images saved to: {debug_dir}")
            print("   Review these images to troubleshoot OCR issues")
            print("   - detected_bubbles.png shows all detected bubbles")
            print("   - gray_image.png and threshold_image.png show processing steps")
    else:
        print("❌ Failed to process PDF file")
    
    # Additional testing suggestions
    print(f"\n{'='*60}")
    print("TESTING SUGGESTIONS")
    print(f"{'='*60}")
    print("1. Test with answer extraction:")
    print(f"   python {sys.argv[0]} --answers")
    print("\n2. Full debug mode with answers:")
    print(f"   python {sys.argv[0]} --debug --answers")
    print("\n3. If OCR confidence is low, try:")
    print("   - Better quality PDF scan")
    print("   - Adjusting DPI in pdf_to_images() method")
    print("   - Different OCR page segmentation modes")
    print("\n4. For answer detection issues:")
    print("   - Check bubble detection parameters")
    print("   - Adjust intensity thresholds")
    print("   - Verify answer sheet format alignment")

if __name__ == "__main__":
    main()
    debug_dir = os.path.join(os.path.dirname(pdf_path), 'debug_images')
    print(f"\n📁 Debug images saved to: {debug_dir}")
    print("   Review these images to troubleshoot OCR issues")
    print("   - detected_bubbles.png shows all detected bubbles")
    print("   - gray_image.png and threshold_image.png show processing steps")
else:
    print("❌ Failed to process PDF file")
    