from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import authenticate
from .models import User

class SignUpForm(UserCreationForm):
    """Custom signup form with additional fields"""
    first_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your first name'
        })
    )
    last_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your last name'
        })
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your email address'
        })
    )
    institution = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your institution/school'
        })
    )
    password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Create a password'
        })
    )
    password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm your password'
        })
    )
    terms = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )
    
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'institution', 'password1', 'password2', 'terms')
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.username = self.cleaned_data['email']  # Use email as username
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.institution = self.cleaned_data['institution']
        if commit:
            user.save()
        return user

class LoginForm(AuthenticationForm):
    """Custom login form using email instead of username"""
    username = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your email address',
            'autofocus': True
        }),
        label='Email Address'
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your password'
        })
    )
    
    def clean(self):
        email = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')
        
        if email and password:
            try:
                user = User.objects.get(email=email)
                self.user_cache = authenticate(
                    self.request, 
                    username=user.username, 
                    password=password
                )
                if self.user_cache is None:
                    raise forms.ValidationError("Invalid email or password.")
                else:
                    self.confirm_login_allowed(self.user_cache)
            except User.DoesNotExist:
                raise forms.ValidationError("Invalid email or password.")
        
        return self.cleaned_data
