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
        
        filename_suffix = "_answer_key" if show_answers else "_blank_sheet"
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{test_info.test_name}{filename_suffix}.csv"'
        
        writer = csv.writer(response)
        
        # Header with course information
        writer.writerow(['Test Name', test_info.test_name])
        writer.writerow(['Type', 'Answer Key' if show_answers else 'Blank Answer Sheet'])
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
        
        # Answer key header
        if show_answers:
            writer.writerow(['Question Number', 'Answer'])
            # Answer key data
            for answer in answer_keys:
                writer.writerow([answer.question_number, answer.answer])
        else:
            writer.writerow(['Question Number', 'Student Answer'])
            # Blank sheet data
            for answer in answer_keys:
                writer.writerow([answer.question_number, ''])  # Empty answer column
        
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
                status='active'  # Mark as active since it's processed
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
        from django.http import HttpResponse
        from django.template.loader import render_to_string
        import io
        
        try:
            # Try to use ReportLab for PDF generation
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import letter, A4
            from reportlab.lib.units import inch
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
            from reportlab.lib import colors
            
            # Create response
            response = HttpResponse(content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="answer_sheet_template_{test_type}_{question_count}q.pdf"'
            
            # Create PDF
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch)
            
            # Get styles
            styles = getSampleStyleSheet()
            title_style = styles['Title']
            heading_style = styles['Heading2']
            normal_style = styles['Normal']
            
            # Content list
            content = []
            
            # Title
            content.append(Paragraph("CheckMate Answer Sheet Template", title_style))
            content.append(Spacer(1, 0.2*inch))
            
            # Test information
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
            
            content.append(Paragraph(f"<b>Test Type:</b> {type_display}", normal_style))
            content.append(Paragraph(f"<b>Number of Questions:</b> {question_count}", normal_style))
            content.append(Spacer(1, 0.2*inch))
            
            # Instructions
            content.append(Paragraph("Instructions:", heading_style))
            content.append(Paragraph("• Fill in the bubbles completely with a dark pencil or pen", normal_style))
            content.append(Paragraph("• Make sure only one answer is selected per question", normal_style))
            content.append(Paragraph("• Erase completely if you need to change an answer", normal_style))
            content.append(Spacer(1, 0.3*inch))
            
            # Student information section
            student_info = [
                ["Name: ________________________", "Student ID: ________________________"],
                ["Course: ______________________", "Section: ___________________________"],
                ["Date: ________________________", "Instructor: _________________________"]
            ]
            
            student_table = Table(student_info, colWidths=[3*inch, 3*inch])
            student_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ]))
            content.append(student_table)
            content.append(Spacer(1, 0.3*inch))
            
            # Answer grid
            content.append(Paragraph("Answer Sheet:", heading_style))
            
            # Create answer grid - organize in columns
            questions_per_page = min(question_count, 60)  # Limit per page
            cols = 3 if len(choices) <= 4 else 2  # Adjust columns based on choices
            rows_per_col = (questions_per_page + cols - 1) // cols
            
            # Build answer grid data
            grid_data = []
            for row in range(rows_per_col + 1):  # +1 for header
                row_data = []
                for col in range(cols):
                    if row == 0:  # Header row
                        row_data.append("Q")
                        for choice in choices:
                            row_data.append(choice)
                    else:
                        q_num = (col * rows_per_col) + row
                        if q_num <= question_count:
                            row_data.append(f"{q_num:2d}.")
                            for _ in choices:
                                row_data.append("○")  # Empty bubble
                        else:
                            # Fill with empty cells
                            for _ in range(len(choices) + 1):
                                row_data.append("")
                
                grid_data.append(row_data)
            
            # Calculate column widths
            q_width = 0.3*inch
            choice_width = 0.25*inch
            col_widths = []
            for col in range(cols):
                col_widths.extend([q_width] + [choice_width] * len(choices))
            
            answer_table = Table(grid_data, colWidths=col_widths)
            answer_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),  # Header background
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),  # Header font
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightblue]),
            ]))
            
            content.append(answer_table)
            
            # Build PDF
            doc.build(content)
            buffer.seek(0)
            response.write(buffer.getvalue())
            buffer.close()
            
            return response
            
        except ImportError:
            # Fallback: Return HTML that can be printed as PDF
            return AnswerKeyService._generate_html_template(test_type, question_count)
    
    @staticmethod
    def _generate_html_template(test_type, question_count):
        """Fallback HTML template when ReportLab is not available"""
        from django.http import HttpResponse
        
        # Get choices
        if test_type == 'multiple_choice_4':
            choices = ['A', 'B', 'C', 'D']
            type_display = 'Multiple Choice (A-D)'
        elif test_type == 'multiple_choice_5':
            choices = ['A', 'B', 'C', 'D', 'E']
            type_display = 'Multiple Choice (A-E)'
        elif test_type == 'true_false':
            choices = ['T', 'F']
            type_display = 'True/False'
        else:
            choices = ['A', 'B', 'C', 'D']
            type_display = 'Multiple Choice (A-D)'
        
        html_content = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Answer Sheet Template - {type_display}</title>
            <style>
                @media print {{
                    body {{ margin: 10mm; }}
                    .no-print {{ display: none; }}
                }}
                body {{ font-family: Arial, sans-serif; font-size: 12px; }}
                .header {{ text-align: center; margin-bottom: 20px; }}
                .info-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px; }}
                .answer-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }}
                .question {{ border: 1px solid #ccc; padding: 5px; text-align: center; }}
                .bubble {{ display: inline-block; width: 20px; height: 20px; border: 2px solid #000; border-radius: 50%; margin: 0 5px; }}
                .instructions {{ background: #f0f0f0; padding: 10px; margin-bottom: 20px; }}
            </style>
        </head>
        <body>
            <div class="no-print">
                <button onclick="window.print()">Print Template</button>
                <p><strong>Instructions:</strong> Use your browser's print function to save as PDF</p>
            </div>
            
            <div class="header">
                <h1>CheckMate Answer Sheet Template</h1>
                <h2>{type_display} - {question_count} Questions</h2>
            </div>
            
            <div class="instructions">
                <strong>Instructions:</strong>
                <ul>
                    <li>Fill in the bubbles completely with a dark pencil or pen</li>
                    <li>Make sure only one answer is selected per question</li>
                    <li>Erase completely if you need to change an answer</li>
                </ul>
            </div>
            
            <div class="info-grid">
                <div>
                    <strong>Name:</strong> ________________________________<br><br>
                    <strong>Course:</strong> ______________________________<br><br>
                    <strong>Date:</strong> ________________________________
                </div>
                <div>
                    <strong>Student ID:</strong> __________________________<br><br>
                    <strong>Section:</strong> _____________________________<br><br>
                    <strong>Instructor:</strong> ___________________________
                </div>
            </div>
            
            <div class="answer-grid">
        '''
        
        # Add questions
        for i in range(1, question_count + 1):
            html_content += f'''
                <div class="question">
                    <strong>{i}.</strong><br>
                    {' '.join([f'<span class="bubble"></span>{choice}' for choice in choices])}
                </div>
            '''
        
        html_content += '''
            </div>
        </body>
        </html>
        '''
        
        response = HttpResponse(html_content, content_type='text/html')
        response['Content-Disposition'] = f'attachment; filename="answer_sheet_template_{test_type}_{question_count}q.html"'
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
