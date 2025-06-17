from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse

from .forms import CreateAnswerKeyForm, CourseForm, CourseFilterForm
from .services.answer_key_service import AnswerKeyService
from .services.auth_service import AuthService
from .services.course_service import CourseService
from .utils.form_helpers import FormHelper
from .utils.session_helpers import SessionHelper
from .utils.auth_helpers import AuthFormHelper

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
    
    if request.method == 'POST' and 'create_form' in request.POST:
        create_form = FormHelper.create_answer_key_form(request.POST)
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
        'create_form': CreateAnswerKeyForm()
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
    except:
        messages.error(request, 'Test not found.')
    
    return redirect('main:answer_keys')

@login_required
def download_answer_key(request, test_id):
    """Download answer key as CSV file"""
    try:
        test_info, answer_keys = AnswerKeyService.get_test_with_answers(test_id, request.user)
        return AnswerKeyService.generate_csv_response(test_info, answer_keys)
    except:
        messages.error(request, 'Test not found.')
        return redirect('main:answer_keys')

@login_required
def print_answer_key_data(request, test_id):
    """Return answer key data as JSON for printing"""
    try:
        test_info, answer_keys = AnswerKeyService.get_test_with_answers(test_id, request.user)
        data = AnswerKeyService.generate_print_data(test_info, answer_keys)
        return JsonResponse(data)
    except:
        return JsonResponse({'error': 'Test not found'}, status=404)

@login_required
def print_answer_key(request, test_id):
    """Print answer key in a simple HTML format"""
    try:
        test_info, answer_keys = AnswerKeyService.get_test_with_answers(test_id, request.user)
        context = {
            'test_info': test_info,
            'answer_keys': answer_keys,
            'answer_choices': test_info.get_answer_choices(),
            'page_title': f'Print Answer Key - {test_info.test_name}'
        }
        return render(request, 'main/answer_keys_print.html', context)
    except:
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
    """Students Management - View and manage students"""
    context = {'page_title': 'Students', 'current_page': 'test_overview'}
    return render(request, 'main/student_management.html', context)

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
    from django.core.paginator import Paginator
    paginator = Paginator(user_courses, 10)  # Show 10 courses per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_title': 'Courses',
        'current_page': 'course_management',
        'user_courses': page_obj,
        'course_stats': course_stats,
        'course_form': CourseForm(),
        'filter_form': filter_form,
        'unique_years': unique_years,
        'has_filters': any(filters.values()) if filters else False
    }
    return render(request, 'main/course_management.html', context)

@login_required
def add_course(request):
    """Add a new course"""
    if request.method == 'POST':
        form = CourseForm(request.POST)
        if form.is_valid():
            try:
                course = CourseService.create_course(request.user, form.cleaned_data)
                messages.success(request, f'Course "{course.course_name}" has been created successfully!')
                return redirect('main:course_management')
            except ValidationError as e:
                messages.error(request, str(e))
            except Exception as e:
                messages.error(request, f'Error creating course: {str(e)}')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field.title()}: {error}')
    
    return redirect('main:course_management')

@login_required
def edit_course(request, course_id):
    """Edit an existing course"""
    if request.method == 'POST':
        form = CourseForm(request.POST)
        if form.is_valid():
            try:
                course = CourseService.update_course(course_id, request.user, form.cleaned_data)
                messages.success(request, f'Course "{course.course_name}" has been updated successfully!')
            except ValidationError as e:
                messages.error(request, str(e))
            except Exception as e:
                messages.error(request, f'Error updating course: {str(e)}')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field.title()}: {error}')
    
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