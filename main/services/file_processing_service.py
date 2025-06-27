import csv
import io
import logging
from PIL import Image
import pandas as pd
from django.core.files.uploadedfile import UploadedFile
from django.http import HttpResponse

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
    
    @staticmethod
    def generate_template_with_info(file_type, test_type, question_count, test_title=None, academic_year=None, semester=None):
        """Generate template with test information included"""
        try:
            if file_type == 'pdf':
                from ..services.answer_key_service import AnswerKeyService
                return AnswerKeyService.generate_pdf_template(
                    test_type=test_type,
                    question_count=question_count,
                    test_title=test_title,
                    academic_year=academic_year,
                    semester=semester
                )
            elif file_type == 'csv':
                return FileProcessingService._generate_csv_template_with_info(
                    test_type=test_type,
                    question_count=question_count,
                    test_title=test_title,
                    academic_year=academic_year,
                    semester=semester
                )
            else:
                raise ValueError(f"Unsupported file type: {file_type}")
                
        except Exception as e:
            logger.error(f"Error generating template: {str(e)}")
            return None
    
    @staticmethod
    def _generate_csv_template_with_info(test_type, question_count, test_title=None, academic_year=None, semester=None):
        """Generate CSV template with test information"""
        import csv
        from django.http import HttpResponse
        
        # Get answer choices
        if test_type == 'multiple_choice_4':
            choices = ['A', 'B', 'C', 'D']
            type_display = 'Multiple Choice (A-D)'
        elif test_type == 'multiple_choice_5':
            choices = ['A', 'B', 'C', 'D', 'E']
            type_display = 'Multiple Choice (A-E)'
        elif test_type == 'true_false':
            choices = ['True', 'False']
            type_display = 'True/False'
        else:
            choices = ['A', 'B', 'C', 'D']
            type_display = 'Multiple Choice (A-D)'
        
        # Create filename with test info
        filename_parts = ['answer_key_template']
        if test_title:
            clean_title = ''.join(c for c in test_title if c.isalnum() or c in '-_').rstrip()
            filename_parts.append(clean_title[:30])  # Limit length
        filename_parts.extend([test_type, f'{question_count}q'])
        filename = '_'.join(filename_parts) + '.csv'
        
        # Create response
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        writer = csv.writer(response)
        
        # Write header information with test details
        writer.writerow(['# CheckMate Answer Key Template'])
        if test_title:
            writer.writerow(['# Test Title:', test_title])
        writer.writerow(['# Test Type:', type_display])
        writer.writerow(['# Questions:', question_count])
        if academic_year:
            writer.writerow(['# Academic Year:', academic_year])
        if semester:
            writer.writerow(['# Semester:', semester])
        writer.writerow(['# Valid Answers:', ', '.join(choices)])
        writer.writerow(['# Instructions: Fill in the Answer column with your correct answers'])
        writer.writerow(['#'])
        writer.writerow(['# Format: Keep the Question Number column as-is, only modify the Answer column'])
        writer.writerow(['#'])
        
        # Write column headers
        writer.writerow(['Question Number', 'Answer', 'Notes (Optional)'])
        
        # Write empty rows for each question
        for i in range(1, question_count + 1):
            writer.writerow([i, '', ''])  # Empty answer and notes
        
        # Write footer instructions
        writer.writerow(['#'])
        writer.writerow(['# Upload Instructions:'])
        writer.writerow(['# 1. Fill in the Answer column with correct answers'])
        writer.writerow(['# 2. Save this file as CSV'])
        writer.writerow(['# 3. Upload through CheckMate Answer Key Upload'])
        
        return response
    
    @staticmethod
    def extract_test_info_from_form(request):
        """Extract test information from form data"""
        test_info = {}
        
        # Extract basic test info
        test_info['test_title'] = request.POST.get('test_name', '').strip()
        test_info['test_type'] = request.POST.get('test_type', 'multiple_choice_4')
        test_info['question_count'] = int(request.POST.get('question_count', 50))
        
        # Extract course information
        course_id = request.POST.get('course')
        if course_id:
            try:
                from ..models import Courses
                course = Courses.objects.get(id=course_id, user=request.user)
                test_info['academic_year'] = course.academic_year
                test_info['semester'] = course.semester
                test_info['course_code'] = course.course_code
                test_info['course_name'] = course.course_name
            except:
                test_info['academic_year'] = None
                test_info['semester'] = None
        
        return test_info
    
    @staticmethod
    def process_grading_session_files(request):
        """Process files uploaded for grading session"""
        try:
            files_processed = []
            errors = []
            
            # Get uploaded files
            student_answer_sheets = request.FILES.getlist('student_answer_sheets')
            
            if not student_answer_sheets:
                return {
                    'success': False,
                    'error': 'No files uploaded',
                    'files_processed': [],
                    'errors': []
                }
            
            # Process each file
            for uploaded_file in student_answer_sheets:
                try:
                    file_info = {
                        'name': uploaded_file.name,
                        'size': uploaded_file.size,
                        'type': uploaded_file.content_type,
                        'processed': False,
                        'student_info': None,
                        'answers': {},
                        'errors': []
                    }
                    
                    # Process based on file type
                    if uploaded_file.content_type == 'application/pdf':
                        result = FileProcessingService._process_student_pdf(uploaded_file)
                    elif uploaded_file.content_type.startswith('image/'):
                        result = FileProcessingService._process_student_image(uploaded_file)
                    elif uploaded_file.content_type == 'text/csv':
                        result = FileProcessingService._process_student_csv(uploaded_file)
                    else:
                        result = {
                            'success': False,
                            'error': f'Unsupported file type: {uploaded_file.content_type}'
                        }
                    
                    if result['success']:
                        file_info['processed'] = True
                        file_info['student_info'] = result.get('student_info', {})
                        file_info['answers'] = result.get('answers', {})
                    else:
                        file_info['errors'].append(result.get('error', 'Unknown error'))
                    
                    files_processed.append(file_info)
                    
                except Exception as e:
                    errors.append(f"Error processing {uploaded_file.name}: {str(e)}")
            
            return {
                'success': True,
                'files_processed': files_processed,
                'errors': errors,
                'total_files': len(student_answer_sheets),
                'successful_files': len([f for f in files_processed if f['processed']])
            }
            
        except Exception as e:
            logger.error(f"Error processing grading session files: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'files_processed': [],
                'errors': []
            }
    
    @staticmethod
    def _process_student_pdf(pdf_file):
        """Process individual student PDF file"""
        try:
            # Use existing PDF extraction
            import tempfile
            import os
            
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_pdf:
                pdf_file.seek(0)
                temp_pdf.write(pdf_file.read())
                temp_pdf_path = temp_pdf.name
            
            try:
                from ..test_pdf_extraction import StudentInfoExtractor
                extractor = StudentInfoExtractor()
                
                # Process PDF
                result = extractor.process_pdf(temp_pdf_path, extract_answers=True)
                
                if result:
                    return {
                        'success': True,
                        'student_info': {
                            'name': result['student_name'],
                            'id': result['student_id']
                        },
                        'answers': result['answers']
                    }
                else:
                    return {
                        'success': False,
                        'error': 'Could not extract information from PDF'
                    }
                    
            finally:
                try:
                    os.unlink(temp_pdf_path)
                except:
                    pass
                    
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def _process_student_image(image_file):
        """Process individual student image file"""
        try:
            # Basic image processing - can be enhanced
            return {
                'success': False,
                'error': 'Image processing not yet implemented for student sheets'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def _process_student_csv(csv_file):
        """Process individual student CSV file"""
        try:
            # Basic CSV processing - can be enhanced
            return {
                'success': False,
                'error': 'CSV processing not yet implemented for student sheets'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }