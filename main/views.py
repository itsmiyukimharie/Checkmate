from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
import logging

from .services.answer_key_service import AnswerKeyService
from .services.auth_service import AuthService
from .services.course_service import CourseService
from .services.student_service import StudentService
from .services.file_processing_service import FileProcessingService
from .utils.form_helpers import FormHelper
from .utils.session_helpers import SessionHelper
from .utils.auth_helpers import AuthFormHelper
from .forms import CreateAnswerKeyForm, CourseForm, CourseFilterForm, StudentForm, StudentFilterForm

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
    """Download answer key as CSV file"""
    try:
        test_info, answer_keys = AnswerKeyService.get_test_with_answers(test_id, request.user)
        show_answers = request.GET.get('show_answers', '1') == '1'
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
    """Print answer key in a simple HTML format"""
    try:
        test_info, answer_keys = AnswerKeyService.get_test_with_answers(test_id, request.user)
        
        # Check if we should show answers (default: True for backward compatibility)
        show_answers = request.GET.get('show_answers', '1') == '1'
        
        context = {
            'test_info': test_info,
            'answer_keys': answer_keys,
            'answer_choices': test_info.get_answer_choices(),
            'show_answers': show_answers,
            'page_title': f'Print {"Answer Key" if show_answers else "Blank Sheet"} - {test_info.test_name}'
        }
        return render(request, 'main/answer_keys_print.html', context)
    except Exception as e:
        messages.error(request, 'Test not found.')
        return redirect('main:answer_keys')

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
    context = {'page_title': 'Grade Test', 'current_page': 'grade_test'}
    return render(request, 'main/grade_test.html', context)

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
                'message': 'Invalid data provided.',
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