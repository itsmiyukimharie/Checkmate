from django.contrib.auth import login as auth_login, logout as auth_logout
from django.shortcuts import redirect
from django.contrib import messages

class AuthService:
    """Service class for authentication operations"""
    
    @staticmethod
    def login_user(request, user):
        """Login user and set success message"""
        auth_login(request, user)
        messages.success(request, f'Welcome back, {user.first_name}!')
        return AuthService._get_redirect_url(request)
    
    @staticmethod
    def signup_user(request, user):
        """Signup and login user with welcome message"""
        auth_login(request, user)
        messages.success(request, f'Welcome to CheckMate, {user.first_name}!')
        return 'main:dashboard'
    
    @staticmethod
    def logout_user(request):
        """Logout user and set info message"""
        auth_logout(request)
        messages.info(request, 'You have been successfully logged out.')
        return 'main:landingpage'
    
    @staticmethod
    def _get_redirect_url(request):
        """Get redirect URL from request or default to dashboard"""
        return request.GET.get('next', 'main:dashboard')
    
    @staticmethod
    def handle_login_error(request):
        """Handle login form errors"""
        messages.error(request, 'Invalid email or password.')
    
    @staticmethod
    def handle_signup_error(request):
        """Handle signup form errors"""
        messages.error(request, 'Please correct the errors below.')
    
    @staticmethod
    def is_authenticated(user):
        """Check if user is authenticated"""
        return user.is_authenticated
