from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
import logging
import os

from .services.answer_key_service import AnswerKeyService
from .services.auth_service import AuthService
from .services.course_service import CourseService
from .services.student_service import StudentService
from .services.file_processing_service import FileProcessingService
from .utils.form_helpers import FormHelper
from .utils.session_helpers import SessionHelper
from .utils.auth_helpers import AuthFormHelper
from .forms import CreateAnswerKeyForm, CourseForm, CourseFilterForm, StudentForm, StudentFilterForm
from scripts.pdf_processor_main_prototype import CheckmateService
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)

@login_required
def dashboard(request):
    """Dashboard page - main entry point"""
    context = {
        'page_title': 'Dashboard',
        'current_page': 'dashboard',
        'user': request.user
    }
    return render(request, 'main/dashboard.html', context)

@login_required
def answer_keys(request):
    """Answer Keys Management - Upload or create answer keys"""
    user_tests = AnswerKeyService.get_user_tests(request.user)
    
    if request.method == 'POST':
        if 'create_form' in request.POST:
            # Handle manual creation
            create_form = CreateAnswerKeyForm(request.POST, user=request.user)
            if create_form.is_valid():
                test_data = AnswerKeyService.create_temp_test_data(create_form.cleaned_data)
                SessionHelper.store_temp_test_data(request, test_data)
                
                messages.success(request, f'Test "{test_data["test_name"]}" setup complete. Please enter answers to save.')
                return redirect('main:enter_answers', test_id=0)
            else:
                messages.error(request, 'Please correct the errors in the create form.')
    
    context = {
        'page_title': 'Manage Answer Keys',
        'current_page': 'answer_keys',
        'user_tests': user_tests,
        'create_form': CreateAnswerKeyForm(user=request.user)
    }
    return render(request, 'main/answer_keys.html', context)

@login_required
def enter_answers(request, test_id):
    """Enter answers for a specific test"""
    if test_id == 0:
        # Handle new test creation
        temp_test_data = SessionHelper.get_temp_test_data(request)
        if not temp_test_data:
            messages.error(request, 'No test data found. Please create a new test.')
            return redirect('main:answer_keys')
        
        test_info = AnswerKeyService.create_temp_test_object(temp_test_data)
        is_new_test = True
    else:
        # Handle existing test
        try:
            test_info = AnswerKeyService.get_test_by_id(test_id, request.user)
            is_new_test = False
        except:
            messages.error(request, 'Test not found.')
            return redirect('main:answer_keys')
    
    if request.method == 'POST':
        form = FormHelper.create_answer_entry_form(test_info, request.POST)
        if form.is_valid():
            if is_new_test:
                test_info = AnswerKeyService.save_test_to_db(test_info, request.user)
                SessionHelper.clear_temp_test_data(request)
            
            AnswerKeyService.save_answers(test_info, form.cleaned_data)
            messages.success(request, f'Answer key for "{test_info.test_name}" has been saved successfully!')
            return redirect('main:answer_keys')
    else:
        initial_data = None if is_new_test else AnswerKeyService.get_existing_answers(test_info)
        form = FormHelper.create_answer_entry_form(test_info, initial_data=initial_data)
    
    context = {
        'page_title': f'Enter Answers - {test_info.test_name}',
        'current_page': 'answer_keys',
        'test_info': test_info,
        'form': form,
        'answer_choices': test_info.get_answer_choices(),
        'is_new_test': is_new_test
    }
    return render(request, 'main/answer_keys_enter.html', context)

@login_required
def delete_test(request, test_id):
    """Delete a test and its answer keys"""
    try:
        test_name = AnswerKeyService.delete_test(test_id, request.user)
        messages.success(request, f'Test "{test_name}" has been deleted successfully!')
    except Exception as e:
        messages.error(request, 'Test not found.')
    
    return redirect('main:answer_keys')

@login_required
def download_answer_key(request, test_id):
    """Download answer key or answer sheet as CSV file"""
    try:
        test_info, answer_keys = AnswerKeyService.get_test_with_answers(test_id, request.user)
        
        # Get format from URL parameter (answer_key or answer_sheet)
        format_type = request.GET.get('format', 'answer_key')
        show_answers = format_type == 'answer_key'
        
        return AnswerKeyService.generate_csv_response(test_info, answer_keys, show_answers)
    except Exception as e:
        messages.error(request, 'Test not found.')
        return redirect('main:answer_keys')

