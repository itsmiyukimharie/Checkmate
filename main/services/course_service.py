from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.core.exceptions import ValidationError
from ..models import Courses

class CourseService:
    """Service class for course operations"""
    
    @staticmethod
    def get_user_courses(user, filters=None):
        """Get all courses for a user with optional filtering"""
        queryset = Courses.objects.filter(user=user)
        
        if filters:
            # Search filter
            search = filters.get('search')
            if search:
                queryset = queryset.filter(
                    Q(course_code__icontains=search) |
                    Q(course_name__icontains=search) |
                    Q(description__icontains=search)
                )
            
            # Semester filter
            semester = filters.get('semester')
            if semester:
                if semester == 'not_specified':
                    queryset = queryset.filter(Q(semester__isnull=True) | Q(semester=''))
                else:
                    queryset = queryset.filter(semester=semester)
            
            # Academic year filter
            academic_year = filters.get('academic_year')
            if academic_year:
                queryset = queryset.filter(academic_year__icontains=academic_year)
            
            # Sorting
            sort_by = filters.get('sort_by', '-created_at')
            if sort_by:
                queryset = queryset.order_by(sort_by)
        else:
            queryset = queryset.order_by('-created_at')
        
        return queryset
    
    @staticmethod
    def create_course(user, form_data):
        """Create a new course with validation"""
        # Check for duplicate course code
        if Courses.objects.filter(course_code=form_data['course_code']).exists():
            raise ValidationError(f"Course code '{form_data['course_code']}' already exists.")
        
        course = Courses(
            user=user,
            course_code=form_data['course_code'],
            course_name=form_data['course_name'],
            description=form_data.get('description', ''),
            academic_year=form_data.get('academic_year', ''),
            semester=form_data.get('semester', ''),
            name=form_data.get('course_name', '')
        )
        course.save()
        return course
    
    @staticmethod
    def get_course_by_id(course_id, user):
        """Get course by ID for specific user"""
        return get_object_or_404(Courses, id=course_id, user=user)
    
    @staticmethod
    def update_course(course_id, user, form_data):
        """Update an existing course with validation"""
        course = CourseService.get_course_by_id(course_id, user)
        
        # Check for duplicate course code (excluding current course)
        if Courses.objects.filter(course_code=form_data['course_code']).exclude(id=course_id).exists():
            raise ValidationError(f"Course code '{form_data['course_code']}' already exists.")
        
        course.course_code = form_data['course_code']
        course.course_name = form_data['course_name']
        course.description = form_data.get('description', '')
        course.academic_year = form_data.get('academic_year', '')
        course.semester = form_data.get('semester', '')
        course.name = form_data.get('course_name', '')
        course.save()
        return course
    
    @staticmethod
    def delete_course(course_id, user):
        """Delete a course and return course name"""
        course = CourseService.get_course_by_id(course_id, user)
        course_name = course.course_name
        course.delete()
        return course_name
    
    @staticmethod
    def get_course_stats(user, filters=None):
        """Get course statistics for user"""
        courses = CourseService.get_user_courses(user, filters)
        total_courses = courses.count()
        
        # Count by semester
        semester_stats = {}
        for course in courses:
            semester = course.semester or 'Not specified'
            semester_stats[semester] = semester_stats.get(semester, 0) + 1
        
        # Count by academic year
        year_stats = {}
        for course in courses:
            year = course.academic_year or 'Not specified'
            year_stats[year] = year_stats.get(year, 0) + 1
        
        return {
            'total_courses': total_courses,
            'semester_stats': semester_stats,
            'year_stats': year_stats
        }
    
    @staticmethod
    def get_unique_academic_years(user):
        """Get list of unique academic years for filter dropdown"""
        years = Courses.objects.filter(user=user).values_list('academic_year', flat=True).distinct()
        return [year for year in years if year]
