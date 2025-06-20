"""
CheckMate PDF Processor - Main Coordinator

This is the main entry point that coordinates all PDF processing tasks.
Uses modular components for student info extraction and answer processing.
"""

import cv2
import numpy as np
import pdf2image
from PIL import Image
import os
import logging
import argparse
from pathlib import Path

# Import our modular components
from pdf_processor_stud_info import StudentInfoExtractor
from pdf_processor_stud_answer import StudentAnswerProcessor

# Import configuration
try:
    from field_coordinates_config import (
        FIELD_COORDINATES, 
        STUDENT_REGION, 
        get_student_region_config,
        print_current_config
    )
    CONFIG_AVAILABLE = True
except ImportError:
    CONFIG_AVAILABLE = False

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CheckMatePDFProcessor:
    """
    Main CheckMate PDF processor that coordinates all processing tasks
    """
    
    def __init__(self, debug_mode=False):
        self.debug_mode = debug_mode
        self.debug_images = []
        
        # A4 dimensions at 300 DPI
        self.target_width = 2480
        self.target_height = 3508
        
        # Initialize specialized processors
        self.student_info_extractor = StudentInfoExtractor()
        self.answer_processor = StudentAnswerProcessor()
        
        # Log configuration status
        if CONFIG_AVAILABLE:
            logger.info("✓ Configuration loaded from field_coordinates_config.py")
            if debug_mode:
                print_current_config()
        else:
            logger.warning("⚠ Configuration file not found - using defaults")

    def convert_pdf_to_image(self, pdf_path, page_number=0, dpi=300):
        """
        Convert PDF page to image
        
        Args:
            pdf_path: Path to PDF file
            page_number: Page number to convert (0-indexed)
            dpi: Resolution for conversion
            
        Returns:
            PIL Image object or None if failed
        """
        try:
            logger.info(f"Converting PDF to image: {pdf_path}")
            
            # Convert PDF to images using pdf2image
            images = pdf2image.convert_from_path(
                pdf_path,
                dpi=dpi,
                first_page=page_number + 1,
                last_page=page_number + 1,
                fmt='RGB'
            )
            
            if not images:
                logger.error("No images generated from PDF")
                return None
                
            image = images[0]
            logger.info(f"✓ PDF converted successfully: {image.size}")
            
            if self.debug_mode:
                self.debug_images.append(('01_pdf_original', np.array(image)))
                
            return image
            
        except Exception as e:
            logger.error(f"✗ Error converting PDF to image: {str(e)}")
            return None

    def detect_corner_markers(self, image):
        """
        Enhanced corner detection with fine-tuning capabilities
        
        Args:
            image: PIL Image or numpy array
            
        Returns:
            List of 4 corner points [(x,y), ...] or None if failed
        """
        try:
            logger.info("Detecting corner markers...")
            
            # Convert to numpy array if needed
            if isinstance(image, Image.Image):
                img_array = np.array(image)
            else:
                img_array = image.copy()
            
            # Convert to grayscale
            if len(img_array.shape) == 3:
                gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            else:
                gray = img_array.copy()
            
            height, width = gray.shape
            logger.info(f"Processing image for corner detection: {width}x{height}")
            
            if self.debug_mode:
                self.debug_images.append(('02_grayscale', gray))
            
            # Enhanced corner detection approach
            corner_size = 100  # Reduced search area for more precision
            corners_found = []
            
            # Define corner regions to search with better margins
            margin = 30  # Distance from edge to avoid border artifacts
            corner_regions = [
                (margin, margin, "TL"),  # Top-left
                (width - corner_size - margin, margin, "TR"),  # Top-right
                (margin, height - corner_size - margin, "BL"),  # Bottom-left
                (width - corner_size - margin, height - corner_size - margin, "BR")  # Bottom-right
            ]
            
            for x, y, label in corner_regions:
                # Extract corner region
                region = gray[y:y+corner_size, x:x+corner_size]
                
                # Apply preprocessing to find dark markers better
                blurred = cv2.GaussianBlur(region, (5, 5), 0)
                _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                
                # Find contours to locate marker more precisely
                contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                if contours:
                    # Find the largest contour (likely the marker)
                    largest_contour = max(contours, key=cv2.contourArea)
                    
                    # Get the center of the contour
                    M = cv2.moments(largest_contour)
                    if M["m00"] != 0:
                        cx = int(M["m10"] / M["m00"])
                        cy = int(M["m01"] / M["m00"])
                    else:
                        cx, cy = corner_size // 2, corner_size // 2
                    
                    # Convert back to full image coordinates
                    corner_x = x + cx
                    corner_y = y + cy
                else:
                    # Fallback to darkest point method
                    min_val = np.min(region)
                    min_loc = np.unravel_index(np.argmin(region), region.shape)
                    corner_x = x + min_loc[1]
                    corner_y = y + min_loc[0]
                
                corners_found.append((corner_x, corner_y))
                logger.info(f"Corner {label}: ({corner_x}, {corner_y})")
            
            if len(corners_found) == 4:
                logger.info("✓ Successfully detected 4 corner markers")
                return corners_found
            else:
                logger.warning("⚠ Could not detect all corners, using fallback")
                # Better fallback based on typical PDF margins
                margin = 50
                return [
                    (margin, margin),  # Top-left
                    (width - margin, margin),  # Top-right
                    (margin, height - margin),  # Bottom-left
                    (width - margin, height - margin)  # Bottom-right
                ]
            
        except Exception as e:
            logger.error(f"✗ Error detecting corner markers: {str(e)}")
            return None

    def fine_tune_corners(self, image, initial_corners, adjustment=None):
        """
        Fine-tune corner positions for better perspective correction
        
        Args:
            image: PIL Image or numpy array
            initial_corners: List of 4 corner points [(x,y), ...]
            adjustment: Dictionary with corner adjustments {'tl': (dx, dy), 'tr': (dx, dy), etc.}
            
        Returns:
            Adjusted corner points
        """
        try:
            if adjustment is None:
                # Default fine-tuning based on your PDF analysis
                adjustment = {
                    'tl': (-10, -10),  # Move top-left up and left
                    'tr': (10, -10),   # Move top-right up and right
                    'bl': (-10, 10),   # Move bottom-left down and left
                    'br': (10, 10)     # Move bottom-right down and right
                }
            
            adjusted_corners = []
            corner_labels = ['tl', 'tr', 'bl', 'br']
            
            for i, (x, y) in enumerate(initial_corners):
                label = corner_labels[i]
                if label in adjustment:
                    dx, dy = adjustment[label]
                    new_x = max(0, min(x + dx, image.width if hasattr(image, 'width') else image.shape[1] - 1))
                    new_y = max(0, min(y + dy, image.height if hasattr(image, 'height') else image.shape[0] - 1))
                    adjusted_corners.append((new_x, new_y))
                    logger.info(f"Adjusted {label}: ({x}, {y}) -> ({new_x}, {new_y})")
                else:
                    adjusted_corners.append((x, y))
            
            return adjusted_corners
            
        except Exception as e:
            logger.error(f"Error fine-tuning corners: {str(e)}")
            return initial_corners

    def debug_corner_detection(self, image, output_dir=None):
        """
        Debug corner detection with visual feedback
        
        Args:
            image: PIL Image or numpy array
            output_dir: Directory to save debug images
            
        Returns:
            Dictionary with corner analysis
        """
        try:
            logger.info("=== CORNER DETECTION DEBUG MODE ===")
            
            # Convert to numpy array if needed
            if isinstance(image, Image.Image):
                img_array = np.array(image)
            else:
                img_array = image.copy()
            
            # Convert to RGB for visualization
            if len(img_array.shape) == 3:
                debug_img = img_array.copy()
            else:
                debug_img = cv2.cvtColor(img_array, cv2.COLOR_GRAY2RGB)
            
            height, width = img_array.shape[:2]
            
            # Detect corners
            corners = self.detect_corner_markers(image)
            if corners is None:
                return {'success': False, 'error': 'Corner detection failed'}
            
            # Draw detected corners
            corner_labels = ['TL', 'TR', 'BL', 'BR']
            colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]  # Red, Green, Blue, Yellow
            
            for i, ((x, y), label, color) in enumerate(zip(corners, corner_labels, colors)):
                # Draw corner marker
                cv2.circle(debug_img, (int(x), int(y)), 15, color, 3)
                cv2.putText(debug_img, f"{label}", (int(x)+20, int(y)+20), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
                
                # Draw coordinates
                cv2.putText(debug_img, f"({int(x)},{int(y)})", (int(x)+20, int(y)+40), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            
            # Draw bounding rectangle
            cv2.polylines(debug_img, [np.array(corners, dtype=np.int32)], 
                         True, (255, 255, 255), 2)
            
            # Test different corner adjustments
            test_adjustments = [
                {'name': 'Original', 'adj': None},
                {'name': 'Inward_5px', 'adj': {'tl': (5, 5), 'tr': (-5, 5), 'bl': (5, -5), 'br': (-5, -5)}},
                {'name': 'Outward_5px', 'adj': {'tl': (-5, -5), 'tr': (5, -5), 'bl': (-5, 5), 'br': (5, 5)}},
                {'name': 'Inward_10px', 'adj': {'tl': (10, 10), 'tr': (-10, 10), 'bl': (10, -10), 'br': (-10, -10)}},
                {'name': 'Outward_10px', 'adj': {'tl': (-10, -10), 'tr': (10, -10), 'bl': (-10, 10), 'br': (10, 10)}}
            ]
            
            results = []
            
            for test in test_adjustments:
                if test['adj'] is None:
                    test_corners = corners
                else:
                    test_corners = self.fine_tune_corners(image, corners, test['adj'])
                
                # Apply perspective correction with these corners
                corrected = self.apply_perspective_correction(image, test_corners)
                
                if corrected is not None:
                    results.append({
                        'name': test['name'],
                        'corners': test_corners,
                        'corrected_shape': corrected.shape,
                        'adjustment': test['adj']
                    })
                    
                    # Save corrected image for comparison
                    if output_dir:
                        debug_dir = os.path.join(output_dir, 'corner_tuning_debug')
                        os.makedirs(debug_dir, exist_ok=True)
                        
                        corrected_bgr = cv2.cvtColor(corrected, cv2.COLOR_RGB2BGR)
                        cv2.imwrite(os.path.join(debug_dir, f'corrected_{test["name"]}.png'), corrected_bgr)
            
            # Save debug images
            if output_dir:
                debug_dir = os.path.join(output_dir, 'corner_tuning_debug')
                os.makedirs(debug_dir, exist_ok=True)
                
                # Save original with corners marked
                debug_bgr = cv2.cvtColor(debug_img, cv2.COLOR_RGB2BGR)
                cv2.imwrite(os.path.join(debug_dir, 'corners_detected.png'), debug_bgr)
                
                # Save analysis report
                with open(os.path.join(debug_dir, 'corner_analysis.txt'), 'w') as f:
                    f.write("CORNER DETECTION ANALYSIS\n")
                    f.write("="*50 + "\n\n")
                    f.write(f"Original image size: {width} x {height}\n")
                    f.write(f"Target size: {self.target_width} x {self.target_height}\n\n")
                    
                    f.write("DETECTED CORNERS:\n")
                    for i, (corner, label) in enumerate(zip(corners, corner_labels)):
                        f.write(f"{label}: ({corner[0]}, {corner[1]})\n")
                    f.write("\n")
                    
                    f.write("TEST RESULTS:\n")
                    for result in results:
                        f.write(f"\n{result['name']}:\n")
                        f.write(f"  Corrected shape: {result['corrected_shape']}\n")
                        if result['adjustment']:
                            f.write(f"  Adjustment: {result['adjustment']}\n")
                        f.write(f"  Corners used: {result['corners']}\n")
                    
                    f.write("\nRECOMMENDATIONS:\n")
                    f.write("1. Check the corrected images to see which looks best\n")
                    f.write("2. Use the adjustment values that produce the most aligned result\n")
                    f.write("3. If none look good, try manual corner specification\n")
                
                logger.info(f"Corner debug analysis saved to: {debug_dir}")
            
            return {
                'success': True,
                'original_corners': corners,
                'test_results': results,
                'image_size': (width, height),
                'target_size': (self.target_width, self.target_height)
            }
            
        except Exception as e:
            logger.error(f"Error in corner debug: {str(e)}")
            return {'success': False, 'error': str(e)}

    def apply_perspective_correction(self, image, corners):
        """
        Apply perspective correction using detected corners
        
        Args:
            image: PIL Image or numpy array
            corners: List of 4 corner points [(x,y), ...]
            
        Returns:
            Corrected numpy array image or None if failed
        """
        try:
            logger.info("Applying perspective correction...")
            
            # Convert to numpy array if needed
            if isinstance(image, Image.Image):
                img_array = np.array(image)
            else:
                img_array = image.copy()
            
            # Log original corners for debugging
            logger.info(f"Original detected corners: {corners}")
            
            # Define source points (detected corners)
            # Order: Top-left, Top-right, Bottom-left, Bottom-right
            src_points = np.array([
                corners[0],  # Top-left
                corners[1],  # Top-right  
                corners[2],  # Bottom-left
                corners[3]   # Bottom-right
            ], dtype=np.float32)
            
            # Define destination points (standard A4 rectangle)
            dst_points = np.array([
                [0, 0],                                    # Top-left
                [self.target_width-1, 0],                  # Top-right
                [0, self.target_height-1],                 # Bottom-left
                [self.target_width-1, self.target_height-1] # Bottom-right
            ], dtype=np.float32)
            
            logger.info(f"Source points: {src_points}")
            logger.info(f"Destination points: {dst_points}")
            
            # Calculate perspective transformation matrix
            matrix = cv2.getPerspectiveTransform(src_points, dst_points)
            logger.info(f"Transformation matrix: {matrix}")
            
            # Apply perspective correction
            corrected = cv2.warpPerspective(
                img_array, 
                matrix, 
                (self.target_width, self.target_height),
                flags=cv2.INTER_LINEAR
            )
            
            logger.info(f"✓ Perspective correction applied: {corrected.shape}")
            
            if self.debug_mode:
                self.debug_images.append(('03_perspective_corrected', corrected))
                # Add corner visualization
                corner_debug = img_array.copy()
                if len(corner_debug.shape) == 3:
                    corner_debug = cv2.cvtColor(corner_debug, cv2.COLOR_RGB2BGR)
                else:
                    corner_debug = cv2.cvtColor(corner_debug, cv2.COLOR_GRAY2BGR)
                
                # Draw detected corners
                for i, (x, y) in enumerate(corners):
                    cv2.circle(corner_debug, (int(x), int(y)), 10, (0, 0, 255), 3)
                    cv2.putText(corner_debug, f"C{i}", (int(x)+15, int(y)+15), 
                               cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                
                # Draw bounding rectangle
                cv2.polylines(corner_debug, [np.array(corners, dtype=np.int32)], 
                             True, (0, 255, 0), 3)
                
                self.debug_images.append(('03a_corner_detection', corner_debug))
            
            return corrected
            
        except Exception as e:
            logger.error(f"✗ Error in perspective correction: {str(e)}")
            return None

    def manual_perspective_correction(self, image, manual_corners=None):
        """
        Apply manual perspective correction with custom corner points
        
        Args:
            image: PIL Image or numpy array  
            manual_corners: List of 4 corner points [(x,y), ...] in order TL, TR, BL, BR
            
        Returns:
            Corrected numpy array image
        """
        try:
            logger.info("Applying manual perspective correction...")
            
            # Convert to numpy array if needed
            if isinstance(image, Image.Image):
                img_array = np.array(image)
            else:
                img_array = image.copy()
            
            if manual_corners is None:
                # Use default corners based on typical CheckMate layout
                height, width = img_array.shape[:2]
                # Adjust these values based on your PDF layout
                margin = 50  # Distance from edge to actual content
                manual_corners = [
                    (margin, margin),                    # Top-left
                    (width - margin, margin),            # Top-right  
                    (margin, height - margin),           # Bottom-left
                    (width - margin, height - margin)    # Bottom-right
                ]
            
            logger.info(f"Using manual corners: {manual_corners}")
            
            # Define source points
            src_points = np.array(manual_corners, dtype=np.float32)
            
            # Define destination points (standard A4 rectangle)
            dst_points = np.array([
                [0, 0],                                    # Top-left
                [self.target_width-1, 0],                  # Top-right
                [0, self.target_height-1],                 # Bottom-left
                [self.target_width-1, self.target_height-1] # Bottom-right
            ], dtype=np.float32)
            
            # Calculate and apply perspective transformation
            matrix = cv2.getPerspectiveTransform(src_points, dst_points)
            corrected = cv2.warpPerspective(
                img_array, 
                matrix, 
                (self.target_width, self.target_height),
                flags=cv2.INTER_LINEAR
            )
            
            logger.info(f"✓ Manual perspective correction applied: {corrected.shape}")
            return corrected
            
        except Exception as e:
            logger.error(f"✗ Error in manual perspective correction: {str(e)}")
            return None

    def extract_student_information(self, corrected_image, output_dir=None):
        """
        Extract student information using the specialized extractor
        
        Args:
            corrected_image: Perspective corrected image
            output_dir: Directory to save debug images (optional)
            
        Returns:
            Dictionary with extracted student info
        """
        logger.info("=== STUDENT INFORMATION EXTRACTION ===")
        return self.student_info_extractor.extract_student_info(corrected_image, output_dir)

    def extract_student_answers(self, corrected_image, question_count, test_type, output_dir=None):
        """
        Extract student answers using the specialized processor
        
        Args:
            corrected_image: Perspective corrected image
            question_count: Number of questions in the test
            test_type: Type of test (multiple_choice_4, multiple_choice_5, true_false)
            output_dir: Directory to save debug images (optional)
            
        Returns:
            Dictionary with extracted answers
        """
        logger.info("=== STUDENT ANSWER EXTRACTION ===")
        return self.answer_processor.extract_student_answers(
            corrected_image, question_count, test_type, output_dir
        )

    def save_debug_images(self, output_dir, prefix="main"):
        """Save debug images from main processor"""
        if not self.debug_mode:
            return
            
        try:
            # Create main debug directory
            main_debug_dir = os.path.join(output_dir, 'main_debug')
            os.makedirs(main_debug_dir, exist_ok=True)
            
            for stage_name, debug_img in self.debug_images:
                filename = f"{prefix}_{stage_name}.png"
                filepath = os.path.join(main_debug_dir, filename)
                
                # Save image
                cv2.imwrite(filepath, debug_img)
                logger.info(f"Saved main debug image: {filepath}")
                
        except Exception as e:
            logger.error(f"Error saving main debug images: {str(e)}")

    def process_pdf_answer_sheet(self, pdf_path, output_dir=None, 
                                extract_student_info=True, extract_answers=False,
                                question_count=None, test_type=None):
        """
        Complete processing pipeline for PDF answer sheets
        
        Args:
            pdf_path: Path to PDF file
            output_dir: Directory to save debug images and results
            extract_student_info: Whether to extract student information
            extract_answers: Whether to extract student answers
            question_count: Number of questions (required if extract_answers=True)
            test_type: Test type (required if extract_answers=True)
            
        Returns:
            Dictionary with processing results
        """
        try:
            logger.info("="*70)
            logger.info("CHECKMATE PDF PROCESSING PIPELINE")
            logger.info("="*70)
            logger.info(f"Processing: {pdf_path}")
            
            # Clear previous debug images
            self.debug_images = []
            
            # Step 1: Convert PDF to image
            logger.info("Step 1: Converting PDF to image...")
            image = self.convert_pdf_to_image(pdf_path)
            if image is None:
                return self._create_error_result("Failed to convert PDF to image")
            
            # Step 2: Detect corner markers
            logger.info("Step 2: Detecting corner markers...")
            corners = self.detect_corner_markers(image)
            if corners is None:
                return self._create_error_result("Failed to detect corner markers")
            
            # Step 3: Apply perspective correction
            logger.info("Step 3: Applying perspective correction...")
            corrected_image = self.apply_perspective_correction(image, corners)
            if corrected_image is None:
                return self._create_error_result("Failed to apply perspective correction")
            
            # Step 4: Extract information based on requests
            student_info = None
            student_answers = None
            
            if extract_student_info:
                logger.info("Step 4a: Extracting student information...")
                student_info = self.extract_student_information(corrected_image, output_dir)
            
            if extract_answers:
                if question_count is None or test_type is None:
                    logger.warning("Question count and test type required for answer extraction")
                    student_answers = {'error': 'Missing question_count or test_type parameters'}
                else:
                    logger.info("Step 4b: Extracting student answers...")
                    student_answers = self.extract_student_answers(
                        corrected_image, question_count, test_type, output_dir
                    )
            
            # Step 5: Save results and debug images
            if output_dir:
                logger.info("Step 5: Saving results and debug images...")
                os.makedirs(output_dir, exist_ok=True)
                
                # Save main debug images
                self.save_debug_images(output_dir)
                
                # Save final corrected image
                output_path = os.path.join(output_dir, f"{Path(pdf_path).stem}_corrected.png")
                cv2.imwrite(output_path, cv2.cvtColor(corrected_image, cv2.COLOR_RGB2BGR))
                logger.info(f"Final corrected image saved: {output_path}")
            
            # Return results
            result = {
                'success': True,
                'pdf_path': pdf_path,
                'corrected_image_shape': corrected_image.shape,
                'corners_detected': corners,
                'student_info': student_info,
                'student_answers': student_answers,
                'output_dir': output_dir
            }
            
            logger.info("="*70)
            logger.info("✓ PROCESSING COMPLETED SUCCESSFULLY")
            logger.info("="*70)
            
            return result
            
        except Exception as e:
            logger.error(f"✗ Error in processing pipeline: {str(e)}")
            return self._create_error_result(str(e))

    def _create_error_result(self, error_message):
        """Create standardized error result"""
        return {
            'success': False,
            'error': error_message,
            'pdf_path': None,
            'corrected_image_shape': None,
            'corners_detected': None,
            'student_info': None,
            'student_answers': None,
            'output_dir': None
        }

    def update_student_region(self, x=None, y=None, width=None, height=None):
        """Update student info region coordinates in the extractor"""
        self.student_info_extractor.update_student_region(x, y, width, height)

    def get_configuration_status(self):
        """Get current configuration status"""
        status = {
            'config_available': CONFIG_AVAILABLE,
            'student_region': self.student_info_extractor.student_info_region if hasattr(self, 'student_info_extractor') else None,
            'field_coordinates': FIELD_COORDINATES if CONFIG_AVAILABLE else None
        }
        return status

    def debug_answer_grid(self, corrected_image, output_dir=None):
        """
        Debug answer grid area to help with coordinate fine-tuning
        
        Args:
            corrected_image: Perspective corrected image
            output_dir: Directory to save debug images
            
        Returns:
            Dictionary with grid analysis
        """
        try:
            logger.info("=== ANSWER GRID DEBUG MODE ===")
            
            # Convert to grayscale if needed
            if len(corrected_image.shape) == 3:
                gray = cv2.cvtColor(corrected_image, cv2.COLOR_RGB2GRAY)
            else:
                gray = corrected_image.copy()
            
            # Get answer grid config
            if CONFIG_AVAILABLE:
                from field_coordinates_config import get_answer_grid_config
                grid_config = get_answer_grid_config()
            else:
                # Fallback config
                grid_config = {
                    'grid': {'x': 30, 'y': 650, 'width': 2420, 'height': 2400},
                    'columns': {'column_width': 605, 'max_questions_per_column': 25},
                    'bubbles': {'spacing': 18, 'start_x_offset': 35}
                }
            
            grid = grid_config['grid']
            x, y, w, h = grid['x'], grid['y'], grid['width'], grid['height']
            
            # Create visualization image
            height, width = gray.shape
            debug_img = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)
            
            # Draw answer grid boundary
            cv2.rectangle(debug_img, (x, y), (x + w, y + h), (0, 255, 0), 3)
            cv2.putText(debug_img, "ANSWER GRID AREA", (x + 10, y + 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            
            # Draw column boundaries
            column_width = grid_config['columns']['column_width']
            for col in range(4):
                col_x = x + (col * column_width)
                if col > 0:
                    cv2.line(debug_img, (col_x, y), (col_x, y + h), (255, 0, 0), 2)
                
                # Label columns
                cv2.putText(debug_img, f"COL {col+1}", (col_x + 10, y + 60), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
            
            # Extract and save answer grid region
            answer_grid = gray[y:y+h, x:x+w] if y + h <= height and x + w <= width else gray[y:height, x:width]
            
            # Create enhanced visualization of answer grid
            if answer_grid.size > 0:
                # Apply contrast enhancement
                clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
                enhanced = clahe.apply(answer_grid)
                
                # Convert to RGB for annotation
                grid_debug = cv2.cvtColor(enhanced, cv2.COLOR_GRAY2RGB)
                
                # Draw sample bubble positions for first few questions
                bubble_spacing = grid_config['bubbles']['spacing']
                start_x_offset = grid_config['bubbles']['start_x_offset']
                choices = ['A', 'B', 'C', 'D']
                
                for col in range(min(2, 4)):  # Show first 2 columns
                    col_x_local = col * column_width
                    
                    for q in range(min(5, 25)):  # Show first 5 questions per column
                        q_y = 50 + (q * 16)  # question_start_y + (q * question_row_height)
                        
                        # Draw question number
                        cv2.putText(grid_debug, f"Q{col*25 + q + 1}", 
                                   (col_x_local + 5, q_y + 5), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 0), 1)
                        
                        # Draw sample bubbles
                        for i, choice in enumerate(choices):
                            bubble_x = col_x_local + start_x_offset + (i * bubble_spacing)
                            cv2.circle(grid_debug, (bubble_x, q_y), 6, (0, 255, 255), 2)
                            cv2.putText(grid_debug, choice, (bubble_x - 3, q_y - 10), 
                                       cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 255, 255), 1)
            
            # Save debug images
            if output_dir:
                debug_dir = os.path.join(output_dir, 'answer_grid_debug')
                os.makedirs(debug_dir, exist_ok=True)
                
                # Save full image with grid overlay
                cv2.imwrite(os.path.join(debug_dir, 'full_image_with_grid.png'), debug_img)
                logger.info(f"Saved full image with grid overlay")
                
                # Save extracted grid region
                if answer_grid.size > 0:
                    cv2.imwrite(os.path.join(debug_dir, 'answer_grid_region.png'), answer_grid)
                    cv2.imwrite(os.path.join(debug_dir, 'answer_grid_with_samples.png'), grid_debug)
                    logger.info(f"Saved answer grid region and sample bubbles")
                
                # Save coordinate analysis
                analysis_file = os.path.join(debug_dir, 'grid_analysis.txt')
                with open(analysis_file, 'w') as f:
                    f.write("ANSWER GRID COORDINATE ANALYSIS\n")
                    f.write("="*50 + "\n\n")
                    f.write(f"Image dimensions: {width} x {height}\n")
                    f.write(f"Grid coordinates: x={x}, y={y}, w={w}, h={h}\n")
                    f.write(f"Grid bottom: {y + h} (image height: {height})\n")
                    f.write(f"Grid right: {x + w} (image width: {width})\n")
                    f.write(f"Column width: {column_width}\n")
                    f.write(f"Bubble spacing: {bubble_spacing}\n")
                    f.write(f"Start X offset: {start_x_offset}\n\n")
                    
                    f.write("COORDINATE SUGGESTIONS:\n")
                    if y + h > height:
                        f.write(f"- Grid height too large! Reduce height or Y position\n")
                    if x + w > width:
                        f.write(f"- Grid width too large! Reduce width or X position\n")
                    if y < 0:
                        f.write(f"- Grid Y position negative! Increase Y\n")
                    if x < 0:
                        f.write(f"- Grid X position negative! Increase X\n")
                    
                    f.write(f"\nRecommended adjustments for your PDF:\n")
                    suggested_y = max(650, 600)  # Below student info
                    suggested_height = min(2400, height - suggested_y - 50)  # Leave margin
                    f.write(f"- Try Y position: {suggested_y}\n")
                    f.write(f"- Try height: {suggested_height}\n")
                    f.write(f"- Current config seems: {'OK' if y + h <= height and x + w <= width else 'NEEDS ADJUSTMENT'}\n")
                
                logger.info(f"Saved coordinate analysis to: {analysis_file}")
            
            return {
                'success': True,
                'grid_config': grid_config,
                'image_size': (width, height),
                'grid_bounds': (x, y, w, h),
                'extracted_region_size': answer_grid.shape if answer_grid.size > 0 else (0, 0),
                'needs_adjustment': y + h > height or x + w > width
            }
            
        except Exception as e:
            logger.error(f"Error in answer grid debug: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def debug_answer_grid_headers(self, corrected_image, output_dir=None):
        """
        Debug answer grid headers to visualize column headers and spacing
        
        Args:
            corrected_image: Perspective corrected image
            output_dir: Directory to save debug images
            
        Returns:
            Dictionary with header analysis
        """
        try:
            logger.info("=== ANSWER GRID HEADER DEBUG MODE ===")
            
            # Convert to grayscale if needed
            if len(corrected_image.shape) == 3:
                gray = cv2.cvtColor(corrected_image, cv2.COLOR_RGB2GRAY)
            else:
                gray = corrected_image.copy()
            
            # Get answer grid config
            if CONFIG_AVAILABLE:
                from field_coordinates_config import get_answer_grid_config
                grid_config = get_answer_grid_config()
            else:
                # Fallback config
                grid_config = {
                    'grid': {'x': 30, 'y': 650, 'width': 2420, 'height': 2400},
                    'columns': {'column_width': 605, 'header_height': 30, 'question_start_y': 50, 'max_questions_per_column': 25},
                    'bubbles': {'spacing': 18, 'start_x_offset': 35}
                }
            
            grid = grid_config['grid']
            columns = grid_config['columns']
            x, y, w, h = grid['x'], grid['y'], grid['width'], grid['height']
            
            # Create visualization image
            height, width = gray.shape
            debug_img = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)
            
            # Draw main answer grid boundary
            cv2.rectangle(debug_img, (x, y), (x + w, y + h), (0, 255, 0), 3)
            cv2.putText(debug_img, "ANSWER GRID AREA", (x + 10, y + 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            
            # Extract answer grid region
            answer_grid = gray[y:y+h, x:x+w] if y + h <= height and x + w <= width else gray[y:height, x:width]
            
            # Create detailed header visualization
            if answer_grid.size > 0:
                # Apply contrast enhancement
                clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
                enhanced = cv2.cvtColor(clahe.apply(answer_grid), cv2.COLOR_GRAY2RGB)
                
                # Draw column divisions and headers
                column_width = columns['column_width']
                header_height = columns['header_height']
                question_start_y = columns['question_start_y']
                
                for col in range(4):
                    col_x_local = col * column_width
                    
                    # Draw column separator
                    if col > 0:
                        cv2.line(enhanced, (col_x_local, 0), (col_x_local, h), (255, 0, 0), 2)
                    
                    # Draw header area box
                    header_rect = (col_x_local + 5, 5, column_width - 10, header_height)
                    cv2.rectangle(enhanced, 
                                (header_rect[0], header_rect[1]), 
                                (header_rect[0] + header_rect[2], header_rect[1] + header_rect[3]), 
                                (255, 255, 0), 2)
                    
                    # Label header area
                    cv2.putText(enhanced, f"HEADER {col+1}", 
                               (col_x_local + 10, 20), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
                    
                    # Draw question start line
                    question_line_y = question_start_y
                    cv2.line(enhanced, 
                           (col_x_local + 5, question_line_y), 
                           (col_x_local + column_width - 5, question_line_y), 
                           (0, 255, 255), 2)
                    
                    cv2.putText(enhanced, f"Q START", 
                               (col_x_local + 10, question_line_y - 5), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)
                    
                    # Show measurements
                    cv2.putText(enhanced, f"H:{header_height}px", 
                               (col_x_local + 10, header_height + 15), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 0, 255), 1)
                    
                    cv2.putText(enhanced, f"W:{column_width}px", 
                               (col_x_local + 10, 40), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 0, 255), 1)
                
                # Draw overall measurements
                cv2.putText(enhanced, f"Grid: {w}x{h} | Header Height: {header_height}px | Question Start Y: {question_start_y}px", 
                           (10, h - 20), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                
                # Add column header examples (Q1-25, Q26-50, etc.)
                for col in range(4):
                    col_x_local = col * column_width
                    start_q = col * 25 + 1
                    end_q = start_q + 24
                    
                    # Draw example header text area
                    text_area_y = header_height // 2
                    cv2.putText(enhanced, f"Q{start_q}-{end_q}", 
                               (col_x_local + column_width//2 - 30, text_area_y), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                    
                    # Draw text area boundary
                    text_width = cv2.getTextSize(f"Q{start_q}-{end_q}", cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0][0]
                    text_x = col_x_local + column_width//2 - text_width//2
                    cv2.rectangle(enhanced, 
                                (text_x - 5, text_area_y - 15), 
                                (text_x + text_width + 5, text_area_y + 5), 
                                (0, 0, 255), 1)
            
            # Save debug images
            if output_dir:
                debug_dir = os.path.join(output_dir, 'answer_header_debug')
                os.makedirs(debug_dir, exist_ok=True)
                
                # Save full image with grid overlay
                cv2.imwrite(os.path.join(debug_dir, 'full_image_with_headers.png'), debug_img)
                logger.info(f"Saved full image with header overlay")
                
                # Save detailed header region
                if answer_grid.size > 0:
                    cv2.imwrite(os.path.join(debug_dir, 'header_detail_analysis.png'), enhanced)
                    logger.info(f"Saved detailed header analysis")
                
                # Save coordinate analysis
                analysis_file = os.path.join(debug_dir, 'header_analysis.txt')
                with open(analysis_file, 'w') as f:
                    f.write("ANSWER GRID HEADER ANALYSIS\n")
                    f.write("="*50 + "\n\n")
                    f.write(f"Grid position: x={x}, y={y}\n")
                    f.write(f"Grid size: {w} x {h}\n")
                    f.write(f"Column width: {columns['column_width']}px\n")
                    f.write(f"Header height: {columns['header_height']}px\n")
                    f.write(f"Question start Y: {columns['question_start_y']}px\n")
                    f.write(f"Space between header and questions: {question_start_y - header_height}px\n\n")
                    
                    f.write("COLUMN LAYOUT:\n")
                    for col in range(4):
                        col_x = x + (col * columns['column_width'])
                        start_q = col * 25 + 1
                        end_q = start_q + 24
                        f.write(f"Column {col+1}: x={col_x}, header='Q{start_q}-{end_q}'\n")
                    
                    f.write(f"\nHEADER STRUCTURE:\n")
                    f.write(f"- Headers are positioned at Y=5 to Y={header_height+5} within grid\n")
                    f.write(f"- Questions start at Y={question_start_y} within grid\n")
                    f.write(f"- Gap between headers and questions: {question_start_y - header_height - 5}px\n")
                    f.write(f"- Each column is {columns['column_width']}px wide\n")
                
                logger.info(f"Saved header analysis to: {analysis_file}")
            
            return {
                'success': True,
                'grid_config': grid_config,
                'header_measurements': {
                    'header_height': columns['header_height'],
                    'question_start_y': columns['question_start_y'],
                    'column_width': columns['column_width'],
                    'header_to_questions_gap': question_start_y - header_height
                }
            }
            
        except Exception as e:
            logger.error(f"Error in header debug: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def debug_bubble_positions(self, corrected_image, question_count, test_type, output_dir=None):
        """
        Debug bubble positions to visualize where the system expects bubbles
        
        Args:
            corrected_image: Perspective corrected image
            question_count: Number of questions to visualize
            test_type: Type of test (multiple_choice_4, multiple_choice_5, true_false)
            output_dir: Directory to save debug images
            
        Returns:
            Dictionary with bubble position analysis
        """
        try:
            logger.info("=== BUBBLE POSITION DEBUG MODE ===")
            
            # Convert to grayscale if needed
            if len(corrected_image.shape) == 3:
                gray = cv2.cvtColor(corrected_image, cv2.COLOR_RGB2GRAY)
            else:
                gray = corrected_image.copy()
            
            # Get answer grid config
            if CONFIG_AVAILABLE:
                from field_coordinates_config import get_answer_grid_config, calculate_column_layout, get_bubble_coordinates
                grid_config = get_answer_grid_config()
                layout = calculate_column_layout(question_count)
                choices = grid_config['bubbles']['choices'][test_type]
            else:
                # Fallback config
                grid_config = {
                    'grid': {'x': 50, 'y': 680, 'width': 2380, 'height': 1680},
                    'columns': {'column_width': 600, 'max_questions_per_column': 25, 'question_start_y': 120},
                    'bubbles': {'radius': 32, 'spacing': 70, 'start_x_offset': 150}
                }
                layout = {'columns': min(4, (question_count + 24) // 25), 'column_ranges': []}
                for col in range(layout['columns']):
                    start_q = col * 25 + 1
                    end_q = min(start_q + 24, question_count)
                    layout['column_ranges'].append({
                        'column': col, 'start_question': start_q, 'end_question': end_q
                    })
                choices = ['A', 'B', 'C', 'D'] if test_type == 'multiple_choice_4' else ['A', 'B', 'C', 'D', 'E'] if test_type == 'multiple_choice_5' else ['T', 'F']
            
            height, width = gray.shape
            
            # Create visualization image
            debug_img = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)
            
            # Draw answer grid boundary
            grid = grid_config['grid']
            x, y, w, h = grid['x'], grid['y'], grid['width'], grid['height']
            
            # Ensure coordinates are within bounds
            x = max(0, min(x, width - 1))
            y = max(0, min(y, height - 1))
            w = min(w, width - x)
            h = min(h, height - y)
            
            cv2.rectangle(debug_img, (x, y), (x + w, y + h), (0, 255, 0), 3)
            cv2.putText(debug_img, "ANSWER GRID AREA", (x + 10, y + 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            
            # Draw column boundaries and bubbles
            column_width = grid_config['columns']['column_width']
            bubble_radius = grid_config['bubbles']['radius']
            bubble_spacing = grid_config['bubbles']['spacing']
            start_x_offset = grid_config['bubbles']['start_x_offset']
            question_start_y = grid_config['columns']['question_start_y']
            question_row_height = grid_config['columns'].get('question_row_height', 20)
            
            bubble_positions = []
            
            for col_info in layout['column_ranges']:
                column = col_info['column']
                col_x = x + (column * column_width)
                
                # Draw column separator
                if column > 0:
                    cv2.line(debug_img, (col_x, y), (col_x, y + h), (255, 0, 0), 2)
                
                # Label column
                cv2.putText(debug_img, f"COL {column+1}", (col_x + 10, y + 60), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
                
                # Show first few questions in detail
                questions_to_show = min(5, col_info['end_question'] - col_info['start_question'] + 1)
                
                for i in range(questions_to_show):
                    q_num = col_info['start_question'] + i
                    
                    # Calculate question position
                    question_in_col = ((q_num - 1) % 25)
                    question_y = y + question_start_y + (question_in_col * question_row_height)
                    
                    # Draw question number
                    cv2.putText(debug_img, f"Q{q_num}", (col_x + 5, question_y + 5), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 0), 1)
                    
                    # Draw bubbles for this question
                    for choice_idx, choice in enumerate(choices):
                        if CONFIG_AVAILABLE:
                            # Use configuration-based coordinates
                            coords = get_bubble_coordinates(column, q_num, choice_idx, test_type)
                            bubble_x = coords['x']
                            bubble_y = coords['y']
                            radius = coords['radius']
                        else:
                            # Fallback calculation
                            bubble_x = col_x + start_x_offset + (choice_idx * bubble_spacing)
                            bubble_y = question_y
                            radius = bubble_radius
                        
                        # Draw bubble circle
                        cv2.circle(debug_img, (int(bubble_x), int(bubble_y)), radius, (0, 255, 255), 2)
                        
                        # Label bubble with choice
                        cv2.putText(debug_img, choice, (int(bubble_x - 5), int(bubble_y - radius - 5)), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 255, 255), 1)
                        
                        # Store position info
                        bubble_positions.append({
                            'question': q_num,
                            'choice': choice,
                            'column': column,
                            'x': int(bubble_x),
                            'y': int(bubble_y),
                            'radius': radius
                        })
                
                # Show ellipsis for remaining questions
                if questions_to_show < (col_info['end_question'] - col_info['start_question'] + 1):
                    remaining = (col_info['end_question'] - col_info['start_question'] + 1) - questions_to_show
                    ellipsis_y = y + question_start_y + (questions_to_show * question_row_height) + 10
                    cv2.putText(debug_img, f"... +{remaining} more", (col_x + 5, ellipsis_y), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.3, (128, 128, 128), 1)
            
            # Add configuration info overlay
            config_text = [
                f"Grid: x={x}, y={y}, w={w}, h={h}",
                f"Columns: {layout['columns']}, Width: {column_width}",
                f"Bubble: radius={bubble_radius}, spacing={bubble_spacing}",
                f"Start offset: {start_x_offset}, Question Y: {question_start_y}",
                f"Row height: {question_row_height}",
                f"Test type: {test_type}, Choices: {', '.join(choices)}"
            ]
            
            # Draw semi-transparent background for text
            overlay = debug_img.copy()
            cv2.rectangle(overlay, (10, height - 150), (800, height - 10), (0, 0, 0), -1)
            cv2.addWeighted(overlay, 0.7, debug_img, 0.3, 0, debug_img)
            
            for i, text in enumerate(config_text):
                cv2.putText(debug_img, text, (15, height - 140 + (i * 20)), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            # Save debug images
            if output_dir:
                debug_dir = os.path.join(output_dir, 'bubble_position_debug')
                os.makedirs(debug_dir, exist_ok=True)
                
                # Save full bubble visualization
                cv2.imwrite(os.path.join(debug_dir, 'bubble_positions_full.png'), debug_img)
                logger.info(f"Saved bubble position visualization")
                
                # Extract and save just the answer grid region for detailed view
                if y + h <= height and x + w <= width:
                    grid_region = debug_img[y:y+h, x:x+w]
                    cv2.imwrite(os.path.join(debug_dir, 'bubble_positions_grid_only.png'), grid_region)
                    logger.info(f"Saved detailed grid visualization")
                
                # Save bubble position data
                import json
                with open(os.path.join(debug_dir, 'bubble_positions.json'), 'w') as f:
                    json.dump({
                        'grid_config': grid_config,
                        'layout': layout,
                        'bubble_positions': bubble_positions,
                        'image_size': (width, height),
                        'test_info': {
                            'question_count': question_count,
                            'test_type': test_type,
                            'choices': choices
                        }
                    }, f, indent=2)
                
                # Create detailed analysis report
                with open(os.path.join(debug_dir, 'bubble_analysis.txt'), 'w') as f:
                    f.write("BUBBLE POSITION ANALYSIS\n")
                    f.write("="*50 + "\n\n")
                    f.write(f"Image Size: {width} x {height}\n")
                    f.write(f"Question Count: {question_count}\n")
                    f.write(f"Test Type: {test_type}\n")
                    f.write(f"Choices: {', '.join(choices)}\n\n")
                    
                    f.write("GRID CONFIGURATION:\n")
                    f.write(f"  Position: x={x}, y={y}\n")
                    f.write(f"  Size: {w} x {h}\n")
                    f.write(f"  Columns: {layout['columns']}\n")
                    f.write(f"  Column Width: {column_width}\n\n")
                    
                    f.write("BUBBLE CONFIGURATION:\n")
                    f.write(f"  Radius: {bubble_radius} pixels\n")
                    f.write(f"  Spacing: {bubble_spacing} pixels\n")
                    f.write(f"  Start X Offset: {start_x_offset} pixels\n")
                    f.write(f"  Question Start Y: {question_start_y} pixels\n")
                    f.write(f"  Question Row Height: {question_row_height} pixels\n\n")
                    
                    f.write("COLUMN LAYOUT:\n")
                    for col_info in layout['column_ranges']:
                        f.write(f"  Column {col_info['column']}: Q{col_info['start_question']}-{col_info['end_question']}\n")
                    f.write("\n")
                    
                    f.write("SAMPLE BUBBLE POSITIONS (first 5 questions):\n")
                    for pos in bubble_positions[:20]:  # Show first 20 bubbles
                        f.write(f"  Q{pos['question']}-{pos['choice']}: ({pos['x']}, {pos['y']}) r={pos['radius']}\n")
                    
                    if len(bubble_positions) > 20:
                        f.write(f"  ... and {len(bubble_positions) - 20} more bubbles\n")
                    
                    f.write("\nTROUBLESHOOTING:\n")
                    f.write("1. Check if bubble circles align with actual bubbles in your PDF\n")
                    f.write("2. If misaligned, adjust coordinates in field_coordinates_config.py:\n")
                    f.write("   - ANSWER_GRID: overall position and size\n")
                    f.write("   - COLUMN_CONFIG: column layout and question spacing\n")
                    f.write("   - BUBBLE_CONFIG: bubble size and spacing\n")
                    f.write("3. Use corner adjustment if perspective correction is off\n")
                
                logger.info(f"Bubble position analysis saved to: {debug_dir}")
            
            return {
                'success': True,
                'grid_config': grid_config,
                'layout': layout,
                'bubble_positions': bubble_positions,
                'image_size': (width, height),
                'visualized_questions': min(question_count, sum(min(5, col['end_question'] - col['start_question'] + 1) for col in layout['column_ranges']))
            }
            
        except Exception as e:
            logger.error(f"Error in bubble position debug: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

def main():
    """Main function for command-line usage"""
    parser = argparse.ArgumentParser(description='CheckMate PDF Processor - Extract student info and answers from PDF answer sheets')
    
    # Required arguments
    parser.add_argument('pdf_path', help='Path to PDF file to process')
    
    # Optional arguments
    parser.add_argument('--output-dir', '-o', default='checkmate_output', 
                       help='Directory to save debug images and results (default: checkmate_output)')
    parser.add_argument('--debug', action='store_true',
                       help='Enable debug mode with detailed logging and debug images')
    
    # Processing options
    parser.add_argument('--student-info', action='store_true', default=True,
                       help='Extract student information (default: True)')
    parser.add_argument('--no-student-info', action='store_true',
                       help='Skip student information extraction')
    parser.add_argument('--answers', action='store_true',
                       help='Extract student answers (requires --question-count and --test-type)')
    
    # Answer extraction parameters
    parser.add_argument('--question-count', type=int,
                       help='Number of questions (required for answer extraction)')
    parser.add_argument('--test-type', choices=['multiple_choice_4', 'multiple_choice_5', 'true_false'],
                       help='Test type (required for answer extraction)')
    
    # Debug modes
    parser.add_argument('--debug-answer-grid', action='store_true',
                       help='Debug answer grid coordinates (helps with fine-tuning)')
    parser.add_argument('--debug-headers', action='store_true',
                       help='Debug answer grid headers and spacing')
    parser.add_argument('--debug-bubbles', action='store_true',
                       help='Debug bubble positions (shows where system expects bubbles)')
    parser.add_argument('--debug-corners', action='store_true',
                       help='Debug corner detection and show detected corners')
    
    # Corner adjustment options
    parser.add_argument('--manual-corners', nargs=8, type=int, metavar=('TL_X', 'TL_Y', 'TR_X', 'TR_Y', 'BL_X', 'BL_Y', 'BR_X', 'BR_Y'),
                       help='Manual corner coordinates: top-left-x top-left-y top-right-x top-right-y bottom-left-x bottom-left-y bottom-right-x bottom-right-y')
    parser.add_argument('--fine-tune-corners', action='store_true',
                       help='Test different corner adjustments for better perspective correction')
    parser.add_argument('--corner-adjustment', nargs=8, type=int, metavar=('TL_DX', 'TL_DY', 'TR_DX', 'TR_DY', 'BL_DX', 'BL_DY', 'BR_DX', 'BR_DY'),
                       help='Corner adjustments: tl_dx tl_dy tr_dx tr_dy bl_dx bl_dy br_dx br_dy')
    
    # Student region override
    parser.add_argument('--student-region', nargs=4, type=int, metavar=('X', 'Y', 'W', 'H'),
                       help='Override student region coordinates: x y width height')
    
    # PDF conversion settings
    parser.add_argument('--dpi', type=int, default=300, 
                       help='DPI for PDF conversion (default: 300)')
    
    args = parser.parse_args()
    
    # Validate arguments
    if not os.path.exists(args.pdf_path):
        logger.error(f"✗ PDF file not found: {args.pdf_path}")
        return 1
    
    if args.answers and (not args.question_count or not args.test_type):
        logger.error("✗ Answer extraction requires both --question-count and --test-type")
        return 1
    
    # Create processor
    processor = CheckMatePDFProcessor(debug_mode=args.debug)
    
    # Show configuration status
    config_status = processor.get_configuration_status()
    logger.info("Configuration Status:")
    logger.info(f"  Config File: {'✓ Available' if config_status['config_available'] else '✗ Not found'}")
    if config_status['student_region']:
        region = config_status['student_region']
        logger.info(f"  Student Region: x={region['x']}, y={region['y']}, w={region['width']}, h={region['height']}")
    
    # Update student region if provided
    if args.student_region:
        x, y, w, h = args.student_region
        processor.update_student_region(x, y, w, h)
        logger.info(f"Student region updated: x={x}, y={y}, w={w}, h={h}")
    
    # Special debug mode for answer grid
    if args.debug_answer_grid:
        # Get corrected image first
        image = processor.convert_pdf_to_image(args.pdf_path)
        if image is None:
            logger.error("Failed to convert PDF to image")
            return 1
        
        corners = processor.detect_corner_markers(image)
        if corners is None:
            logger.error("Failed to detect corner markers")
            return 1
        
        corrected_image = processor.apply_perspective_correction(image, corners)
        if corrected_image is None:
            logger.error("Failed to apply perspective correction")
            return 1
        
        # Debug the answer grid
        debug_result = processor.debug_answer_grid(corrected_image, args.output_dir)
        
        if debug_result['success']:
            print("\n" + "="*70)
            print("ANSWER GRID DEBUG RESULTS")
            print("="*70)
            print(f"Image Size: {debug_result['image_size']}")
            print(f"Grid Bounds: x={debug_result['grid_bounds'][0]}, y={debug_result['grid_bounds'][1]}, w={debug_result['grid_bounds'][2]}, h={debug_result['grid_bounds'][3]}")
            print(f"Extracted Region: {debug_result['extracted_region_size']}")
            print(f"Needs Adjustment: {'Yes' if debug_result['needs_adjustment'] else 'No'}")
            print(f"\nDebug images saved in: {args.output_dir}/answer_grid_debug/")
            print("Check the files:")
            print("- full_image_with_grid.png (shows where the grid area is)")
            print("- answer_grid_region.png (extracted grid area)")
            print("- answer_grid_with_samples.png (grid with sample bubble positions)")
            print("- grid_analysis.txt (coordinate analysis and suggestions)")
            print("="*70)
        else:
            logger.error("Answer grid debug failed!")
            logger.error(f"Error: {debug_result['error']}")
        
        return 0
    
    # Special debug mode for headers
    if args.debug_headers:
        # Get corrected image first
        image = processor.convert_pdf_to_image(args.pdf_path)
        if image is None:
            logger.error("Failed to convert PDF to image")
            return 1
        
        corners = processor.detect_corner_markers(image)
        if corners is None:
            logger.error("Failed to detect corner markers")
            return 1
        
        corrected_image = processor.apply_perspective_correction(image, corners)
        if corrected_image is None:
            logger.error("Failed to apply perspective correction")
            return 1
        
        # Debug the headers
        debug_result = processor.debug_answer_grid_headers(corrected_image, args.output_dir)
        
        if debug_result['success']:
            measurements = debug_result['header_measurements']
            print("\n" + "="*70)
            print("ANSWER GRID HEADER DEBUG RESULTS")
            print("="*70)
            print(f"Header Height: {measurements['header_height']}px")
            print(f"Question Start Y: {measurements['question_start_y']}px")
            print(f"Column Width: {measurements['column_width']}px")
            print(f"Header to Questions Gap: {measurements['header_to_questions_gap']}px")
            print(f"\nHeader Structure:")
            print(f"  - Headers span from Y=5 to Y={measurements['header_height']+5}")
            print(f"  - Questions begin at Y={measurements['question_start_y']}")
            print(f"  - Each column is {measurements['column_width']}px wide")
            print(f"  - 4 columns total: Q1-25, Q26-50, Q51-75, Q76-100")
            print(f"\nDebug images saved in: {args.output_dir}/answer_header_debug/")
            print("Check the files:")
            print("- full_image_with_headers.png (shows header locations on full PDF)")
            print("- header_detail_analysis.png (detailed header structure)")
            print("- header_analysis.txt (measurements and layout details)")
            print("="*70)
        else:
            logger.error("Header debug failed!")
            logger.error(f"Error: {debug_result['error']}")
        
        return 0
    
    # Special debug mode for corners
    if args.debug_corners:
        # Get original image and show corner detection
        image = processor.convert_pdf_to_image(args.pdf_path)
        if image is None:
            logger.error("Failed to convert PDF to image")
            return 1
        
        corners = processor.detect_corner_markers(image)
        if corners is None:
            logger.error("Failed to detect corner markers")
            return 1
        
        # Apply perspective correction and save debug
        if args.manual_corners:
            # Use manual corners
            manual_corners = [
                (args.manual_corners[0], args.manual_corners[1]),  # TL
                (args.manual_corners[2], args.manual_corners[3]),  # TR
                (args.manual_corners[4], args.manual_corners[5]),  # BL
                (args.manual_corners[6], args.manual_corners[7])   # BR
            ]
            corrected_image = processor.manual_perspective_correction(image, manual_corners)
        else:
            corrected_image = processor.apply_perspective_correction(image, corners)
        
        if corrected_image is None:
            logger.error("Failed to apply perspective correction")
            return 1
        
        # Save debug images
        processor.save_debug_images(args.output_dir, "corner_debug")
        
        print("\n" + "="*70)
        print("CORNER DETECTION DEBUG RESULTS")
        print("="*70)
        print(f"Detected corners: {corners}")
        if args.manual_corners:
            print(f"Used manual corners: {manual_corners}")
        print(f"Corrected image shape: {corrected_image.shape}")
        print(f"Target dimensions: {processor.target_width} x {processor.target_height}")
        print(f"\nDebug images saved in: {args.output_dir}/main_debug/")
        print("Check the files:")
        print("- corner_debug_01_pdf_original.png (original PDF)")
        print("- corner_debug_02_grayscale.png (grayscale conversion)")
        print("- corner_debug_03a_corner_detection.png (detected corners marked)")
        print("- corner_debug_03_perspective_corrected.png (corrected result)")
        print("\nTo use manual corners, use:")
        print(f"--manual-corners TL_X TL_Y TR_X TR_Y BL_X BL_Y BR_X BR_Y")
        print("="*70)
        
        return 0
    
    # Special debug mode for bubble positions
    if args.debug_bubbles:
        if not args.question_count or not args.test_type:
            logger.error("Bubble position debug requires --question-count and --test-type")
            return 1
        
        # Get corrected image first
        image = processor.convert_pdf_to_image(args.pdf_path)
        if image is None:
            logger.error("Failed to convert PDF to image")
            return 1
        
        corners = processor.detect_corner_markers(image)
        if corners is None:
            logger.error("Failed to detect corner markers")
            return 1
        
        corrected_image = processor.apply_perspective_correction(image, corners)
        if corrected_image is None:
            logger.error("Failed to apply perspective correction")
            return 1
        
        # Debug bubble positions
        debug_result = processor.debug_bubble_positions(corrected_image, args.question_count, args.test_type, args.output_dir)
        
        if debug_result['success']:
            print("\n" + "="*70)
            print("BUBBLE POSITION DEBUG RESULTS")
            print("="*70)
            print(f"Image Size: {debug_result['image_size']}")
            print(f"Grid Layout: {debug_result['layout']['columns']} columns")
            print(f"Questions Visualized: {debug_result['visualized_questions']} (showing first 5 per column)")
            print(f"Total Bubble Positions: {len(debug_result['bubble_positions'])}")
            print(f"Test Type: {args.test_type}")
            print(f"\nDebug images saved in: {args.output_dir}/bubble_position_debug/")
            print("Check the files:")
            print("- bubble_positions_full.png (full image with bubble overlays)")
            print("- bubble_positions_grid_only.png (detailed grid view)")
            print("- bubble_positions.json (raw position data)")
            print("- bubble_analysis.txt (detailed analysis and troubleshooting)")
            print("\nLook for yellow circles - they should align with actual bubbles!")
            print("If misaligned, adjust coordinates in field_coordinates_config.py")
            print("="*70)
        else:
            logger.error("Bubble position debug failed!")
            logger.error(f"Error: {debug_result['error']}")
        
        return 0
    
    # Determine what to extract
    extract_student_info = args.student_info and not args.no_student_info
    extract_answers = args.answers
    
    # Process the PDF
    result = processor.process_pdf_answer_sheet(
        args.pdf_path,
        args.output_dir,
        extract_student_info=extract_student_info,
        extract_answers=extract_answers,
        question_count=args.question_count,
        test_type=args.test_type
    )
    
    # Display results
    if result['success']:
        print("\n" + "="*70)
        print("CHECKMATE PROCESSING RESULTS")
        print("="*70)
        
        if result['student_info']:
            student_info = result['student_info']
            print("STUDENT INFORMATION:")
            print(f"  Name: '{student_info.get('name', 'Not detected')}'")
            print(f"  ID: '{student_info.get('id', 'Not detected')}'")
            print(f"  Course: '{student_info.get('course', 'Not detected')}'")
            print(f"  Section: '{student_info.get('section', 'Not detected')}'")
            if 'error' in student_info:
                print(f"  ⚠ Warning: {student_info['error']}")
            print()
        
        if result['student_answers']:
            answers = result['student_answers']
            print("STUDENT ANSWERS:")
            if 'error' in answers:
                print(f"  ⚠ Error: {answers['error']}")
            else:
                print(f"  Total Detected: {answers.get('total_detected', 0)}")
                if answers.get('answers'):
                    print(f"  Sample Answers: {dict(list(answers['answers'].items())[:5])}")  # Show first 5
            print()
        
        print(f"Corrected Image Shape: {result['corrected_image_shape']}")
        if args.debug and result['output_dir']:
            print(f"Debug images saved in: {result['output_dir']}")
        
        print("="*70)
        return 0
        
    else:
        print("\n" + "="*70)
        print("✗ PROCESSING FAILED")
        print("="*70)
        print(f"Error: {result['error']}")
        print("="*70)
        return 1


if __name__ == "__main__":
    exit(main())
