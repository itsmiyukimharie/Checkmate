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
        Detect corner alignment markers for perspective correction
        
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
            
            # Simple corner detection approach
            corner_size = 200
            corners_found = []
            
            # Define corner regions to search
            corner_regions = [
                (0, 0, "TL"),  # Top-left
                (width - corner_size, 0, "TR"),  # Top-right
                (0, height - corner_size, "BL"),  # Bottom-left
                (width - corner_size, height - corner_size, "BR")  # Bottom-right
            ]
            
            for x, y, label in corner_regions:
                # Extract corner region
                region = gray[y:y+corner_size, x:x+corner_size]
                
                # Find darkest point in region (marker should be dark)
                min_val = np.min(region)
                min_loc = np.unravel_index(np.argmin(region), region.shape)
                
                # Convert back to full image coordinates
                corner_x = x + min_loc[1]
                corner_y = y + min_loc[0]
                
                corners_found.append((corner_x, corner_y))
                logger.info(f"Corner {label}: ({corner_x}, {corner_y}) darkness={min_val}")
            
            if len(corners_found) == 4:
                logger.info("✓ Successfully detected 4 corner markers")
                return corners_found
            else:
                logger.warning("⚠ Could not detect all corners, using image edges as fallback")
                return [(0, 0), (width, 0), (0, height), (width, height)]
            
        except Exception as e:
            logger.error(f"✗ Error detecting corner markers: {str(e)}")
            return None

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
            
            # Define source points (detected corners)
            src_points = np.array(corners, dtype=np.float32)
            
            # Define destination points (standard A4 rectangle)
            dst_points = np.array([
                [0, 0],                                    # Top-left
                [self.target_width-1, 0],                  # Top-right
                [0, self.target_height-1],                 # Bottom-left
                [self.target_width-1, self.target_height-1] # Bottom-right
            ], dtype=np.float32)
            
            # Calculate perspective transformation matrix
            matrix = cv2.getPerspectiveTransform(src_points, dst_points)
            
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
            
            return corrected
            
        except Exception as e:
            logger.error(f"✗ Error in perspective correction: {str(e)}")
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