@login_required
def print_answer_key_data(request, test_id):
    """Return answer key data as JSON for printing"""
    try:
        test_info, answer_keys = AnswerKeyService.get_test_with_answers(test_id, request.user)
        data = AnswerKeyService.generate_print_data(test_info, answer_keys)
        return JsonResponse(data)
    except Exception as e:
        return JsonResponse({'error': 'Test not found'}, status=404)

@login_required
def print_answer_key(request, test_id):
    """Generate and download PDF for answer key or answer sheet"""
    try:
        test_info, answer_keys = AnswerKeyService.get_test_with_answers(test_id, request.user)
        
        # Get mode from URL parameter (answer_key or answer_sheet)
        mode = request.GET.get('mode', 'answer_key')
        if mode not in ['answer_key', 'answer_sheet']:
            mode = 'answer_key'
        
        # Try to generate PDF first
        pdf_response = AnswerKeyService.generate_answer_key_pdf(test_info, answer_keys, mode)
        
        if pdf_response:
            return pdf_response
        else:
            # If PDF generation fails, return error message
            from django.http import HttpResponse
            response = HttpResponse(content_type='text/plain')
            response['Content-Disposition'] = f'attachment; filename="PDF_ERROR.txt"'
            
            error_content = f"""
PDF Generation Error

Unfortunately, the PDF could not be generated for this answer key.

Error Details:
- Test: {test_info.test_name}
- Mode: {mode}
- Questions: {test_info.question_count}

This usually happens when:
1. ReportLab library is not properly installed
2. There's insufficient memory for large tests
3. Invalid test data

Please try:
1. Using the CSV download option instead
2. Contacting your system administrator
3. Reducing the number of questions if the test is very large

Alternative: Use the CSV download option from the dropdown menu.
"""
            response.write(error_content)
            return response
            
    except Exception as e:
        # Return error as downloadable text file
        from django.http import HttpResponse
        response = HttpResponse(content_type='text/plain')
        response['Content-Disposition'] = f'attachment; filename="DOWNLOAD_ERROR.txt"'
        
        error_content = f"""
Download Error

An error occurred while trying to generate your answer key.

Error: {str(e)}

Please try again or contact support if the problem persists.

Alternative options:
- Use the CSV download from the dropdown menu
- Try refreshing the page and attempting again
- Contact your system administrator
"""
        response.write(error_content)
        return response

# Authentication Views - Now modularized
def login(request):
    """Login page"""
    if AuthService.is_authenticated(request.user):
        return redirect('main:dashboard')
    
    if request.method == 'POST':
        form = AuthFormHelper.create_login_form({'request': request, 'POST': request.POST})
        user = AuthFormHelper.process_login_form(request, form)
        
        if user:
            redirect_url = AuthService.login_user(request, user)
            return redirect(redirect_url)
        else:
            AuthService.handle_login_error(request)
    else:
        form = AuthFormHelper.create_login_form()
    
    context = {'page_title': 'Login - CheckMate', 'form': form}
    return render(request, 'main/login.html', context)

def signup(request):
    """Signup page"""
    if AuthService.is_authenticated(request.user):
        return redirect('main:dashboard')
    
    if request.method == 'POST':
        form = AuthFormHelper.create_signup_form(request.POST)
        user = AuthFormHelper.process_signup_form(form)
        
        if user:
            redirect_url = AuthService.signup_user(request, user)
            return redirect(redirect_url)
        else:
            AuthService.handle_signup_error(request)
    else:
        form = AuthFormHelper.create_signup_form()
    
    context = {'page_title': 'Sign Up - CheckMate', 'form': form}
    return render(request, 'main/signup.html', context)

def logout(request):
    """Logout user"""
    redirect_url = AuthService.logout_user(request)
    return redirect(redirect_url)

def landingpage(request):
    """Landing page - main entry point"""
    if AuthService.is_authenticated(request.user):
        return redirect('main:dashboard')
    
    context = {'page_title': 'CheckMate - AI-Powered Test Score Scanner'}
    return render(request, 'main/landingpage.html', context)

# Simplified view functions
@login_required
def test_overview(request):
    """Redirect to student management"""
    return redirect('main:student_management')

