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

# Placeholder models - implement these when building the backend
# class Test(models.Model):
#     pass

# class AnswerKey(models.Model):
#     pass

# class StudentResponse(models.Model):
#     pass

# class GradingResult(models.Model):
#     pass
