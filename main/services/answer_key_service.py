import csv
from django.shortcuts import get_object_or_404
from django.http import HttpResponse, JsonResponse
from ..models import TestInformation, TestAnswerKey
from .image_processing_service import ImageProcessingService

class AnswerKeyService:
    """Service class for answer key operations"""
    
    @staticmethod
    def get_user_tests(user):
        """Get all tests for a user with related answer keys"""
        return TestInformation.objects.filter(user=user).prefetch_related('answer_keys')
    
    @staticmethod
    def create_temp_test_data(form_data):
        """Create temporary test data from form"""
        return {
            'course_id': form_data['course'].id,
            'test_name': form_data['test_name'],
            'test_type': form_data['test_type'],
            'question_count': form_data['question_count'],
        }
    
    @staticmethod
    def create_temp_test_object(temp_data):
        """Create a temporary test object for processing"""
        from ..models import TestInformation, Courses
        
        # Get the course object
        course = Courses.objects.get(id=temp_data['course_id'])
        
        test_info = TestInformation(
            course=course,
            test_name=temp_data['test_name'],
            test_type=temp_data['test_type'],
            question_count=temp_data['question_count'],
        )
        return test_info
    
    @staticmethod
    def get_test_by_id(test_id, user):
        """Get test by ID for specific user"""
        return get_object_or_404(TestInformation, id=test_id, user=user)
    
    @staticmethod
    def save_test_to_db(test_info, user):
        """Save the test information to database"""
        test_info.user = user
        test_info.name = test_info.test_name  # Set name field
        test_info.save()
        return test_info
    
    @staticmethod
    def save_answers(test_info, form_data):
        """Save answers for a test"""
        # Delete existing answers
        TestAnswerKey.objects.filter(test_information=test_info).delete()
        
        # Save new answers
        answer_keys = []
        for i in range(1, test_info.question_count + 1):
            answer_key = TestAnswerKey(
                test_information=test_info,
                question_number=i,
                answer=form_data[f'question_{i}']
            )
            answer_keys.append(answer_key)
        
        TestAnswerKey.objects.bulk_create(answer_keys)
        return len(answer_keys)
    
    @staticmethod
    def get_existing_answers(test_info):
        """Get existing answers as initial data for form"""
        existing_answers = TestAnswerKey.objects.filter(test_information=test_info)
        initial_data = {}
        for answer_key in existing_answers:
            initial_data[f'question_{answer_key.question_number}'] = answer_key.answer
        return initial_data
    
    @staticmethod
    def delete_test(test_id, user):
        """Delete a test and return test name"""
        test_info = get_object_or_404(TestInformation, id=test_id, user=user)
        test_name = test_info.test_name
        test_info.delete()
        return test_name
    
    @staticmethod
    def get_test_with_answers(test_id, user):
        """Get test with all answers for printing/exporting"""
        test_info = get_object_or_404(TestInformation, id=test_id, user=user)
        answer_keys = TestAnswerKey.objects.filter(test_information=test_info).order_by('question_number')
        return test_info, answer_keys
    
    # Export Methods
    @staticmethod
    def generate_csv_response(test_info, answer_keys, show_answers=True):
        """Generate CSV response for download"""
        import csv
        from django.http import HttpResponse
        
        if show_answers:
            filename_suffix = "_answer_key"
            sheet_type = "Answer Key"
        else:
            filename_suffix = "_answer_sheet"
            sheet_type = "Answer Sheet"
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{test_info.test_name}{filename_suffix}.csv"'
        
        writer = csv.writer(response)
        
        # Header with course information
        writer.writerow(['Test Name', test_info.test_name])
        writer.writerow(['Type', sheet_type])
        if test_info.course:
            writer.writerow(['Course Code', test_info.course.course_code])
            writer.writerow(['Course Name', test_info.course.course_name])
            if test_info.course.academic_year:
                writer.writerow(['Academic Year', test_info.course.academic_year])
            if test_info.course.semester:
                writer.writerow(['Semester', test_info.course.semester])
        writer.writerow(['Test Type', test_info.get_test_type_display()])
        writer.writerow(['Total Questions', test_info.question_count])
        writer.writerow(['Created Date', test_info.created_at.strftime('%Y-%m-%d')])
        writer.writerow([])  # Empty row
        
        if not show_answers:
            # Add student information section for answer sheets
            writer.writerow(['STUDENT INFORMATION'])
            writer.writerow(['Name:', ''])
            writer.writerow(['Date:', ''])
            writer.writerow(['Course:', ''])
            writer.writerow(['Section:', ''])
            writer.writerow([])  # Empty row
            writer.writerow(['INSTRUCTIONS'])
            writer.writerow(['Fill in your answers in the Student Answer column'])
            writer.writerow(['Use only the valid answer choices for this test type'])
            writer.writerow(['Valid choices:', ', '.join(test_info.get_answer_choices())])
            writer.writerow([])  # Empty row
        
        # Answer section header
        if show_answers:
            writer.writerow(['Question Number', 'Correct Answer'])
            # Answer key data
            for answer in answer_keys:
                writer.writerow([answer.question_number, answer.answer])
        else:
            writer.writerow(['Question Number', 'Student Answer', 'Notes'])
            # Blank sheet data for student completion
            for answer in answer_keys:
                writer.writerow([answer.question_number, '', ''])  # Empty answer and notes columns
        
        return response
    
    @staticmethod
    def _write_csv_header(writer, test_info):
        """Write CSV header section"""
        writer.writerow(['# CheckMate Answer Key - Machine Readable Format'])
        writer.writerow(['# Test Name:', test_info.test_name])
        writer.writerow(['# Test Type:', test_info.test_type])
        writer.writerow(['# Question Count:', test_info.question_count])
        writer.writerow(['# Answer Choices:', ','.join(test_info.get_answer_choices())])
        writer.writerow(['# Created:', test_info.created_at.isoformat()])
        writer.writerow(['# Generated:', test_info.updated_at.isoformat()])
        writer.writerow([])  # Empty row separator
    
    @staticmethod
    def _write_csv_data(writer, test_info, answer_keys):
        """Write CSV answer data section"""
        writer.writerow(['question_number', 'correct_answer', 'answer_index'])
        
        answer_choices = test_info.get_answer_choices()
        
        if answer_keys:
            for answer_key in answer_keys:
                try:
                    answer_index = answer_choices.index(answer_key.answer)
                except ValueError:
                    answer_index = -1  # Invalid answer
                
                writer.writerow([
                    answer_key.question_number,
                    answer_key.answer,
                    answer_index
                ])
        else:
            # Write placeholder for empty answer key
            for i in range(1, test_info.question_count + 1):
                writer.writerow([i, '', -1])
    
    @staticmethod
    def _write_csv_metadata(writer, test_info, answer_keys):
        """Write CSV metadata section"""
        writer.writerow([])
        writer.writerow(['# Metadata for Verification'])
        writer.writerow(['# Total Questions Expected:', test_info.question_count])
        writer.writerow(['# Total Answers Provided:', len(answer_keys)])
        writer.writerow(['# Answer Choice Count:', len(test_info.get_answer_choices())])
        writer.writerow(['# Format Version:', '1.0'])
        writer.writerow(['# Compatible with CheckMate Image Processing'])
    
    @staticmethod
    def _write_csv_mapping(writer, test_info):
        """Write CSV answer choice mapping section"""
        writer.writerow([])
        writer.writerow(['# Answer Choice Mapping'])
        writer.writerow(['index', 'choice', 'display'])
        for i, choice in enumerate(test_info.get_answer_choices()):
            display = 'T' if choice == 'True' else 'F' if choice == 'False' else choice
            writer.writerow([i, choice, display])
    
    @staticmethod
    def generate_print_data(test_info, answer_keys):
        """Generate data structure for JSON printing"""
        course_info = {}
        if test_info.course:
            course_info = {
                'course_code': test_info.course.course_code,
                'course_name': test_info.course.course_name,
                'academic_year': test_info.course.academic_year or '',
                'semester': test_info.course.semester or ''
            }
        
        return {
            'test_name': test_info.test_name,
            'course': course_info,
            'test_type': test_info.get_test_type_display(),
            'question_count': test_info.question_count,
            'created_date': test_info.created_at.strftime('%Y-%m-%d'),
            'answers': [
                {
                    'question_number': answer.question_number,
                    'answer': answer.answer
                }
                for answer in answer_keys
            ]
        }
    
    @staticmethod
    def process_uploaded_image(image_file, test_type, question_count, auto_detect_format=True, enhance_image=True):
        """Process uploaded answer key image and extract answers"""
        try:
            # Try bubble detection first (matches our printed format)
            result = ImageProcessingService.process_answer_key_image(
                image_file, test_type, question_count, enhance_image
            )
            
            if result['success']:
                # Calculate average confidence
                confidence_scores = result.get('confidence_scores', {})
                avg_confidence = sum(confidence_scores.values()) / len(confidence_scores) if confidence_scores else 0.5
                
                processing_metadata = result.get('metadata', {})
                processing_metadata.update({
                    'avg_confidence': avg_confidence * 100,  # Convert to percentage
                    'total_questions_detected': len(result['answers']),
                    'questions_with_high_confidence': len([c for c in confidence_scores.values() if c > 0.8])
                })
                
                return {
                    'success': True,
                    'answers': result['answers'],
                    'confidence_scores': {k: v * 100 for k, v in confidence_scores.items()},  # Convert to percentage
                    'metadata': processing_metadata,
                    'message': f'Successfully extracted {len(result["answers"])} answers from image'
                }
            else:
                # Fallback to OCR if bubble detection fails
                if auto_detect_format:
                    # Reset file pointer
                    image_file.seek(0)
                    ocr_result = ImageProcessingService.process_with_ocr_fallback(
                        image_file, test_type, question_count
                    )
                    
                    if ocr_result['success']:
                        return {
                            'success': True,
                            'answers': ocr_result['answers'],
                            'confidence_scores': ocr_result['confidence_scores'],
                            'metadata': ocr_result['metadata'],
                            'message': 'Extracted answers using OCR (fallback method)'
                        }
                
                return {
                    'success': False,
                    'message': 'Could not process the image. Please ensure it\'s a clear answer sheet.',
                    'errors': {'processing': result.get('error', 'Unknown error')}
                }
                
        except Exception as e:
            return {
                'success': False,
                'message': f'Error processing image: {str(e)}',
                'errors': {'processing': str(e)}
            }
    
    @staticmethod
    def create_test_from_upload(user, test_data):
        """Create test and answer keys from uploaded data"""
        from ..models import TestInformation, TestAnswerKey, Courses
        
        try:
            # Get course
            course = Courses.objects.get(id=test_data['course_id'], user=user)
            
            # Create test information
            test_info = TestInformation.objects.create(
                user=user,
                course=course,
                name=test_data['test_name'],
                test_name=test_data['test_name'],
                test_type=test_data['test_type'],
                question_count=test_data['question_count'],
                status='draft'  # Mark as active since it's processed
            )
            
            # Create answer keys
            for question_num, answer in test_data['extracted_answers'].items():
                TestAnswerKey.objects.create(
                    test_information=test_info,
                    question_number=question_num,
                    answer=answer
                )
            
            return test_info
            
        except Exception as e:
            raise Exception(f"Error creating test from upload: {str(e)}")

    @staticmethod
    def generate_csv_template(test_type, question_count):
        """Generate a blank CSV template for manual answer entry"""
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
        
        # Create response
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="answer_key_template_{test_type}_{question_count}q.csv"'
        
        writer = csv.writer(response)
        
        # Write header information
        writer.writerow(['# CheckMate Answer Key Template'])
        writer.writerow(['# Test Type:', type_display])
        writer.writerow(['# Questions:', question_count])
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
    def generate_pdf_template(test_type, question_count):
        """Generate a compact PDF template with improved padding and spacing"""
        import io
        import logging
        from django.http import HttpResponse
        
        logger = logging.getLogger(__name__)
        
        try:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import letter, A4
            from reportlab.lib.units import inch
            
            response = HttpResponse(content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="ALPHA_V4_template_{test_type}_{question_count}q.pdf"'
            
            buffer = io.BytesIO()
            
            # Get test type info
            if test_type == 'multiple_choice_4':
                type_display = 'Multiple Choice (A, B, C, D)'
                choices = ['A', 'B', 'C', 'D']
            elif test_type == 'multiple_choice_5':
                type_display = 'Multiple Choice (A, B, C, D, E)'
                choices = ['A', 'B', 'C', 'D', 'E']
            elif test_type == 'true_false':
                type_display = 'True or False'
                choices = ['T', 'F']
            else:
                type_display = 'Multiple Choice (A, B, C, D)'
                choices = ['A', 'B', 'C', 'D']
            
            c = canvas.Canvas(buffer, pagesize=A4)
            width, height = A4
            
            # ALPHA V4 - IMPROVED LAYOUT PARAMETERS
            margin = 0.4 * inch  # Slightly larger margins for better appearance
            content_width = width - 2 * margin
            
            # OPTIMIZED GRID - 4 columns with better spacing
            columns = 4  # 4 columns of questions
            questions_per_page = 100  # 100 questions per page (25 per column)
            questions_per_column = 25
            column_width = content_width / columns
            
            # IMPROVED spacing for better readability
            row_height = 14  # Slightly increased from 12 for better spacing
            bubble_radius = 5  # Increased from 4 for better visibility
            bubble_spacing = 16  # Increased from 14 for better spacing between choices
            
            current_question = 1
            page_num = 1
            
            while current_question <= question_count:
                # IMPROVED HEADER with better padding
                header_y = height - 0.3 * inch  # More space from top
                header_height = 45  # Slightly increased
                
                c.setLineWidth(2)
                c.rect(margin, header_y - header_height, content_width, header_height, stroke=1, fill=0)
                
                # Title with better vertical centering
                c.setFont("Helvetica-Bold", 13)  # Slightly smaller for better fit
                title_text = f"ALPHA V4 - {type_display}"
                text_width = c.stringWidth(title_text, "Helvetica-Bold", 13)
                title_x = margin + (content_width - text_width) / 2
                c.drawString(title_x, header_y - 16, title_text)  # Better vertical position
                
                # Question range and page info with better spacing
                questions_this_page = min(questions_per_page, question_count - current_question + 1)
                end_question = current_question + questions_this_page - 1
                
                c.setFont("Helvetica", 9)
                info_text = f"Questions {current_question}-{end_question} | Total: {question_count} | Page {page_num}"
                text_width = c.stringWidth(info_text, "Helvetica", 9)
                info_x = margin + (content_width - text_width) / 2
                c.drawString(info_x, header_y - 32, info_text)  # Better spacing from title
                
                # IMPROVED STUDENT INFO (only on first page)
                if page_num == 1:
                    student_y = header_y - header_height - 15  # More spacing from header
                    info_height = 55  # Slightly increased height
                    
                    c.setLineWidth(1)
                    c.rect(margin, student_y - info_height, content_width, info_height, stroke=1, fill=0)
                    
                    c.setFont("Helvetica-Bold", 10)
                    c.drawString(margin + 8, student_y - 18, "STUDENT INFO")  # Better padding from edge
                    
                    c.setFont("Helvetica", 9)
                    # Better spacing and alignment for form fields
                    c.drawString(margin + 12, student_y - 34, "Name:")
                    c.line(margin + 55, student_y - 36, margin + content_width/2 - 12, student_y - 36)
                    
                    c.drawString(margin + content_width/2 + 12, student_y - 34, "ID:")
                    c.line(margin + content_width/2 + 35, student_y - 36, margin + content_width - 12, student_y - 36)
                    
                    c.drawString(margin + 12, student_y - 50, "Course:")
                    c.line(margin + 55, student_y - 52, margin + content_width/2 - 12, student_y - 52)
                    
                    c.drawString(margin + content_width/2 + 12, student_y - 50, "Section:")
                    c.line(margin + content_width/2 + 55, student_y - 52, margin + content_width - 12, student_y - 52)
                    
                    grid_start_y = student_y - info_height - 20  # More spacing before grid
                else:
                    grid_start_y = header_y - header_height - 20  # More spacing for non-first pages
                
                # IMPROVED ANSWER GRID with better padding
                grid_height = questions_per_column * row_height + 40  # Increased header space
                c.setLineWidth(2)
                c.rect(margin, grid_start_y - grid_height, content_width, grid_height, stroke=1, fill=0)
                
                # Draw 4 columns with improved spacing
                for col in range(columns):
                    col_x = margin + col * column_width
                    
                    # Column separator with proper padding
                    if col > 0:
                        c.setLineWidth(1)
                        separator_x = col_x + 3  # Small offset from edge
                        c.line(separator_x, grid_start_y - 5, separator_x, grid_start_y - grid_height + 5)
                    
                    # Column header with better dimensions
                    header_padding = 4
                    c.setLineWidth(1)
                    c.rect(col_x + header_padding, grid_start_y - 25, column_width - (2 * header_padding), 20, stroke=1, fill=0)
                    
                    c.setFillGray(0.9)
                    c.rect(col_x + header_padding + 1, grid_start_y - 24, column_width - (2 * header_padding) - 2, 18, stroke=0, fill=1)
                    c.setFillGray(0)
                    
                    # Calculate question range for this column
                    col_start = current_question + col * questions_per_column
                    col_end = min(col_start + questions_per_column - 1, current_question + questions_this_page - 1)
                    
                    if col_start <= question_count:
                        c.setFont("Helvetica-Bold", 8)
                        col_title = f"Q{col_start}-{min(col_end, question_count)}"
                        title_width = c.stringWidth(col_title, "Helvetica-Bold", 8)
                        title_x = col_x + (column_width - title_width) / 2
                        c.drawString(title_x, grid_start_y - 18, col_title)
                        
                        # Choice headers with better spacing
                        c.setFont("Helvetica", 7)
                        choice_start_x = col_x + 30  # More space for question numbers
                        for i, choice in enumerate(choices):
                            choice_x = choice_start_x + i * bubble_spacing
                            c.drawString(choice_x + 2, grid_start_y - 35, choice)  # Better alignment
                        
                        # Draw questions with improved spacing
                        for row in range(questions_per_column):
                            question_num = col_start + row
                            if question_num > question_count or question_num > col_end:
                                break
                            
                            row_y = grid_start_y - 40 - (row * row_height)  # Better starting position
                            
                            # Question number with better positioning
                            c.setFont("Helvetica", 8)
                            q_text = f"{question_num}."
                            c.drawString(col_x + 8, row_y - 6, q_text)  # Better padding from edge
                            
                            # Answer bubbles with improved positioning
                            for i, choice in enumerate(choices):
                                bubble_x = choice_start_x + i * bubble_spacing + bubble_radius
                                bubble_y = row_y - 6  # Better vertical alignment
                                
                                c.setLineWidth(1.5)
                                c.circle(bubble_x, bubble_y, bubble_radius, stroke=1, fill=0)
                
                # Update for next page
                current_question += questions_this_page
                
                # Footer with better positioning
                footer_y = 30  # More space from bottom
                c.setFont("Helvetica", 7)
                footer_text = "ALPHA V4 - Compact Design | CheckMate System"
                text_width = c.stringWidth(footer_text, "Helvetica", 7)
                footer_x = margin + (content_width - text_width) / 2
                c.drawString(footer_x, footer_y, footer_text)
                
                # Corner alignment markers (slightly larger for better visibility)
                marker_size = 8
                c.setFillGray(0)
                c.rect(margin - 4, height - margin - 4, marker_size, marker_size, stroke=0, fill=1)
                c.rect(width - margin - 4, height - margin - 4, marker_size, marker_size, stroke=0, fill=1)
                c.rect(margin - 4, margin - 4, marker_size, marker_size, stroke=0, fill=1)
                c.rect(width - margin - 4, margin - 4, marker_size, marker_size, stroke=0, fill=1)
                
                # Start new page if more questions
                if current_question <= question_count:
                    c.showPage()
                    page_num += 1
            
            c.save()
            pdf_data = buffer.getvalue()
            buffer.close()
            response.write(pdf_data)
            return response
            
        except ImportError as e:
            logger.warning(f"ReportLab not available: {str(e)}")
            return AnswerKeyService._create_reportlab_install_response(test_type, question_count)
            
        except Exception as e:
            logger.error(f"PDF generation error: {str(e)}")
            return AnswerKeyService._create_pdf_error_response(test_type, question_count, str(e))

    @staticmethod
    def generate_answer_key_pdf(test_info, answer_keys, mode='answer_key'):
        """Generate compact PDF for answer key or answer sheet with improved padding"""
        import io
        import logging
        from django.http import HttpResponse
        
        logger = logging.getLogger(__name__)
        
        try:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import letter, A4
            from reportlab.lib.units import inch
            
            # Clean test name for filename
            import re
            clean_test_name = re.sub(r'[^\w\s-]', '', test_info.test_name)
            clean_test_name = re.sub(r'[-\s]+', '_', clean_test_name)
            
            if mode == 'answer_key':
                filename = f"ALPHA_V4_{clean_test_name}_answer_key.pdf"
            else:
                filename = f"ALPHA_V4_{clean_test_name}_answer_sheet.pdf"
            
            response = HttpResponse(content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            
            buffer = io.BytesIO()
            
            # Get test type info
            if test_info.test_type == 'multiple_choice_4':
                type_display = 'Multiple Choice (A, B, C, D)'
                choices = ['A', 'B', 'C', 'D']
            elif test_info.test_type == 'multiple_choice_5':
                type_display = 'Multiple Choice (A, B, C, D, E)'
                choices = ['A', 'B', 'C', 'D', 'E']
            elif test_info.test_type == 'true_false':
                type_display = 'True or False'
                choices = ['T', 'F']
            else:
                type_display = 'Multiple Choice (A, B, C, D)'
                choices = ['A', 'B', 'C', 'D']
            
            c = canvas.Canvas(buffer, pagesize=A4)
            width, height = A4
            
            # ALPHA V4 - IMPROVED LAYOUT (same as template)
            margin = 0.4 * inch
            content_width = width - 2 * margin
            columns = 4
            questions_per_page = 100
            questions_per_column = 25
            column_width = content_width / columns
            row_height = 14
            bubble_radius = 5
            bubble_spacing = 16
            
            # Create answer mapping
            answer_map = {}
            for answer_key in answer_keys:
                answer_map[answer_key.question_number] = answer_key.answer
            
            current_question = 1
            page_num = 1
            
            while current_question <= test_info.question_count:
                # IMPROVED HEADER
                header_y = height - 0.3 * inch
                header_height = 45
                
                c.setLineWidth(2)
                c.rect(margin, header_y - header_height, content_width, header_height, stroke=1, fill=0)
                
                # Title
                c.setFont("Helvetica-Bold", 13)
                if mode == 'answer_key':
                    title_text = f"ALPHA V4 - {test_info.test_name} (ANSWER KEY)"
                else:
                    title_text = f"ALPHA V4 - {test_info.test_name} (SHEET)"
                
                # Truncate title if too long
                if len(title_text) > 55:
                    title_text = title_text[:52] + "..."
                
                text_width = c.stringWidth(title_text, "Helvetica-Bold", 13)
                title_x = margin + (content_width - text_width) / 2
                c.drawString(title_x, header_y - 16, title_text)
                
                # Question range and info
                questions_this_page = min(questions_per_page, test_info.question_count - current_question + 1)
                end_question = current_question + questions_this_page - 1
                
                c.setFont("Helvetica", 9)
                info_text = f"Questions {current_question}-{end_question} | {type_display} | Page {page_num}"
                text_width = c.stringWidth(info_text, "Helvetica", 9)
                info_x = margin + (content_width - text_width) / 2
                c.drawString(info_x, header_y - 32, info_text)
                
                # IMPROVED STUDENT INFO (only for answer sheets on first page)
                if mode == 'answer_sheet' and page_num == 1:
                    student_y = header_y - header_height - 15
                    info_height = 55
                    
                    c.setLineWidth(1)
                    c.rect(margin, student_y - info_height, content_width, info_height, stroke=1, fill=0)
                    
                    c.setFillGray(0.95)
                    c.rect(margin + 1, student_y - info_height + 1, content_width - 2, info_height - 2, stroke=0, fill=1)
                    c.setFillGray(0)
                    
                    c.setFont("Helvetica-Bold", 10)
                    c.drawString(margin + 8, student_y - 18, "STUDENT INFO")
                    
                    c.setFont("Helvetica", 9)
                    c.drawString(margin + 12, student_y - 34, "Name:")
                    c.line(margin + 55, student_y - 36, margin + content_width/2 - 12, student_y - 36)
                    
                    c.drawString(margin + content_width/2 + 12, student_y - 34, "ID:")
                    c.line(margin + content_width/2 + 35, student_y - 36, margin + content_width - 12, student_y - 36)
                    
                    c.drawString(margin + 12, student_y - 50, "Course:")
                    c.line(margin + 55, student_y - 52, margin + content_width/2 - 12, student_y - 52)
                    
                    c.drawString(margin + content_width/2 + 12, student_y - 50, "Section:")
                    c.line(margin + content_width/2 + 55, student_y - 52, margin + content_width - 12, student_y - 52)
                    
                    grid_start_y = student_y - info_height - 20
                else:
                    grid_start_y = header_y - header_height - 20
                
                # IMPROVED ANSWER GRID
                grid_height = questions_per_column * row_height + 40
                c.setLineWidth(2)
                c.rect(margin, grid_start_y - grid_height, content_width, grid_height, stroke=1, fill=0)
                
                # Draw 4 columns with improved spacing
                for col in range(columns):
                    col_x = margin + col * column_width
                    
                    # Column separator
                    if col > 0:
                        c.setLineWidth(1)
                        separator_x = col_x + 3
                        c.line(separator_x, grid_start_y - 5, separator_x, grid_start_y - grid_height + 5)
                    
                    # Column header
                    header_padding = 4
                    c.setLineWidth(1)
                    c.rect(col_x + header_padding, grid_start_y - 25, column_width - (2 * header_padding), 20, stroke=1, fill=0)
                    c.setFillGray(0.9)
                    c.rect(col_x + header_padding + 1, grid_start_y - 24, column_width - (2 * header_padding) - 2, 18, stroke=0, fill=1)
                    c.setFillGray(0)
                    
                    # Calculate question range for this column
                    col_start = current_question + col * questions_per_column
                    col_end = min(col_start + questions_per_column - 1, current_question + questions_this_page - 1)
                    
                    if col_start <= test_info.question_count:
                        c.setFont("Helvetica-Bold", 8)
                        col_title = f"Q{col_start}-{min(col_end, test_info.question_count)}"
                        title_width = c.stringWidth(col_title, "Helvetica-Bold", 8)
                        title_x = col_x + (column_width - title_width) / 2
                        c.drawString(title_x, grid_start_y - 18, col_title)
                        
                        # Choice headers
                        c.setFont("Helvetica", 7)
                        choice_start_x = col_x + 30
                        for i, choice in enumerate(choices):
                            choice_x = choice_start_x + i * bubble_spacing
                            display_choice = choice
                            if choice == 'True':
                                display_choice = 'T'
                            elif choice == 'False':
                                display_choice = 'F'
                            c.drawString(choice_x + 2, grid_start_y - 35, display_choice)
                        
                        # Draw questions
                        for row in range(questions_per_column):
                            question_num = col_start + row
                            if question_num > test_info.question_count or question_num > col_end:
                                break
                            
                            row_y = grid_start_y - 40 - (row * row_height)
                            
                            # Question number
                            c.setFont("Helvetica", 8)
                            c.drawString(col_x + 8, row_y - 6, f"{question_num}.")
                            
                            # Answer bubbles
                            correct_answer = answer_map.get(question_num)
                            
                            for i, choice in enumerate(choices):
                                bubble_x = choice_start_x + i * bubble_spacing + bubble_radius
                                bubble_y = row_y - 6
                                
                                c.setLineWidth(1.5)
                                
                                # Fill bubble if correct answer and answer key mode
                                if mode == 'answer_key' and correct_answer == choice:
                                    c.setFillGray(0)  # Black fill
                                    c.circle(bubble_x, bubble_y, bubble_radius, stroke=1, fill=1)
                                    c.setFillGray(0)
                                else:
                                    c.circle(bubble_x, bubble_y, bubble_radius, stroke=1, fill=0)
                
                # Update for next page
                current_question += questions_this_page
                
                # Footer with better positioning
                footer_y = 30
                c.setFont("Helvetica", 7)
                footer_text = "ALPHA V4 - Compact Design | CheckMate System"
                text_width = c.stringWidth(footer_text, "Helvetica", 7)
                footer_x = margin + (content_width - text_width) / 2
                c.drawString(footer_x, footer_y, footer_text)
                
                # Corner markers
                marker_size = 8
                c.setFillGray(0)
                c.rect(margin - 4, height - margin - 4, marker_size, marker_size, stroke=0, fill=1)
                c.rect(width - margin - 4, height - margin - 4, marker_size, marker_size, stroke=0, fill=1)
                c.rect(margin - 4, margin - 4, marker_size, marker_size, stroke=0, fill=1)
                c.rect(width - margin - 4, margin - 4, marker_size, marker_size, stroke=0, fill=1)
                
                if current_question <= test_info.question_count:
                    c.showPage()
                    page_num += 1
            
            c.save()
            pdf_data = buffer.getvalue()
            buffer.close()
            response.write(pdf_data)
            return response
            
        except ImportError as e:
            logger.warning(f"ReportLab not available: {str(e)}")
            return None
            
        except Exception as e:
            logger.error(f"PDF generation error: {str(e)}")
            return None

def get_answer_choices_for_type(test_type):
    """Helper function to get answer choices for test type"""
    if test_type == 'multiple_choice_4':
        return ['A', 'B', 'C', 'D']
    elif test_type == 'multiple_choice_5':
        return ['A', 'B', 'C', 'D', 'E']
    elif test_type == 'true_false':
        return ['True', 'False']
    else:
        return ['A', 'B', 'C', 'D']
