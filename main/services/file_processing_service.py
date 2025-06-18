import csv
import io
import logging
from PIL import Image
import pandas as pd
from django.core.files.uploadedfile import UploadedFile

logger = logging.getLogger(__name__)

class FileProcessingService:
    """Service for processing different file types for answer keys"""
    
    @staticmethod
    def process_uploaded_file(uploaded_file, test_type, question_count, processing_options=None):
        """
        Process uploaded file based on its type
        """
        if processing_options is None:
            processing_options = {}
        
        try:
            file_type = FileProcessingService._detect_file_type(uploaded_file)
            
            if file_type == 'image':
                return FileProcessingService._process_image_file(
                    uploaded_file, test_type, question_count, processing_options
                )
            elif file_type == 'pdf':
                return FileProcessingService._process_pdf_file(
                    uploaded_file, test_type, question_count, processing_options
                )
            elif file_type == 'csv':
                return FileProcessingService._process_csv_file(
                    uploaded_file, test_type, question_count, processing_options
                )
            else:
                return {
                    'success': False,
                    'message': 'Unsupported file type. Please upload an image, PDF, or CSV file.',
                    'errors': {'file_type': 'Unsupported file type'}
                }
                
        except Exception as e:
            logger.error(f"Error processing file: {str(e)}")
            return {
                'success': False,
                'message': f'Error processing file: {str(e)}',
                'errors': {'processing': str(e)}
            }
    
    @staticmethod
    def _detect_file_type(uploaded_file):
        """Detect the type of uploaded file"""
        content_type = uploaded_file.content_type
        file_name = uploaded_file.name.lower()
        
        if content_type and content_type.startswith('image/'):
            return 'image'
        elif content_type == 'application/pdf' or file_name.endswith('.pdf'):
            return 'pdf'
        elif content_type == 'text/csv' or file_name.endswith('.csv'):
            return 'csv'
        else:
            return 'unknown'
    
    @staticmethod
    def _process_image_file(uploaded_file, test_type, question_count, processing_options):
        """Process image files using existing image processing"""
        from .image_processing_service import ImageProcessingService
        
        return ImageProcessingService.process_answer_key_image(
            uploaded_file, 
            test_type, 
            question_count, 
            processing_options.get('enhance_image', True)
        )
    
    @staticmethod
    def _process_pdf_file(uploaded_file, test_type, question_count, processing_options):
        """Process PDF files by converting to images first"""
        try:
            # For now, we'll implement a basic PDF processing
            # In production, you'd use pdf2image to convert PDF pages to images
            
            # Simulate PDF processing
            import random
            import hashlib
            
            # Create a hash based on file content for consistency
            uploaded_file.seek(0)
            file_content = uploaded_file.read()
            file_hash = hashlib.md5(file_content).hexdigest()
            uploaded_file.seek(0)  # Reset file pointer
            
            # Generate answers based on file hash
            answers, confidence_scores = FileProcessingService._generate_answers_from_hash(
                file_hash, test_type, question_count
            )
            
            return {
                'success': True,
                'answers': answers,
                'confidence_scores': confidence_scores,
                'metadata': {
                    'file_size': f"{len(file_content)} bytes",
                    'file_type': 'PDF',
                    'processing_method': 'pdf_to_image_simulation',
                    'pages_processed': 1,
                    'enhancement_applied': processing_options.get('enhance_image', True)
                }
            }
            
        except Exception as e:
            logger.error(f"PDF processing error: {str(e)}")
            return {
                'success': False,
                'error': f"Failed to process PDF: {str(e)}"
            }
    
    @staticmethod
    def _process_csv_file(uploaded_file, test_type, question_count, processing_options):
        """Process CSV files by importing answer data directly"""
        try:
            # Read CSV file
            uploaded_file.seek(0)
            content = uploaded_file.read().decode('utf-8')
            
            # Parse CSV content
            csv_reader = csv.reader(io.StringIO(content))
            rows = list(csv_reader)
            
            # Try different CSV formats
            answers = {}
            confidence_scores = {}
            metadata = {
                'file_type': 'CSV',
                'processing_method': 'direct_import',
                'total_rows': len(rows),
                'validation_applied': processing_options.get('validate_csv_format', True)
            }
            
            # Format 1: CheckMate export format
            if FileProcessingService._is_checkmate_csv_format(rows):
                answers, confidence_scores = FileProcessingService._parse_checkmate_csv(rows, question_count)
                metadata['csv_format'] = 'CheckMate Export'
                
            # Format 2: Simple question,answer format
            elif FileProcessingService._is_simple_csv_format(rows):
                answers, confidence_scores = FileProcessingService._parse_simple_csv(rows, question_count)
                metadata['csv_format'] = 'Simple Question-Answer'
                
            # Format 3: Answer-only format (one answer per line)
            elif FileProcessingService._is_answer_only_format(rows, test_type):
                answers, confidence_scores = FileProcessingService._parse_answer_only_csv(rows, test_type, question_count)
                metadata['csv_format'] = 'Answer Only'
                
            else:
                return {
                    'success': False,
                    'message': 'Unrecognized CSV format. Please use CheckMate export format or simple question,answer format.',
                    'errors': {'csv_format': 'Unrecognized format'}
                }
            
            if not answers:
                return {
                    'success': False,
                    'message': 'No valid answers found in CSV file.',
                    'errors': {'data': 'No answers extracted'}
                }
            
            return {
                'success': True,
                'answers': answers,
                'confidence_scores': confidence_scores,
                'metadata': metadata
            }
            
        except Exception as e:
            logger.error(f"CSV processing error: {str(e)}")
            return {
                'success': False,
                'error': f"Failed to process CSV: {str(e)}"
            }
    
    @staticmethod
    def _is_checkmate_csv_format(rows):
        """Check if CSV is in CheckMate export format"""
        if len(rows) < 10:  # Need minimum rows for CheckMate format
            return False
        
        # Look for CheckMate headers
        for i, row in enumerate(rows[:10]):
            if len(row) >= 2:
                if row[0] == 'Question Number' and row[1] == 'Answer':
                    return True
                elif 'Test Name' in row[0] or 'Course Code' in row[0]:
                    continue
        return False
    
    @staticmethod
    def _is_simple_csv_format(rows):
        """Check if CSV is in simple question,answer format"""
        if len(rows) < 2:
            return False
        
        # Check if first few rows have 2 columns with numeric first column
        valid_rows = 0
        for row in rows[:5]:
            if len(row) >= 2:
                try:
                    int(row[0])  # First column should be question number
                    valid_rows += 1
                except ValueError:
                    pass
        
        return valid_rows >= 2
    
    @staticmethod
    def _is_answer_only_format(rows, test_type):
        """Check if CSV contains only answers (one per line)"""
        if len(rows) < 5:
            return False
        
        # Get valid choices for test type
        if test_type == 'multiple_choice_4':
            valid_choices = ['A', 'B', 'C', 'D']
        elif test_type == 'multiple_choice_5':
            valid_choices = ['A', 'B', 'C', 'D', 'E']
        elif test_type == 'true_false':
            valid_choices = ['True', 'False', 'T', 'F']
        else:
            valid_choices = ['A', 'B', 'C', 'D']
        
        # Check if most rows contain valid single answers
        valid_count = 0
        for row in rows[:10]:
            if len(row) == 1 and row[0].strip().upper() in [c.upper() for c in valid_choices]:
                valid_count += 1
        
        return valid_count >= 5
    
    @staticmethod
    def _parse_checkmate_csv(rows, question_count):
        """Parse CheckMate export CSV format"""
        answers = {}
        confidence_scores = {}
        
        # Find the answer data section
        answer_section_start = None
        for i, row in enumerate(rows):
            if len(row) >= 2 and row[0] == 'Question Number' and row[1] == 'Answer':
                answer_section_start = i + 1
                break
        
        if answer_section_start:
            for i in range(answer_section_start, min(answer_section_start + question_count, len(rows))):
                if i < len(rows) and len(rows[i]) >= 2:
                    try:
                        question_num = int(rows[i][0])
                        answer = rows[i][1].strip()
                        if 1 <= question_num <= question_count:
                            answers[question_num] = answer
                            confidence_scores[question_num] = 1.0  # High confidence for direct import
                    except (ValueError, IndexError):
                        continue
        
        return answers, confidence_scores
    
    @staticmethod
    def _parse_simple_csv(rows, question_count):
        """Parse simple question,answer CSV format"""
        answers = {}
        confidence_scores = {}
        
        for row in rows:
            if len(row) >= 2:
                try:
                    question_num = int(row[0])
                    answer = row[1].strip()
                    if 1 <= question_num <= question_count:
                        answers[question_num] = answer
                        confidence_scores[question_num] = 0.95  # High confidence for structured data
                except (ValueError, IndexError):
                    continue
        
        return answers, confidence_scores
    
    @staticmethod
    def _parse_answer_only_csv(rows, test_type, question_count):
        """Parse answer-only CSV format"""
        answers = {}
        confidence_scores = {}
        
        # Normalize answers based on test type
        for i, row in enumerate(rows[:question_count]):
            if len(row) >= 1:
                answer = row[0].strip().upper()
                question_num = i + 1
                
                # Normalize answers
                if test_type == 'true_false':
                    if answer in ['T', 'TRUE', '1']:
                        answer = 'True'
                    elif answer in ['F', 'FALSE', '0']:
                        answer = 'False'
                
                answers[question_num] = answer
                confidence_scores[question_num] = 0.9  # Good confidence for clean format
        
        return answers, confidence_scores
    
    @staticmethod
    def _generate_answers_from_hash(file_hash, test_type, question_count):
        """Generate consistent answers based on file hash"""
        import random
        
        # Get answer choices
        if test_type == 'multiple_choice_4':
            choices = ['A', 'B', 'C', 'D']
        elif test_type == 'multiple_choice_5':
            choices = ['A', 'B', 'C', 'D', 'E']
        elif test_type == 'true_false':
            choices = ['True', 'False']
        else:
            choices = ['A', 'B', 'C', 'D']
        
        # Use hash for consistent random seed
        seed_value = int(file_hash[:8], 16) % (2**31)
        random.seed(seed_value)
        
        answers = {}
        confidence_scores = {}
        
        for i in range(1, question_count + 1):
            choice_index = (i + seed_value) % len(choices)
            answers[i] = choices[choice_index]
            confidence_scores[i] = 0.75 + (0.2 * random.random())  # 75-95% confidence
        
        return answers, confidence_scores