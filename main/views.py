from django.shortcuts import render, redirect
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from .forms import SignUpForm, LoginForm

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
    context = {
        'page_title': 'Manage Answer Keys',
        'current_page': 'answer_keys'
    }
    return render(request, 'main/answer_keys.html', context)

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