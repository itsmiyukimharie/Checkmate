from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import authenticate
from .models import User, TestInformation, TestAnswerKey, Courses

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

class CourseForm(forms.ModelForm):
    """Form for creating and editing courses"""
    
    class Meta:
        model = Courses
        fields = ['course_code', 'course_name', 'description', 'academic_year', 'semester']
        widgets = {
            'course_code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., CS101, MATH201'
            }),
            'course_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Introduction to Computer Science'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Course description...'
            }),
            'academic_year': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., 2023-2024'
            }),
            'semester': forms.Select(attrs={
                'class': 'form-select'
            }, choices=[
                ('', 'Select Semester'),
                ('1st Semester', '1st Semester'),
                ('2nd Semester', '2nd Semester'),
                ('3rd Semester', '3rd Semester'),
                ('Summer', 'Summer')
            ])
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'form-control'})
        self.fields['semester'].widget.attrs.update({'class': 'form-select'})
    
    def clean_course_code(self):
        """Validate course code format"""
        course_code = self.cleaned_data.get('course_code')
        if course_code:
            # Remove extra spaces and convert to uppercase
            course_code = course_code.strip().upper()
            
            # Validate format (letters followed by numbers OR letters-numbers)
            import re
            pattern1 = r'^[A-Z]{2,4}[0-9]{1,4}$'  # CS101, MATH201
            pattern2 = r'^[A-Z]{2,4}-[0-9]{1,4}$'  # MATH-001, CS-101
            
            if not (re.match(pattern1, course_code) or re.match(pattern2, course_code)):
                raise forms.ValidationError(
                    'Course code must be 2-4 letters followed by 1-4 numbers (e.g., CS101, MATH201) or 2-4 letters, hyphen, then 1-4 numbers (e.g., MATH-001, CS-101)'
                )
        return course_code
    
    def clean_course_name(self):
        """Validate course name"""
        course_name = self.cleaned_data.get('course_name')
        if course_name:
            course_name = course_name.strip()
            if len(course_name) < 3:
                raise forms.ValidationError('Course name must be at least 3 characters long.')
        return course_name
    
    def clean_academic_year(self):
        """Validate academic year format"""
        academic_year = self.cleaned_data.get('academic_year')
        if academic_year:
            academic_year = academic_year.strip()
            # Validate format like 2023-2024
            import re
            if not re.match(r'^20\d{2}-20\d{2}$', academic_year):
                raise forms.ValidationError(
                    'Academic year must be in format YYYY-YYYY (e.g., 2023-2024)'
                )
            
            # Validate that second year is one year after first
            start_year, end_year = map(int, academic_year.split('-'))
            if end_year != start_year + 1:
                raise forms.ValidationError(
                    'End year must be exactly one year after start year.'
                )
        return academic_year

class CourseFilterForm(forms.Form):
    """Form for filtering courses"""
    search = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by course code or name...'
        })
    )
    
    semester = forms.ChoiceField(
        choices=[
            ('', 'All Semesters'),
            ('1st Semester', '1st Semester'),
            ('2nd Semester', '2nd Semester'),
            ('3rd Semester', '3rd Semester'),
            ('Summer', 'Summer'),
            ('not_specified', 'Not Specified')
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    academic_year = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., 2023-2024'
        })
    )
    
    sort_by = forms.ChoiceField(
        choices=[
            ('created_at', 'Newest First'),
            ('-created_at', 'Oldest First'),
            ('course_code', 'Course Code A-Z'),
            ('-course_code', 'Course Code Z-A'),
            ('course_name', 'Course Name A-Z'),
            ('-course_name', 'Course Name Z-A')
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
