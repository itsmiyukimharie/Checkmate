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
        """Generate a blank PDF template for manual answer sheet creation"""
        import io
        import logging
        from django.http import HttpResponse
        
        logger = logging.getLogger(__name__)
        
        try:
            # Try to use ReportLab for PDF generation
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import letter, A4
            from reportlab.lib.units import inch
            
            # Create response
            response = HttpResponse(content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="answer_sheet_template_{test_type}_{question_count}q.pdf"'
            
            # Create PDF buffer
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
            
            # Create canvas
            c = canvas.Canvas(buffer, pagesize=A4)
            width, height = A4
            
            # Fixed layout parameters - reduced margins for more space
            margin = 0.25 * inch
            content_width = width - 2 * margin
            
            # Fixed grid: exactly 5 columns, 40 rows per column
            max_columns = 5
            rows_per_column = 40
            questions_per_page = max_columns * rows_per_column  # 200 questions per page
            
            # Calculate spacing
            column_width = content_width / max_columns
            row_height = 14
            bubble_radius = 5
            bubble_spacing = 12
            
            # Helper function to draw centered text
            def draw_centered_text(canvas_obj, x, y, text, font_name="Helvetica", font_size=10):
                canvas_obj.setFont(font_name, font_size)
                text_width = canvas_obj.stringWidth(text, font_name, font_size)
                canvas_obj.drawString(x - text_width/2, y, text)
            
            current_question = 1
            page_num = 1
            
            while current_question <= question_count:
                # Header section - more compact spacing
                header_y = height - 0.3 * inch
                
                # Main title with border
                c.setLineWidth(2)
                header_height = 55  # Reduced from 60
                c.rect(margin, header_y - header_height, content_width, header_height, stroke=1, fill=0)
                
                # Title
                c.setFont("Helvetica-Bold", 16)
                title_y = header_y - 15
                draw_centered_text(c, width/2, title_y, "CheckMate Answer Sheet Template", "Helvetica-Bold", 16)
                
                # Test info - more compact
                c.setFont("Helvetica-Bold", 10)
                info_y = title_y - 18  # Reduced spacing
                draw_centered_text(c, width/2, info_y, f"Test Type: {type_display}", "Helvetica-Bold", 10)
                
                info_y -= 10  # Reduced spacing
                draw_centered_text(c, width/2, info_y, f"Questions: {question_count} | Date: _____________", "Helvetica", 9)
                
                if page_num > 1:
                    info_y -= 8  # Reduced spacing
                    draw_centered_text(c, width/2, info_y, f"Page {page_num}", "Helvetica-Bold", 9)
                
                # Student Information Section - only on first page with reduced spacing
                if page_num == 1:
                    student_info_y = header_y - header_height - 8  # Reduced from 15
                    
                    # Student info box - smaller height
                    info_box_height = 45  # Reduced from 50
                    c.setLineWidth(2)
                    c.rect(margin, student_info_y - info_box_height, content_width, info_box_height, stroke=1, fill=0)
                    
                    # Background shading
                    c.setFillGray(0.95)
                    c.rect(margin + 1, student_info_y - info_box_height + 1, content_width - 2, info_box_height - 2, stroke=0, fill=1)
                    c.setFillGray(0)
                    
                    # Student info title
                    c.setFont("Helvetica-Bold", 12)
                    c.drawString(margin + 5, student_info_y - 12, "STUDENT INFORMATION")
                    
                    # Student info fields - more compact
                    c.setFont("Helvetica-Bold", 9)
                    field_y = student_info_y - 22  # Adjusted
                    
                    # Row 1
                    c.drawString(margin + 10, field_y, "Name:")
                    c.line(margin + 45, field_y - 2, margin + content_width/2 - 10, field_y - 2)
                    
                    c.drawString(margin + content_width/2, field_y, "Student ID:")
                    c.line(margin + content_width/2 + 60, field_y - 2, margin + content_width - 10, field_y - 2)
                    
                    # Row 2
                    field_y -= 12  # Reduced spacing
                    c.drawString(margin + 10, field_y, "Course:")
                    c.line(margin + 50, field_y - 2, margin + content_width/2 - 10, field_y - 2)
                    
                    c.drawString(margin + content_width/2, field_y, "Section:")
                    c.line(margin + content_width/2 + 45, field_y - 2, margin + content_width - 10, field_y - 2)
                    
                    # Instructions box - more compact
                    instructions_y = student_info_y - info_box_height - 8  # Reduced from 15
                    instructions_height = 30  # Reduced from 35
                    
                    c.setLineWidth(1)
                    c.rect(margin, instructions_y - instructions_height, content_width, instructions_height, stroke=1, fill=0)
                    
                    # Instructions background
                    c.setFillGray(0.98)
                    c.rect(margin + 1, instructions_y - instructions_height + 1, content_width - 2, instructions_height - 2, stroke=0, fill=1)
                    c.setFillGray(0)
                    
                    c.setFont("Helvetica-Bold", 10)
                    c.drawString(margin + 5, instructions_y - 10, "INSTRUCTIONS:")
                    
                    c.setFont("Helvetica", 8)
                    c.drawString(margin + 10, instructions_y - 20, "• Fill in the bubbles completely with a dark pencil or pen")
                    c.drawString(margin + 10, instructions_y - 28, "• Make sure only one answer is selected per question • Erase completely if you need to change an answer")
                    
                    grid_start_y = instructions_y - instructions_height - 10  # Reduced from 20
                else:
                    # For subsequent pages - reduced spacing
                    grid_start_y = header_y - header_height - 10  # Reduced from 20
                
                # Calculate columns needed for remaining questions
                remaining_questions = question_count - current_question + 1
                columns_needed = min(max_columns, (remaining_questions + rows_per_column - 1) // rows_per_column)
                
                # Draw main answer grid border
                grid_height = rows_per_column * row_height + 25
                c.setLineWidth(2)
                c.rect(margin, grid_start_y - grid_height, content_width, grid_height, stroke=1, fill=0)
                
                # Column headers with background
                header_row_y = grid_start_y - 5
                header_cell_height = 20
                
                for col in range(columns_needed):
                    x_col_start = margin + col * column_width
                    
                    # Header cell border
                    c.setLineWidth(1)
                    c.rect(x_col_start + 1, header_row_y - header_cell_height, column_width - 2, header_cell_height, stroke=1, fill=0)
                    
                    # Header background
                    c.setFillGray(0.9)
                    c.rect(x_col_start + 2, header_row_y - header_cell_height + 1, column_width - 4, header_cell_height - 2, stroke=0, fill=1)
                    c.setFillGray(0)
                    
                    # Draw "Q" header
                    c.setFont("Helvetica-Bold", 8)
                    c.drawString(x_col_start + 8, header_row_y - 12, "Q")
                    
                    # Draw choice headers
                    choice_x = x_col_start + 22
                    for choice in choices:
                        c.drawString(choice_x, header_row_y - 12, choice)
                        choice_x += bubble_spacing
                
                # Draw column separators (vertical lines between columns)
                c.setLineWidth(1)
                for col in range(1, columns_needed):
                    x_separator = margin + col * column_width
                    # Draw line from header top to bottom of answer area
                    c.line(x_separator, header_row_y, x_separator, grid_start_y - grid_height)
                
                # Draw the answer grid - 40 rows per column (no individual question borders)
                c.setFont("Helvetica", 7)
                
                for col in range(columns_needed):
                    x_col_start = margin + col * column_width
                    
                    for row in range(rows_per_column):
                        question_num = current_question + col * rows_per_column + row
                        
                        if question_num > question_count:
                            break
                        
                        # Calculate row position with 1px margin
                        row_y = grid_start_y - header_cell_height - 5 - (row * row_height) - 1  # Added 1px margin
                        
                        # Alternating row background (light) with margin
                        if row % 2 == 0:
                            c.setFillGray(0.97)
                            c.rect(x_col_start + 2, row_y - row_height + 3, column_width - 4, row_height - 1, stroke=0, fill=1)  # Reduced height by 1px for margin
                            c.setFillGray(0)
                        
                        # Draw question number
                        c.setFont("Helvetica-Bold", 7)
                        c.drawString(x_col_start + 5, row_y - 8, f"{question_num}.")
                        
                        # Draw bubbles for each choice
                        choice_x = x_col_start + 22
                        for choice in choices:
                            # Draw empty circle (bubble)
                            bubble_center_x = choice_x + bubble_radius
                            bubble_center_y = row_y - 7
                            c.setLineWidth(1)
                            c.circle(bubble_center_x, bubble_center_y, bubble_radius, stroke=1, fill=0)
                            choice_x += bubble_spacing
                
                # Update current question for next page
                questions_on_this_page = min(questions_per_page, question_count - current_question + 1)
                current_question += questions_on_this_page
                
                # Footer positioned correctly at bottom
                footer_y = 0.4 * inch  # Reduced from 0.5 inch for more space
                c.setFont("Helvetica", 8)
                footer_text = f"Generated by CheckMate - Optimized for OMR Processing"
                draw_centered_text(c, width/2, footer_y, footer_text, "Helvetica", 8)
                
                # Start new page if more questions remain
                if current_question <= question_count:
                    c.showPage()
                    page_num += 1
            
            # Save the PDF
            c.save()
            
            # Get PDF data
            pdf_data = buffer.getvalue()
            buffer.close()
            
            # Write to response
            response.write(pdf_data)
            return response
            
        except ImportError as e:
            logger.warning(f"ReportLab not available: {str(e)}")
            return AnswerKeyService._create_reportlab_install_response(test_type, question_count)
            
        except Exception as e:
            logger.error(f"PDF generation error: {str(e)}")
            return AnswerKeyService._create_pdf_error_response(test_type, question_count, str(e))
    
    @staticmethod
    def _create_reportlab_install_response(test_type, question_count):
        """Create a response indicating ReportLab needs to be installed"""
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/plain')
        response['Content-Disposition'] = f'attachment; filename="INSTALL_REPORTLAB_FOR_PDF.txt"'
        
        content = f"""
CheckMate PDF Template Generation

ERROR: ReportLab library is not installed.

To enable PDF template generation, please install ReportLab:

1. Open your terminal/command prompt
2. Navigate to your project directory
3. Run: pip install reportlab

After installation, refresh this page and try downloading the PDF template again.

ALTERNATIVE: You can use the CSV template option which doesn't require additional libraries.

Template Request Details:
- Test Type: {test_type}
- Question Count: {question_count}
- Requested Format: PDF

For support, please contact your system administrator.
"""
        
        response.write(content)
        return response
    
    @staticmethod
    def _create_pdf_error_response(test_type, question_count, error_message):
        """Create a response for PDF generation errors"""
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/plain')
        response['Content-Disposition'] = f'attachment; filename="PDF_GENERATION_ERROR.txt"'
        
        content = f"""
CheckMate PDF Template Generation Error

An error occurred while generating the PDF template.

Error Details: {error_message}

Template Request Details:
- Test Type: {test_type}
- Question Count: {question_count}
- Requested Format: PDF

ALTERNATIVE SOLUTIONS:
1. Try the CSV template option instead
2. Reduce the number of questions if it's very large
3. Contact your system administrator

For immediate use, please use the CSV template download option.
"""
        
        response.write(content)
        return response

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