@login_required
def course_management(request):
    """Course Management - View and manage courses"""
    # Handle filter form
    filter_form = CourseFilterForm(request.GET or None)
    filters = None
    
    if filter_form.is_valid():
        filters = {
            'search': filter_form.cleaned_data.get('search'),
            'semester': filter_form.cleaned_data.get('semester'),
            'academic_year': filter_form.cleaned_data.get('academic_year'),
            'sort_by': filter_form.cleaned_data.get('sort_by', '-created_at')
        }
    
    user_courses = CourseService.get_user_courses(request.user, filters)
    course_stats = CourseService.get_course_stats(request.user, filters)
    unique_years = CourseService.get_unique_academic_years(request.user)
    
    # Pagination
    paginator = Paginator(user_courses, 10)  # Show 10 courses per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_title': 'Courses',
        'current_page': 'course_management',
        'user_courses': page_obj,
        'course_stats': course_stats,
        'course_form': CourseForm(user=request.user),  # Pass user to form
        'filter_form': filter_form,
        'unique_years': unique_years,
        'has_filters': any(filters.values()) if filters else False
    }
    return render(request, 'main/course_management.html', context)

@login_required
def add_course(request):
    """Add a new course"""
    if request.method == 'POST':
        form = CourseForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                course = CourseService.create_course(request.user, form.cleaned_data)
                return JsonResponse({
                    'success': True,
                    'message': f'Course "{course.course_name}" has been created successfully!'
                })
            except ValidationError as e:
                return JsonResponse({
                    'success': False,
                    'errors': {'__all__': [str(e)]}
                })
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'errors': {'__all__': [f'Error creating course: {str(e)}']}
                })
        else:
            # Format form errors for JSON response
            errors = {}
            for field, field_errors in form.errors.items():
                errors[field] = field_errors
            
            return JsonResponse({
                'success': False,
                'errors': errors
            })
    
    return redirect('main:course_management')

@login_required
def edit_course(request, course_id):
    """Edit an existing course"""
    if request.method == 'POST':
        form = CourseForm(request.POST, user=request.user, course_id=course_id)
        if form.is_valid():
            try:
                course = CourseService.update_course(course_id, request.user, form.cleaned_data)
                return JsonResponse({
                    'success': True,
                    'message': f'Course "{course.course_name}" has been updated successfully!'
                })
            except ValidationError as e:
                return JsonResponse({
                    'success': False,
                    'errors': {'__all__': [str(e)]}
                })
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'errors': {'__all__': [f'Error updating course: {str(e)}']}
                })
        else:
            # Format form errors for JSON response
            errors = {}
            for field, field_errors in form.errors.items():
                errors[field] = field_errors
            
            return JsonResponse({
                'success': False,
                'errors': errors
            })
    
    return redirect('main:course_management')

@login_required
def delete_course(request, course_id):
    """Delete a course"""
    try:
        course_name = CourseService.delete_course(course_id, request.user)
        messages.success(request, f'Course "{course_name}" has been deleted successfully!')
    except Exception as e:
        messages.error(request, f'Error deleting course: {str(e)}')
    
    return redirect('main:course_management')

@login_required
def grade_test(request):
    """Grade Test - Upload answer sheets and process grading"""
    from .services.grade_test_service import GradeTestService

    # Get filter options for dropdowns
    filter_options = GradeTestService.get_filter_options(request.user)

    # Get overview statistics
    overview_stats = GradeTestService.get_grading_overview_stats(request.user)

    # Get grade distribution
    grade_distribution = GradeTestService.get_grade_distribution(request.user)

    # Get grading history (default to all time)
    time_filter = request.GET.get('time_filter', 'all')
    grading_history = GradeTestService.get_grading_history(request.user, time_filter)

    # Add user_tests for initial answer key dropdown population
    user_tests = GradeTestService.get_filtered_answer_keys(request.user, {})

    context = {
        'page_title': 'Grade Test',
        'current_page': 'grade_test',
        'filter_options': filter_options,
        'overview_stats': overview_stats,
        'grade_distribution': grade_distribution,
        'grading_history': grading_history,
        'time_filter': time_filter,
        'user_tests': user_tests,  # <-- Ensure this is present for the dropdown
    }
    return render(request, 'main/grade_test.html', context)

