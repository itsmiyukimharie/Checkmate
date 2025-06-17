from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import authenticate
from .models import User, TestInformation, TestAnswerKey

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

class CreateAnswerKeyForm(forms.ModelForm):
    """Form for creating a new answer key"""
    
    class Meta:
        model = TestInformation
        fields = ['test_name', 'test_type', 'question_count']
        widgets = {
            'test_name': forms.TextInput(attrs={
                'class': 'form-control rounded-pill',
                'placeholder': 'Enter test name'
            }),
            'test_type': forms.Select(attrs={
                'class': 'form-select rounded-pill'
            }),
            'question_count': forms.NumberInput(attrs={
                'class': 'form-control rounded-pill',
                'min': 1,
                'max': 200,
                'value': 50
            })
        }

class AnswerKeyEntryForm(forms.Form):
    """Form for entering individual answer key answers"""
    def __init__(self, *args, **kwargs):
        question_count = kwargs.pop('question_count', 50)
        answer_choices = kwargs.pop('answer_choices', ['A', 'B', 'C', 'D'])
        super().__init__(*args, **kwargs)
        
        # Create choice tuples
        choices = [(choice, choice) for choice in answer_choices]
        
        # Generate fields for each question
        for i in range(1, question_count + 1):
            self.fields[f'question_{i}'] = forms.ChoiceField(
                choices=choices,
                widget=forms.Select(attrs={
                    'class': 'form-select form-select-sm'
                }),
                label=f'Q{i}'
            )

class UploadAnswerKeyForm(forms.ModelForm):
    """Form for uploading answer key file"""
    answer_key_image = forms.ImageField(
        widget=forms.FileInput(attrs={
            'class': 'form-control rounded-pill',
            'accept': 'image/*'
        }),
        help_text='Upload answer key image (JPG, PNG, etc.)'
    )
    
    class Meta:
        model = TestInformation
        fields = ['test_name', 'test_type', 'question_count', 'answer_key_image']
        widgets = {
            'test_name': forms.TextInput(attrs={
                'class': 'form-control rounded-pill',
                'placeholder': 'Enter test name'
            }),
            'test_type': forms.Select(attrs={
                'class': 'form-select rounded-pill'
            }),
            'question_count': forms.NumberInput(attrs={
                'class': 'form-control rounded-pill',
                'min': 1,
                'max': 200,
                'value': 50
            })
        }
