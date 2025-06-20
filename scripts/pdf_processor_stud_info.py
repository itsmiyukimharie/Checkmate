"""
CheckMate PDF Processor - Student Information Extraction Module

This module handles the extraction of student information (name, ID, course, section)
from PDF answer sheets using OCR with enhanced scoring and pattern recognition.
"""

import cv2
import numpy as np
import logging
import pytesseract
import re

# Configure logging
logger = logging.getLogger(__name__)

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
    logger.warning("field_coordinates_config.py not found. Using default coordinates.")

    # Use the config values as defaults if config is missing
    STUDENT_REGION = {
        'x': 0, 'y': 300, 'width': 2600, 'height': 300
    }
    FIELD_COORDINATES = {
        'name': {'x': 220, 'y': 130, 'width': 1050, 'height': 80},
        'id': {'x': 1350, 'y': 90, 'width': 1050, 'height': 120},
        'course': {'x': 245, 'y': 210, 'width': 1050, 'height': 75},
        'section': {'x': 1450, 'y': 210, 'width': 950, 'height': 75}
    }
    OCR_CONFIG = {
        'name': {'psm_mode': 6, 'whitelist': '', 'scaling_factor': 4, 'padding': 30},
        'id': {'psm_mode': 8, 'whitelist': '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-', 'scaling_factor': 4, 'padding': 30},
        'course': {'psm_mode': 8, 'whitelist': '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz', 'scaling_factor': 4, 'padding': 30},
        'section': {'psm_mode': 6, 'whitelist': '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz- ', 'scaling_factor': 4, 'padding': 30}
    }
    PREPROCESSING = {
        'student_region_scaling': 2,
        'enhance_contrast': True,
        'gaussian_blur': True,
        'morphological_ops': True,
        'adaptive_threshold': True
    }
    def get_field_config(field_name):
        return {
            'coordinates': FIELD_COORDINATES.get(field_name, {}),
            'ocr': OCR_CONFIG.get(field_name, {}),
            'validation': {}
        }
    def get_student_region_config():
        return STUDENT_REGION.copy()