@login_required
def get_filtered_answer_keys(request):
    """AJAX endpoint to get filtered answer keys"""
    from .services.grade_test_service import GradeTestService

    try:
        filters = {
            'course': request.GET.get('course'),
            'academic_year': request.GET.get('academic_year'),
            'semester': request.GET.get('semester')
        }
        # Remove empty filters
        filters = {k: v for k, v in filters.items() if v not in [None, '', 'null', 'undefined']}

        # Always use get_filtered_answer_keys, even if no filters are set
        answer_keys = GradeTestService.get_filtered_answer_keys(request.user, filters)

        # Convert to JSON-serializable format
        answer_keys_data = []
        for answer_key in answer_keys:
            answer_keys_data.append({
                'id': answer_key.id,
                'name': f"{answer_key.test_name} - {answer_key.get_test_type_display()} ({answer_key.question_count} questions)",
                'test_name': answer_key.test_name,
                'test_type': answer_key.get_test_type_display(),
                'question_count': answer_key.question_count,
                'course_code': answer_key.course.course_code if answer_key.course else '',
                'course_name': answer_key.course.course_name if answer_key.course else '',
                'academic_year': answer_key.course.academic_year if answer_key.course else '',
                'semester': answer_key.course.semester if answer_key.course else '',
                'created_date': answer_key.created_at.strftime('%Y-%m-%d')
            })

        return JsonResponse({
            'success': True,
            'answer_keys': answer_keys_data
        })

    except Exception as e:
        logger.error(f"Error getting filtered answer keys: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to get answer keys'
        }, status=500)

@login_required
def get_course_students(request):
    """AJAX endpoint to get students for a specific course"""
    from .services.grade_test_service import GradeTestService
    
    try:
        course_id = request.GET.get('course_id')
        if not course_id:
            return JsonResponse({
                'success': False,
                'error': 'Course ID is required'
            }, status=400)
        
        students = GradeTestService.get_students_for_course(course_id, request.user)
        
        # Convert to JSON-serializable format
        students_data = []
        for student in students:
            students_data.append({
                'id': student.id,
                'student_id': student.student_id,
                'name': f"{student.last_name}, {student.first_name}",
                'full_name': f"{student.first_name} {student.last_name}",
                'section': student.section or 'Not specified',
                'email': student.email or ''
            })
        
        return JsonResponse({
            'success': True,
            'students': students_data
        })
        
    except Exception as e:
        logger.error(f"Error getting course students: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to get students'
        }, status=500)

@login_required
def start_grading_session(request):
    """Start a new grading session"""
    from .services.grade_test_service import GradeTestService

    if request.method == 'POST':
        try:
            # Get form data
            session_data = {
                'answer_key_id': request.POST.get('answer_key_id'),
                'file_format': request.POST.get('file_format'),
                'uploaded_files': request.FILES.getlist('student_answer_sheets'),
            }

            # Accept extracted_data JSON if provided (from process-answer-sheets-pdf)
            extracted_data_json = request.POST.get('extracted_data')
            if extracted_data_json:
                import json
                try:
                    session_data['extracted_data'] = json.loads(extracted_data_json)
                except Exception:
                    session_data['extracted_data'] = None

            # Validate data
            validation_errors = GradeTestService.validate_grading_session_data(session_data)
            if validation_errors:
                return JsonResponse({
                    'success': False,
                    'errors': validation_errors
                })

            # Create grading session (pass extracted_data if present)
            result = GradeTestService.create_grading_session(request.user, session_data)

            if result['success']:
                # Store session data for processing
                request.session['grading_session'] = {
                    'session_id': result['session_id'],
                    'answer_key_id': session_data['answer_key_id'],
                    'file_format': session_data['file_format'],
                    'student_count': len(result['students']),
                    'uploaded_files_count': len(result['processed_files']),
                    'extracted_data': session_data.get('extracted_data')
                }

                return JsonResponse({
                    'success': True,
                    'message': f'Grading session started successfully! Processing {len(result["processed_files"])} files.',
                    'session_id': result['session_id'],
                    'redirect_url': f'/grade-test/session/{result["session_id"]}/'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': result['error']
                })

        except Exception as e:
            logger.error(f"Error starting grading session: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to start grading session'
            }, status=500)

    return JsonResponse({
        'success': False,
        'error': 'Invalid request method'
    }, status=405)

