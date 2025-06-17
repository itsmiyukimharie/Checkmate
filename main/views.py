from django.shortcuts import render, redirect
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
import csv

# Make WeasyPrint import truly optional
WEASYPRINT_AVAILABLE = False
try:
    from weasyprint import HTML, CSS
    from weasyprint.fonts import FontConfiguration
    WEASYPRINT_AVAILABLE = True
except (ImportError, OSError) as e:
    # Handle both import errors and OS errors (like missing system libraries)
    WEASYPRINT_AVAILABLE = False

from .forms import SignUpForm, LoginForm, CreateAnswerKeyForm, AnswerKeyEntryForm, UploadAnswerKeyForm
from .models import TestInformation, TestAnswerKey

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
def test_overview(request):
    """Test Management Section - View test overview"""
    context = {
        'page_title': 'Test Overview',
        'current_page': 'test_overview'
    }
    return render(request, 'main/test_overview.html', context)

@login_required
def answer_keys(request):
    """Answer Keys Management - Upload or create answer keys"""
    # Get user's existing tests
    user_tests = TestInformation.objects.filter(user=request.user).prefetch_related('answer_keys')
    
    if request.method == 'POST':
        if 'create_form' in request.POST:
            # Handle create form
            create_form = CreateAnswerKeyForm(request.POST)
            if create_form.is_valid():
                # Don't save to DB yet, just pass data to enter_answers view
                test_data = {
                    'test_name': create_form.cleaned_data['test_name'],
                    'test_type': create_form.cleaned_data['test_type'],
                    'question_count': create_form.cleaned_data['question_count']
                }
                
                # Store in session for the enter_answers view
                request.session['temp_test_data'] = test_data
                
                messages.success(request, f'Test "{test_data["test_name"]}" setup complete. Please enter answers to save.')
                return redirect('main:enter_answers', test_id=0)  # Use 0 for new test
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
    # Handle new test creation (test_id = 0)
    if test_id == 0:
        temp_test_data = request.session.get('temp_test_data')
        if not temp_test_data:
            messages.error(request, 'No test data found. Please create a new test.')
            return redirect('main:answer_keys')
        
        # Create a temporary test object for form generation (not saved to DB)
        test_info = TestInformation(
            test_name=temp_test_data['test_name'],
            test_type=temp_test_data['test_type'],
            question_count=temp_test_data['question_count']
        )
        is_new_test = True
    else:
        # Handle existing test
        try:
            test_info = TestInformation.objects.get(id=test_id, user=request.user)
            is_new_test = False
        except TestInformation.DoesNotExist:
            messages.error(request, 'Test not found.')
            return redirect('main:answer_keys')
    
    # Get answer choices based on test type
    answer_choices = test_info.get_answer_choices()
    
    if request.method == 'POST':
        form = AnswerKeyEntryForm(
            request.POST,
            question_count=test_info.question_count,
            answer_choices=answer_choices
        )
        if form.is_valid():
            if is_new_test:
                # Now save the test to database
                test_info.user = request.user
                test_info.name = test_info.test_name
                test_info.status = 'draft'
                test_info.save()
                
                # Clear session data
                if 'temp_test_data' in request.session:
                    del request.session['temp_test_data']
            else:
                # Delete existing answers for existing test
                TestAnswerKey.objects.filter(test_information=test_info).delete()
            
            # Save new answers
            for i in range(1, test_info.question_count + 1):
                answer = form.cleaned_data[f'question_{i}']
                TestAnswerKey.objects.create(
                    test_information=test_info,
                    question_number=i,
                    answer=answer
                )
            
            messages.success(request, f'Answer key for "{test_info.test_name}" has been saved successfully!')
            return redirect('main:answer_keys')
    else:
        if is_new_test:
            # New test - no existing answers
            form = AnswerKeyEntryForm(
                question_count=test_info.question_count,
                answer_choices=answer_choices
            )
        else:
            # Load existing answers if they exist
            existing_answers = TestAnswerKey.objects.filter(test_information=test_info)
            initial_data = {}
            for answer_key in existing_answers:
                initial_data[f'question_{answer_key.question_number}'] = answer_key.answer
            
            form = AnswerKeyEntryForm(
                initial=initial_data,
                question_count=test_info.question_count,
                answer_choices=answer_choices
            )
    
    context = {
        'page_title': f'Enter Answers - {test_info.test_name}',
        'current_page': 'answer_keys',
        'test_info': test_info,
        'form': form,
        'answer_choices': answer_choices,
        'is_new_test': is_new_test
    }
    return render(request, 'main/answer_keys_enter.html', context)

@login_required
def delete_test(request, test_id):
    """Delete a test and its answer keys"""
    try:
        test_info = TestInformation.objects.get(id=test_id, user=request.user)
        test_name = test_info.test_name
        test_info.delete()  # This will cascade delete answer keys
        messages.success(request, f'Test "{test_name}" has been deleted successfully!')
    except TestInformation.DoesNotExist:
        messages.error(request, 'Test not found.')
    
    return redirect('main:answer_keys')

@login_required
def grade_test(request):
    """Grade Test - Upload answer sheets and process grading"""
    context = {
        'page_title': 'Grade Test',
        'current_page': 'grade_test'
    }
    return render(request, 'main/grade_test.html', context)

@login_required
def export_results(request):
    """Export Results - Download results as CSV/PDF"""
    context = {
        'page_title': 'Export Results',
        'current_page': 'export_results'
    }
    return render(request, 'main/export_results.html', context)

