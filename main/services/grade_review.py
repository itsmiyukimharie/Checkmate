from django.core.exceptions import ValidationError
from ..models import Students

class GradeReviewService:
    """
    Service class for reviewing graded answer sheets and resolving student info.
    """

    @staticmethod
    def get_student_by_id_for_user(student_id, user):
        """
        Get a Students object by its primary key (id) and user.
        Returns the student instance if found, otherwise returns None.
        """
        try:
            return Students.objects.get(id=student_id, user=user)
        except Students.DoesNotExist:
            return None

    @staticmethod
    def get_student_by_student_id_for_user(student_id_str, user):
        """
        Get a Students object by its student_id field and user.
        Returns the student instance if found, otherwise returns None.
        """
        try:
            return Students.objects.get(student_id=student_id_str, user=user)
        except Students.DoesNotExist:
            return None

    @staticmethod
    def get_student_or_message(student_id, user):
        """
        Get a Students object by id and user, or return a not found message.
        """
        student = GradeReviewService.get_student_by_id_for_user(student_id, user)
        if student:
            return student
        return "Student not found for your account."