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
    course = models.ForeignKey('Courses', on_delete=models.CASCADE, related_name='tests', help_text="Course associated with the test")
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

class Courses(models.Model):
    """Model to represent a course"""
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='courses')
    course_name = models.CharField(max_length=100)
    academic_year = models.CharField(max_length=20, blank=True, null=True, help_text="e.g., 2023-2024")
    semester = models.CharField(max_length=20, blank=True, null=True, help_text="e.g., 1st Semester, 2nd Semester, 3rd Semester, Summer")
    name = models.CharField(max_length=100, blank=True, null=True, help_text="Optional course name")
    course_code = models.CharField(max_length=20, help_text="Course identifier")
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'main_courses'
        ordering = ['-created_at']
        unique_together = ('user', 'course_code')  # Unique per user

    def __str__(self):
        return self.course_name
    
class Students(models.Model):
    """Model to represent a student"""
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='students')
    student_id = models.CharField(max_length=20, help_text="Student identifier")
    first_name = models.CharField(max_length=30)
    middle_name = models.CharField(max_length=30, blank=True, null=True, help_text="Optional middle name")
    last_name = models.CharField(max_length=30)
    email = models.EmailField(blank=True, null=True)
    section = models.CharField(max_length=20, blank=True, null=True, help_text="Student's section")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'main_students'
        ordering = ['last_name', 'first_name']
        unique_together = ('user', 'student_id')  # Unique per user

    def __str__(self):
        return f"{self.last_name}, {self.first_name} ({self.student_id})"
    

class AssignedCourse(models.Model):
    """Model to represent a course assigned to a student"""
    id = models.AutoField(primary_key=True)
    course = models.ForeignKey(Courses, on_delete=models.CASCADE, related_name='assigned_courses')
    student = models.ForeignKey(Students, on_delete=models.CASCADE, related_name='assigned_courses')

    class Meta:
        db_table = 'main_assigned_course'
        unique_together = ('course', 'student')

    def __str__(self):
        return f"{self.student} assigned to {self.course}"
    
class TestResult(models.Model):
    """Model to represent a student's test result"""
    id = models.AutoField(primary_key=True)
    test_information = models.ForeignKey(TestInformation, on_delete=models.CASCADE, related_name='test_results')
    student = models.ForeignKey(Students, on_delete=models.CASCADE, related_name='test_results')
    score = models.FloatField(help_text="Score achieved by the student")
    total_questions = models.IntegerField(help_text="Total number of questions in the test")
    correct_answers = models.IntegerField(help_text="Number of correct answers")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'main_test_result'
        unique_together = ('test_information', 'student')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.student} - {self.test_information.test_name} - Score: {self.score}"
    
class SpecificTestResult(models.Model):
    """Model to represent a specific test result for a student"""
    id = models.AutoField(primary_key=True)
    test_result = models.ForeignKey(TestResult, on_delete=models.CASCADE, related_name='specific_results')
    question_number = models.IntegerField(help_text="Question number in the test")
    student_answer = models.CharField(max_length=100, help_text="Answer provided by the student")
    is_correct = models.BooleanField(default=False, help_text="Whether the student's answer is correct")

    class Meta:
        db_table = 'main_specific_test_result'
        unique_together = ('test_result', 'question_number')
        ordering = ['question_number']

    def __str__(self):
        return f"Q{self.question_number} - {self.student_answer} ({'Correct' if self.is_correct else 'Incorrect'})"