@login_required
def get_grading_history(request):
    """AJAX endpoint to get grading history with time filter"""
    from .services.grade_test_service import GradeTestService
    
    try:
        time_filter = request.GET.get('time_filter', 'all')
        grading_history = GradeTestService.get_grading_history(request.user, time_filter)
        
        # Convert to JSON-serializable format
        history_data = []
        for session in grading_history:
            history_data.append({
                'test_name': session['test_info'].test_name,
                'test_type': session['test_info'].get_test_type_display(),
                'question_count': session['test_info'].question_count,
                'course_code': session['test_info'].course.course_code if session['test_info'].course else '',
                'course_name': session['test_info'].course.course_name if session['test_info'].course else '',
                'student_count': session['student_count'],
                'average_score': session['average_score'],
                'graded_date': session['graded_date'].strftime('%Y-%m-%d %H:%M'),
                'sections': session['sections']
            })
        
        return JsonResponse({
            'success': True,
            'grading_history': history_data
        })
        
    except Exception as e:
        logger.error(f"Error getting grading history: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to get grading history'
        }, status=500)

@login_required
def download_template(request):
    """Download template files with test information"""
    file_type = request.GET.get('file_type', 'pdf')
    test_type = request.GET.get('test_type', 'multiple_choice_4')
    question_count = int(request.GET.get('question_count', 50))
    
    # Extract test information from session or request
    test_title = request.GET.get('test_title')
    academic_year = request.GET.get('academic_year')
    semester = request.GET.get('semester')
    
    try:
        from .services.file_processing_service import FileProcessingService
        
        response = FileProcessingService.generate_template_with_info(
            file_type=file_type,
            test_type=test_type,
            question_count=question_count,
            test_title=test_title,
            academic_year=academic_year,
            semester=semester
        )
        
        if response:
            return response
        else:
            messages.error(request, 'Failed to generate template')
            return redirect('main:answer_keys')
            
    except Exception as e:
        messages.error(request, f'Error generating template: {str(e)}')
        return redirect('main:answer_keys')

@login_required
def upload_answer_key(request):
    """Upload and process answer key file (image, PDF, or CSV)"""
    if request.method == 'POST':
        try:
            # Get form data
            test_name = request.POST.get('test_name', '').strip()
            test_type = request.POST.get('test_type', 'multiple_choice_4')
            question_count = int(request.POST.get('question_count', 50))
            course_id = request.POST.get('course')
            answer_key_file = request.FILES.get('answer_key_file')
            
            # Enforce 200 question maximum
            if question_count < 1 or question_count > 200:
                return JsonResponse({
                    'success': False,
                    'message': 'Question count must be between 1 and 200.',
                    'errors': {'question_count': 'Invalid question count'}
                })
            
            # Processing options
            processing_options = {
                'auto_detect_format': request.POST.get('auto_detect_format') == 'on',
                'enhance_image': request.POST.get('enhance_image') == 'on',
                'validate_csv_format': request.POST.get('validate_csv_format') == 'on',
            }
            review_before_save = request.POST.get('review_before_save') == 'on'
            
            # Validate required fields
            if not all([test_name, course_id, answer_key_file]):
                return JsonResponse({
                    'success': False,
                    'message': 'Please fill in all required fields and upload a file.',
                    'errors': {'required_fields': 'Missing required data'}
                })
            
            # Get course
            try:
                from .models import Courses
                course = Courses.objects.get(id=course_id, user=request.user)
            except Courses.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': 'Invalid course selected.',
                    'errors': {'course': 'Course not found'}
                })
            
            # Process the uploaded file
            processing_result = FileProcessingService.process_uploaded_file(
                uploaded_file=answer_key_file,
                test_type=test_type,
                question_count=question_count,
                processing_options=processing_options
            )
            
            if not processing_result['success']:
                return JsonResponse({
                    'success': False,
                    'message': processing_result.get('message', 'Failed to process file'),
                    'errors': processing_result.get('errors', {})
                })
            
            # Analyze detection quality
            confidence_scores = processing_result.get('confidence_scores', {})
            if confidence_scores:
                avg_confidence = sum(confidence_scores.values()) / len(confidence_scores)
                low_confidence_count = len([c for c in confidence_scores.values() if c < 0.6])
                
                # Force review if many low confidence detections
                if avg_confidence < 0.5 or low_confidence_count > question_count * 0.3:
                    review_before_save = True
            
            # Create test data
            test_data = {
                'course_id': course.id,
                'test_name': test_name,
                'test_type': test_type,
                'question_count': question_count,
                'extracted_answers': processing_result['answers'],
                'confidence_scores': processing_result.get('confidence_scores', {}),
                'processing_metadata': processing_result.get('metadata', {})
            }
            
            # Add detection quality info
            if confidence_scores:
                test_data['processing_metadata'].update({
                    'avg_confidence': avg_confidence * 100,
                    'low_confidence_count': low_confidence_count,
                    'detection_quality': 'High' if avg_confidence > 0.8 else 'Medium' if avg_confidence > 0.5 else 'Low'
                })
            
            if review_before_save:
                # Store data for review
                SessionHelper.store_temp_test_data(request, test_data)
                
                quality_message = ""
                if confidence_scores:
                    if avg_confidence < 0.5:
                        quality_message = " Some answers have low confidence - please review carefully."
                    elif low_confidence_count > 0:
                        quality_message = f" {low_confidence_count} answers need verification."
                
                return JsonResponse({
                    'success': True,
                    'review_required': True,
                    'review_url': f"/answer-keys/review-upload/",
                    'message': f'Image processed successfully.{quality_message} Please review the detected answers.'
                })
            else:
                # Save directly
                test_info = AnswerKeyService.create_test_from_upload(request.user, test_data)
                return JsonResponse({
                    'success': True,
                    'review_required': False,
                    'message': f'Answer key for "{test_name}" has been created successfully from uploaded file!'
                })
                
        except ValueError as e:
            return JsonResponse({
                'success': False,
                'message': 'Invalid data provided. Please check your inputs.',
                'errors': {'validation': str(e)}
            })
        except Exception as e:
            logger.error(f"Upload processing error: {str(e)}")
            return JsonResponse({
                'success': False,
                'message': 'An error occurred while processing the file.',
                'errors': {'processing': str(e)}
            })
    
    return JsonResponse({
        'success': False,
        'message': 'Invalid request method.'
    })

