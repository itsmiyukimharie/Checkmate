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
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tests')
    name = models.CharField(max_length=100)
    test_name = models.CharField(max_length=100)
    question_count = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'main_test_information'
        ordering = ['-created_at']

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