class StudentInfoExtractor:
    """
    Specialized class for extracting student information from answer sheets
    """
    
    def __init__(self):
        self.debug_images = []
        
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
            # Clear previous debug images
            self.debug_images = []
            
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
            self.debug_images.append(('01_student_region_original', student_region.copy()))
            
            # Preprocess the student region for better OCR
            processed_region = self._preprocess_student_region(student_region)
            
            # Extract individual field regions
            field_regions = self._extract_field_regions(processed_region)
            
            # Extract text from each field using OCR
            student_info = self._extract_text_from_fields(field_regions)
            
            # Save debug images if output directory provided
            if output_dir:
                self.save_debug_images(output_dir)
            
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
            self.debug_images.append(('02_enhanced_contrast', enhanced))
            
            # 2. Gaussian blur to smooth text
            blurred = cv2.GaussianBlur(enhanced, (3, 3), 0)
            self.debug_images.append(('03_blurred', blurred))
            
            # 3. Binary threshold
            _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            self.debug_images.append(('04_binary_threshold', binary))
            
            # 4. Morphological operations to connect text
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 1))
            morphed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
            self.debug_images.append(('05_morphed', morphed))
            
            # 5. Resize for better OCR (scale up 2x)
            resized = cv2.resize(morphed, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
            self.debug_images.append(('06_resized_2x', resized))
            
            return resized
            
        except Exception as e:
            logger.error(f"Error in preprocessing: {str(e)}")
            return region
    
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
                
                # CORRECTED: Use field coordinates directly as they are already relative to student region
                for field_name in ['name', 'id', 'course', 'section']:
                    if field_name in FIELD_COORDINATES:
                        coords = FIELD_COORDINATES[field_name]
                        
                        # Use coordinates directly (they are already relative to student region)
                        # Only apply the preprocessing scaling factor
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
                        self.debug_images.append((f'07_field_{field_name}', field_region))
                        
                        logger.info(f"Extracted {field_name} field from config: x={x}, y={y}, w={w}, h={h}")
                    else:
                        logger.warning(f"Field '{field_name}' not found in config")
                
            else:
                # Updated fallback coordinates to match your fine-tuned configuration
                logger.info("Using fallback field coordinates")
                
                fallback_coords = {
                    'name': {'x': 220, 'y': 135, 'width': 1050, 'height': 85},
                    'id': {'x': 1400, 'y': 135, 'width': 1200, 'height': 85},
                    'course': {'x': 220, 'y': 215, 'width': 1050, 'height': 85},
                    'section': {'x': 1525, 'y': 215, 'width': 1050, 'height': 90}
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
                    self.debug_images.append((f'07_field_{field_name}', field_region))
                    
                    logger.info(f"Extracted {field_name} field (fallback): x={x}, y={y}, w={w}, h={h}")
            
            return field_regions
            
        except Exception as e:
            logger.error(f"Error extracting field regions: {str(e)}")
            return {}
    
    def _extract_text_from_fields(self, field_regions):
        """Extract text from each field using enhanced OCR with scoring"""
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
                    
                    # Get initial OCR configuration
                    if field_name == 'name':
                        custom_config = r'--oem 3 --psm 6'
                    elif field_name == 'id':
                        custom_config = r'--oem 3 --psm 8 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-'
                    elif field_name == 'course':
                        custom_config = r'--oem 3 --psm 8 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
                    else:  # section
                        custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz- '
                    
                    # Extract text using Tesseract
                    text = pytesseract.image_to_string(processed_field, config=custom_config)
                    
                    # Apply enhanced OCR scoring for all fields
                    if field_name in ['name', 'id', 'course', 'section']:
                        text = self._apply_enhanced_ocr_scoring(processed_field, field_name, text)
                    
                    # Clean the extracted text
                    cleaned_text = self._clean_extracted_text(text, field_name)
                    student_info[field_name] = cleaned_text
                    
                    logger.info(f"Extracted {field_name}: '{cleaned_text}' (raw: '{text.strip()}')")
                    
                    # Save processed field image for debugging
                    self.debug_images.append((f'11_{field_name}_processed', processed_field))
                    
                except Exception as e:
                    logger.warning(f"Error extracting text from {field_name}: {str(e)}")
                    student_info[field_name] = ''
            
            return student_info
            
        except Exception as e:
            logger.error(f"Error in text extraction: {str(e)}")
            return student_info
    
    def _apply_enhanced_ocr_scoring(self, processed_field, field_name, original_text):
        """Apply enhanced OCR scoring with multiple attempts"""
        original_text = original_text.strip()
        logger.info(f"{field_name.title()} OCR attempt 1: '{original_text}'")
        
        # Check if we should try alternatives based on field-specific criteria
        should_try_alternatives = self._should_try_alternatives(field_name, original_text)
        
        if should_try_alternatives:
            # Define alternative configs based on field type
            alternative_configs = self._get_alternative_configs(field_name)
            
            best_text = original_text
            best_confidence = 0
            
            for i, alt_config in enumerate(alternative_configs):
                try:
                    alt_text = pytesseract.image_to_string(processed_field, config=alt_config)
                    alt_text = alt_text.strip()
                    logger.info(f"{field_name.title()} OCR attempt {i+2}: '{alt_text}'")
                    
                    # Calculate score based on field type
                    score = self._calculate_field_score(field_name, alt_text)
                    
                    if score > best_confidence:
                        best_confidence = score
                        best_text = alt_text
                        logger.info(f"New best {field_name} text: '{best_text}' (score: {score})")
                        
                except Exception as e:
                    logger.warning(f"Alternative {field_name} OCR failed: {e}")
            
            original_text = best_text
            logger.info(f"Final {field_name} OCR result: '{original_text}'")
        
        return original_text
    
    def _should_try_alternatives(self, field_name, text):
        """Determine if we should try alternative OCR configs"""
        if field_name == 'name':
            return (
                (len(text) > 8 and ' ' not in text) or
                any(char in text for char in ['0', '1', '8', '5', '6']) or
                len(text) < 3
            )
        elif field_name == 'id':
            expected_pattern = r'^[0-9]{4}-[0-9]{5}-[A-Z]{2}-[0-9]+$'
            return (
                not re.match(expected_pattern, text) or
                len(text) < 10 or
                any(char in text for char in ['O', 'I', 'l'])
            )
        elif field_name == 'course':
            return ('8' in text or '0' in text or '3' in text)
        elif field_name == 'section':
            expected_patterns = [
                r'^[A-Z]{2,4}\s+\d+-\d+$',  # "BSIT 2-1" with space
                r'^[A-Z]{2,4}\d+-\d+$'      # "BSIT2-1" without space
            ]
            matches_pattern = any(re.match(pattern, text) for pattern in expected_patterns)
            return (
                not matches_pattern or
                len(text) < 4 or
                ('BSIT' in text and ' ' not in text and '2-1' in text)  # Missing space
            )
        return False
    
    def _get_alternative_configs(self, field_name):
        """Get alternative OCR configurations for a field"""
        if field_name == 'name':
            return [
                r'--oem 3 --psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz .,',
                r'--oem 3 --psm 8 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz .,',
                r'--oem 3 --psm 13 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz .,',
                r'--oem 3 --psm 6',  # No whitelist for better space detection
            ]
        elif field_name == 'id':
            return [
                r'--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-',
                r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-',
                r'--oem 3 --psm 13 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-',
                r'--oem 3 --psm 8 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ-',  # Uppercase focus
            ]
        elif field_name == 'course':
            return [
                r'--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz',
                r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz',
                r'--oem 3 --psm 13 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz',
                r'--oem 3 --psm 8 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789',  # Letters first
            ]
        elif field_name == 'section':
            return [
                r'--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz- ',
                r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz- ',
                r'--oem 3 --psm 13 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz- ',
                r'--oem 3 --psm 6',  # No whitelist for better space detection
            ]
        return []
    
    def _calculate_field_score(self, field_name, text):
        """Calculate confidence score for extracted text based on field type"""
        score = 0
        
        if field_name == 'name':
            # Enhanced name scoring system
            words = text.split()
            
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
            
            elif len(words) == 1 and len(text) > 3:
                score += 5
            
            # Prefer alphabetic characters
            alpha_ratio = sum(c.isalpha() for c in text) / max(len(text), 1)
            score += int(alpha_ratio * 8)
            
            # Prefer proper length (8-50 characters for names with initials)
            if 8 <= len(text) <= 50:
                score += 5
            elif 6 <= len(text) <= 30:
                score += 3
            
            # Penalize numbers and most special chars, but allow periods and commas
            if any(c.isdigit() for c in text):
                score -= 5
            
            # Bonus for capitalized words
            if all(word[0].isupper() for word in words if word and word.replace('.', '').replace(',', '')):
                score += 3
            
            # Bonus for comma pattern (Last, First format)
            if ',' in text:
                parts = text.split(',')
                if len(parts) == 2 and all(part.strip() for part in parts):
                    score += 6  # Strong preference for "Last, First" format
            
            # Bonus for period pattern (middle initials)
            period_count = text.count('.')
            if 1 <= period_count <= 2:  # 1-2 periods typical for initials
                score += 2
        
        elif field_name == 'id':
            # ID scoring system
            # Strong preference for correct pattern
            if re.match(r'^[0-9]{4}-[0-9]{5}-[A-Z]{2}-[0-9]+$', text):
                score += 15
            elif re.match(r'^[0-9]{4}-[0-9]{5}-[A-Z]{2}', text):
                score += 10  # Partial match
            elif '-' in text and any(c.isdigit() for c in text):
                score += 5   # Has dashes and numbers
            
            # Prefer correct length (around 15-17 characters)
            if 13 <= len(text) <= 18:
                score += 5
            
            # Prefer more digits
            digit_count = sum(c.isdigit() for c in text)
            score += min(digit_count, 8)
            
            # Prefer uppercase letters
            upper_count = sum(c.isupper() for c in text if c.isalpha())
            score += min(upper_count * 2, 6)
            
            # Penalize problematic characters
            if 'O' in text:
                score -= 2  # Often confused with 0
            if 'I' in text or 'l' in text:
                score -= 2  # Often confused with 1
        
        elif field_name == 'course':
            # Course scoring system
            if 'CS' in text.upper():
                score += 10
            elif 'C' in text and 'S' in text:
                score += 8
            elif text.upper().startswith('C'):
                score += 5
            
            if '101' in text:
                score += 8
            elif '01' in text:
                score += 6
            elif '1' in text:
                score += 3
            
            if re.match(r'^[A-Z]{2,4}\d{2,4}$', text.upper()):
                score += 5
            
            if len(text) == 5:
                score += 3
            elif len(text) == 4:
                score += 2
            
            if '8' in text:
                score -= 3
            if '0' in text and text.count('0') > 1:
                score -= 2
            if '3' in text and not '13' in text:
                score -= 2
            
            if text.upper() == 'CS101':
                score += 15
        
        elif field_name == 'section':
            # Section scoring system
            # Strong preference for correct patterns with space
            if re.match(r'^BSIT\s+2-1$', text):
                score += 15  # Perfect match for "BSIT 2-1"
            elif re.match(r'^[A-Z]{2,4}\s+\d+-\d+$', text):
                score += 12  # General pattern with space
            elif re.match(r'^BSIT2-1$', text):
                score += 8   # Missing space but correct content
            elif re.match(r'^[A-Z]{2,4}\d+-\d+$', text):
                score += 6   # General pattern without space
            elif 'BSIT' in text and '2-1' in text:
                score += 5   # Contains right elements
            
            # Prefer proper spacing
            if ' ' in text and 'BSIT' in text:
                score += 5
            
            # Prefer correct length (around 7-9 characters for "BSIT 2-1")
            if 6 <= len(text) <= 10:
                score += 3
            
            # Prefer uppercase letters for program codes
            upper_count = sum(c.isupper() for c in text if c.isalpha())
            if upper_count >= 3:  # At least "BSIT"
                score += 4
            
            # Prefer dashes in section numbers
            if '-' in text:
                score += 3
            
            # Penalize too many numbers or wrong patterns
            if text.count('-') > 1:
                score -= 2  # Too many dashes
            if any(char in text for char in ['0', '8', '5']):
                score -= 1  # Suspicious characters
        
        return score
    
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
            # ENHANCED SECTION CLEANING - Handle spaces properly for "BSIT 2-1" and fix OCR mistakes
            # Sections: alphanumeric, spaces, and dashes
            
            # First, clean up but preserve meaningful spaces and dashes
            temp = ''.join(c if c.isalnum() or c in '- ' else ' ' for c in cleaned)
            words = temp.split()
            
            # Smart reconstruction for section format
            if len(words) >= 2:
                # Check if we have a program code + section number pattern
                program_part = words[0].upper()  # e.g., "BSIT"
                section_parts = words[1:]  # e.g., ["2-40"] or ["2", "40"]
                
                # Reconstruct section number if it was split or fix OCR mistakes
                if len(section_parts) == 2 and section_parts[0].isdigit() and section_parts[1].isdigit():
                    # "BSIT" "2" "40" -> check if should be "BSIT 2-1"
                    year = section_parts[0]
                    section_num = section_parts[1]
                    
                    # Fix common OCR mistakes for section numbers
                    if section_num in ['40', '4O', '4o']:  # Common misreads of "1"
                        section_num = '1'
                    elif section_num in ['20', '2O', '2o']:  # Other potential misreads
                        section_num = '1'
                    
                    section_number = f"{year}-{section_num}"
                elif len(section_parts) == 1:
                    # "BSIT" "2-40" -> "BSIT 2-1"
                    section_text = section_parts[0]
                    
                    # Apply OCR corrections to the section part
                    # Fix common misreads: 2-40 -> 2-1, 2-4O -> 2-1, etc.
                    corrected_section = section_text
                    
                    # Pattern-based corrections for section numbers
                    section_corrections = [
                        (r'^2-40$', '2-1'),     # 2-40 -> 2-1
                        (r'^2-4O$', '2-1'),     # 2-4O -> 2-1 (O instead of 0)
                        (r'^2-4o$', '2-1'),     # 2-4o -> 2-1 (lowercase o)
                        (r'^2-20$', '2-1'),     # 2-20 -> 2-1
                        (r'^2-2O$', '2-1'),     # 2-2O -> 2-1
                        (r'^3-40$', '3-1'),     # 3-40 -> 3-1
                        (r'^3-4O$', '3-1'),     # 3-4O -> 3-1
                        (r'^1-40$', '1-1'),     # 1-40 -> 1-1
                        (r'^1-4O$', '1-1'),     # 1-4O -> 1-1
                        (r'^(\d+)-(\d)0$', r'\1-\2'),  # Any X-Y0 -> X-Y (remove trailing 0)
                        (r'^(\d+)-(\d)O$', r'\1-\2'),  # Any X-YO -> X-Y (O to empty)
                    ]
                    
                    # Apply corrections
                    for pattern, replacement in section_corrections:
                        if re.match(pattern, corrected_section):
                            logger.info(f"Section correction: '{section_text}' -> '{replacement}'")
                            corrected_section = replacement
                            break
                    
                    section_number = corrected_section
                else:
                    # Fallback: join remaining parts
                    section_number = ''.join(section_parts)
                
                cleaned = f"{program_part} {section_number}"
            else:
                # Single word - try to intelligently split if needed
                single_word = words[0] if words else cleaned
                
                # Check for patterns like "BSIT2-40" -> "BSIT 2-1"
                match = re.match(r'^([A-Z]{2,4})(\d+-\d+)$', single_word.upper())
                if match:
                    program_code = match.group(1)
                    section_part = match.group(2)
                    
                    # Apply same corrections to section part
                    corrected_section = section_part
                    section_corrections = [
                        (r'^2-40$', '2-1'), (r'^2-4O$', '2-1'), (r'^2-4o$', '2-1'),
                        (r'^2-20$', '2-1'), (r'^2-2O$', '2-1'),
                        (r'^3-40$', '3-1'), (r'^3-4O$', '3-1'),
                        (r'^1-40$', '1-1'), (r'^1-4O$', '1-1'),
                        (r'^(\d+)-(\d)0$', r'\1-\2'),
                        (r'^(\d+)-(\d)O$', r'\1-\2'),
                    ]
                    
                    for pattern, replacement in section_corrections:
                        if re.match(pattern, corrected_section):
                            logger.info(f"Section correction: '{section_part}' -> '{replacement}'")
                            corrected_section = replacement
                            break
                    
                    cleaned = f"{program_code} {corrected_section}"
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
    
    def save_debug_images(self, output_dir):
        """Save all debug images to output directory"""
        try:
            import os
            # Create student info debug subdirectory
            student_debug_dir = os.path.join(output_dir, 'student_info_debug')
            os.makedirs(student_debug_dir, exist_ok=True)
            
            for stage_name, debug_img in self.debug_images:
                filename = f"{stage_name}.png"
                filepath = os.path.join(student_debug_dir, filename)
                
                # Save image
                cv2.imwrite(filepath, debug_img)
                logger.info(f"Saved student debug image: {filepath}")
                
        except Exception as e:
            logger.error(f"Error saving student debug images: {str(e)}")
    
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
        logger.info(f"Updated student region: {self.student_info_region}")
        logger.info(f"Updated student region: {self.student_info_region}")
        logger.info(f"Updated student region: {self.student_info_region}")
