from ..forms import SignUpForm, LoginForm

class AuthFormHelper:
    """Helper class for authentication form operations"""
    
    @staticmethod
    def create_login_form(request_data=None):
        """Create login form instance"""
        if request_data:
            return LoginForm(request_data.get('request'), data=request_data.get('POST'))
        return LoginForm()
    
    @staticmethod
    def create_signup_form(request_data=None):
        """Create signup form instance"""
        return SignUpForm(request_data)
    
    @staticmethod
    def process_login_form(request, form):
        """Process login form and return user if valid"""
        if form.is_valid():
            return form.get_user()
        return None
    
    @staticmethod
    def process_signup_form(form):
        """Process signup form and return user if valid"""
        if form.is_valid():
            return form.save()
        return None
