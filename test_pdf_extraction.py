import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import re
import io
import os
import sys
import cv2
import numpy as np
from pdf2image import convert_from_path

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
            # Try pdf2image first (better quality but requires Poppler)
            from pdf2image import convert_from_path
            images = convert_from_path(pdf_path, dpi=dpi)
            print(f"Converted PDF to {len(images)} image(s) at {dpi} DPI using pdf2image")
            return images
        except ImportError:
            print("pdf2image not found, falling back to PyMuPDF...")
        except Exception as e:
            print(f"pdf2image failed ({str(e)}), falling back to PyMuPDF...")
        
        # Fallback to PyMuPDF (always available)
        try:
            doc = fitz.open(pdf_path)
            images = []
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                
                # Convert page to image with higher quality settings
                mat = fitz.Matrix(dpi/72, dpi/72)  # Scale factor for DPI
                pix = page.get_pixmap(matrix=mat, alpha=False)  # No alpha channel for better OCR
                img_data = pix.tobytes("png")
                
                # Convert to PIL Image
                img = Image.open(io.BytesIO(img_data))
                images.append(img)
                
                print(f"Converted page {page_num + 1} to image (Size: {img.size})")
            
            doc.close()
            print(f"Successfully converted PDF using PyMuPDF fallback")
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

    def detect_alpha_v2_layout(self, image, debug=False):
        """Detect ALPHA V2 layout grid structure from the template"""
        # Convert PIL to OpenCV format
        cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
        height, width = gray.shape
        
        if debug:
            debug_dir = os.path.join(os.path.dirname(os.getcwd()), 'debug_images')
            os.makedirs(debug_dir, exist_ok=True)
            cv2.imwrite(os.path.join(debug_dir, 'layout_detection_input.png'), cv_image)
        
        # ALPHA V2 Layout Analysis - Based on exact answer_key_service.py generation
        # From the PDF generation code: margin = 0.25 * inch, converted to pixels at 300 DPI
        dpi_scale = 300 / 72  # Convert from points to pixels at 300 DPI
        margin = 0.25 * 72 * dpi_scale  # 0.25 inch margins
        content_width = width - 2 * margin
        
        # Grid configuration from answer_key_service.py for multiple_choice_4
        max_columns = 6  # 2 question groups, each with A,B,C,D choices
        rows_per_column = 33  # 33 questions per column
        column_width = content_width / max_columns
        
        # Spacing from PDF generation (converted to pixels) - EXACT values from answer_key_service.py
        row_height = 14 * dpi_scale  # Row height in pixels
        bubble_radius = 5 * dpi_scale  # Bubble radius in pixels
        bubble_spacing = 12 * dpi_scale  # Spacing between bubbles
        
        # Header calculation from answer_key_service.py - CORRECTED based on actual PDF generation
        header_height = 55 * dpi_scale
        student_info_height = 45 * dpi_scale
        instructions_height = 30 * dpi_scale
        header_cell_height = 20 * dpi_scale
        
        # FINAL CORRECTED grid calculation
        # Based on the detection pattern (Q3,Q5 instead of Q1,Q3), we need to move up by 2 more rows
        
        # Calculate from top of page based on the actual layout shown in OCR
        top_margin = 0.3 * 72 * dpi_scale  # Top margin
        
        # Based on the OCR text and actual bubble positions in the PDF
        current_y = top_margin + header_height + 8 * dpi_scale  # After header + spacing
        current_y += student_info_height + 8 * dpi_scale  # After student info + spacing
        current_y += instructions_height + 10 * dpi_scale  # After instructions + spacing
        current_y += header_cell_height + 5 * dpi_scale   # After column headers + spacing
        
        # Final adjustment: we're detecting Q3,Q5 instead of Q1,Q3
        # This means we need to move up by 2 more row heights
        actual_grid_start_y = current_y - (3 * row_height)  # Move up by 3 rows total
        
        layout_info = {
            'margin': margin,
            'column_width': column_width,
            'row_height': row_height,
            'bubble_radius': bubble_radius,
            'bubble_spacing': bubble_spacing,
            'grid_start_y': actual_grid_start_y,
            'max_columns': max_columns,
            'rows_per_column': rows_per_column,
            'dpi_scale': dpi_scale
        }
        
        if debug:
            print(f"Detected ALPHA V2 Layout:")
            for key, value in layout_info.items():
                print(f"  {key}: {value:.2f}")
            print(f"  Image dimensions: {width}x{height}")
            print(f"  Final adjusted grid start: {actual_grid_start_y:.2f}")
            print(f"  Question 1 should be at Y: {actual_grid_start_y:.2f}")
            print(f"  Question 2 should be at Y: {actual_grid_start_y + row_height:.2f}")
            print(f"  Question 3 should be at Y: {actual_grid_start_y + 2 * row_height:.2f}")
            print(f"  Question 4 should be at Y: {actual_grid_start_y + 3 * row_height:.2f}")
            print(f"  Question 5 should be at Y: {actual_grid_start_y + 4 * row_height:.2f}")
        
        return layout_info

    def extract_bubble_regions(self, image, layout_info, debug=False):
        """Extract individual bubble regions for analysis"""
        cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
        
        bubble_regions = {}
        dpi_scale = layout_info['dpi_scale']
        
        # Extract bubbles for questions 1-50 based on actual layout
        for question_num in range(1, 51):
            bubble_regions[question_num] = {}
            
            # Layout: Left column (questions 1-33), Right column (questions 34-50)
            if question_num <= 33:
                # Left side questions (1-33) - column group 0
                column_group = 0  
                row_in_group = question_num - 1  # 0-based indexing for rows
            else:
                # Right side questions (34-50) - column group 3
                column_group = 3  
                row_in_group = question_num - 34  # 0-based indexing for rows
            
            # Calculate base position for this question
            x_base = layout_info['margin'] + column_group * layout_info['column_width']
            # Y position: start from grid_start_y and add row offset (going DOWN the page)
            y_base = layout_info['grid_start_y'] + (row_in_group * layout_info['row_height'])
            
            # Extract each choice bubble (A, B, C, D)
            # From PDF generation: choice_x starts at x_col_start + 22 (points)
            choice_x_start = x_base + 22 * dpi_scale
            
            for i, choice in enumerate(['A', 'B', 'C', 'D']):
                # Calculate bubble center
                # From PDF: bubble_center_x = choice_x + bubble_radius
                bubble_x = int(choice_x_start + i * layout_info['bubble_spacing'] + layout_info['bubble_radius'])
                # From PDF: bubble_center_y = row_y - 7 (offset from row baseline)
                bubble_y = int(y_base - 7 * dpi_scale)
                
                # Define extraction region (larger than bubble for context)
                extract_size = int(layout_info['bubble_radius'] * 2.5)  # Slightly smaller to be more precise
                x1 = max(0, bubble_x - extract_size)
                y1 = max(0, bubble_y - extract_size)
                x2 = min(gray.shape[1], bubble_x + extract_size)
                y2 = min(gray.shape[0], bubble_y + extract_size)
                
                # Extract bubble region
                bubble_region = gray[y1:y2, x1:x2]
                
                if bubble_region.size > 0:
                    bubble_regions[question_num][choice] = {
                        'region': bubble_region,
                        'center': (bubble_x, bubble_y),
                        'bounds': (x1, y1, x2, y2),
                        'expected_radius': layout_info['bubble_radius']
                    }
        
        if debug:
            debug_dir = os.path.join(os.path.dirname(os.getcwd()), 'debug_images')
            print(f"Extracted {sum(len(q.keys()) for q in bubble_regions.values())} bubble regions")
            
            # Save visual layout debug image with focus on first few questions
            debug_img = cv_image.copy()
            
            # Draw grid overlay for first 10 questions to verify positioning
            for q_num in range(1, min(11, 51)):
                if q_num in bubble_regions:
                    for choice in ['A', 'B', 'C', 'D']:
                        if choice in bubble_regions[q_num]:
                            center = bubble_regions[q_num][choice]['center']
                            
                            # Use different colors for questions 1 and 3 to highlight them
                            if q_num == 1:
                                color = (0, 255, 0)  # Green for Q1
                                thickness = 4
                            elif q_num == 3:
                                color = (255, 0, 0)  # Red for Q3
                                thickness = 4
                            elif q_num in [2, 4]:
                                color = (0, 165, 255)  # Orange for Q2,Q4 (currently detected)
                                thickness = 3
                            else:
                                color = (0, 255, 255)  # Yellow for others
                                thickness = 2
                            
                            # Draw circle at expected position
                            cv2.circle(debug_img, center, int(layout_info['bubble_radius']), color, thickness)
                            # Label with question and choice
                            cv2.putText(debug_img, f"Q{q_num}{choice}", 
                                      (center[0]-15, center[1]+35), 
                                      cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
            
            # Add a legend for the colors
            legend_y_start = 50
            cv2.putText(debug_img, "Legend:", (10, legend_y_start), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            cv2.putText(debug_img, "Green: Q1 (Target)", (10, legend_y_start + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            cv2.putText(debug_img, "Red: Q3 (Target)", (10, legend_y_start + 45), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
            cv2.putText(debug_img, "Orange: Q2,Q4 (Currently Detected)", (10, legend_y_start + 65), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 165, 255), 2)
            
            cv2.imwrite(os.path.join(debug_dir, 'layout_overlay_debug.png'), debug_img)
            
            # Print coordinates for verification
            for q_num in [1, 2, 3, 4]:
                if q_num in bubble_regions and 'A' in bubble_regions[q_num]:
                    center = bubble_regions[q_num]['A']['center']
                    print(f"  Question {q_num} bubble A center: ({center[0]}, {center[1]})")
            
            # Save sample bubble regions for detailed analysis (especially target questions)
            for q_num in [1, 2, 3, 4, 10, 20]:
                if q_num in bubble_regions:
                    for choice in ['A', 'B', 'C', 'D']:
                        if choice in bubble_regions[q_num]:
                            region = bubble_regions[q_num][choice]['region']
                            cv2.imwrite(os.path.join(debug_dir, f'bubble_Q{q_num}_{choice}.png'), region)
        
        return bubble_regions

    def detect_alpha_v3_layout(self, image, debug=False):
        """Detect ALPHA V3 layout - Optimized machine-readable design"""
        cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
        height, width = gray.shape
        
        if debug:
            debug_dir = os.path.join(os.path.dirname(os.getcwd()), 'debug_images')
            os.makedirs(debug_dir, exist_ok=True)
            cv2.imwrite(os.path.join(debug_dir, 'layout_detection_input.png'), cv_image)
        
        # ALPHA V3 Layout - Optimized for machine reading
        dpi_scale = 300 / 72  # Convert points to pixels at 300 DPI
        margin = 0.5 * 72 * dpi_scale  # 0.5 inch margins (larger than V2)
        content_width = width - 2 * margin
        
        # Simplified 2-column layout
        max_columns = 2  # Only left and right columns
        questions_per_column = 25  # 25 questions per column
        column_width = content_width / max_columns
        
        # Larger spacing for better detection
        row_height = 20 * dpi_scale  # Increased from 14
        bubble_radius = 8 * dpi_scale  # Increased from 5
        bubble_spacing = 24 * dpi_scale  # Increased from 12
        choice_spacing = 30 * dpi_scale  # New parameter for choice spacing
        
        # Header components (larger than V2)
        header_height = 60 * dpi_scale
        student_info_height = 80 * dpi_scale  # Only if present
        grid_header_height = 40 * dpi_scale
        
        # Calculate grid start position
        top_margin = 0.5 * 72 * dpi_scale
        current_y = top_margin + header_height + 30 * dpi_scale  # After main header
        
        # Check if this is the first page (has student info)
        # For now, assume it's first page - we can detect this later
        has_student_info = True  # Could be detected by looking for "STUDENT INFORMATION" text
        
        if has_student_info:
            current_y += student_info_height + 50 * dpi_scale  # After student info + spacing
        else:
            current_y += 30 * dpi_scale  # Just spacing
        
        # After grid header
        grid_start_y = current_y + grid_header_height + 5 * dpi_scale
        
        layout_info = {
            'margin': margin,
            'column_width': column_width,
            'row_height': row_height,
            'bubble_radius': bubble_radius,
            'bubble_spacing': bubble_spacing,
            'choice_spacing': choice_spacing,
            'grid_start_y': grid_start_y,
            'max_columns': max_columns,
            'questions_per_column': questions_per_column,
            'dpi_scale': dpi_scale,
            'version': 'ALPHA_V3'
        }
        
        if debug:
            print(f"Detected ALPHA V3 Layout:")
            for key, value in layout_info.items():
                print(f"  {key}: {value:.2f}")
            print(f"  Image dimensions: {width}x{height}")
            print(f"  Grid start Y: {grid_start_y:.2f}")
        
        return layout_info

    def extract_bubble_regions_v3(self, image, layout_info, debug=False):
        """Extract bubble regions for ALPHA V3 layout"""
        cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
        
        bubble_regions = {}
        dpi_scale = layout_info['dpi_scale']
        
        # ALPHA V3: 2 columns, 25 questions each
        for question_num in range(1, 51):  # Up to 50 questions
            bubble_regions[question_num] = {}
            
            # Determine column and row
            if question_num <= 25:
                # Left column (questions 1-25)
                column = 0
                row_in_column = question_num - 1
            else:
                # Right column (questions 26-50)
                column = 1
                row_in_column = question_num - 26
            
            # Calculate column position
            col_x = layout_info['margin'] + column * layout_info['column_width']
            
            # Calculate row position (going down from grid start)
            row_y = layout_info['grid_start_y'] + (row_in_column * layout_info['row_height'])
            
            # Choice bubbles start position (after question number)
            choice_start_x = col_x + 50 * dpi_scale  # After "Q##." space
            
            # Extract each choice bubble
            for i, choice in enumerate(['A', 'B', 'C', 'D']):
                # Calculate bubble center
                bubble_center_x = int(choice_start_x + i * layout_info['choice_spacing'] + layout_info['bubble_radius'])
                bubble_center_y = int(row_y - 10 * dpi_scale)  # Offset from row baseline
                
                # Define extraction region
                extract_size = int(layout_info['bubble_radius'] * 2)  # Precise extraction
                x1 = max(0, bubble_center_x - extract_size)
                y1 = max(0, bubble_center_y - extract_size)
                x2 = min(gray.shape[1], bubble_center_x + extract_size)
                y2 = min(gray.shape[0], bubble_center_y + extract_size)
                
                # Extract bubble region
                bubble_region = gray[y1:y2, x1:x2]
                
                if bubble_region.size > 0:
                    bubble_regions[question_num][choice] = {
                        'region': bubble_region,
                        'center': (bubble_center_x, bubble_center_y),
                        'bounds': (x1, y1, x2, y2),
                        'expected_radius': layout_info['bubble_radius']
                    }
        
        if debug:
            debug_dir = os.path.join(os.path.dirname(os.getcwd()), 'debug_images')
            print(f"Extracted {sum(len(q.keys()) for q in bubble_regions.values())} bubble regions (ALPHA V3)")
            
            # Create visual debug image
            debug_img = cv_image.copy()
            
            # Draw overlay for first 10 questions
            for q_num in range(1, min(11, 51)):
                if q_num in bubble_regions:
                    for choice in ['A', 'B', 'C', 'D']:
                        if choice in bubble_regions[q_num]:
                            center = bubble_regions[q_num][choice]['center']
                            
                            # Color code: Green for Q1, Red for Q3
                            if q_num == 1:
                                color = (0, 255, 0)  # Green
                                thickness = 4
                            elif q_num == 3:
                                color = (255, 0, 0)  # Red  
                                thickness = 4
                            else:
                                color = (0, 255, 255)  # Yellow
                                thickness = 2
                            
                            cv2.circle(debug_img, center, int(layout_info['bubble_radius']), color, thickness)
                            cv2.putText(debug_img, f"Q{q_num}{choice}", 
                                      (center[0]-15, center[1]+30), 
                                      cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
            
            cv2.imwrite(os.path.join(debug_dir, 'alpha_v3_overlay_debug.png'), debug_img)
            
            # Print coordinates for verification
            for q_num in [1, 3, 25, 26]:  # Test questions from both columns
                if q_num in bubble_regions and 'A' in bubble_regions[q_num]:
                    center = bubble_regions[q_num]['A']['center']
                    print(f"  ALPHA V3 Question {q_num} bubble A: ({center[0]}, {center[1]})")
        
        return bubble_regions

    def detect_alpha_v4_layout(self, image, debug=False):
        """Detect ALPHA V4 layout - Ultra-compact 4-column design with improved spacing"""
        cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
        height, width = gray.shape
        
        if debug:
            debug_dir = os.path.join(os.path.dirname(os.getcwd()), 'debug_images')
            os.makedirs(debug_dir, exist_ok=True)
            cv2.imwrite(os.path.join(debug_dir, 'layout_detection_input.png'), cv_image)
        
        # ALPHA V4 Layout - Improved spacing parameters
        dpi_scale = 300 / 72  # Convert points to pixels at 300 DPI
        margin = 0.4 * 72 * dpi_scale  # Improved margins (0.4 inch instead of 0.3)
        content_width = width - 2 * margin
        
        # 4-column layout for maximum density
        columns = 4  # 4 columns of questions
        questions_per_column = 25  # 25 questions per column = 100 per page
        column_width = content_width / columns
        
        # Improved spacing parameters
        row_height = 14 * dpi_scale  # Increased from 12
        bubble_radius = 5 * dpi_scale  # Increased from 4
        bubble_spacing = 16 * dpi_scale  # Increased from 14
        
        # Improved header components
        header_height = 45 * dpi_scale  # Increased from 40
        student_info_height = 55 * dpi_scale  # Increased from 50
        
        # Calculate grid start position with better spacing
        top_margin = 0.3 * 72 * dpi_scale
        current_y = top_margin + header_height + 15 * dpi_scale  # More spacing after header
        
        # Check if this is the first page (has student info)
        has_student_info = True  # Could be detected by looking for "STUDENT INFO" text
        
        if has_student_info:
            current_y += student_info_height + 20 * dpi_scale  # More spacing after student info
        else:
            current_y += 20 * dpi_scale  # More spacing for non-first pages
        
        # Grid starts after column headers with better spacing
        grid_start_y = current_y + 40 * dpi_scale  # More space for column headers
        
        layout_info = {
            'margin': margin,
            'column_width': column_width,
            'row_height': row_height,
            'bubble_radius': bubble_radius,
            'bubble_spacing': bubble_spacing,
            'grid_start_y': grid_start_y,
            'columns': columns,
            'questions_per_column': questions_per_column,
            'dpi_scale': dpi_scale,
            'version': 'ALPHA_V4'
        }
        
        if debug:
            print(f"Detected ALPHA V4 Layout (Improved):")
            for key, value in layout_info.items():
                print(f"  {key}: {value:.2f}")
            print(f"  Image dimensions: {width}x{height}")
            print(f"  Questions per page: {columns * questions_per_column}")
        
        return layout_info

    def extract_bubble_regions_v4(self, image, layout_info, debug=False):
        """Extract bubble regions for ALPHA V4 compact layout with improved positioning"""
        cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
        
        bubble_regions = {}
        dpi_scale = layout_info['dpi_scale']
        
        # ALPHA V4: 4 columns, 25 questions each = 100 questions per page
        questions_per_page = layout_info['columns'] * layout_info['questions_per_column']
        
        for question_num in range(1, 301):  # Support up to 300 questions (3 pages)
            bubble_regions[question_num] = {}
            
            # Determine which page this question is on
            page_num = ((question_num - 1) // questions_per_page) + 1
            question_on_page = ((question_num - 1) % questions_per_page) + 1
            
            # Determine column and row within that page
            column = ((question_on_page - 1) // layout_info['questions_per_column']) 
            row_in_column = (question_on_page - 1) % layout_info['questions_per_column']
            
            # Calculate column position with better spacing
            col_x = layout_info['margin'] + column * layout_info['column_width']
            
            # Calculate row position (going down from grid start)
            row_y = layout_info['grid_start_y'] + (row_in_column * layout_info['row_height'])
            
            # Choice bubbles start position with improved spacing (after question number)
            choice_start_x = col_x + 30 * dpi_scale  # More space for question numbers (increased from 25)
            
            # Extract each choice bubble
            for i, choice in enumerate(['A', 'B', 'C', 'D']):
                # Calculate bubble center with improved positioning
                bubble_center_x = int(choice_start_x + i * layout_info['bubble_spacing'] + layout_info['bubble_radius'])
                bubble_center_y = int(row_y - 6 * dpi_scale)  # Better vertical alignment
                
                # Define extraction region
                extract_size = int(layout_info['bubble_radius'] * 2)  # Precise extraction
                x1 = max(0, bubble_center_x - extract_size)
                y1 = max(0, bubble_center_y - extract_size)
                x2 = min(gray.shape[1], bubble_center_x + extract_size)
                y2 = min(gray.shape[0], bubble_center_y + extract_size)
                
                # Extract bubble region
                bubble_region = gray[y1:y2, x1:x2]
                
                if bubble_region.size > 0:
                    bubble_regions[question_num][choice] = {
                        'region': bubble_region,
                        'center': (bubble_center_x, bubble_center_y),
                        'bounds': (x1, y1, x2, y2),
                        'expected_radius': layout_info['bubble_radius'],
                        'page': page_num
                    }
        
        if debug:
            debug_dir = os.path.join(os.path.dirname(os.getcwd()), 'debug_images')
            print(f"Extracted {sum(len(q.keys()) for q in bubble_regions.values())} bubble regions (ALPHA V4 Improved)")
            
            # Create visual debug image for first page
            debug_img = cv_image.copy()
            
            # Draw overlay for first 20 questions
            for q_num in range(1, min(21, 101)):
                if q_num in bubble_regions:
                    for choice in ['A', 'B', 'C', 'D']:
                        if choice in bubble_regions[q_num]:
                            center = bubble_regions[q_num][choice]['center']
                            
                            # Color code for different columns
                            if q_num <= 25:
                                color = (0, 255, 0)  # Green - Column 1
                            elif q_num <= 50:
                                color = (255, 0, 0)  # Red - Column 2
                            elif q_num <= 75:
                                color = (0, 0, 255)  # Blue - Column 3
                            else:
                                color = (255, 255, 0)  # Yellow - Column 4
                            
                            thickness = 2
                            
                            cv2.circle(debug_img, center, int(layout_info['bubble_radius']), color, thickness)
                            
                            # Only label every 5th question to avoid clutter
                            if q_num % 5 == 1:
                                cv2.putText(debug_img, f"Q{q_num}{choice}", 
                                          (center[0]-10, center[1]+15), 
                                          cv2.FONT_HERSHEY_SIMPLEX, 0.3, color, 1)
            
            cv2.imwrite(os.path.join(debug_dir, 'alpha_v4_improved_overlay_debug.png'), debug_img)
            
            # Print coordinates for verification
            test_questions = [1, 25, 26, 50, 51, 75, 76, 100]  # One from each column
            for q_num in test_questions:
                if q_num in bubble_regions and 'A' in bubble_regions[q_num]:
                    center = bubble_regions[q_num]['A']['center']
                    page = bubble_regions[q_num]['A']['page']
                    print(f"  ALPHA V4 Improved Question {q_num} bubble A: ({center[0]}, {center[1]}) Page {page}")
        
        return bubble_regions

    def classify_bubble_fill(self, bubble_region, expected_radius, debug=False):
        """Use computer vision to classify if a bubble is filled"""
        if bubble_region.size == 0:
            return False, 0.0
        
        # Method 1: Morphological operations to separate border from fill
        # Use a smaller kernel to detect the inner area vs border
        kernel_size = max(3, int(expected_radius * 0.3))  # Adaptive kernel based on bubble size
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
        
        # Apply different thresholding approaches
        _, binary_global = cv2.threshold(bubble_region, 127, 255, cv2.THRESH_BINARY_INV)
        binary_otsu = cv2.threshold(bubble_region, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
        
        # Morphological opening to remove thin borders while keeping filled areas
        opened_global = cv2.morphologyEx(binary_global, cv2.MORPH_OPEN, kernel)
        opened_otsu = cv2.morphologyEx(binary_otsu, cv2.MORPH_OPEN, kernel)
        
        # Method 2: Create a much smaller circular mask for the inner area only
        center = (bubble_region.shape[1] // 2, bubble_region.shape[0] // 2)
        # Use only 50% of expected radius to avoid the thick border
        inner_radius = max(2, int(expected_radius * 0.5))
        
        if inner_radius <= 1:
            return False, 0.0
        
        # Create inner circular mask (much smaller to avoid borders)
        inner_mask = np.zeros(bubble_region.shape, dtype=np.uint8)
        cv2.circle(inner_mask, center, inner_radius, 255, -1)
        
        # Also create a border mask to detect if we're looking at empty circles with borders
        outer_radius = min(int(expected_radius * 0.8), center[0] - 2, center[1] - 2)
        border_mask = np.zeros(bubble_region.shape, dtype=np.uint8)
        cv2.circle(border_mask, center, outer_radius, 255, -1)
        # Subtract inner mask to get border-only area
        border_only_mask = cv2.subtract(border_mask, inner_mask)
        
        # Method 3: Analyze the inner area only
        inner_pixels = bubble_region[inner_mask > 0]
        border_pixels = bubble_region[border_only_mask > 0]
        
        if len(inner_pixels) == 0:
            return False, 0.0
        
        # Statistics for inner area
        inner_mean = np.mean(inner_pixels)
        inner_std = np.std(inner_pixels)
        inner_dark_ratio = np.sum(inner_pixels < 100) / len(inner_pixels)
        inner_very_dark_ratio = np.sum(inner_pixels < 60) / len(inner_pixels)
        
        # Statistics for border area (to detect empty circles with thick borders)
        border_mean = np.mean(border_pixels) if len(border_pixels) > 0 else 255
        border_dark_ratio = np.sum(border_pixels < 100) / len(border_pixels) if len(border_pixels) > 0 else 0
        
        # Method 4: Use morphologically processed images on inner area
        inner_filled_global = np.sum(opened_global[inner_mask > 0] > 0) / np.sum(inner_mask > 0)
        inner_filled_otsu = np.sum(opened_otsu[inner_mask > 0] > 0) / np.sum(inner_mask > 0)
        
        # Method 5: Edge analysis - filled bubbles should have fewer edges in the inner area
        edges = cv2.Canny(bubble_region, 50, 150)
        inner_edge_density = np.sum(edges[inner_mask > 0] > 0) / np.sum(inner_mask > 0)
        
        # Method 6: Variance analysis - filled areas should have low variance
        inner_variance = np.var(inner_pixels)
        
        # Scoring system specifically for thick-bordered bubbles
        # Key insight: filled bubbles will have dark inner areas, empty bubbles will have light inner areas
        
        # Inner darkness score (most important)
        inner_darkness_score = max(0, (255 - inner_mean) / 255)
        
        # Dark pixel ratios in inner area
        dark_ratio_score = inner_dark_ratio
        very_dark_ratio_score = inner_very_dark_ratio
        
        # Morphological fill scores (after removing borders)
        morph_fill_score = max(inner_filled_global, inner_filled_otsu)
        
        # Border vs inner contrast (empty circles should have light inner, dark border)
        contrast_score = max(0, (border_mean - inner_mean) / 255) if border_mean > inner_mean else 0
        # Invert contrast score - we want low contrast (both inner and border dark) for filled bubbles
        contrast_penalty = min(1.0, contrast_score)
        
        # Low variance indicates uniform fill
        variance_score = max(0, 1 - (inner_variance / 1000))  # Normalize variance
        
        # Low edge density in inner area indicates solid fill
        edge_score = max(0, 1 - inner_edge_density * 5)
        
        # Combined confidence with emphasis on inner area analysis
        confidence = (
            inner_darkness_score * 0.30 +      # Inner area must be dark
            very_dark_ratio_score * 0.25 +     # High ratio of very dark pixels
            dark_ratio_score * 0.15 +          # Good ratio of dark pixels
            morph_fill_score * 0.10 +          # Morphological opening result
            variance_score * 0.10 +            # Low variance indicates uniform fill
            edge_score * 0.05 +                # Low edge density
            (1 - contrast_penalty) * 0.05      # Penalty for high border-inner contrast
        )
        
        # Much more restrictive criteria for filled bubbles with thick borders
        is_filled = (
            confidence > 0.6 and               # High confidence threshold
            inner_mean < 130 and               # Inner area must be significantly darker
            inner_dark_ratio > 0.5 and         # At least 50% of inner pixels are dark
            very_dark_ratio_score > 0.2 and    # At least 20% are very dark
            morph_fill_score > 0.1             # Some fill after morphological opening
        )
        
        if debug:
            print(f"    Inner mean: {inner_mean:.1f}, Border mean: {border_mean:.1f}")
            print(f"    Inner dark ratio: {inner_dark_ratio:.3f}, Very dark ratio: {very_dark_ratio_score:.3f}")
            print(f"    Morph fill (global/otsu): {inner_filled_global:.3f}/{inner_filled_otsu:.3f}")
            print(f"    Inner variance: {inner_variance:.1f}, Edge density: {inner_edge_density:.3f}")
            print(f"    Contrast penalty: {contrast_penalty:.3f}")
            print(f"    Inner darkness: {inner_darkness_score:.3f}, Confidence: {confidence:.3f}")
            print(f"    Filled: {is_filled}")
        
        return is_filled, confidence

    def extract_answers_ai(self, image, debug=False):
        """AI-powered answer extraction - Auto-detect layout version"""
        print("Starting AI-powered bubble detection...")
        
        # Try to detect layout version first
        layout_version = self.detect_layout_version(image)
        print(f"Detected layout version: {layout_version}")
        
        if layout_version == 'ALPHA_V4':
            # Use new V4 detection (compact)
            layout_info = self.detect_alpha_v4_layout(image, debug)
            bubble_regions = self.extract_bubble_regions_v4(image, layout_info, debug)
        elif layout_version == 'ALPHA_V3':
            # Use V3 detection
            layout_info = self.detect_alpha_v3_layout(image, debug)
            bubble_regions = self.extract_bubble_regions_v3(image, layout_info, debug)
        else:
            # Fallback to V2 detection
            layout_info = self.detect_alpha_v2_layout(image, debug)
            bubble_regions = self.extract_bubble_regions(image, layout_info, debug)
        
        # Rest of the classification remains the same
        answers = {}
        confidence_scores = {}
        
        # Determine max questions based on layout
        if layout_version == 'ALPHA_V4':
            max_questions = 300  # Support up to 300 questions (3 pages)
        else:
            max_questions = 100  # V2/V3 layouts
        
        for question_num in range(1, max_questions + 1):
            if question_num not in bubble_regions:
                answers[question_num] = None
                confidence_scores[question_num] = 0.0
                continue
            
            question_results = {}
            
            for choice in ['A', 'B', 'C', 'D']:
                if choice in bubble_regions[question_num]:
                    bubble_data = bubble_regions[question_num][choice]
                    is_filled, confidence = self.classify_bubble_fill(
                        bubble_data['region'], 
                        bubble_data['expected_radius'],
                        debug and question_num in [1, 26, 51, 76]  # Debug first question of each column
                    )
                    
                    question_results[choice] = {
                        'filled': is_filled,
                        'confidence': confidence
                    }
            
            # Determine answer
            filled_choices = [choice for choice, result in question_results.items() 
                            if result['filled']]
            
            if len(filled_choices) == 1:
                answers[question_num] = filled_choices[0]
                confidence_scores[question_num] = question_results[filled_choices[0]]['confidence']
            elif len(filled_choices) > 1:
                best_choice = max(filled_choices, 
                                key=lambda c: question_results[c]['confidence'])
                answers[question_num] = best_choice
                confidence_scores[question_num] = question_results[best_choice]['confidence'] * 0.8
                
                if debug:
                    print(f"Question {question_num}: Multiple choices {filled_choices}, chose {best_choice}")
            else:
                answers[question_num] = None
                confidence_scores[question_num] = 0.0
        
        # Remove empty answers for cleaner output
        answers = {k: v for k, v in answers.items() if v is not None}
        confidence_scores = {k: v for k, v in confidence_scores.items() if k in answers}
        
        answered_count = len(answers)
        avg_confidence = sum(confidence_scores.values()) / len(confidence_scores) if confidence_scores else 0
        
        if debug:
            print(f"\nAI Detection Results ({layout_version}):")
            print(f"  Questions answered: {answered_count}")
            print(f"  Average confidence: {avg_confidence:.3f}")
            print(f"  Detected answers: {[f'Q{q}:{a}' for q, a in list(answers.items())[:10]]}")  # Show first 10
            if answered_count > 10:
                print(f"  ... and {answered_count - 10} more")
        
        return {
            'answers': answers,
            'confidence_scores': confidence_scores,
            'stats': {
                'answered_count': answered_count,
                'avg_confidence': avg_confidence,
                'method': f'AI Computer Vision ({layout_version})',
                'layout_version': layout_version,
                'max_questions_supported': max_questions
            }
        }

    def detect_layout_version(self, image):
        """Detect which layout version is being used"""
        try:
            # Convert to text and look for version markers
            import pytesseract
            
            # Crop header area to look for version markers
            width, height = image.size
            header_area = image.crop((0, 0, width, height // 4))
            
            # Extract text from header
            text = pytesseract.image_to_string(header_area, config='--psm 6')
            
            if 'ALPHA V4' in text or 'Compact' in text:
                return 'ALPHA_V4'
            elif 'ALPHA V3' in text or 'Machine Optimized' in text:
                return 'ALPHA_V3'
            elif 'ALPHA V2' in text:
                return 'ALPHA_V2'
            else:
                # Default to V4 for new sheets (most compact)
                return 'ALPHA_V4'
                
        except Exception:
            # If detection fails, default to V4
            return 'ALPHA_V4'

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

    def process_pdf(self, pdf_path, save_debug=False, extract_answers=False):
        """Main function to process a PDF and extract student information and answers"""
        print(f"\n{'='*60}")
        print(f"Processing: {os.path.basename(pdf_path)}")
        print(f"Full path: {pdf_path}")
        if extract_answers:
            print("Mode: Extract student info + AI-powered answer detection")
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
        
        # Extract student information from top section
        width, height = first_page.size
        print(f"Original image size: {width}x{height}")
        
        # Focus on top section where student info is typically located
        top_section = first_page.crop((0, 0, width, height // 3))
        print(f"Student info section size: {top_section.size}")
        
        text, confidence = self.extract_text_from_image(top_section)
        student_id, student_name = self.extract_student_info(text)
        
        # Extract answers using AI if requested
        answer_results = {}
        if extract_answers:
            print("\nExtracting answers using AI-powered bubble detection...")
            answer_results = self.extract_answers_ai(first_page, debug=save_debug)
        
        result = {
            'file': os.path.basename(pdf_path),
            'student_id': student_id,
            'student_name': student_name,
            'ocr_confidence': confidence,
            'raw_text': text[:500] + "..." if len(text) > 500 else text,
            'full_path': pdf_path,
            'answers': answer_results.get('answers', {}),
            'answer_confidence_scores': answer_results.get('confidence_scores', {}),
            'answer_stats': answer_results.get('stats', {}),
            'total_answers': sum(1 for ans in answer_results.get('answers', {}).values() if ans is not None),
            'answered_questions': [q for q, ans in answer_results.get('answers', {}).items() if ans is not None]
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
            result = self.process_pdf(pdf_path, extract_answers=True)  # Enable AI answers for batch
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
            print(f"  python {sys.argv[0]} --ai               # Extract answers using AI")
            print(f"  python {sys.argv[0]} --batch <directory> # Process all PDFs in directory")
            print(f"\nDefault test file: {default_pdf_path}")
            return
        
        elif sys.argv[1] == '--debug':
            pdf_path = default_pdf_path
            save_debug = True
            extract_answers = '--ai' in sys.argv
        elif sys.argv[1] == '--ai':
            pdf_path = default_pdf_path
            save_debug = '--debug' in sys.argv
            extract_answers = True
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
                    if result['total_answers'] > 0: success_indicators.append(f"Answers({result['total_answers']})")
                    
                    status = f"[{', '.join(success_indicators) if success_indicators else 'No Info'}]"
                    print(f"{status:<25} {result['file']}")
                    
                    if result['student_id'] or result['student_name']:
                        successful += 1
                        if result['student_id']: print(f"                         Student ID: {result['student_id']}")
                        if result['student_name']: print(f"                         Student Name: {result['student_name']}")
                        if result['total_answers'] > 0:
                            avg_conf = result['answer_stats'].get('avg_confidence', 0)
                            print(f"                         Answers: {result['total_answers']}/50 (Confidence: {avg_conf:.2f})")
                        print(f"                         OCR Confidence: {result['ocr_confidence']:.1f}%")
                        print()
                
                print(f"Summary: {successful}/{len(results)} files processed successfully")
                return
            else:
                print("Error: --batch requires a directory path")
                return
        else:
            pdf_path = sys.argv[1]
            save_debug = '--debug' in sys.argv
            extract_answers = '--ai' in sys.argv
    else:
        pdf_path = default_pdf_path
        save_debug = False
        extract_answers = False
    
    print(f"Testing PDF extraction with: {pdf_path}")
    if save_debug:
        print("Debug mode: Will save cropped images for analysis")
    if extract_answers:
        print("AI mode: Will use computer vision for bubble detection")
    
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
            stats = result.get('answer_stats', {})
            print(f"AI Answer Detection: {stats.get('method', 'N/A')}")
            print(f"Total Answers Detected: {result['total_answers']}/50")
            print(f"Average Detection Confidence: {stats.get('avg_confidence', 0):.3f}")
            print(f"Answered Questions: {result['answered_questions']}")
            
            if result['answers']:
                print("\nDetected Answers:")
                for q_num in sorted(result['answers'].keys()):
                    if result['answers'][q_num] is not None:
                        conf = result['answer_confidence_scores'].get(q_num, 0)
                        print(f"  Question {q_num}: {result['answers'][q_num]} (confidence: {conf:.3f})")
        
        print(f"\nRaw Text Preview:")
        print("-" * 40)
        print(result['raw_text'])
        print("-" * 40)
        
        # Summary
        success_rate = 0
        if result['student_id']: success_rate += 30
        if result['student_name']: success_rate += 30
        if extract_answers and result['total_answers'] > 0: success_rate += 40
        
        print(f"\nExtraction Success Rate: {success_rate}%")
        
        if success_rate >= 80:
            print("✅ Extraction successful!")
        elif success_rate >= 50:
            print("⚠️ Partial extraction - some information missing")
        else:
            print("❌ Extraction failed - limited information found")
            
        if save_debug:
            debug_dir = os.path.join(os.path.dirname(pdf_path), 'debug_images')
            print(f"\n📁 Debug images saved to: {debug_dir}")
            print("   Review these images to troubleshoot detection issues")
    else:
        print("❌ Failed to process PDF file")
    
    # Additional testing suggestions
    print(f"\n{'='*60}")
    print("USAGE EXAMPLES")
    print(f"{'='*60}")
    print("1. Process with AI bubble detection:")
    print(f"   python {sys.argv[0]} --ai")
    print("\n2. Full debug mode with AI:")
    print(f"   python {sys.argv[0]} --debug --ai")
    print("\n3. Batch process directory:")
    print(f"   python {sys.argv[0]} --batch path/to/pdf/directory")
    print("\n4. If detection accuracy is low:")
    print("   - Ensure PDF quality is high (300+ DPI)")
    print("   - Check that answer sheet follows ALPHA V2 template exactly")
    print("   - Use --debug to analyze bubble extraction")

if __name__ == "__main__":
    main()


