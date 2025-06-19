import fitz  # PyMuPDF
import cv2
import numpy as np
from PIL import Image
import re
import os
import tempfile
import logging
from typing import Dict, List, Tuple, Optional, Any

# Handle pytesseract import gracefully
try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False
    pytesseract = None

class PDFExtractionService:
    """Independent PDF extraction service for CheckMate answer sheets"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Detection parameters
        self.bubble_detection_params = {
            'min_radius': 5,
            'max_radius': 25,
            'dp': 1,
            'min_dist': 15,
            'param1': 50,
            'param2': 20,
            'threshold_ratio': 0.3  # Minimum fill ratio to consider bubble filled
        }
        
        # Template-based detection parameters for CheckMate V4 format
        self.template_params = {
            'questions_per_column': 25,
            'columns': 4,
            'bubble_radius': 5,
            'bubble_spacing_x': 16,  # Horizontal spacing between choices
            'bubble_spacing_y': 14,  # Vertical spacing between questions
            'column_width': None,    # Will be calculated from image
            'grid_start_x': None,    # Will be detected from image
            'grid_start_y': None,    # Will be detected from image
            'darkness_threshold': 0.35  # Minimum darkness ratio to consider filled
        }
        
        # OCR configuration
        self.ocr_config = r'--oem 3 --psm 6'
        
        # Student info patterns
        self.student_patterns = {
            'name': [
                r'Name:\s*([A-Za-z\s\-\.\']{3,50})',
                r'Student Name:\s*([A-Za-z\s\-\.\']{3,50})',
                r'Name\s*:\s*([A-Za-z\s\-\.\']{3,50})',
                r'(?:Student|STUDENT)\s+(?:Name|NAME)\s*[:\-]?\s*([A-Za-z\s\-\.\']{3,50})'
            ],
            'id': [
                r'ID:\s*([A-Za-z0-9\-]{4,20})',
                r'Student ID:\s*([A-Za-z0-9\-]{4,20})',
                r'ID\s*:\s*([A-Za-z0-9\-]{4,20})',
                r'(?:Student|STUDENT)\s+(?:ID|Id|id)\s*[:\-]?\s*([A-Za-z0-9\-]{4,20})'
            ]
        }

    def extract_from_pdf(self, pdf_path: str, test_type: str = 'multiple_choice_4', 
                        question_count: int = None, debug_mode: bool = False) -> Dict[str, Any]:
        """
        Main extraction method for PDF files
        
        Args:
            pdf_path: Path to PDF file
            test_type: Type of test (multiple_choice_4, multiple_choice_5, true_false)
            question_count: Expected number of questions
            debug_mode: Enable debug output and image saving
            
        Returns:
            Dictionary with extracted data
        """
        try:
            result = {
                'success': False,
                'student_name': '',
                'student_id': '',
                'answers': {},
                'confidence_scores': {},
                'metadata': {
                    'extraction_method': '',
                    'pages_processed': 0,
                    'total_questions_found': 0,
                    'student_info_confidence': 0.0,
                    'tesseract_available': TESSERACT_AVAILABLE,
                    'debug_images': []
                },
                'errors': [],
                'debug_info': {} if debug_mode else None
            }
            
            # Open PDF document
            doc = fitz.open(pdf_path)
            result['metadata']['pages_processed'] = len(doc)
            
            # Extract student information from first page
            student_info = self._extract_student_info(doc)
            result['student_name'] = student_info['name']
            result['student_id'] = student_info['id']
            result['metadata']['student_info_confidence'] = student_info['confidence']
            
            # Extract answers using multiple methods
            answers_result = self._extract_answers_multi_method(
                doc, test_type, question_count, debug_mode
            )
            
            result['answers'] = answers_result['answers']
            result['confidence_scores'] = answers_result['confidence_scores']
            result['metadata'].update(answers_result['metadata'])
            
            if debug_mode:
                result['debug_info'] = answers_result.get('debug_info', {})
            
            if result['answers'] or result['student_name'] or result['student_id']:
                result['success'] = True
                result['metadata']['total_questions_found'] = len(result['answers'])
            
            doc.close()
            return result
            
        except Exception as e:
            self.logger.error(f"PDF extraction error: {str(e)}")
            return {
                'success': False,
                'student_name': '',
                'student_id': '',
                'answers': {},
                'confidence_scores': {},
                'metadata': {'extraction_method': 'failed', 'tesseract_available': TESSERACT_AVAILABLE},
                'errors': [f"Extraction failed: {str(e)}"]
            }

    def _extract_student_info(self, doc: fitz.Document) -> Dict[str, Any]:
        """Extract student name and ID from PDF"""
        student_info = {
            'name': '',
            'id': '',
            'confidence': 0.0
        }
        
        try:
            # Process first page for student information
            page = doc[0]
            
            # Method 1: Extract from form fields/annotations
            form_info = self._extract_from_form_fields(page)
            if form_info['name'] or form_info['id']:
                student_info.update(form_info)
                student_info['confidence'] = 0.9
                return student_info
            
            # Method 2: OCR-based extraction
            if TESSERACT_AVAILABLE:
                ocr_info = self._extract_student_info_ocr(page)
                if ocr_info['name'] or ocr_info['id']:
                    student_info.update(ocr_info)
                    student_info['confidence'] = 0.7
                    return student_info
            
            # Method 3: Text extraction with patterns
            text_info = self._extract_student_info_text(page)
            if text_info['name'] or text_info['id']:
                student_info.update(text_info)
                student_info['confidence'] = 0.6
                
        except Exception as e:
            self.logger.warning(f"Student info extraction error: {str(e)}")
        
        return student_info

    def _extract_from_form_fields(self, page: fitz.Page) -> Dict[str, str]:
        """Extract student info from PDF form fields and annotations"""
        info = {'name': '', 'id': ''}
        
        try:
            # Check annotations for text content
            annotations = page.annots()
            for annot in annotations:
                if annot.type[1] == 'FreeText':
                    content = annot.info.get('content', '').strip()
                    if content:
                        # Check if it's a student ID (alphanumeric with dashes)
                        if re.match(r'^[A-Za-z0-9\-]{4,20}$', content) and '-' in content:
                            info['id'] = content.strip()
                        # Check if it's a name (has spaces and letters, reasonable length)
                        elif len(content) > 5 and ' ' in content and any(c.isalpha() for c in content):
                            # Avoid matching course codes or IDs
                            if not re.match(r'^[A-Z]{2,4}\s*\d+', content):
                                info['name'] = self._clean_student_name(content)
                            
        except Exception as e:
            self.logger.warning(f"Form field extraction error: {str(e)}")
        
        return info

    def _extract_student_info_ocr(self, page: fitz.Page) -> Dict[str, str]:
        """Extract student info using OCR"""
        info = {'name': '', 'id': ''}
        
        if not TESSERACT_AVAILABLE:
            return info
        
        try:
            # Convert page to image
            mat = fitz.Matrix(2.0, 2.0)
            pix = page.get_pixmap(matrix=mat)
            img_data = pix.tobytes("png")
            
            nparr = np.frombuffer(img_data, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    def _extract_student_info_text(self, page: fitz.Page) -> Dict[str, str]:
        """Extract student info from page text"""
        info = {'name': '', 'id': ''}
        
        try:
            text = page.get_text()
            info = self._apply_student_patterns(text)
        except Exception as e:
            self.logger.warning(f"Text student info extraction error: {str(e)}")
        
        return info

    def _apply_student_patterns(self, text: str) -> Dict[str, str]:
        """Apply regex patterns to extract student information"""
        info = {'name': '', 'id': ''}
        
        text = re.sub(r'\s+', ' ', text.strip())
        
        # Extract name
        for pattern in self.student_patterns['name']:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                name = self._clean_student_name(match.group(1))
                if name and len(name) > 3:
                    info['name'] = name
                    break
        
        # Extract ID  
        for pattern in self.student_patterns['id']:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                student_id = match.group(1).strip()
                if student_id and len(student_id) >= 4 and '-' in student_id:
                    info['id'] = student_id
                    break
        
        return info

    def _clean_student_name(self, name: str) -> str:
        """Clean and validate student name"""
        if not name:
            return ''
        
        name = re.sub(r'[^\w\s\-\.\']', '', name)
        name = re.sub(r'\s+', ' ', name.strip())
        name = re.sub(r'\b(Name|NAME|name|Student|STUDENT)\b', '', name).strip()
        name = re.sub(r'^[:\-\s]+', '', name).strip()
        
        if re.match(r'^[A-Z]{2,4}\s*\d+', name):
            return ''
        
        parts = name.split()
        if len(parts) >= 2 and 3 <= len(name) <= 50:
            return ' '.join(part.title() for part in parts)
        
        return ''

    def _extract_answers_multi_method(self, doc: fitz.Document, test_type: str, 
                                    question_count: int, debug_mode: bool = False) -> Dict[str, Any]:
        """Extract answers using multiple methods with enhanced detection"""
        
        choices = self._get_answer_choices(test_type)
        debug_info = {} if debug_mode else None
        
        methods = [
            ('enhanced_bubble_detection', self._extract_answers_enhanced_bubble_detection),
            ('comprehensive_pattern_matching', self._extract_answers_comprehensive_pattern_matching),
        ]
        
        if TESSERACT_AVAILABLE:
            methods.append(('enhanced_ocr_analysis', self._extract_answers_enhanced_ocr))
        
        methods.extend([
            ('text_analysis', self._extract_answers_text_analysis),
            ('visual_marks_detection', self._extract_answers_visual_marks)
        ])
        
        best_result = {
            'answers': {},
            'confidence_scores': {},
            'metadata': {'extraction_method': 'none', 'success_rate': 0.0},
            'debug_info': debug_info
        }
        
        all_results = []
        
        for method_name, method_func in methods:
            try:
                if debug_mode:
                    print(f"🔍 Trying method: {method_name}")
                
                result = method_func(doc, choices, question_count, debug_mode)
                all_results.append((method_name, result))
                
                if result['answers']:
                    if debug_mode:
                        print(f"   ✅ Found {len(result['answers'])} answers")
                        for q, a in sorted(result['answers'].items())[:5]:
                            print(f"      Q{q}: {a}")
                    
                    success_rate = len(result['answers']) / max(question_count or 1, 1)
                    result['metadata']['success_rate'] = success_rate
                    result['metadata']['extraction_method'] = method_name
                    
                    if success_rate > best_result['metadata']['success_rate']:
                        best_result = result
                        if debug_mode:
                            print(f"   🎯 New best method: {method_name} ({success_rate:.1%})")
                        
                    if question_count and success_rate >= 0.8:
                        break
                else:
                    if debug_mode:
                        print(f"   ❌ No answers found")
                        
            except Exception as e:
                self.logger.warning(f"Method {method_name} failed: {str(e)}")
                if debug_mode:
                    print(f"   ❌ Error: {str(e)}")
                continue
        
        # If no method worked well, try combining results
        if best_result['metadata']['success_rate'] < 0.3:
            combined_result = self._combine_extraction_results(all_results, choices)
            if len(combined_result['answers']) > len(best_result['answers']):
                best_result = combined_result
                if debug_mode:
                    print(f"🔄 Using combined results: {len(combined_result['answers'])} answers")
        
        return best_result

    def _extract_answers_enhanced_bubble_detection(self, doc: fitz.Document, choices: List[str], 
                                                 question_count: int, debug_mode: bool = False) -> Dict[str, Any]:
        """Enhanced bubble detection with multiple algorithms"""
        answers = {}
        confidence_scores = {}
        debug_info = {'method': 'enhanced_bubble_detection', 'details': []} if debug_mode else None
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            
            # Convert page to high-resolution image
            mat = fitz.Matrix(3.0, 3.0)  # Higher resolution
            pix = page.get_pixmap(matrix=mat)
            img_data = pix.tobytes("png")
            
            nparr = np.frombuffer(img_data, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if debug_mode:
                debug_info['details'].append(f"Page {page_num+1}: Image size {image.shape}")
            
            # Multiple bubble detection approaches
            detection_methods = [
                self._detect_circles_hough,
                self._detect_filled_rectangles,
                self._detect_checkmarks,
                self._detect_dark_regions
            ]
            
            page_answers = {}
            for method in detection_methods:
                try:
                    method_answers = method(image, choices, debug_mode)
                    page_answers.update(method_answers)
                    if debug_mode and method_answers:
                        debug_info['details'].append(f"Method {method.__name__}: {len(method_answers)} answers")
                except Exception as e:
                    if debug_mode:
                        debug_info['details'].append(f"Method {method.__name__} failed: {str(e)}")
            
            # Merge with existing answers
            for q_num, answer in page_answers.items():
                if q_num not in answers:
                    answers[q_num] = answer
                    confidence_scores[q_num] = 0.8
        
        return {
            'answers': answers,
            'confidence_scores': confidence_scores,
            'metadata': {'method': 'enhanced_bubble_detection'},
            'debug_info': debug_info
        }

    def _detect_circles_hough(self, image: np.ndarray, choices: List[str], debug_mode: bool = False) -> Dict[int, str]:
        """Detect filled circles using Hough Circle Transform"""
        answers = {}
        
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Apply multiple detection parameters
            param_sets = [
                {'dp': 1, 'min_dist': 20, 'param1': 50, 'param2': 30, 'min_r': 5, 'max_r': 25},
                {'dp': 1, 'min_dist': 15, 'param1': 40, 'param2': 25, 'min_r': 3, 'max_r': 30},
                {'dp': 2, 'min_dist': 10, 'param1': 60, 'param2': 35, 'min_r': 4, 'max_r': 20}
            ]
            
            all_circles = []
            for params in param_sets:
                circles = cv2.HoughCircles(
                    gray, cv2.HOUGH_GRADIENT,
                    dp=params['dp'],
                    minDist=params['min_dist'],
                    param1=params['param1'],
                    param2=params['param2'],
                    minRadius=params['min_r'],
                    maxRadius=params['max_r']
                )
                
                if circles is not None:
                    circles = np.round(circles[0, :]).astype("int")
                    all_circles.extend(circles)
            
            if all_circles:
                # Remove duplicates and group by rows
                unique_circles = self._remove_duplicate_circles(all_circles)
                circle_groups = self._group_circles_by_rows(unique_circles)
                
                # Analyze each group
                for row_idx, circle_group in enumerate(circle_groups, 1):
                    filled_bubble = self._find_filled_bubble_enhanced(gray, circle_group, choices)
                    if filled_bubble and row_idx <= (len(choices) * 50):  # Reasonable limit
                        answers[row_idx] = filled_bubble
                        
        except Exception as e:
            if debug_mode:
                print(f"Circle detection error: {str(e)}")
        
        return answers

    def _detect_filled_rectangles(self, image: np.ndarray, choices: List[str], debug_mode: bool = False) -> Dict[int, str]:
        """Detect filled rectangular answer boxes"""
        answers = {}
        
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Threshold to find dark regions
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            
            # Find contours
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # Filter contours by size and shape
            potential_boxes = []
            for contour in contours:
                area = cv2.contourArea(contour)
                if 50 < area < 2000:  # Reasonable size range
                    x, y, w, h = cv2.boundingRect(contour)
                    aspect_ratio = float(w) / h
                    
                    # Look for square-ish or rectangular shapes
                    if 0.5 <= aspect_ratio <= 2.0:
                        # Check if it's filled (dark)
                        roi = gray[y:y+h, x:x+w]
                        mean_intensity = np.mean(roi)
                        
                        if mean_intensity < 150:  # Dark enough to be filled
                            potential_boxes.append((x, y, w, h, mean_intensity))
            
            # Group boxes by rows and assign to questions
            if potential_boxes:
                # Sort by y-coordinate (top to bottom)
                potential_boxes.sort(key=lambda box: box[1])
                
                # Group by rows
                rows = []
                current_row = [potential_boxes[0]]
                current_y = potential_boxes[0][1]
                
                for box in potential_boxes[1:]:
                    if abs(box[1] - current_y) <= 20:  # Same row
                        current_row.append(box)
                    else:
                        rows.append(current_row)
                        current_row = [box]
                        current_y = box[1]
                
                if current_row:
                    rows.append(current_row)
                
                # Assign answers based on position
                for row_idx, row_boxes in enumerate(rows, 1):
                    if len(row_boxes) <= len(choices):
                        # Sort by x-coordinate (left to right)
                        row_boxes.sort(key=lambda box: box[0])
                        
                        # Find the darkest box in the row
                        darkest_box = min(row_boxes, key=lambda box: box[4])
                        box_index = row_boxes.index(darkest_box)
                        
                        if box_index < len(choices):
                            answers[row_idx] = choices[box_index]
                            
        except Exception as e:
            if debug_mode:
                print(f"Rectangle detection error: {str(e)}")
        
        return answers

    def _detect_checkmarks(self, image: np.ndarray, choices: List[str], debug_mode: bool = False) -> Dict[int, str]:
        """Detect checkmarks or X marks"""
        answers = {}
        
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Edge detection to find checkmarks
            edges = cv2.Canny(gray, 50, 150, apertureSize=3)
            
            # Look for line intersections (checkmarks)
            lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=20, minLineLength=10, maxLineGap=5)
            
            if lines is not None:
                # Group lines by proximity to find intersections
                intersections = []
                for i, line1 in enumerate(lines):
                    x1, y1, x2, y2 = line1[0]
                    for j, line2 in enumerate(lines[i+1:], i+1):
                        x3, y3, x4, y4 = line2[0]
                        
                        # Calculate intersection
                        intersection = self._line_intersection((x1, y1, x2, y2), (x3, y3, x4, y4))
                        if intersection:
                            intersections.append(intersection)
                
                # Process intersections as potential checkmarks
                # This is a simplified approach - could be enhanced
                pass
                
        except Exception as e:
            if debug_mode:
                print(f"Checkmark detection error: {str(e)}")
        
        return answers

    def _detect_dark_regions(self, image: np.ndarray, choices: List[str], debug_mode: bool = False) -> Dict[int, str]:
        """Detect dark regions that might be filled bubbles or marks"""
        answers = {}
        
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Use adaptive thresholding to find dark regions
            adaptive_thresh = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2
            )
            
            # Find connected components
            num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(adaptive_thresh)
            
            # Filter components by size and density
            potential_marks = []
            for i in range(1, num_labels):  # Skip background (label 0)
                area = stats[i, cv2.CC_STAT_AREA]
                if 20 < area < 1000:  # Reasonable size for answer marks
                    x, y, w, h = stats[i, cv2.CC_STAT_LEFT], stats[i, cv2.CC_STAT_TOP], stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT]
                    
                    # Check density (how filled the region is)
                    roi = adaptive_thresh[y:y+h, x:x+w]
                    density = np.sum(roi > 0) / (w * h)
                    
                    if density > 0.3:  # At least 30% filled
                        potential_marks.append((x + w//2, y + h//2, area, density))
            
            # Group marks by rows and assign answers
            if potential_marks:
                # Sort by y-coordinate
                potential_marks.sort(key=lambda mark: mark[1])
                
                # Group by rows (similar y-coordinates)
                rows = []
                current_row = [potential_marks[0]]
                current_y = potential_marks[0][1]
                
                for mark in potential_marks[1:]:
                    if abs(mark[1] - current_y) <= 30:  # Same row tolerance
                        current_row.append(mark)
                    else:
                        rows.append(current_row)
                        current_row = [mark]
                        current_y = mark[1]
                
                if current_row:
                    rows.append(current_row)
                
                # Assign answers
                for row_idx, row_marks in enumerate(rows, 1):
                    if len(row_marks) <= len(choices) and row_idx <= 100:  # Reasonable limits
                        # Sort by x-coordinate
                        row_marks.sort(key=lambda mark: mark[0])
                        
                        # Find the most filled mark
                        best_mark = max(row_marks, key=lambda mark: mark[3])  # Highest density
                        mark_index = row_marks.index(best_mark)
                        
                        if mark_index < len(choices):
                            answers[row_idx] = choices[mark_index]
                            
        except Exception as e:
            if debug_mode:
                print(f"Dark region detection error: {str(e)}")
        
        return answers

    def _extract_answers_comprehensive_pattern_matching(self, doc: fitz.Document, choices: List[str], 
                                                      question_count: int, debug_mode: bool = False) -> Dict[str, Any]:
        """Comprehensive pattern matching for answers"""
        answers = {}
        confidence_scores = {}
        debug_info = {'method': 'comprehensive_pattern_matching', 'patterns_tried': []} if debug_mode else None
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            
            # Enhanced patterns for different answer formats
            patterns = [
                # Standard formats
                r'\b(\d{1,3})[\.\)]\s*([A-E]|True|False|T|F)\b',
                r'Question\s*(\d{1,3})[:\.\)]\s*([A-E]|True|False|T|F)',
                r'Q(\d{1,3})\s*[:\.\)]\s*([A-E]|True|False|T|F)',
                
                # Spaced formats
                r'(\d{1,3})\s+([A-E]|True|False)\b',
                r'(\d{1,3})\s*-\s*([A-E]|True|False)',
                
                # With answer indicators
                r'Answer\s*(\d{1,3})[:\.\)]\s*([A-E]|True|False)',
                r'(\d{1,3})\s*Answer[:\.\)]\s*([A-E]|True|False)',
                
                # Grid format (common in answer sheets)
                r'(\d{1,3})\s*\|\s*([A-E])',
                r'(\d{1,3})\s*\[\s*([A-E])\s*\]',
                
                # Marked/selected format
                r'(\d{1,3})\s*[:\.\)]\s*\*([A-E])\*',
                r'(\d{1,3})\s*[:\.\)]\s*>([A-E])<',
            ]
            
            found_patterns = []
            
            for pattern in patterns:
                matches = list(re.finditer(pattern, text, re.IGNORECASE))
                if matches:
                    found_patterns.append((pattern, len(matches)))
                    
                for match in matches:
                    try:
                        q_num = int(match.group(1))
                        if not (1 <= q_num <= 200):  # Reasonable range
                            continue
                            
                        answer = match.group(2).upper()
                        
                        # Normalize true/false answers
                        if answer in ['T', 'TRUE']:
                            answer = 'True'
                        elif answer in ['F', 'FALSE']:
                            answer = 'False'
                        
                        if answer in choices and q_num not in answers:
                            answers[q_num] = answer
                            confidence_scores[q_num] = 0.7
                            
                    except (ValueError, IndexError):
                        continue
            
            if debug_mode:
                debug_info['patterns_tried'].extend(found_patterns)
        
        return {
            'answers': answers,
            'confidence_scores': confidence_scores,
            'metadata': {'method': 'comprehensive_pattern_matching'},
            'debug_info': debug_info
        }

    def _extract_answers_enhanced_ocr(self, doc: fitz.Document, choices: List[str], 
                                    question_count: int, debug_mode: bool = False) -> Dict[str, Any]:
        """Enhanced OCR with better preprocessing"""
        answers = {}
        confidence_scores = {}
        debug_info = {'method': 'enhanced_ocr', 'ocr_results': []} if debug_mode else None
        
        if not TESSERACT_AVAILABLE:
            raise Exception("Tesseract OCR not available")
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            
            # Convert to high-resolution image
            mat = fitz.Matrix(3.0, 3.0)
            pix = page.get_pixmap(matrix=mat)
            img_data = pix.tobytes("png")
            
            nparr = np.frombuffer(img_data, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            # Try multiple image preprocessing approaches
            preprocessing_methods = [
                self._enhance_image_for_ocr,
                self._enhance_for_text_detection,
                self._enhance_for_marks_detection
            ]
            
            page_text_results = []
            
            for preprocess_func in preprocessing_methods:
                try:
                    enhanced = preprocess_func(image)
                    
                    # Try different OCR configurations
                    ocr_configs = [
                        r'--oem 3 --psm 6',  # Uniform block of text
                        r'--oem 3 --psm 4',  # Single column of text
                        r'--oem 3 --psm 8',  # Single word
                        r'--oem 3 --psm 13', # Raw line (bypass text analysis)
                    ]
                    
                    for config in ocr_configs:
                        try:
                            text = pytesseract.image_to_string(enhanced, config=config)
                            if text.strip():
                                page_text_results.append(text)
                        except:
                            continue
                            
                except Exception as e:
                    if debug_mode:
                        print(f"OCR preprocessing error: {str(e)}")
                    continue
            
            # Process all OCR results
            for text_result in page_text_results:
                page_answers = self._parse_ocr_text_enhanced(text_result, choices)
                for q_num, answer in page_answers.items():
                    if q_num not in answers:
                        answers[q_num] = answer
                        confidence_scores[q_num] = 0.6
            
            if debug_mode:
                debug_info['ocr_results'].append({
                    'page': page_num + 1,
                    'texts_found': len(page_text_results),
                    'answers_extracted': len([a for a in answers.keys()])
                })
        
        return {
            'answers': answers,
            'confidence_scores': confidence_scores,
            'metadata': {'method': 'enhanced_ocr'},
            'debug_info': debug_info
        }

    def _extract_answers_text_analysis(self, doc: fitz.Document, choices: List[str], 
                                     question_count: int, debug_mode: bool = False) -> Dict[str, Any]:
        """Analyze PDF text content directly"""
        answers = {}
        confidence_scores = {}
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            
            # Get text with formatting information
            text_dict = page.get_text("dict")
            
            # Analyze text blocks for answer patterns
            for block in text_dict.get("blocks", []):
                if "lines" in block:
                    for line in block["lines"]:
                        line_text = ""
                        for span in line.get("spans", []):
                            line_text += span.get("text", "")
                        
                        # Look for answer patterns in each line
                        matches = re.finditer(r'(\d{1,3})\s*[:\.\)]\s*([A-E]|True|False)', line_text, re.IGNORECASE)
                        for match in matches:
                            try:
                                q_num = int(match.group(1))
                                if 1 <= q_num <= 200:
                                    answer = match.group(2).upper()
                                    if answer in ['TRUE', 'T']:
                                        answer = 'True'
                                    elif answer in ['FALSE', 'F']:
                                        answer = 'False'
                                    
                                    if answer in choices:
                                        answers[q_num] = answer
                                        confidence_scores[q_num] = 0.8
                            except ValueError:
                                continue
        
        return {
            'answers': answers,
            'confidence_scores': confidence_scores,
            'metadata': {'method': 'text_analysis'}
        }

    def _extract_answers_visual_marks(self, doc: fitz.Document, choices: List[str], 
                                    question_count: int, debug_mode: bool = False) -> Dict[str, Any]:
        """Detect visual marks like highlights, underlines, or circles"""
        answers = {}
        confidence_scores = {}
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            
            # Check for annotations that might indicate answers
            annotations = page.annots()
            for annot in annotations:
                try:
                    annot_type = annot.type[1]
                    if annot_type in ['Highlight', 'Underline', 'Circle', 'Square']:
                        # Get annotation content or nearby text
                        rect = annot.rect
                        
                        # Get text in the annotation area
                        nearby_text = page.get_textbox(rect)
                        
                        # Look for answer patterns
                        match = re.search(r'(\d{1,3})\s*[:\.\)]\s*([A-E]|True|False)', nearby_text, re.IGNORECASE)
                        if match:
                            q_num = int(match.group(1))
                            if 1 <= q_num <= 200:
                                answer = match.group(2).upper()
                                if answer in choices:
                                    answers[q_num] = answer
                                    confidence_scores[q_num] = 0.9  # High confidence for explicit marks
                                    
                except Exception:
                    continue
        
        return {
            'answers': answers,
            'confidence_scores': confidence_scores,
            'metadata': {'method': 'visual_marks'}
        }

    # Helper methods
    def _remove_duplicate_circles(self, circles: List) -> List:
        """Remove duplicate circles that are too close to each other"""
        if not circles:
            return []
        
        unique_circles = []
        for circle in circles:
            x, y, r = circle
            is_duplicate = False
            
            for existing in unique_circles:
                ex, ey, er = existing
                distance = np.sqrt((x - ex)**2 + (y - ey)**2)
                if distance < min(r, er) * 1.5:  # Too close
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                unique_circles.append(circle)
        
        return unique_circles

    def _group_circles_by_rows(self, circles: List, row_tolerance: int = 25) -> List[List]:
        """Group circles by rows with improved tolerance"""
        if not circles:
            return []
        
        # Sort by y-coordinate
        sorted_circles = sorted(circles, key=lambda c: c[1])
        
        groups = []
        current_group = [sorted_circles[0]]
        current_y = sorted_circles[0][1]
        
        for circle in sorted_circles[1:]:
            if abs(circle[1] - current_y) <= row_tolerance:
                current_group.append(circle)
            else:
                if len(current_group) <= 6:  # Reasonable number of choices per row
                    current_group.sort(key=lambda c: c[0])  # Sort by x-coordinate
                    groups.append(current_group)
                current_group = [circle]
                current_y = circle[1]
        
        if current_group and len(current_group) <= 6:
            current_group.sort(key=lambda c: c[0])
            groups.append(current_group)
        
        return groups

    def _find_filled_bubble_enhanced(self, thresh_image: np.ndarray, circles: List, 
                                   choices: List[str]) -> Optional[str]:
        """Enhanced bubble fill detection"""
        max_fill_ratio = 0
        selected_choice = None
        
        for idx, (x, y, r) in enumerate(circles):
            if idx >= len(choices):
                break
            
            # Create multiple masks with different radii
            mask_ratios = [0.6, 0.7, 0.8]
            fill_ratios = []
            
            for ratio in mask_ratios:
                mask = np.zeros(thresh_image.shape, dtype=np.uint8)
                cv2.circle(mask, (x, y), int(r * ratio), 255, -1)
                
                bubble_region = cv2.bitwise_and(thresh_image, mask)
                white_pixels = cv2.countNonZero(bubble_region)
                total_pixels = cv2.countNonZero(mask)
                
                if total_pixels > 0:
                    fill_ratios.append(white_pixels / total_pixels)
            
            # Use average fill ratio
            avg_fill_ratio = np.mean(fill_ratios) if fill_ratios else 0
            
            # Lower threshold for more sensitive detection
            if avg_fill_ratio > max_fill_ratio and avg_fill_ratio > 0.2:
                max_fill_ratio = avg_fill_ratio
                selected_choice = choices[idx]
        
        return selected_choice

    def _enhance_for_text_detection(self, image: np.ndarray) -> np.ndarray:
        """Enhance image specifically for text detection"""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        
        # Increase contrast
        enhanced = cv2.convertScaleAbs(gray, alpha=1.5, beta=0)
        
        # Denoise
        denoised = cv2.fastNlMeansDenoising(enhanced)
        
        # Morphological operations to clean up
        kernel = np.ones((2, 2), np.uint8)
        cleaned = cv2.morphologyEx(denoised, cv2.MORPH_CLOSE, kernel)
        
        return cleaned

    def _enhance_for_marks_detection(self, image: np.ndarray) -> np.ndarray:
        """Enhance image for detecting marks and filled areas"""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        
        # Apply bilateral filter to reduce noise while keeping edges
        filtered = cv2.bilateralFilter(gray, 9, 75, 75)
        
        # Enhance dark marks
        enhanced = cv2.convertScaleAbs(filtered, alpha=1.3, beta=-20)
        
        return enhanced

    def _parse_ocr_text_enhanced(self, text: str, choices: List[str]) -> Dict[int, str]:
        """Enhanced OCR text parsing with better pattern recognition"""
        answers = {}
        
        # Split text into lines for better analysis
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Enhanced patterns
            patterns = [
                r'(\d{1,3})\s*[\.\)]\s*([A-E]|True|False)',
                r'(\d{1,3})\s+([A-E]|True|False)',
                r'Q\s*(\d{1,3})\s*[:\.\)]\s*([A-E]|True|False)',
                r'Question\s*(\d{1,3})\s*[:\.\)]\s*([A-E]|True|False)',
            ]
            
            for pattern in patterns:
                matches = re.finditer(pattern, line, re.IGNORECASE)
                for match in matches:
                    try:
                        q_num = int(match.group(1))
                        if 1 <= q_num <= 200:
                            answer = match.group(2).upper()
                            if answer in ['TRUE', 'T']:
                                answer = 'True'
                            elif answer in ['FALSE', 'F']:
                                answer = 'False'
                            
                            if answer in choices:
                                answers[q_num] = answer
                    except (ValueError, IndexError):
                        continue
        
        return answers

    def _combine_extraction_results(self, all_results: List, choices: List[str]) -> Dict[str, Any]:
        """Combine results from multiple extraction methods"""
        combined_answers = {}
        combined_confidence = {}
        method_votes = {}
        
        # Collect all answers with their confidence scores
        for method_name, result in all_results:
            for q_num, answer in result.get('answers', {}).items():
                if q_num not in method_votes:
                    method_votes[q_num] = {}
                
                if answer not in method_votes[q_num]:
                    method_votes[q_num][answer] = []
                
                confidence = result.get('confidence_scores', {}).get(q_num, 0.5)
                method_votes[q_num][answer].append((method_name, confidence))
        
        # Determine best answer for each question based on votes and confidence
        for q_num, votes in method_votes.items():
            best_answer = None
            best_score = 0
            
            for answer, vote_list in votes.items():
                # Calculate weighted score
                score = sum(conf for _, conf in vote_list) * len(vote_list)
                
                if score > best_score:
                    best_score = score
                    best_answer = answer
            
            if best_answer and best_score > 0.3:
                combined_answers[q_num] = best_answer
                combined_confidence[q_num] = min(best_score / 2, 0.9)  # Normalize confidence
        
        return {
            'answers': combined_answers,
            'confidence_scores': combined_confidence,
            'metadata': {'method': 'combined_results', 'success_rate': 0.0}
        }

    def _line_intersection(self, line1: Tuple, line2: Tuple) -> Optional[Tuple]:
        """Calculate intersection point of two lines"""
        x1, y1, x2, y2 = line1
        x3, y3, x4, y4 = line2
        
        denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
        if abs(denom) < 1e-10:
            return None
        
        t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
        u = -((x1 - x2) * (y1 - y3) - (y1 - y2) * (x1 - x3)) / denom
        
        if 0 <= t <= 1 and 0 <= u <= 1:
            x = x1 + t * (x2 - x1)
            y = y1 + t * (y2 - y1)
            return (int(x), int(y))
        
        return None

    def _enhance_image_for_ocr(self, image: np.ndarray) -> np.ndarray:
        """Enhance image quality for better OCR results"""
        try:
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image.copy()
            
            # Noise removal
            denoised = cv2.fastNlMeansDenoising(gray)
            
            # Contrast enhancement
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            enhanced = clahe.apply(denoised)
            
            # Sharpening
            kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
            sharpened = cv2.filter2D(enhanced, -1, kernel)
            
            return sharpened
            
        except Exception as e:
            self.logger.warning(f"Image enhancement error: {str(e)}")
            return image

    def _get_answer_choices(self, test_type: str) -> List[str]:
        """Get valid answer choices for test type"""
        if test_type == 'multiple_choice_4':
            return ['A', 'B', 'C', 'D']
        elif test_type == 'multiple_choice_5':
            return ['A', 'B', 'C', 'D', 'E']
        elif test_type == 'true_false':
            return ['True', 'False']
        else:
            return ['A', 'B', 'C', 'D']

    def extract_from_uploaded_file(self, file_obj, test_type: str = 'multiple_choice_4', 
                                 question_count: int = None) -> Dict[str, Any]:
        """Extract data from uploaded file object"""
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                for chunk in file_obj.chunks():
                    temp_file.write(chunk)
                temp_path = temp_file.name
            
            return self.extract_from_pdf(temp_path, test_type, question_count)
            
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass

# Usage example and testing function
def test_extraction(pdf_path: str, debug: bool = True):
    """Test function for PDF extraction with debug mode"""
    extractor = PDFExtractionService()
    
    result = extractor.extract_from_pdf(
        pdf_path=pdf_path,
        test_type='multiple_choice_4',
        question_count=50,
        debug_mode=debug
    )
    
    print("=== PDF Extraction Results ===")
    print(f"Success: {result['success']}")
    print(f"Student Name: '{result['student_name']}'")
    print(f"Student ID: '{result['student_id']}'")
    print(f"Total Answers: {len(result['answers'])}")
    print(f"Extraction Method: {result['metadata'].get('extraction_method', 'N/A')}")
    print(f"Student Info Confidence: {result['metadata'].get('student_info_confidence', 0):.1%}")
    print(f"Tesseract Available: {result['metadata'].get('tesseract_available', False)}")
    
    if result['answers']:
        print("\nExtracted Answers:")
        for q_num, answer in sorted(result['answers'].items()):
            confidence = result['confidence_scores'].get(q_num, 0)
            print(f"  Q{q_num}: {answer} (confidence: {confidence:.1%})")
    else:
        print("\n❌ No answers detected!")
        print("This might indicate:")
        print("  - The PDF doesn't contain standard answer sheet format")
        print("  - Answers are handwritten or in non-standard format")
        print("  - The image quality is too low for detection")
        print("  - Different answer marking method is used")
    
    if result['errors']:
        print(f"\nErrors: {result['errors']}")
    
    return result

if __name__ == "__main__":
    # Test with the provided PDF
    test_pdf_path = r"d:\YUKI\ADET\Checkmate\pdf_directory\Test.pdf"
    if os.path.exists(test_pdf_path):
        test_extraction(test_pdf_path, debug=True)
    else:
        print(f"Test PDF not found at: {test_pdf_path}")