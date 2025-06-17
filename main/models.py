from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    """Custom User model with additional fields"""
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    institution = models.CharField(max_length=200, blank=True)
    date_joined = models.DateTimeField(auto_now_add=True)
    is_verified = models.BooleanField(default=False)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.email})"
    
    class Meta:
        db_table = 'main_user'

class TestInformation(models.Model):
    """Model to represent a test individual"""
    TEST_TYPE_CHOICES = [
        ('multiple_choice_4', 'Multiple Choice (A-D)'),
        ('multiple_choice_5', 'Multiple Choice (A-E)'),
        ('true_false', 'True or False'),
    ]
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('active', 'Active'),
    ]
    
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tests')
    name = models.CharField(max_length=100)
    test_name = models.CharField(max_length=100)
    test_type = models.CharField(max_length=20, choices=TEST_TYPE_CHOICES, default='multiple_choice_4')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    question_count = models.IntegerField()
    answer_key_image = models.ImageField(upload_to='answer_keys/', null=True, blank=True, help_text="Upload answer key image for processing")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'main_test_information'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.test_name} - {self.question_count} questions"

    def get_answer_choices(self):
        """Return available answer choices based on test type"""
        if self.test_type == 'multiple_choice_4':
            return ['A', 'B', 'C', 'D']
        elif self.test_type == 'multiple_choice_5':
            return ['A', 'B', 'C', 'D', 'E']
        elif self.test_type == 'true_false':
            return ['True', 'False']
        else:
            return ['A', 'B', 'C', 'D']  # Default

class TestAnswerKey(models.Model):
    """Model to represent the answer key for a test"""
    id = models.AutoField(primary_key=True)
    test_information = models.ForeignKey(TestInformation, on_delete=models.CASCADE, related_name='answer_keys')
    question_number = models.IntegerField()
    answer = models.CharField(max_length=100)

    class Meta:
        db_table = 'main_test_answer_key'
        unique_together = ('test_information', 'question_number')
        ordering = ['question_number']

    def __str__(self):
        return f"Q{self.question_number}: {self.answer}"