@login_required
def review_upload(request):
    """Review extracted answers before saving"""
    temp_test_data = SessionHelper.get_temp_test_data(request)
    if not temp_test_data or 'extracted_answers' not in temp_test_data:
        messages.error(request, 'No upload data found. Please upload an answer key first.')
        return redirect('main:answer_keys')
    
    if request.method == 'POST':
        if 'save_answers' in request.POST:
            # Save the reviewed answers
            try:
                # Update answers with any manual corrections
                corrected_answers = {}
                for i in range(1, temp_test_data['question_count'] + 1):
                    answer = request.POST.get(f'question_{i}')
                    if answer:
                        corrected_answers[i] = answer
                
                temp_test_data['extracted_answers'] = corrected_answers
                test_info = AnswerKeyService.create_test_from_upload(request.user, temp_test_data)
                
                SessionHelper.clear_temp_test_data(request)
                messages.success(request, f'Answer key for "{test_info.test_name}" has been saved successfully!')
                return redirect('main:answer_keys')
                
            except Exception as e:
                messages.error(request, f'Error saving answer key: {str(e)}')
    
    # Prepare context for review template
    from .models import Courses
    try:
        course = Courses.objects.get(id=temp_test_data['course_id'])
    except Courses.DoesNotExist:
        messages.error(request, 'Course not found.')
        return redirect('main:answer_keys')
    
    # Get answer choices for the test type
    answer_choices = get_answer_choices_for_type(temp_test_data['test_type'])
    
    # Normalize extracted answers to use integer keys
    extracted_answers = temp_test_data.get('extracted_answers', {})
    normalized_answers = {}
    for key, value in extracted_answers.items():
        try:
            # Convert string keys to integers
            int_key = int(key)
            normalized_answers[int_key] = value
        except (ValueError, TypeError):
            # Keep non-numeric keys as-is
            normalized_answers[key] = value
    
    # Normalize confidence scores to use integer keys
    confidence_scores = temp_test_data.get('confidence_scores', {})
    normalized_confidence = {}
    for key, value in confidence_scores.items():
        try:
            # Convert string keys to integers
            int_key = int(key)
            normalized_confidence[int_key] = value
        except (ValueError, TypeError):
            # Keep non-numeric keys as-is
            normalized_confidence[key] = value
    
    # Update the temp_test_data with normalized keys
    temp_test_data['extracted_answers'] = normalized_answers
    temp_test_data['confidence_scores'] = normalized_confidence
    
    context = {
        'page_title': f'Review Extracted Answers - {temp_test_data["test_name"]}',
        'current_page': 'answer_keys',
        'test_data': temp_test_data,
        'course': course,
        'answer_choices': answer_choices,
        'confidence_scores': normalized_confidence,
        'processing_metadata': temp_test_data.get('processing_metadata', {})
    }
    return render(request, 'main/answer_keys_review.html', context)

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