@login_required
def analytics(request):
    """Performance Analytics - View common mistakes and trends"""
    context = {
        'page_title': 'Performance Analytics',
        'current_page': 'analytics'
    }
    return render(request, 'main/analytics.html', context)

def landingpage(request):
    """Landing page - main entry point"""
    # Redirect to dashboard if user is already logged in
    if request.user.is_authenticated:
        return redirect('main:dashboard')
    
    context = {
        'page_title': 'CheckMate - AI-Powered Test Score Scanner',
    }
    return render(request, 'main/landingpage.html', context)

def login(request):
    """Login page"""
    if request.user.is_authenticated:
        return redirect('main:dashboard')
    
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            auth_login(request, user)
            messages.success(request, f'Welcome back, {user.first_name}!')
            next_url = request.GET.get('next', 'main:dashboard')
            return redirect(next_url)
        else:
            messages.error(request, 'Invalid email or password.')
    else:
        form = LoginForm()
    
    context = {
        'page_title': 'Login - CheckMate',
        'form': form
    }
    return render(request, 'main/login.html', context)

def signup(request):
    """Signup page"""
    if request.user.is_authenticated:
        return redirect('main:dashboard')
    
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user)
            messages.success(request, f'Welcome to CheckMate, {user.first_name}!')
            return redirect('main:dashboard')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = SignUpForm()
    
    context = {
        'page_title': 'Sign Up - CheckMate',
        'form': form
    }
    return render(request, 'main/signup.html', context)

def logout(request):
    """Logout user"""
    auth_logout(request)
    messages.info(request, 'You have been successfully logged out.')
    return redirect('main:landingpage')

@login_required
def download_answer_key(request, test_id):
    """Download answer key as CSV file"""
    try:
        test_info = TestInformation.objects.get(id=test_id, user=request.user)
        answer_keys = TestAnswerKey.objects.filter(test_information=test_info).order_by('question_number')
    except TestInformation.DoesNotExist:
        messages.error(request, 'Test not found.')
        return redirect('main:answer_keys')
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="answer_key_{test_info.test_name.replace(" ", "_")}.csv"'
    
    writer = csv.writer(response)
    
    # Write structured header for machine processing
    writer.writerow(['# CheckMate Answer Key - Machine Readable Format'])
    writer.writerow(['# Test Name:', test_info.test_name])
    writer.writerow(['# Test Type:', test_info.test_type])
    writer.writerow(['# Question Count:', test_info.question_count])
    writer.writerow(['# Answer Choices:', ','.join(test_info.get_answer_choices())])
    writer.writerow(['# Created:', test_info.created_at.isoformat()])
    writer.writerow(['# Generated:', test_info.updated_at.isoformat()])
    writer.writerow([])  # Empty row separator
    
    # Write structured answer data for comparison
    writer.writerow(['question_number', 'correct_answer', 'answer_index'])
    
    answer_choices = test_info.get_answer_choices()
    
    if answer_keys:
        for answer_key in answer_keys:
            # Get answer index for numerical comparison
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
    
    # Write additional metadata for verification
    writer.writerow([])
    writer.writerow(['# Metadata for Verification'])
    writer.writerow(['# Total Questions Expected:', test_info.question_count])
    writer.writerow(['# Total Answers Provided:', len(answer_keys)])
    writer.writerow(['# Answer Choice Count:', len(answer_choices)])
    writer.writerow(['# Format Version:', '1.0'])
    writer.writerow(['# Compatible with CheckMate Image Processing'])
    
    # Write answer choice mapping for reference
    writer.writerow([])
    writer.writerow(['# Answer Choice Mapping'])
    writer.writerow(['index', 'choice', 'display'])
    for i, choice in enumerate(answer_choices):
        display = 'T' if choice == 'True' else 'F' if choice == 'False' else choice
        writer.writerow([i, choice, display])
    
    return response

@login_required
def print_answer_key_data(request, test_id):
    """Return answer key data as JSON for printing"""
    try:
        test_info = TestInformation.objects.get(id=test_id, user=request.user)
        answer_keys = TestAnswerKey.objects.filter(test_information=test_info).order_by('question_number')
    except TestInformation.DoesNotExist:
        return JsonResponse({'error': 'Test not found'}, status=404)
    
    data = {
        'test_info': {
            'test_name': test_info.test_name,
            'test_type_display': test_info.get_test_type_display(),
            'question_count': test_info.question_count,
            'created_at': test_info.created_at.isoformat(),
        },
        'answer_keys': [
            {
                'question_number': ak.question_number,
                'answer': ak.answer
            }
            for ak in answer_keys
        ],
        'answer_choices': test_info.get_answer_choices()
    }
    
    return JsonResponse(data)

@login_required
def print_answer_key(request, test_id):
    """Print answer key in a simple HTML format"""
    try:
        test_info = TestInformation.objects.get(id=test_id, user=request.user)
        answer_keys = TestAnswerKey.objects.filter(test_information=test_info).order_by('question_number')
    except TestInformation.DoesNotExist:
        messages.error(request, 'Test not found.')
        return redirect('main:answer_keys')
    
    # Get answer choices based on test type
    answer_choices = test_info.get_answer_choices()
    
    context = {
        'test_info': test_info,
        'answer_keys': answer_keys,
        'answer_choices': answer_choices,
        'page_title': f'Print Answer Key - {test_info.test_name}'
    }
    return render(request, 'main/answer_keys_print.html', context)