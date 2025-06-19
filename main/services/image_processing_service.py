import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import logging
import math
import os
import tempfile
import cv2
import csv
import io

logger = logging.getLogger(__name__)

class ImageProcessingService:
    """Service for processing answer key images and detecting filled bubbles"""
    
    @staticmethod
    def process_answer_key_image(image_file, test_type, question_count, enhance_image=True):
        """
        Process uploaded answer key image and detect filled bubbles
        """
        try:
            # Reset file pointer
            image_file.seek(0)
            
            # Convert uploaded file to PIL Image
            image = Image.open(image_file)
            
            # Convert to RGB if not already
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Enhance image if requested
            if enhance_image:
                image = ImageProcessingService._enhance_image(image)
            
            # Extract answers using AI detection
            from ..services.answer_extraction import AnswerExtractor
            extractor = AnswerExtractor()
            
            result = extractor.extract_answers_from_image(image, test_type, question_count)
            
            return {
                'success': True,
                'answers': result.get('answers', {}),
                'confidence_scores': result.get('confidence_scores', {}),
                'metadata': {
                    'method': 'AI Computer Vision',
                    'image_size': image.size,
                    'enhanced': enhance_image,
                    'total_detected': len(result.get('answers', {}))
                }
            }
            
        except Exception as e:
            logger.error(f"Error processing answer key image: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'answers': {},
                'confidence_scores': {},
                'metadata': {}
            }
    
    @staticmethod
    def process_with_ocr_fallback(image_file, test_type, question_count):
        """Fallback OCR processing when AI detection fails"""
        try:
            # Reset file pointer
            image_file.seek(0)
            
            # Simple fallback - return empty results for now
            # This can be enhanced with actual OCR processing
            return {
                'success': False,
                'error': 'OCR fallback not yet implemented',
                'answers': {},
                'confidence_scores': {},
                'metadata': {'method': 'OCR Fallback'}
            }
            
        except Exception as e:
            logger.error(f"Error in OCR fallback: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'answers': {},
                'confidence_scores': {},
                'metadata': {}
            }
    
    @staticmethod
    def _enhance_image(image):
        """Enhance image quality for better processing"""
        try:
            # Convert PIL to OpenCV
            cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            
            # Apply basic enhancements
            # 1. Increase contrast
            lab = cv2.cvtColor(cv_image, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            l = clahe.apply(l)
            enhanced = cv2.merge([l, a, b])
            enhanced = cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)
            
            # 2. Sharpen
            kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
            enhanced = cv2.filter2D(enhanced, -1, kernel)
            
            # Convert back to PIL
            enhanced_image = Image.fromarray(cv2.cvtColor(enhanced, cv2.COLOR_BGR2RGB))
            
            return enhanced_image
            
        except Exception as e:
            logger.warning(f"Image enhancement failed: {str(e)}, using original")
            return image
    
    @staticmethod
    def process_csv_file(csv_file, test_type, question_count, validate_format=True):
        """Process uploaded CSV file and extract answers"""
        try:
            # Reset file pointer and read content
            csv_file.seek(0)
            content = csv_file.read()
            
            # Handle different encodings
            try:
                content = content.decode('utf-8')
            except UnicodeDecodeError:
                try:
                    content = content.decode('utf-8-sig')  # Handle BOM
                except UnicodeDecodeError:
                    content = content.decode('latin-1')  # Fallback
            
            # Parse CSV
            csv_reader = csv.reader(io.StringIO(content))
            rows = list(csv_reader)
            
            if not rows:
                return {
                    'success': False,
                    'error': 'CSV file is empty',
                    'answers': {}
                }
            
            # Extract answers from CSV
            answers = {}
            
            # Look for data rows (skip headers and comments)
            for row in rows:
                if not row or len(row) < 2:
                    continue
                
                # Skip comment rows
                if row[0].startswith('#'):
                    continue
                
                # Skip header rows
                if row[0].lower() in ['question', 'question_number', 'q']:
                    continue
                
                try:
                    # Try to parse question number and answer
                    question_num = int(row[0])
                    answer = row[1].strip().upper()
                    
                    # Validate question number
                    if 1 <= question_num <= question_count:
                        # Validate answer based on test type
                        valid_answers = ImageProcessingService._get_valid_answers(test_type)
                        if answer in valid_answers:
                            answers[question_num] = answer
                        else:
                            logger.warning(f"Invalid answer '{answer}' for question {question_num}")
                    
                except (ValueError, IndexError):
                    continue
            
            return {
                'success': True,
                'answers': answers,
                'confidence_scores': {q: 1.0 for q in answers.keys()},  # High confidence for manual CSV
                'metadata': {
                    'method': 'CSV Import',
                    'total_rows': len(rows),
                    'valid_answers': len(answers),
                    'encoding_used': 'auto-detected'
                }
            }
            
        except Exception as e:
            logger.error(f"Error processing CSV file: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'answers': {}
            }
    
    @staticmethod
    def _get_valid_answers(test_type):
        """Get valid answer choices for test type"""
        if test_type == 'multiple_choice_4':
            return ['A', 'B', 'C', 'D']
        elif test_type == 'multiple_choice_5':
            return ['A', 'B', 'C', 'D', 'E']
        elif test_type == 'true_false':
            return ['TRUE', 'FALSE', 'T', 'F']
        else:
            return ['A', 'B', 'C', 'D']
    
    @staticmethod
    def process_pdf_file(pdf_file, test_type, question_count, enhance_image=True):
        """Process uploaded PDF file and extract answers"""
        try:
            import tempfile
            import os
            
            # Save PDF to temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_pdf:
                pdf_file.seek(0)
                temp_pdf.write(pdf_file.read())
                temp_pdf_path = temp_pdf.name
            
            try:
                # Convert PDF to images using existing extraction code
                from ..test_pdf_extraction import StudentInfoExtractor
                extractor = StudentInfoExtractor()
                
                # Convert PDF to images
                images = extractor.pdf_to_images(temp_pdf_path)
                
                if not images:
                    return {
                        'success': False,
                        'error': 'Could not convert PDF to images',
                        'answers': {}
                    }
                
                # Process first page for answers
                first_page = images[0]
                
                # Extract answers using AI
                result = extractor.extract_answers_ai(first_page, debug=False)
                
                return {
                    'success': True,
                    'answers': result.get('answers', {}),
                    'confidence_scores': result.get('confidence_scores', {}),
                    'metadata': {
                        'method': 'PDF + AI Computer Vision',
                        'pages_processed': len(images),
                        'layout_version': result.get('stats', {}).get('layout_version', 'unknown'),
                        'total_detected': len(result.get('answers', {}))
                    }
                }
                
            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_pdf_path)
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"Error processing PDF file: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'answers': {}
            }
       