@login_required
def download_template(request):
    """Download template files with test information"""
    file_type = request.GET.get('file_type', 'pdf')
    test_type = request.GET.get('test_type', 'multiple_choice_4')
    question_count = int(request.GET.get('question_count', 50))
    
    # Extract test information from session or request
    test_title = request.GET.get('test_title')
    academic_year = request.GET.get('academic_year')
    semester = request.GET.get('semester')
    
    try:
        from .services.file_processing_service import FileProcessingService
        
        response = FileProcessingService.generate_template_with_info(
            file_type=file_type,
            test_type=test_type,
            question_count=question_count,
            test_title=test_title,
            academic_year=academic_year,
            semester=semester
        )
        
        if response:
            return response
        else:
            messages.error(request, 'Failed to generate template')
            return redirect('main:answer_keys')
            
    except Exception as e:
        messages.error(request, f'Error generating template: {str(e)}')
        return redirect('main:answer_keys')

@login_required
def student_management(request):
    """Student Management - View and manage students"""
    # Handle filter form
    filter_form = StudentFilterForm(request.GET or None)
    filters = None
    
    if filter_form.is_valid():
        filters = {
            'search': filter_form.cleaned_data.get('search'),
            'section': filter_form.cleaned_data.get('section'),
            'sort_by': filter_form.cleaned_data.get('sort_by', 'last_name')
        }
    
    user_students = StudentService.get_user_students(request.user, filters)
    student_stats = StudentService.get_student_stats(request.user, filters)
    unique_sections = StudentService.get_unique_sections(request.user)
    
    # Pagination
    paginator = Paginator(user_students, 10)  # Show 10 students per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_title': 'Students',
        'current_page': 'student_management',
        'user_students': page_obj,
        'student_stats': student_stats,
        'student_form': StudentForm(user=request.user),
        'filter_form': filter_form,
        'unique_sections': unique_sections,
        'has_filters': any(filters.values()) if filters else False
    }
    return render(request, 'main/student_management.html', context)

@login_required
def add_student(request):
    """Add a new student"""
    if request.method == 'POST':
        form = StudentForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                # Check if at least one course is selected
                courses = form.cleaned_data.get('courses', [])
                if not courses:
                    return JsonResponse({
                        'success': False,
                        'errors': {'courses': ['Please select at least one course for the student.']}
                    })
                
                student = StudentService.create_student(request.user, form.cleaned_data)
                
                # Get assigned courses count for success message
                course_count = len(courses)
                if course_count == 1:
                    course_msg = f" and assigned to {course_count} course"
                else:
                    course_msg = f" and assigned to {course_count} courses"
                
                return JsonResponse({
                    'success': True,
                    'message': f'Student "{student.first_name} {student.last_name}" has been added successfully{course_msg}!'
                })
                
            except ValidationError as e:
                return JsonResponse({
                    'success': False,
                    'errors': {'__all__': [str(e)]}
                })
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'errors': {'__all__': [f'An unexpected error occurred: {str(e)}']}
                })
        else:
            # Format form errors for JSON response
            errors = {}
            for field, field_errors in form.errors.items():
                errors[field] = [error for error in field_errors]
            
            return JsonResponse({
                'success': False,
                'errors': errors
            })
    
    return redirect('main:student_management')

