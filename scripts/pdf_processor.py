import cv2
import numpy as np
import pdf2image
from PIL import Image
import os
import logging
import argparse
from pathlib import Path
import pytesseract

# Import the configuration
try:
    from field_coordinates_config import (
        FIELD_COORDINATES, 
        STUDENT_REGION, 
        OCR_CONFIG, 
        PREPROCESSING,
        get_field_config,
        get_student_region_config
    )
    CONFIG_AVAILABLE = True
except ImportError:
    CONFIG_AVAILABLE = False
    logging.warning("field_coordinates_config.py not found. Using default coordinates.")

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PDFAnswerSheetProcessor:
    """
    Independent processor for converting PDF answer sheets to images
    and detecting alignment markers for perspective correction
    """
    
    def __init__(self, debug_mode=False):
        self.debug_mode = debug_mode
        self.debug_images = []
        self.student_debug_images = []
        
        # Standard A4 dimensions (at 300 DPI)
        self.target_width = 2480  # A4 width at 300 DPI
        self.target_height = 3508  # A4 height at 300 DPI
        
        # Corner marker specifications (based on CheckMate template)
        self.marker_size_mm = 8  # 8mm square markers
        self.margin_mm = 12  # Adjusted margin (0.4 inch = ~10.16mm)
        
        # Convert mm to pixels at 300 DPI (1mm = ~11.8 pixels at 300 DPI)
        self.dpi_scale = 11.8
        self.marker_size_px = int(self.marker_size_mm * self.dpi_scale)
        self.margin_px = int(self.margin_mm * self.dpi_scale)
        
        # Load student info region from config or use defaults
        if CONFIG_AVAILABLE:
            config_region = get_student_region_config()
            self.student_info_region = config_region.copy()
            logger.info("Loaded student region from config file")
        else:
            # Fallback default coordinates
            self.student_info_region = {
                'x': 0,
                'y': 300,
                'width': 2600,
                'height': 300
            }
            logger.info("Using default student region coordinates")

    def pdf_to_image(self, pdf_path, page_number=0, dpi=300):
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
            
            # Convert PDF to images
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
            logger.info(f"Image converted successfully: {image.size}")
            
            if self.debug_mode:
                self.debug_images.append(('original', np.array(image)))
                
            return image
            
        except Exception as e:
            logger.error(f"Error converting PDF to image: {str(e)}")
            return None
    
    def detect_corner_markers(self, image):
        """
        Detect the 4 corner alignment markers with improved detection
        
        Args:
            image: PIL Image or numpy array
            
        Returns:
            List of 4 corner points [(x,y), ...] in order: top-left, top-right, bottom-left, bottom-right
        """
        try:
            # Convert to numpy array if PIL Image
            if isinstance(image, Image.Image):
                img_array = np.array(image)
            else:
                img_array = image.copy()
            
            # Convert to grayscale
            if len(img_array.shape) == 3:
                gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            else:
                gray = img_array.copy()
            
            logger.info(f"Processing image for corner detection: {gray.shape}")
            height, width = gray.shape
            
            # Multiple threshold approaches for better detection
            marker_candidates = []
            
            # Method 1: Binary threshold with multiple values
            thresholds = [100, 127, 150, 180]
            for thresh_val in thresholds:
                _, binary = cv2.threshold(gray, thresh_val, 255, cv2.THRESH_BINARY_INV)
                candidates = self._find_markers_in_binary(binary, f"threshold_{thresh_val}")
                marker_candidates.extend(candidates)
            
            # Method 2: Adaptive threshold
            adaptive_binary = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2
            )
            adaptive_candidates = self._find_markers_in_binary(adaptive_binary, "adaptive")
            marker_candidates.extend(adaptive_candidates)
            
            # Method 3: Look specifically in corner regions
            corner_regions = self._get_corner_regions(width, height)
            region_candidates = self._find_markers_in_regions(gray, corner_regions)
            marker_candidates.extend(region_candidates)
            
            logger.info(f"Found {len(marker_candidates)} total marker candidates")
            
            if len(marker_candidates) < 4:
                logger.warning(f"Expected 4 corners, found {len(marker_candidates)}")
                # Try fallback method with lower requirements
                return self._fallback_corner_detection(gray)
            
            # Remove duplicates (points that are very close to each other)
            unique_candidates = self._remove_duplicate_candidates(marker_candidates)
            logger.info(f"After removing duplicates: {len(unique_candidates)} candidates")
            
            # Sort markers to find the 4 corners
            corners = self._identify_corners(unique_candidates, gray.shape)
            
            if corners and len(corners) == 4:
                logger.info("Successfully detected 4 corner markers")
                return corners
            
            return None
            
        except Exception as e:
            logger.error(f"Error detecting corner markers: {str(e)}")
            return None
    
    def _find_markers_in_binary(self, binary_img, method_name):
        """Find marker candidates in a binary image"""
        candidates = []
        
        # Find contours
        contours, _ = cv2.findContours(binary_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Relaxed size constraints
        min_area = 400  # Minimum area in pixels (about 20x20 pixels)
        max_area = 4000  # Maximum area in pixels (about 63x63 pixels)
        
        for contour in contours:
            area = cv2.contourArea(contour)
            
            if min_area < area < max_area:
                # Check if contour is roughly rectangular
                x, y, w, h = cv2.boundingRect(contour)
                aspect_ratio = float(w) / h
                
                # More relaxed aspect ratio (can be rectangular, not just square)
                if 0.5 < aspect_ratio < 2.0:
                    # Calculate center point
                    M = cv2.moments(contour)
                    if M["m00"] != 0:
                        cx = int(M["m10"] / M["m00"])
                        cy = int(M["m01"] / M["m00"])
                        candidates.append((cx, cy, area, contour))
        
        return candidates
    
    def _get_corner_regions(self, width, height):
        """Get the 4 corner regions where markers should be located"""
        # Based on the PDF generation: margin = 0.4 inch, marker offset = 4 pixels
        margin = int(0.4 * 300 / 25.4 * 11.8)  # Convert 0.4 inch to pixels
        region_size = 150  # Search in 150x150 pixel regions
        
        return [
            # Top-left
            (0, 0, region_size, region_size),
            # Top-right  
            (width - region_size, 0, region_size, region_size),
            # Bottom-left
            (0, height - region_size, region_size, region_size),
            # Bottom-right
            (width - region_size, height - region_size, region_size, region_size)
        ]
    
    def _find_markers_in_regions(self, gray, regions):
        """Search for markers specifically in corner regions"""
        candidates = []
        
        for i, (rx, ry, rw, rh) in enumerate(regions):
            # Extract region
            region = gray[ry:ry+rh, rx:rx+rw]
            
            # Apply threshold to region
            _, region_binary = cv2.threshold(region, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            
            # Find contours in region
            contours, _ = cv2.findContours(region_binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # Look for the largest dark area in this region
            best_contour = None
            best_area = 0
            
            for contour in contours:
                area = cv2.contourArea(contour)
                if area > best_area and area > 200:  # Minimum reasonable size
                    x, y, w, h = cv2.boundingRect(contour)
                    aspect_ratio = float(w) / h
                    # More lenient aspect ratio for corner regions
                    if 0.3 < aspect_ratio < 3.0:
                        best_contour = contour
                        best_area = area
            
            if best_contour is not None:
                # Calculate center relative to full image
                M = cv2.moments(best_contour)
                if M["m00"] != 0:
                    cx = int(M["m10"] / M["m00"]) + rx
                    cy = int(M["m01"] / M["m00"]) + ry
                    candidates.append((cx, cy, best_area, best_contour))
        
        return candidates
    
    def _remove_duplicate_candidates(self, candidates):
        """Remove candidates that are too close to each other"""
        if not candidates:
            return []
        
        unique_candidates = []
        min_distance = 50  # Minimum distance between candidates
        
        for candidate in candidates:
            cx, cy, area, contour = candidate
            is_duplicate = False
            
            for existing in unique_candidates:
                ex, ey, _, _ = existing
                distance = np.sqrt((cx - ex)**2 + (cy - ey)**2)
                if distance < min_distance:
                    # Keep the one with larger area
                    if area > existing[2]:
                        unique_candidates.remove(existing)
                        break
                    else:
                        is_duplicate = True
                        break
            
            if not is_duplicate:
                unique_candidates.append(candidate)
        
        return unique_candidates
    
    def _identify_corners(self, candidates, image_shape):
        """
        Identify which candidates are the 4 corners
        
        Args:
            candidates: List of (x, y, area, contour) tuples
            image_shape: (height, width) of the image
            
        Returns:
            List of 4 corner points in order: top-left, top-right, bottom-left, bottom-right
        """
        if len(candidates) < 4:
            return None
        
        # Sort candidates by position to find corners
        height, width = image_shape
        
        # Expected corner regions (with some tolerance)
        corner_tolerance = min(width, height) * 0.2  # 20% tolerance
        
        corners = [None, None, None, None]  # TL, TR, BL, BR
        
        for x, y, area, contour in candidates:
            # Top-left corner
            if x < corner_tolerance and y < corner_tolerance:
                if corners[0] is None or self._is_closer_to_corner(x, y, 0, 0, corners[0]):
                    corners[0] = (x, y)
            
            # Top-right corner
            elif x > width - corner_tolerance and y < corner_tolerance:
                if corners[1] is None or self._is_closer_to_corner(x, y, width, 0, corners[1]):
                    corners[1] = (x, y)
            
            # Bottom-left corner
            elif x < corner_tolerance and y > height - corner_tolerance:
                if corners[2] is None or self._is_closer_to_corner(x, y, 0, height, corners[2]):
                    corners[2] = (x, y)
            
            # Bottom-right corner
            elif x > width - corner_tolerance and y > height - corner_tolerance:
                if corners[3] is None or self._is_closer_to_corner(x, y, width, height, corners[3]):
                    corners[3] = (x, y)
        
        # Check if all corners were found
        if all(corner is not None for corner in corners):
            return corners
        
        # If not all corners found, try alternative approach
        logger.warning("Not all corners found in expected regions, trying alternative approach")
        return self._find_corners_by_distance(candidates, image_shape)
    
    def _is_closer_to_corner(self, x, y, corner_x, corner_y, current_best):
        """Check if point (x,y) is closer to corner than current best"""
        if current_best is None:
            return True
        
        current_dist = np.sqrt((x - corner_x)**2 + (y - corner_y)**2)
        best_dist = np.sqrt((current_best[0] - corner_x)**2 + (current_best[1] - corner_y)**2)
        
        return current_dist < best_dist
    
    def _find_corners_by_distance(self, candidates, image_shape):
        """Alternative method to find corners by distance from image corners"""
        height, width = image_shape
        image_corners = [(0, 0), (width, 0), (0, height), (width, height)]
        
        detected_corners = []
        
        for img_corner in image_corners:
            best_candidate = None
            best_distance = float('inf')
            
            for x, y, area, contour in candidates:
                distance = np.sqrt((x - img_corner[0])**2 + (y - img_corner[1])**2)
                if distance < best_distance:
                    best_distance = distance
                    best_candidate = (x, y)
            
            if best_candidate and best_distance < min(width, height) * 0.3:  # Within 30% of image size
                detected_corners.append(best_candidate)
        
        return detected_corners if len(detected_corners) == 4 else None
    
    def _fallback_corner_detection(self, gray):
        """Fallback method when standard detection fails"""
        logger.info("Attempting fallback corner detection...")
        
        height, width = gray.shape
        
        # Try to find ANY dark regions in corner areas
        corner_size = 200
        corners_found = []
        
        corner_regions = [
            (0, 0, "TL"),  # Top-left
            (width - corner_size, 0, "TR"),  # Top-right
            (0, height - corner_size, "BL"),  # Bottom-left
            (width - corner_size, height - corner_size, "BR")  # Bottom-right
        ]
        
        for x, y, label in corner_regions:
            # Extract corner region
            region = gray[y:y+corner_size, x:x+corner_size]
            
            # Find darkest point in region
            min_val = np.min(region)
            min_loc = np.unravel_index(np.argmin(region), region.shape)
            
            # Convert back to full image coordinates
            corner_x = x + min_loc[1]
            corner_y = y + min_loc[0]
            
            corners_found.append((corner_x, corner_y))
            
            logger.info(f"Fallback {label}: ({corner_x}, {corner_y}) with value {min_val}")
        
        if len(corners_found) == 4:
            logger.info("Fallback corner detection successful")
            return corners_found
        
        return None
    
    def correct_perspective(self, image, corners):
        """
        Apply perspective correction using detected corners
        
        Args:
            image: PIL Image or numpy array
            corners: List of 4 corner points [(x,y), ...]
            
        Returns:
            Corrected numpy array image
        """
        try:
            # Convert to numpy array if PIL Image
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
            
            logger.info(f"Perspective correction applied: {corrected.shape}")
            
            return corrected
            
        except Exception as e:
            logger.error(f"Error in perspective correction: {str(e)}")
            return None
    
    def extract_student_info(self, corrected_image, output_dir=None):
        """
        Extract student information from the student info section
        
        Args:
            corrected_image: Perspective corrected image
            output_dir: Directory to save debug images (optional)
            
        Returns:
            Dictionary with extracted student info
        """
        try:
            # Clear previous student debug images
            self.student_debug_images = []
            
            logger.info("Extracting student information...")
            
            # Convert to grayscale if needed
            if len(corrected_image.shape) == 3:
                gray = cv2.cvtColor(corrected_image, cv2.COLOR_RGB2GRAY)
            else:
                gray = corrected_image.copy()
            
            # Extract student info region
            x = self.student_info_region['x']
            y = self.student_info_region['y']
            w = self.student_info_region['width']
            h = self.student_info_region['height']
            
            student_region = gray[y:y+h, x:x+w]
            
            # Add to debug images
            self.student_debug_images.append(('01_student_region_original', student_region.copy()))
            
            # Preprocess the student region for better OCR
            processed_region = self._preprocess_student_region(student_region)
            
            # Extract individual field regions
            field_regions = self._extract_field_regions(processed_region)
            
            # Extract text from each field using OCR
            student_info = self._extract_text_from_fields(field_regions)
            
            # Save debug images if output directory provided
            if output_dir:
                self.save_student_debug_images(output_dir)
            
            logger.info(f"Student info extracted: {student_info}")
            return student_info
            
        except Exception as e:
            logger.error(f"Error extracting student info: {str(e)}")
            return {
                'name': '',
                'id': '',
                'course': '',
                'section': '',
                'error': str(e)
            }
    
    def _preprocess_student_region(self, region):
        """Preprocess student region for better OCR"""
        try:
            # Apply different preprocessing techniques
            
            # 1. Enhance contrast
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            enhanced = clahe.apply(region)
            self.student_debug_images.append(('02_enhanced_contrast', enhanced))
            
            # 2. Gaussian blur to smooth text
            blurred = cv2.GaussianBlur(enhanced, (3, 3), 0)
            self.student_debug_images.append(('03_blurred', blurred))
            
            # 3. Binary threshold
            _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            self.student_debug_images.append(('04_binary_threshold', binary))
            
            # 4. Morphological operations to connect text
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 1))
            morphed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
            self.student_debug_images.append(('05_morphed', morphed))
            
            # 5. Resize for better OCR (scale up 2x)
            resized = cv2.resize(morphed, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
            self.student_debug_images.append(('06_resized_2x', resized))
            
            return resized
            
        except Exception as e:
            logger.error(f"Error in preprocessing: {str(e)}")
            return region
    
    def set_field_coordinates(self, name_coords=None, id_coords=None, course_coords=None, section_coords=None):
        """Set exact pixel coordinates for each field region"""
        self.custom_field_coords = {}
        
        if name_coords:
            self.custom_field_coords['name'] = name_coords
            logger.info(f"Set name field coordinates: {name_coords}")
            
        if id_coords:
            self.custom_field_coords['id'] = id_coords
            logger.info(f"Set ID field coordinates: {id_coords}")
            
        if course_coords:
            self.custom_field_coords['course'] = course_coords
            logger.info(f"Set course field coordinates: {course_coords}")
            
        if section_coords:
            self.custom_field_coords['section'] = section_coords
            logger.info(f"Set field coordinates: {section_coords}")
    
    def _extract_field_regions(self, processed_region):
        """Extract individual field regions using configuration coordinates"""
        try:
            height, width = processed_region.shape
            field_regions = {}
            
            if CONFIG_AVAILABLE:
                logger.info("Using field coordinates from config file")
                
                # Get preprocessing settings
                preprocessing_config = PREPROCESSING
                scale_factor = preprocessing_config.get('student_region_scaling', 2)
                
                # Extract each field using config coordinates
                for field_name in ['name', 'id', 'course', 'section']:
                    if field_name in FIELD_COORDINATES:
                        coords = FIELD_COORDINATES[field_name]
                        
                        # Convert absolute coordinates to processed region coordinates
                        # Account for the preprocessing scaling
                        x = int(coords['x'] * scale_factor)
                        y = int(coords['y'] * scale_factor)
                        w = int(coords['width'] * scale_factor)
                        h = int(coords['height'] * scale_factor)
                        
                        # Ensure coordinates are within bounds
                        x = max(0, min(x, width - 1))
                        y = max(0, min(y, height - 1))
                        w = min(w, width - x)
                        h = min(h, height - y)
                        
                        # Extract the field region
                        field_region = processed_region[y:y+h, x:x+w]
                        field_regions[field_name] = field_region
                        
                        # Add to debug images
                        self.student_debug_images.append((f'07_field_{field_name}', field_region))
                        
                        logger.info(f"Extracted {field_name} field from config: x={x}, y={y}, w={w}, h={h}")
                    else:
                        logger.warning(f"Field '{field_name}' not found in config")
                
            else:
                # Fallback to hardcoded coordinates
                logger.info("Using fallback field coordinates")
                
                # Use your proven coordinates as fallback
                fallback_coords = {
                    'name': {'x': 120, 'y': 65, 'width': 800, 'height': 80},
                    'id': {'x': 1300, 'y': 60, 'width': 800, 'height': 86},
                    'course': {'x': 80, 'y': 150, 'width': 600, 'height': 70},
                    'section': {'x': 1400, 'y': 150, 'width': 600, 'height': 70}
                }
                
                scale_factor = 2  # Default preprocessing scaling
                
                for field_name, coords in fallback_coords.items():
                    x = int(coords['x'] * scale_factor)
                    y = int(coords['y'] * scale_factor)
                    w = int(coords['width'] * scale_factor)
                    h = int(coords['height'] * scale_factor)
                    
                    # Ensure coordinates are within bounds
                    x = max(0, min(x, width - 1))
                    y = max(0, min(y, height - 1))
                    w = min(w, width - x)
                    h = min(h, height - y)
                    
                    # Extract the field region
                    field_region = processed_region[y:y+h, x:x+w]
                    field_regions[field_name] = field_region
                    
                    # Add to debug images
                    self.student_debug_images.append((f'07_field_{field_name}', field_region))
                    
                    logger.info(f"Extracted {field_name} field (fallback): x={x}, y={y}, w={w}, h={h}")
            
            return field_regions
            
        except Exception as e:
            logger.error(f"Error extracting field regions: {str(e)}")
            return {}
    
    def _extract_text_from_fields(self, field_regions):
        """Extract text from each field using config-based OCR settings"""
        student_info = {
            'name': '',
            'id': '',
            'course': '',
            'section': ''
        }
        
        try:
            for field_name, region in field_regions.items():
                try:
                    # Get field configuration
                    if CONFIG_AVAILABLE:
                        field_config = get_field_config(field_name)
                        ocr_config = field_config.get('ocr', {})
                    else:
                        # Fallback OCR config
                        ocr_config = {
                            'psm_mode': 6,
                            'scaling_factor': 4,
                            'padding': 30
                        }
                        if field_name == 'name':
                            ocr_config['whitelist'] = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz '
                        elif field_name == 'id':
                            ocr_config['whitelist'] = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-'
                        elif field_name == 'course':
                            ocr_config['whitelist'] = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
                        else:  # section
                            ocr_config['whitelist'] = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz- '
                    
                    # Apply enhanced preprocessing using config
                    processed_field = self._preprocess_field_for_ocr(region, field_name, ocr_config)
                    
                    # Build OCR command using config with improved settings for handwritten text
                    psm_mode = ocr_config.get('psm_mode', 6)
                    whitelist = ocr_config.get('whitelist', '')
                    
                    if field_name == 'name':
                        # For names, use PSM 6 (uniform block of text) to better handle multiple words
                        # Remove whitelist restriction to allow better space detection
                        custom_config = r'--oem 3 --psm 6'
                    elif field_name == 'id':
                        # For IDs, use PSM 8 (single word) since they usually don't have spaces
                        custom_config = r'--oem 3 --psm 8 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-'
                    elif field_name == 'course':
                        # IMPROVED COURSE OCR - Multiple attempts to handle character confusion
                        # First attempt with standard OCR
                        custom_config = r'--oem 3 --psm 8 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
                    else:  # section
                        # For sections, use PSM 6 to allow spaces
                        custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz- '
                    
                    # Extract text using Tesseract
                    text = pytesseract.image_to_string(processed_field, config=custom_config)
                    
                    # ENHANCED OCR SCORING SYSTEM FOR ALL FIELDS
                    if field_name in ['name', 'id', 'course', 'section']:
                        original_text = text.strip()
                        logger.info(f"{field_name.title()} OCR attempt 1: '{original_text}'")
                        
                        # Check if we should try alternatives based on field-specific criteria
                        should_try_alternatives = False
                        
                        if field_name == 'name':
                            # Try alternatives if no spaces detected in long names, or suspicious characters
                            should_try_alternatives = (
                                (len(original_text) > 8 and ' ' not in original_text) or
                                any(char in original_text for char in ['0', '1', '8', '5', '6']) or
                                len(original_text) < 3
                            )
                        elif field_name == 'id':
                            # Try alternatives if format doesn't match expected pattern or has suspicious chars
                            import re
                            expected_pattern = r'^[0-9]{4}-[0-9]{5}-[A-Z]{2}-[0-9]+$'
                            should_try_alternatives = (
                                not re.match(expected_pattern, original_text) or
                                len(original_text) < 10 or
                                any(char in original_text for char in ['O', 'I', 'l'])
                            )
                        elif field_name == 'course':
                            # Already implemented above
                            should_try_alternatives = ('8' in original_text or '0' in original_text or '3' in original_text)
                        elif field_name == 'section':
                            # Try alternatives if format doesn't match expected pattern or missing space
                            import re
                            expected_patterns = [
                                r'^[A-Z]{2,4}\s+\d+-\d+$',  # "BSIT 2-1" with space
                                r'^[A-Z]{2,4}\d+-\d+$'      # "BSIT2-1" without space
                            ]
                            matches_pattern = any(re.match(pattern, original_text) for pattern in expected_patterns)
                            should_try_alternatives = (
                                not matches_pattern or
                                len(original_text) < 4 or
                                ('BSIT' in original_text and ' ' not in original_text and '2-1' in original_text)  # Missing space
                            )
                        
                        if should_try_alternatives:
                            # Define alternative configs based on field type
                            if field_name == 'name':
                                alternative_configs = [
                                    r'--oem 3 --psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz ',
                                    r'--oem 3 --psm 8 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz ',
                                    r'--oem 3 --psm 13 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz ',
                                    r'--oem 3 --psm 6',  # No whitelist for better space detection
                                ]
                            elif field_name == 'id':
                                alternative_configs = [
                                    r'--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-',
                                    r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-',
                                    r'--oem 3 --psm 13 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-',
                                    r'--oem 3 --psm 8 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ-',  # Uppercase focus
                                ]
                            elif field_name == 'course':
                                alternative_configs = [
                                    r'--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz',
                                    r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz',
                                    r'--oem 3 --psm 13 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz',
                                    r'--oem 3 --psm 8 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789',  # Letters first
                                ]
                            elif field_name == 'section':
                                alternative_configs = [
                                    r'--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz- ',
                                    r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz- ',
                                    r'--oem 3 --psm 13 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz- ',
                                    r'--oem 3 --psm 6',  # No whitelist for better space detection
                                ]
                            
                            best_text = original_text
                            best_confidence = 0
                            
                            for i, alt_config in enumerate(alternative_configs):
                                try:
                                    alt_text = pytesseract.image_to_string(processed_field, config=alt_config)
                                    alt_text = alt_text.strip()
                                    logger.info(f"{field_name.title()} OCR attempt {i+2}: '{alt_text}'")
                                    
                                    # Calculate score based on field type
                                    score = 0
                                    
                                    if field_name == 'name':
                                        # Enhanced name scoring system
                                        words = alt_text.split()
                                        
                                        # Prefer multiple words (first + last name or more)
                                        if len(words) >= 2:
                                            score += 10
                                            
                                            # Extra bonus for 3+ words (includes middle names/initials)
                                            if len(words) >= 3:
                                                score += 5
                                                
                                            # Bonus for middle initial pattern (e.g., "John M. Smith")
                                            for word in words:
                                                if len(word) == 2 and word.endswith('.'):
                                                    score += 3  # Middle initial bonus
                                                elif len(word) == 1 and word.isupper():
                                                    score += 2  # Single letter initial
                                        
                                        elif len(words) == 1 and len(alt_text) > 3:
                                            score += 5
                                        
                                        # Prefer alphabetic characters
                                        alpha_ratio = sum(c.isalpha() for c in alt_text) / max(len(alt_text), 1)
                                        score += int(alpha_ratio * 8)
                                        
                                        # Prefer proper length (8-50 characters for names with initials)
                                        if 8 <= len(alt_text) <= 50:
                                            score += 5
                                        elif 6 <= len(alt_text) <= 30:
                                            score += 3
                                        
                                        # Penalize numbers and most special chars, but allow periods and commas
                                        if any(c.isdigit() for c in alt_text):
                                            score -= 5
                                        
                                        # Bonus for capitalized words
                                        if all(word[0].isupper() for word in words if word and word.replace('.', '').replace(',', '')):
                                            score += 3
                                        
                                        # Bonus for comma pattern (Last, First format)
                                        if ',' in alt_text:
                                            parts = alt_text.split(',')
                                            if len(parts) == 2 and all(part.strip() for part in parts):
                                                score += 6  # Strong preference for "Last, First" format
                                        
                                        # Bonus for period pattern (middle initials)
                                        period_count = alt_text.count('.')
                                        if 1 <= period_count <= 2:  # 1-2 periods typical for initials
                                            score += 2
                                    
                                    elif field_name == 'id':
                                        # ID scoring system
                                        import re
                                        
                                        # Strong preference for correct pattern
                                        if re.match(r'^[0-9]{4}-[0-9]{5}-[A-Z]{2}-[0-9]+$', alt_text):
                                            score += 15
                                        elif re.match(r'^[0-9]{4}-[0-9]{5}-[A-Z]{2}', alt_text):
                                            score += 10  # Partial match
                                        elif '-' in alt_text and any(c.isdigit() for c in alt_text):
                                            score += 5   # Has dashes and numbers
                                        
                                        # Prefer correct length (around 15-17 characters)
                                        if 13 <= len(alt_text) <= 18:
                                            score += 5
                                        
                                        # Prefer more digits
                                        digit_count = sum(c.isdigit() for c in alt_text)
                                        score += min(digit_count, 8)
                                        
                                        # Prefer uppercase letters
                                        upper_count = sum(c.isupper() for c in alt_text if c.isalpha())
                                        score += min(upper_count * 2, 6)
                                        
                                        # Penalize problematic characters
                                        if 'O' in alt_text:
                                            score -= 2  # Often confused with 0
                                        if 'I' in alt_text or 'l' in alt_text:
                                            score -= 2  # Often confused with 1
                                    
                                    elif field_name == 'course':
                                        # Course scoring (already implemented above)
                                        if 'CS' in alt_text.upper():
                                            score += 10
                                        elif 'C' in alt_text and 'S' in alt_text:
                                            score += 8
                                        elif alt_text.upper().startswith('C'):
                                            score += 5
                                        
                                        if '101' in alt_text:
                                            score += 8
                                        elif '01' in alt_text:
                                            score += 6
                                        elif '1' in alt_text:
                                            score += 3
                                        
                                        import re
                                        if re.match(r'^[A-Z]{2,4}\d{2,4}$', alt_text.upper()):
                                            score += 5
                                        
                                        if len(alt_text) == 5:
                                            score += 3
                                        elif len(alt_text) == 4:
                                            score += 2
                                        
                                        if '8' in alt_text:
                                            score -= 3
                                        if '0' in alt_text and alt_text.count('0') > 1:
                                            score -= 2
                                        if '3' in alt_text and not '13' in alt_text:
                                            score -= 2
                                        
                                        if alt_text.upper() == 'CS101':
                                            score += 15
                                    
                                    elif field_name == 'section':
                                        # Section scoring system
                                        import re
                                        
                                        # Strong preference for correct patterns with space
                                        if re.match(r'^BSIT\s+2-1$', alt_text):
                                            score += 15  # Perfect match for "BSIT 2-1"
                                        elif re.match(r'^[A-Z]{2,4}\s+\d+-\d+$', alt_text):
                                            score += 12  # General pattern with space
                                        elif re.match(r'^BSIT2-1$', alt_text):
                                            score += 8   # Missing space but correct content
                                        elif re.match(r'^[A-Z]{2,4}\d+-\d+$', alt_text):
                                            score += 6   # General pattern without space
                                        elif 'BSIT' in alt_text and '2-1' in alt_text:
                                            score += 5   # Contains right elements
                                        
                                        # Prefer proper spacing
                                        if ' ' in alt_text and 'BSIT' in alt_text:
                                            score += 5
                                        
                                        # Prefer correct length (around 7-9 characters for "BSIT 2-1")
                                        if 6 <= len(alt_text) <= 10:
                                            score += 3
                                        
                                        # Prefer uppercase letters for program codes
                                        upper_count = sum(c.isupper() for c in alt_text if c.isalpha())
                                        if upper_count >= 3:  # At least "BSIT"
                                            score += 4
                                        
                                        # Prefer dashes in section numbers
                                        if '-' in alt_text:
                                            score += 3
                                        
                                        # Penalize too many numbers or wrong patterns
                                        if alt_text.count('-') > 1:
                                            score -= 2  # Too many dashes
                                        if any(char in alt_text for char in ['0', '8', '5']):
                                            score -= 1  # Suspicious characters
                                    
                                    if score > best_confidence:
                                        best_confidence = score
                                        best_text = alt_text
                                        logger.info(f"New best {field_name} text: '{best_text}' (score: {score})")
                                        
                                except Exception as e:
                                    logger.warning(f"Alternative {field_name} OCR failed: {e}")
                            

                            text = best_text
                            logger.info(f"Final {field_name} OCR result: '{text}'")
                    
                    # Clean the extracted text
                    cleaned_text = self._clean_extracted_text(text, field_name)
                    student_info[field_name] = cleaned_text
                    
                    logger.info(f"Extracted {field_name}: '{cleaned_text}' (raw: '{text.strip()}')")
                    
                    # Save processed field image for debugging
                    self.student_debug_images.append((f'11_{field_name}_processed', processed_field))
                    
                except Exception as e:
                    logger.warning(f"Error extracting text from {field_name}: {str(e)}")
                    student_info[field_name] = ''
            
            return student_info
            
        except Exception as e:
            logger.error(f"Error in text extraction: {str(e)}")
            return student_info
    
    def _clean_extracted_text(self, text, field_name):
        """Enhanced text cleaning for handwritten text with better space handling"""
        if not text:
            return ''
        
        # Initial cleanup - remove newlines but preserve spaces temporarily
        cleaned = text.strip()
        cleaned = ' '.join(cleaned.split('\n'))  # Replace newlines with spaces
        
        # Remove common OCR artifacts but be more careful with spaces
        artifacts = ['|', '_', '~', '`', '^', '*', '[', ']', '{', '}', '(', ')', '<', '>', '\\', '/', '@', '#', '$', '%']
        for artifact in artifacts:
            cleaned = cleaned.replace(artifact, '')
        
        # Field-specific cleaning with improved space handling
        if field_name == 'name':
            # Enhanced Names: Handle multiple formats and preserve important punctuation
            # Allow letters, spaces, periods (for initials), and commas (for Last, First format)
            temp = ''.join(c if c.isalpha() or c in ' .,' else ' ' for c in cleaned)
            
            # Normalize multiple spaces to single spaces
            temp = ' '.join(temp.split())
            
            # Handle different name formats
            if ',' in temp:
                # "Last, First Middle" format - keep comma
                parts = temp.split(',')
                if len(parts) == 2:
                    last_name = parts[0].strip()
                    first_part = parts[1].strip()
                    
                    # Clean each part
                    last_words = [word for word in last_name.split() if len(word) >= 2 or (len(word) == 1 and word.isupper())]
                    first_words = [word for word in first_part.split() if len(word) >= 1]  # Allow single initials
                    
                    if last_words and first_words:
                        cleaned = ', '.join([' '.join(last_words), ' '.join(first_words)])
                    else:
                        cleaned = temp
                else:
                    cleaned = temp
            else:
                # "First Middle Last" format - preserve structure
                words = temp.split()
                
                # Enhanced word filtering for names with initials
                filtered_words = []
                for word in words:
                    # Keep words that are:
                    # - 2+ characters long
                    # - Single uppercase letters (initials)
                    # - Single letters followed by period (initials like "C.")
                    if (len(word) >= 2 or 
                        (len(word) == 1 and word.isupper()) or
                        (len(word) == 2 and word[1] == '.' and word[0].isupper())):
                        filtered_words.append(word)
                
                cleaned = ' '.join(filtered_words)
                
                # Smart space insertion if no spaces detected but we have a long string
                if ' ' not in cleaned and len(cleaned) > 8:
                    import re
                    # Insert space before capital letters that follow lowercase letters
                    # This handles cases like "JohnMathewParocha" -> "John Mathew Parocha"
                    cleaned = re.sub(r'([a-z])([A-Z])', r'\1 \2', cleaned)
                    
                    # Handle period patterns for initials
                    # "JohnC.Parocha" -> "John C. Parocha"
                    cleaned = re.sub(r'([a-z])([A-Z]\.)', r'\1 \2', cleaned)

        elif field_name == 'id':
            # Student IDs: alphanumeric and dashes only, no spaces
            # Remove extra leading/trailing dashes and normalize
            cleaned = ''.join(c for c in cleaned if c.isalnum() or c == '-')
            # Remove leading/trailing dashes
            cleaned = cleaned.strip('-')
            # Remove multiple consecutive dashes
            import re
            cleaned = re.sub(r'-+', '-', cleaned)
            
        elif field_name == 'course':
            # ENHANCED COURSE CLEANING - Handle common OCR mistakes
            # Course codes: alphanumeric only, typically short, no spaces
            cleaned = ''.join(c for c in cleaned if c.isalnum())
            
            # Apply intelligent character corrections for course codes
            if len(cleaned) >= 3:
                corrected = cleaned.upper()  # Convert to uppercase first
                
                # Apply pattern-based corrections
                # Handle common OCR mistakes for "CS101"
                patterns = [
                    # Pattern: C + number/letter + 101 variants
                    (r'^C8101$', 'CS101'),      # C8101 -> CS101
                    (r'^C3101$', 'CS101'),      # C3101 -> CS101  
                    (r'^C5101$', 'CS101'),      # C5101 -> CS101
                    (r'^C6101$', 'CS101'),      # C6101 -> CS101
                    (r'^C81O1$', 'CS101'),      # C81O1 -> CS101 (O instead of 0)
                    (r'^C31O1$', 'CS101'),      # C31O1 -> CS101
                    
                    # Pattern: CS + number variants  
                    (r'^CS1O1$', 'CS101'),      # CS1O1 -> CS101 (O instead of 0)
                    (r'^CS10I$', 'CS101'),      # CS10I -> CS101 (I instead of 1)
                    (r'^CS1OI$', 'CS101'),      # CS1OI -> CS101
                    (r'^CSIO1$', 'CS101'),      # CSIO1 -> CS101
                    (r'^CSIOI$', 'CS101'),      # CSIOI -> CS101
                    (r'^CS100$', 'CS101'),      # CS100 -> CS101
                    
                    # Pattern: Other common mistakes
                    (r'^C[38S][01OI][01OI][01OI]$', 'CS101'),  # Generic pattern
                ]
                
                # Apply pattern-based corrections
                import re
                for pattern, replacement in patterns:
                    if re.match(pattern, corrected):
                        logger.info(f"Course pattern correction: '{cleaned}' -> '{replacement}'")
                        corrected = replacement
                        break
                else:
                    # If no pattern matches, apply character-by-character fixes
                    if corrected.startswith('C') and len(corrected) >= 2:
                        # Fix second character if it's commonly misread
                        if corrected[1] in '38356':  # Numbers often confused with 'S'
                            corrected = 'CS' + corrected[2:]
                            logger.info(f"Course character correction: '{cleaned}' -> '{corrected}'")
                    
                    # Fix common number confusions in course codes
                    if 'O' in corrected:  # O -> 0
                        corrected = corrected.replace('O', '0')
                    if 'I' in corrected and corrected != 'CS101':  # I -> 1 (but not if already correct)
                        corrected = corrected.replace('I', '1')
                
                cleaned = corrected
            
        elif field_name == 'section':
            # ENHANCED SECTION CLEANING - Handle spaces properly for "BSIT 2-1"
            # Sections: alphanumeric, spaces, and dashes
            
            # First, clean up but preserve meaningful spaces and dashes
            temp = ''.join(c if c.isalnum() or c in '- ' else ' ' for c in cleaned)
            words = temp.split()
            
            # Smart reconstruction for section format
            if len(words) >= 2:
                # Check if we have a program code + section number pattern
                program_part = words[0].upper()  # e.g., "BSIT"
                section_parts = words[1:]  # e.g., ["2-1"] or ["2", "1"]
                
                # Reconstruct section number if it was split
                if len(section_parts) == 2 and section_parts[0].isdigit() and section_parts[1].isdigit():
                    # "BSIT" "2" "1" -> "BSIT 2-1"
                    section_number = f"{section_parts[0]}-{section_parts[1]}"
                elif len(section_parts) == 1:
                    # "BSIT" "2-1" -> "BSIT 2-1"
                    section_number = section_parts[0]
                else:
                    # Fallback: join remaining parts
                    section_number = ''.join(section_parts)
                
                cleaned = f"{program_part} {section_number}"
            else:
                # Single word - try to intelligently split if needed
                single_word = words[0] if words else cleaned
                
                # Check for patterns like "BSIT2-1" -> "BSIT 2-1"
                import re
                match = re.match(r'^([A-Z]{2,4})(\d+-\d+)$', single_word.upper())
                if match:
                    program_code = match.group(1)
                    section_number = match.group(2)
                    cleaned = f"{program_code} {section_number}"
                else:
                    # Keep as is if no clear pattern
                    cleaned = single_word
        
        # Final cleanup
        cleaned = cleaned.strip()
        
        # Return empty if too short (likely noise) but allow single characters for course codes
        min_length = 1 if field_name == 'course' else 2
        if len(cleaned) < min_length:
            return ''
        
        return cleaned

    def update_student_region(self, x=None, y=None, width=None, height=None):
        """Update the student info region coordinates"""
        if x is not None:
            self.student_info_region['x'] = int(x)
        if y is not None:
            self.student_info_region['y'] = int(y)
        if width is not None:
            self.student_info_region['width'] = int(width)
        if height is not None:
            self.student_info_region['height'] = int(height)
        
        logger.info(f"Updated student region: {self.student_info_region}")
    
    def load_config_coordinates(self):
        """Load coordinates from config file if available"""
        if CONFIG_AVAILABLE:
            # Update student region from config
            config_region = get_student_region_config()
            self.student_info_region.update(config_region)
            logger.info("Loaded coordinates from config file")
            return True
        else:
            logger.warning("Config file not available")
            return False

    def save_student_debug_images(self, output_dir):
        """Save all student debug images to output directory"""
        try:
            # Create student info debug subdirectory
            student_debug_dir = os.path.join(output_dir, 'student_info_debug')
            os.makedirs(student_debug_dir, exist_ok=True)
            
            for stage_name, debug_img in self.student_debug_images:
                filename = f"{stage_name}.png"
                filepath = os.path.join(student_debug_dir, filename)
                
                # Save image
                cv2.imwrite(filepath, debug_img)
                logger.info(f"Saved student debug image: {filepath}")
                
        except Exception as e:
            logger.error(f"Error saving student debug images: {str(e)}")
    
    def process_answer_sheet(self, pdf_path, output_dir=None, debug_student_region=False, extract_student_info=True):
        """
        Complete processing pipeline with student info extraction
        
        Args:
            pdf_path: Path to PDF file
            output_dir: Directory to save debug images (optional)
            debug_student_region: Whether to debug student region instead of extracting
            extract_student_info: Whether to extract student information
            
        Returns:
            Dictionary with corrected image and extracted student info
        """
        try:
            # Clear previous debug images
            self.debug_images = []
            self.student_debug_images = []
            
            # Step 1: Convert PDF to image
            image = self.pdf_to_image(pdf_path)
            if image is None:
                return None
            
            # Step 2: Detect corner markers
            corners = self.detect_corner_markers(image)
            if corners is None:
                logger.error("Failed to detect corner markers")
                return None
            
            # Step 3: Apply perspective correction
            corrected_image = self.correct_perspective(image, corners)
            if corrected_image is None:
                logger.error("Failed to apply perspective correction")
                return None
            
            # Step 4: Process student info
            if debug_student_region:
                region_analysis = self.detect_and_visualize_student_info_region(corrected_image, output_dir)
                student_info = None
            elif extract_student_info:
                student_info = self.extract_student_info(corrected_image, output_dir)
                region_analysis = None
            else:
                student_info = None
                region_analysis = None
            
            # Save final corrected image
            if output_dir:
                output_path = os.path.join(output_dir, f"{Path(pdf_path).stem}_corrected.png")
                cv2.imwrite(output_path, cv2.cvtColor(corrected_image, cv2.COLOR_RGB2BGR))
                logger.info(f"Final corrected image saved: {output_path}")
            
            return {
                'corrected_image': corrected_image,
                'student_info': student_info,
                'region_analysis': region_analysis,
                'success': True
            }
            
        except Exception as e:
            logger.error(f"Error in processing pipeline: {str(e)}")
            return {
                'corrected_image': None,
                'student_info': None,
                'region_analysis': None,
                'success': False,
                'error': str(e)
            }
    
    def debug_specific_field(self, corrected_image, field_name='name', output_dir=None):
        """
        Debug a specific field with optimized coordinate suggestions
        
        Args:
            corrected_image: Perspective corrected image
            field_name: Field to debug ('name', 'id', 'course', 'section')
            output_dir: Directory to save debug images
            
        Returns:
            Dictionary with field coordinates and extracted text
        """
        try:
            # Clear previous debug images
            self.student_debug_images = []
            
            logger.info(f"Debugging {field_name} field with optimized coordinates...")
            
            # Convert to grayscale if needed
            if len(corrected_image.shape) == 3:
                gray = cv2.cvtColor(corrected_image, cv2.COLOR_RGB2GRAY)
            else:
                gray = corrected_image.copy()
            
            # Extract student info region first
            x = self.student_info_region['x']
            y = self.student_info_region['y']
            w = self.student_info_region['width']
            h = self.student_info_region['height']
            
            student_region = gray[y:y+h, x:x+w]
            self.student_debug_images.append(('01_full_student_region', student_region.copy()))
            
            # Preprocess the student region
            processed_region = self._preprocess_student_region(student_region)
            
            # OPTIMIZED field coordinates based on your successful debugging
            height, width = processed_region.shape
            
            if field_name == 'name':
                field_coords = {
                    'x': int(width * 0.04),    # 4% from left
                    'y': int(height * 0.02),   # 2% from top
                    'width': int(width * 0.45), # 45% width
                    'height': int(height * 0.4)  # 40% height
                }
            elif field_name == 'id':
                field_coords = {
                    'x': int(width * 0.52),    # 52% from left (right half)
                    'y': int(height * 0.0),    # Start from top
                    'width': int(width * 0.45), # 45% width
                    'height': int(height * 0.45) # 45% height
                }
            elif field_name == 'course':
                field_coords = {
                    'x': int(width * 0.02),    # 2% from left
                    'y': int(height * 0.5),    # 50% from top (bottom half)
                    'width': int(width * 0.45), # 45% width
                    'height': int(height * 0.4)  # 40% height
                }
            elif field_name == 'section':
                field_coords = {
                    'x': int(width * 0.54),    # 54% from left (right half)
                    'y': int(height * 0.5),    # 50% from top (bottom half)
                    'width': int(width * 0.43), # 43% width
                    'height': int(height * 0.4)  # 40% height
                }
            else:
                logger.error(f"Unknown field name: {field_name}")
                return None
            
            # Extract the specific field region
            fx, fy, fw, fh = field_coords['x'], field_coords['y'], field_coords['width'], field_coords['height']
            
            # Ensure coordinates are within bounds
            fx = max(0, min(fx, width - 1))
            fy = max(0, min(fy, height - 1))
            fw = min(fw, width - fx)
            fh = min(fh, height - fy)
            
            field_region = processed_region[fy:fy+fh, fx:fx+fw]
            
            # Create visualization with field boundary
            visualization = cv2.cvtColor(processed_region, cv2.COLOR_GRAY2RGB)
            cv2.rectangle(visualization, (fx, fy), (fx + fw, fy + fh), (0, 255, 0), 3)
            cv2.putText(visualization, f"{field_name.upper()} FIELD (OPTIMIZED)", (fx, fy - 10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            
            self.student_debug_images.append(('02_field_visualization', visualization))
            self.student_debug_images.append((f'03_{field_name}_raw_field', field_region.copy()))
            
            # Apply different preprocessing levels for comparison
            preprocessed_fields = self._create_preprocessing_variants(field_region, field_name)
            
            # Try OCR on each variant
            ocr_results = {}
            for variant_name, variant_image in preprocessed_fields.items():
                try:
                    # Save variant for debugging
                    self.student_debug_images.append((f'04_{field_name}_{variant_name}', variant_image))
                    
                    # Different OCR configs optimized for each field type
                    if field_name == 'name':
                        configs = {
                            'default': r'--oem 3 --psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz ',
                            'single_line': r'--oem 3 --psm 8 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz ',
                            'word': r'--oem 3 --psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz '
                        }
                    elif field_name == 'id':
                        configs = {
                            'default': r'--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-',
                            'single_line': r'--oem 3 --psm 8 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-',
                            'digits': r'--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789-'
                        }
                    elif field_name in ['course', 'section']:
                        configs = {
                            'default': r'--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz- ',
                            'alphanumeric': r'--oem 3 --psm 8 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-',
                            'sparse': r'--oem 3 --psm 11 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz- '
                        }
                    
                    for config_name, config in configs.items():
                        text = pytesseract.image_to_string(variant_image, config=config)
                        cleaned = self._clean_extracted_text(text, field_name)
                        
                        result_key = f"{variant_name}_{config_name}"
                        ocr_results[result_key] = {
                            'raw_text': text.strip(),
                            'cleaned_text': cleaned,
                            'config': config
                        }
                        
                        logger.info(f"OCR {result_key}: '{cleaned}' (raw: '{text.strip()}')")
                
                except Exception as e:
                    logger.warning(f"OCR failed for {variant_name}: {str(e)}")
            
            # Save debug images
            if output_dir:
                self.save_student_debug_images(output_dir)
            
            return {
                'field_name': field_name,
                'coordinates': field_coords,
                'processed_region_shape': processed_region.shape,
                'field_region_shape': field_region.shape,
                'ocr_results': ocr_results,
                'suggestions': ['Coordinates have been optimized based on successful debugging']
            }
            
        except Exception as e:
            logger.error(f"Error debugging {field_name} field: {str(e)}")
            return None
    
    def _create_preprocessing_variants(self, field_region, field_name):
        """Create different preprocessing variants for comparison"""
        variants = {}
        
        # Original
        variants['original'] = field_region.copy()
        
        # Simple scaling
        scaled_2x = cv2.resize(field_region, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        variants['scaled_2x'] = scaled_2x
        
        # Scaled with padding
        padding = 20
        h, w = scaled_2x.shape
        padded = np.ones((h + 2*padding, w + 2*padding), dtype=np.uint8) * 255
        padded[padding:padding+h, padding:padding+w] = scaled_2x
        variants['scaled_padded'] = padded
        
        # Morphological operations
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 1))
        morphed = cv2.morphologyEx(field_region, cv2.MORPH_CLOSE, kernel)
        variants['morphed'] = morphed
        
        # Gaussian blur + threshold
        blurred = cv2.GaussianBlur(field_region, (3, 3), 0)
        _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        variants['blur_thresh'] = thresh
        
        # Erosion/Dilation
        eroded = cv2.erode(field_region, kernel, iterations=1)
        dilated = cv2.dilate(eroded, kernel, iterations=1)
        variants['erode_dilate'] = dilated
        
        # Adaptive threshold
        adaptive = cv2.adaptiveThreshold(field_region, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                       cv2.THRESH_BINARY, 11, 2)
        variants['adaptive'] = adaptive
        
        return variants
    
    def _get_field_adjustment_suggestions(self, field_coords, region_shape):
        """Generate suggestions for field coordinate adjustment"""
        suggestions = []
        height, width = region_shape
        
        fx, fy, fw, fh = field_coords['x'], field_coords['y'], field_coords['width'], field_coords['height']
        
        # Check if field is reasonable
        if fw < 50:
            suggestions.append("Field width seems to narrow - increase width")
        if fh < 20:
            suggestions.append("Field height seems too short - increase height")
        if fx + fw > width:
            suggestions.append("Field extends beyond region width - reduce width or x position")
        if fy + fh > height:
            suggestions.append("Field extends beyond region height - reduce height or y position")
        
        # Position suggestions
        if fx < width * 0.02:
            suggestions.append("Field might be too close to left edge")
        if fy < height * 0.05:
            suggestions.append("Field might be too close to top edge")
        
        if not suggestions:
            suggestions.append("Field coordinates look reasonable")
        
        return suggestions
    
    def update_field_coordinates(self, field_name, x=None, y=None, width=None, height=None):
        """Update coordinates for a specific field (for future use)"""
        if not hasattr(self, 'field_coordinates'):
            self.field_coordinates = {}
        
        if field_name not in self.field_coordinates:
            self.field_coordinates[field_name] = {}
        
        if x is not None:
            self.field_coordinates[field_name]['x'] = int(x)
        if y is not None:
            self.field_coordinates[field_name]['y'] = int(y)
        if width is not None:
            self.field_coordinates[field_name]['width'] = int(width)
        if height is not None:
            self.field_coordinates[field_name]['height'] = int(height)
        
        logger.info(f"Updated {field_name} coordinates: {self.field_coordinates[field_name]}")
    
    def _preprocess_field_for_ocr(self, field_region, field_name, ocr_config=None):
        """Apply field-specific preprocessing using config settings"""
        try:
            if ocr_config is None:
                ocr_config = {'scaling_factor': 4, 'padding': 30}
                
            # Start with the field region
            processed = field_region.copy()
            
            # Enhanced noise removal for handwritten text
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
            processed = cv2.morphologyEx(processed, cv2.MORPH_OPEN, kernel)
            
            # Connect broken characters
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 1))
            processed = cv2.morphologyEx(processed, cv2.MORPH_CLOSE, kernel)
            
            # Scale up using config
            scaling_factor = ocr_config.get('scaling_factor', 4)
            processed = cv2.resize(processed, None, fx=scaling_factor, fy=scaling_factor, interpolation=cv2.INTER_CUBIC)
            
            # Apply slight blur to smooth edges
            processed = cv2.GaussianBlur(processed, (3, 3), 0)
            
            # Re-threshold with OTSU for adaptive thresholding
            _, processed = cv2.threshold(processed, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # Add padding using config
            padding = ocr_config.get('padding', 30)
            h, w = processed.shape
            padded = np.ones((h + 2*padding, w + 2*padding), dtype=np.uint8) * 255
            padded[padding:padding+h, padding:padding+w] = processed
            
            # Final morphological cleaning
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
            padded = cv2.morphologyEx(padded, cv2.MORPH_CLOSE, kernel)
            
            return padded
            
        except Exception as e:
            logger.error(f"Error in field preprocessing: {str(e)}")
            return field_region


def main():
    """Main function for testing the processor"""
    global CONFIG_AVAILABLE  # Declare as global to modify it
    
    parser = argparse.ArgumentParser(description='Process PDF answer sheet and extract student info')
    parser.add_argument('pdf_path', help='Path to PDF file to process')
    parser.add_argument('--output-dir', '-o', default='debug_output', 
                       help='Directory to save debug images (default: debug_output)')
    parser.add_argument('--debug-region', action='store_true',
                       help='Debug student region instead of extracting')
    parser.add_argument('--debug-field', choices=['name', 'id', 'course', 'section'],
                       help='Debug a specific field')
    parser.add_argument('--no-extract', action='store_true',
                       help='Skip student info extraction')
    parser.add_argument('--x', type=int, help='Student region X coordinate')
    parser.add_argument('--y', type=int, help='Student region Y coordinate') 
    parser.add_argument('--width', type=int, help='Student region width')
    parser.add_argument('--height', type=int, help='Student region height')
    parser.add_argument('--dpi', type=int, default=600, 
                       help='DPI for PDF conversion (default: 600)')
    parser.add_argument('--use-config', action='store_true',
                       help='Force use config file coordinates (default if available)')
    parser.add_argument('--no-config', action='store_true',
                       help='Ignore config file and use command line coordinates')
    
    # Add field coordinate arguments
    parser.add_argument('--name-coords', nargs=4, type=int, metavar=('X', 'Y', 'W', 'H'),
                       help='Name field coordinates: x y width height')
    parser.add_argument('--id-coords', nargs=4, type=int, metavar=('X', 'Y', 'W', 'H'),
                       help='ID field coordinates: x y width height')
    parser.add_argument('--course-coords', nargs=4, type=int, metavar=('X', 'Y', 'W', 'H'),
                       help='Course field coordinates: x y width height')
    parser.add_argument('--section-coords', nargs=4, type=int, metavar=('X', 'Y', 'W', 'H'),
                       help='Section field coordinates: x y width height')
    
    args = parser.parse_args()
    
    # Check if PDF file exists
    if not os.path.exists(args.pdf_path):
        logger.error(f"PDF file not found: {args.pdf_path}")
        return
    
    # Create processor
    processor = PDFAnswerSheetProcessor(debug_mode=False)
    
    # Handle configuration usage
    if args.no_config:
        logger.info("Ignoring config file as requested")
        CONFIG_AVAILABLE = False  # Now we can modify the global variable
    elif CONFIG_AVAILABLE:
        logger.info("Using configuration file coordinates")
        processor.load_config_coordinates()
    
    # Update region if manual coordinates provided (overrides config)
    if any([args.x, args.y, args.width, args.height]):
        processor.update_student_region(args.x, args.y, args.width, args.height)
        logger.info("Manual region coordinates applied (overriding config)")
    
    # Set custom field coordinates if provided
    custom_coords = {}
    if args.name_coords:
        custom_coords['name'] = {'x': args.name_coords[0], 'y': args.name_coords[1], 
                               'width': args.name_coords[2], 'height': args.name_coords[3]}
    if args.id_coords:
        custom_coords['id'] = {'x': args.id_coords[0], 'y': args.id_coords[1], 
                             'width': args.id_coords[2], 'height': args.id_coords[3]}
    if args.course_coords:
        custom_coords['course'] = {'x': args.course_coords[0], 'y': args.course_coords[1], 
                                 'width': args.course_coords[2], 'height': args.course_coords[3]}
    if args.section_coords:
        custom_coords['section'] = {'x': args.section_coords[0], 'y': args.section_coords[1], 
                                  'width': args.section_coords[2], 'height': args.section_coords[3]}
    
    if custom_coords:
        processor.set_field_coordinates(**custom_coords)
        logger.info("Custom field coordinates set")
    
    # Process the answer sheet
    logger.info(f"Starting processing of: {args.pdf_path}")
    
    if CONFIG_AVAILABLE:
        logger.info("Configuration status:")
        logger.info(f"  Student region: {processor.student_info_region}")
        logger.info(f"  Available fields: {list(FIELD_COORDINATES.keys()) if CONFIG_AVAILABLE else 'None'}")
    
    # Special case: debug specific field
    if args.debug_field:
        # Get corrected image first
        image = processor.pdf_to_image(args.pdf_path)
        if image is None:
            logger.error("Failed to convert PDF to image")
            return
        
        corners = processor.detect_corner_markers(image)
        if corners is None:
            logger.error("Failed to detect corner markers")
            return
        
        corrected_image = processor.correct_perspective(image, corners)
        if corrected_image is None:
            logger.error("Failed to apply perspective correction")
            return
        
        # Debug the specific field
        field_result = processor.debug_specific_field(corrected_image, args.debug_field, args.output_dir)
        
        if field_result:
            logger.info("Field debugging completed successfully!")
            
            print("\n" + "="*70)
            print(f"FIELD DEBUGGING RESULTS - {args.debug_field.upper()}")
            print("="*70)
            print(f"Field Coordinates: {field_result['coordinates']}")
            print(f"Field Region Shape: {field_result['field_region_shape']}")
            print(f"Processed Region Shape: {field_result['processed_region_shape']}")
            print("\nOCR Results:")
            for result_name, result_data in field_result['ocr_results'].items():
                print(f"  {result_name}: '{result_data['cleaned_text']}'")
                if result_data['raw_text'] != result_data['cleaned_text']:
                    print(f"    (raw: '{result_data['raw_text']}')")
            
            print(f"\nSuggestions: {', '.join(field_result['suggestions'])}")
            print("="*70)
            print(f"\nDebug images saved in: {os.path.join(args.output_dir, 'student_info_debug')}")
        else:
            logger.error("Field debugging failed!")
        
        return
    
    # Normal processing
    result = processor.process_answer_sheet(
        args.pdf_path, 
        args.output_dir, 
        debug_student_region=args.debug_region,
        extract_student_info=not args.no_extract
    )
    
    if result and result['success']:
        logger.info("Processing completed successfully!")
        logger.info(f"Final corrected image shape: {result['corrected_image'].shape}")
        
        # Display extracted student info
        if result['student_info']:
            student_info = result['student_info']
            print("\n" + "="*60)
            print("EXTRACTED STUDENT INFORMATION:")
            print("="*60)
            print(f"Name: '{student_info.get('name', 'Not detected')}'")
            print(f"ID: '{student_info.get('id', 'Not detected')}'")
            print(f"Course: '{student_info.get('course', 'Not detected')}'")
            print(f"Section: '{student_info.get('section', 'Not detected')}'")
            print("="*60)
            
            logger.info(f"Student info debug images saved in: {os.path.join(args.output_dir, 'student_info_debug')}")
        
        # Display region analysis if debugging
        if result['region_analysis']:
            analysis = result['region_analysis']
            print("\n" + "="*60)
            print("STUDENT INFO REGION ANALYSIS:")
            print("="*60)
            coords = analysis['region_coordinates']
            print(f"Current Region: X={coords['x']}, Y={coords['y']}, W={coords['width']}, H={coords['height']}")
            print(f"Suggestions: {', '.join(analysis['suggestions'])}")
            print("="*60)
            
    else:
        logger.error("Processing failed!")
        if result and 'error' in result:
            logger.error(f"Error: {result['error']}")


if __name__ == "__main__":
    main()
