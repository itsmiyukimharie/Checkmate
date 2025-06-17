from django.db.models import Q, Count
from django.core.exceptions import ValidationError
from ..models import Students, Courses, AssignedCourse

class StudentService:
    """Service class for student-related operations"""
    
    @staticmethod
    def get_user_students(user, filters=None):
        """Get students for a specific user with optional filters"""
        queryset = Students.objects.filter(user=user)
        
        if filters:
            # Search filter
            if filters.get('search'):
                search_term = filters['search']
                queryset = queryset.filter(
                    Q(student_id__icontains=search_term) |
                    Q(first_name__icontains=search_term) |
                    Q(last_name__icontains=search_term) |
                    Q(email__icontains=search_term)
                )
            
            # Section filter
            if filters.get('section'):
                if filters['section'] == 'not_specified':
                    queryset = queryset.filter(section__isnull=True)
                else:
                    queryset = queryset.filter(section=filters['section'])
            
            # Sort by
            if filters.get('sort_by'):
                queryset = queryset.order_by(filters['sort_by'])
            else:
                queryset = queryset.order_by('last_name', 'first_name')
        else:
            queryset = queryset.order_by('last_name', 'first_name')
        
        return queryset
    
    @staticmethod
    def get_student_stats(user, filters=None):
        """Get student statistics for the user"""
        queryset = Students.objects.filter(user=user)
        
        if filters:
            # Apply same filters as get_user_students
            if filters.get('search'):
                search_term = filters['search']
                queryset = queryset.filter(
                    Q(student_id__icontains=search_term) |
                    Q(first_name__icontains=search_term) |
                    Q(last_name__icontains=search_term) |
                    Q(email__icontains=search_term)
                )
            
            if filters.get('section'):
                if filters['section'] == 'not_specified':
                    queryset = queryset.filter(section__isnull=True)
                else:
                    queryset = queryset.filter(section=filters['section'])
        
        # Total students
        total_students = queryset.count()
        
        # Section statistics
        section_stats = {}
        section_counts = queryset.values('section').annotate(count=Count('id'))
        for item in section_counts:
            section = item['section'] or 'Not Specified'
            section_stats[section] = item['count']
        
        return {
            'total_students': total_students,
            'section_stats': section_stats
        }
    
    @staticmethod
    def get_unique_sections(user):
        """Get unique sections for the user's students"""
        sections = Students.objects.filter(
            user=user,
            section__isnull=False
        ).values_list('section', flat=True).distinct().order_by('section')
        
        return list(sections)
    
    @staticmethod
    def create_student(user, student_data):
        """Create a new student"""
        # Check for duplicate student ID for this user
        if Students.objects.filter(
            user=user,
            student_id=student_data['student_id']
        ).exists():
            raise ValidationError(f"You already have a student with ID '{student_data['student_id']}'.")
        
        # Check for duplicate email if provided
        if student_data.get('email'):
            if Students.objects.filter(
                user=user,
                email=student_data['email']
            ).exists():
                raise ValidationError(f"You already have a student with email '{student_data['email']}'.")
        
        # Extract courses from student_data
        courses = student_data.pop('courses', [])
        
        student = Students.objects.create(
            user=user,
            student_id=student_data['student_id'],
            first_name=student_data['first_name'],
            middle_name=student_data.get('middle_name', ''),
            last_name=student_data['last_name'],
            email=student_data.get('email', ''),
            section=student_data.get('section', '')
        )
        
        # Assign courses to the student
        if courses:
            StudentService._assign_courses_to_student(student, courses, user)
        
        return student
    
    @staticmethod
    def update_student(student_id, user, student_data):
        """Update an existing student"""
        try:
            student = Students.objects.get(id=student_id, user=user)
        except Students.DoesNotExist:
            raise ValidationError("Student not found or you don't have permission to edit it.")
        
        # Check for duplicate student ID (excluding current student)
        if Students.objects.filter(
            user=user,
            student_id=student_data['student_id']
        ).exclude(id=student_id).exists():
            raise ValidationError(f"You already have another student with ID '{student_data['student_id']}'.")
        
        # Check for duplicate email if provided (excluding current student)
        if student_data.get('email'):
            if Students.objects.filter(
                user=user,
                email=student_data['email']
            ).exclude(id=student_id).exists():
                raise ValidationError(f"You already have another student with email '{student_data['email']}'.")
        
        # Extract courses from student_data
        courses = student_data.pop('courses', [])
        
        # Update student fields
        student.student_id = student_data['student_id']
        student.first_name = student_data['first_name']
        student.middle_name = student_data.get('middle_name', '')
        student.last_name = student_data['last_name']
        student.email = student_data.get('email', '')
        student.section = student_data.get('section', '')
        student.save()
        
        # Update course assignments
        StudentService._update_student_courses(student, courses, user)
        
        return student
    
    @staticmethod
    def _assign_courses_to_student(student, courses, user):
        """Helper method to assign courses to a student"""
        assignments = []
        for course in courses:
            # Verify the course belongs to the user
            if course.user == user:
                assignment, created = AssignedCourse.objects.get_or_create(
                    student=student,
                    course=course
                )
                if created:
                    assignments.append(assignment)
        return assignments
    
    @staticmethod
    def _update_student_courses(student, courses, user):
        """Helper method to update course assignments for a student"""
        # Remove all existing assignments
        AssignedCourse.objects.filter(student=student).delete()
        
        # Add new assignments
        if courses:
            StudentService._assign_courses_to_student(student, courses, user)
    
    @staticmethod
    def get_student_with_courses(student_id, user):
        """Get a student with their assigned courses"""
        student = StudentService.get_student_by_id(student_id, user)
        assigned_courses = AssignedCourse.objects.filter(student=student).select_related('course')
        return student, [ac.course for ac in assigned_courses]
    
    @staticmethod
    def get_student_by_id(student_id, user):
        """Get a specific student by ID"""
        try:
            return Students.objects.get(id=student_id, user=user)
        except Students.DoesNotExist:
            raise ValidationError("Student not found or you don't have permission to access it.")
    
    @staticmethod
    def get_student_courses(student_id, user):
        """Get courses assigned to a student"""
        student = StudentService.get_student_by_id(student_id, user)
        return AssignedCourse.objects.filter(student=student).select_related('course')
    
    @staticmethod
    def assign_course_to_student(student_id, course_id, user):
        """Assign a course to a student"""
        student = StudentService.get_student_by_id(student_id, user)
        
        try:
            course = Courses.objects.get(id=course_id, user=user)
        except Courses.DoesNotExist:
            raise ValidationError("Course not found or you don't have permission to access it.")
        
        # Check if already assigned
        if AssignedCourse.objects.filter(student=student, course=course).exists():
            raise ValidationError(f"Student is already assigned to course '{course.course_name}'.")
        
        assignment = AssignedCourse.objects.create(student=student, course=course)
        return assignment
    
    @staticmethod
    def remove_course_from_student(student_id, course_id, user):
        """Remove a course assignment from a student"""
        student = StudentService.get_student_by_id(student_id, user)
        
        try:
            course = Courses.objects.get(id=course_id, user=user)
            assignment = AssignedCourse.objects.get(student=student, course=course)
            assignment.delete()
            return True
        except (Courses.DoesNotExist, AssignedCourse.DoesNotExist):
            raise ValidationError("Assignment not found.")