@login_required
def edit_student(request, student_id):
    """Edit an existing student"""
    if request.method == 'POST':
        form = StudentForm(request.POST, user=request.user, student_id=student_id)
        if form.is_valid():
            try:
                # Check if at least one course is selected
                courses = form.cleaned_data.get('courses', [])
                if not courses:
                    return JsonResponse({
                        'success': False,
                        'errors': {'courses': ['Please select at least one course for the student.']}
                    })
                
                student = StudentService.update_student(student_id, request.user, form.cleaned_data)
                
                # Get assigned courses count for success message
                course_count = len(courses)
                if course_count == 1:
                    course_msg = f" and assigned to {course_count} course"
                else:
                    course_msg = f" and assigned to {course_count} courses"
                
                return JsonResponse({
                    'success': True,
                    'message': f'Student "{student.first_name} {student.last_name}" has been updated successfully{course_msg}!'
                })
                
            except ValidationError as e:
                return JsonResponse({
                    'success': False,
                    'errors': {'__all__': [str(e)]}
                })
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'errors': {'__all__': [f'An unexpected error occurred: {str(e)}']}
                })
        else:
            # Format form errors for JSON response
            errors = {}
            for field, field_errors in form.errors.items():
                errors[field] = [error for error in field_errors]
            
            return JsonResponse({
                'success': False,
                'errors': errors
            })
    
    return redirect('main:student_management')

@login_required
def delete_student(request, student_id):
    """Delete a student"""
    try:
        student_name = StudentService.delete_student(student_id, request.user)
        messages.success(request, f'Student "{student_name}" has been deleted successfully!')
    except Exception as e:
        messages.error(request, f'Error deleting student: {str(e)}')
    
    return redirect('main:student_management')

@login_required
def get_student_courses(request, student_id):
    """Get courses assigned to a student (AJAX endpoint)"""
    try:
        student, courses = StudentService.get_student_with_courses(student_id, request.user)
        course_data = [
            {
                'id': course.id,
                'course_code': course.course_code,
                'course_name': course.course_name,
                'academic_year': course.academic_year or '',
                'semester': course.semester or ''
            }
            for course in courses
        ]
        return JsonResponse({'courses': course_data})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=404)

@login_required
def export_results(request):
    """Export Results - Download results as CSV/PDF"""
    context = {'page_title': 'Export Results', 'current_page': 'export_results'}
    return render(request, 'main/export_results.html', context)

@login_required
def analytics(request):
    """Performance Analytics - View common mistakes and trends"""
    context = {'page_title': 'Performance Analytics', 'current_page': 'analytics'}
    return render(request, 'main/analytics.html', context)

@csrf_exempt
@login_required
@require_POST
def process_answer_sheets_pdf(request):
    """
    API endpoint to process one or more uploaded PDF answer sheets.
    Accepts multiple files via 'pdf_files' (multipart/form-data).
    Returns JSON with extracted student info and answers for each file.
    """
    import json

    # Get parameters from POST or use defaults
    question_count = int(request.POST.get('question_count', 100))
    test_type = request.POST.get('test_type', 'multiple_choice_4')
    # Optional: output_dir for debug images (not required for web)
    output_dir = None

    # Accept multiple files
    pdf_files = request.FILES.getlist('pdf_files')
    if not pdf_files:
        return JsonResponse({'success': False, 'error': 'No PDF files uploaded.'}, status=400)

    # Save uploaded files temporarily and collect paths
    import tempfile
    temp_files = []
    for f in pdf_files:
        suffix = '.pdf'
        temp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        for chunk in f.chunks():
            temp.write(chunk)
        temp.close()
        temp_files.append(temp.name)

    # Process PDFs
    service = CheckmateService()
    results = service.process_pdfs(temp_files, question_count=question_count, test_type=test_type, output_dir=output_dir)

    # Clean up temp files
    for path in temp_files:
        try:
            os.remove(path)
        except Exception:
            pass

    return JsonResponse({'success': True, 'results': results})

    # This endpoint is working correctly.
    # The log message:
    # [20/Jun/2025 18:28:01] "POST /process-answer-sheets/ HTTP/1.1" 200 1422
    # means your endpoint is being called and returning a valid response.

    # The log message:
    # Not Found: /.well-known/appspecific/com.chrome.devtools.json
    # [20/Jun/2025 18:28:10] "GET /.well-known/appspecific/com.chrome.devtools.json HTTP/1.1" 404 8507
    # is unrelated to your grading or answer sheet processing.
    # It is a request from Chrome DevTools or a browser extension probing for debugging endpoints.
    # You can safely ignore this 404 error; it does not affect your application.