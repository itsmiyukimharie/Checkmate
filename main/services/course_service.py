from django.shortcuts import get_object_or_404
from django.db.models import Q, Count
from django.core.exceptions import ValidationError
from ..models import Courses

class CourseService:
    """Service class for course-related operations"""
    
    @staticmethod
    def get_user_courses(user, filters=None):
        """Get courses for a specific user with optional filters"""
        queryset = Courses.objects.filter(user=user)
        
        if filters:
            # Search filter
            if filters.get('search'):
                search_term = filters['search']
                queryset = queryset.filter(
                    Q(course_code__icontains=search_term) |
                    Q(course_name__icontains=search_term)
                )
            
            # Semester filter
            if filters.get('semester'):
                if filters['semester'] == 'not_specified':
                    queryset = queryset.filter(semester__isnull=True)
                else:
                    queryset = queryset.filter(semester=filters['semester'])
            
            # Academic year filter
            if filters.get('academic_year'):
                queryset = queryset.filter(academic_year__icontains=filters['academic_year'])
            
            # Sort by
            if filters.get('sort_by'):
                queryset = queryset.order_by(filters['sort_by'])
            else:
                queryset = queryset.order_by('-created_at')
        else:
            queryset = queryset.order_by('-created_at')
        
        return queryset
    
    @staticmethod
    def create_course(user, course_data):
        """Create a new course"""
        # Check for duplicate course code for this user
        if Courses.objects.filter(
            user=user,
            course_code=course_data['course_code']
        ).exists():
            raise ValidationError(f"You already have a course with code '{course_data['course_code']}'.")
        
        course = Courses.objects.create(
            user=user,
            course_code=course_data['course_code'],
            course_name=course_data['course_name'],
            description=course_data.get('description', ''),
            academic_year=course_data.get('academic_year', ''),
            semester=course_data.get('semester', '')
        )
        
        return course
    
    @staticmethod
    def get_course_by_id(course_id, user):
        """Get a specific course by ID"""
        try:
            return Courses.objects.get(id=course_id, user=user)
        except Courses.DoesNotExist:
            raise ValidationError("Course not found or you don't have permission to access it.")
    
    @staticmethod
    def update_course(course_id, user, course_data):
        """Update an existing course"""
        try:
            course = Courses.objects.get(id=course_id, user=user)
        except Courses.DoesNotExist:
            raise ValidationError("Course not found or you don't have permission to edit it.")
        
        # Check for duplicate course code (excluding current course)
        if Courses.objects.filter(
            user=user,
            course_code=course_data['course_code']
        ).exclude(id=course_id).exists():
            raise ValidationError(f"You already have another course with code '{course_data['course_code']}'.")
        
        # Update course fields
        course.course_code = course_data['course_code']
        course.course_name = course_data['course_name']
        course.description = course_data.get('description', '')
        course.academic_year = course_data.get('academic_year', '')
        course.semester = course_data.get('semester', '')
        course.save()
        
        return course
    
    @staticmethod
    def delete_course(course_id, user):
        """Delete a course"""
        try:
            course = Courses.objects.get(id=course_id, user=user)
            course_name = course.course_name
            course.delete()
            return course_name
        except Courses.DoesNotExist:
            raise ValidationError("Course not found or you don't have permission to delete it.")
    
    @staticmethod
    def get_course_stats(user, filters=None):
        """Get course statistics for the user"""
        queryset = Courses.objects.filter(user=user)
        
        if filters:
            # Apply same filters as get_user_courses
            if filters.get('search'):
                search_term = filters['search']
                queryset = queryset.filter(
                    Q(course_code__icontains=search_term) |
                    Q(course_name__icontains=search_term)
                )
            
            if filters.get('semester'):
                if filters['semester'] == 'not_specified':
                    queryset = queryset.filter(semester__isnull=True)
                else:
                    queryset = queryset.filter(semester=filters['semester'])
            
            if filters.get('academic_year'):
                queryset = queryset.filter(academic_year__icontains=filters['academic_year'])
        
        # Total courses
        total_courses = queryset.count()
        
        # Semester statistics
        semester_stats = {}
        semester_counts = queryset.values('semester').annotate(count=Count('id'))
        for item in semester_counts:
            semester = item['semester'] or 'Not Specified'
            semester_stats[semester] = item['count']
        
        # Academic year statistics
        year_stats = {}
        year_counts = queryset.values('academic_year').annotate(count=Count('id'))
        for item in year_counts:
            year = item['academic_year'] or 'Not Specified'
            year_stats[year] = item['count']
        
        return {
            'total_courses': total_courses,
            'semester_stats': semester_stats,
            'year_stats': year_stats
        }
    
    @staticmethod
    def get_unique_academic_years(user):
        """Get unique academic years for the user's courses"""
        years = Courses.objects.filter(
            user=user,
            academic_year__isnull=False
        ).values_list('academic_year', flat=True).distinct().order_by('-academic_year')
        
        return list(years)
