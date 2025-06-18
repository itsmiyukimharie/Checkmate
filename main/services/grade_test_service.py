from django.shortcuts import get_object_or_404
from django.db.models import Q, Count, Avg
from ..models import TestInformation, Courses, TestResult, Students
import logging

logger = logging.getLogger(__name__)

class GradeTestService:
    """Service class for grade test operations"""
    
    @staticmethod
    def get_user_courses(user):
        """Get all courses for a user"""
        return Courses.objects.filter(user=user).order_by('course_code')
    
    @staticmethod
    def get_unique_academic_years(user):
        """Get unique academic years from user's courses"""
        years = Courses.objects.filter(
            user=user, 
            academic_year__isnull=False
        ).values_list('academic_year', flat=True).distinct().order_by('-academic_year')
        
        return list(years)
    
    @staticmethod
    def get_unique_semesters(user):
        """Get unique semesters from user's courses"""
        semesters = Courses.objects.filter(
            user=user, 
            semester__isnull=False
        ).values_list('semester', flat=True).distinct()
        
        # Define semester order
        semester_order = ['1st Semester', '2nd Semester', '3rd Semester', 'Summer']
        ordered_semesters = []
        
        for sem in semester_order:
            if sem in semesters:
                ordered_semesters.append(sem)
        
        # Add any semesters not in the predefined order
        for sem in semesters:
            if sem not in ordered_semesters:
                ordered_semesters.append(sem)
        
        return ordered_semesters
    
    @staticmethod
    def get_filtered_answer_keys(user, filters=None):
        """Get answer keys filtered by course, academic year, and semester"""
        queryset = TestInformation.objects.filter(
            user=user,
            status='active'  # Only show active tests for grading
        ).select_related('course')
        
        if filters:
            course_filter = filters.get('course')
            academic_year_filter = filters.get('academic_year')
            semester_filter = filters.get('semester')
            
            if course_filter:
                queryset = queryset.filter(course__course_code=course_filter)
            
            if academic_year_filter:
                queryset = queryset.filter(course__academic_year=academic_year_filter)
            
            if semester_filter:
                queryset = queryset.filter(course__semester=semester_filter)
        
        return queryset.order_by('-created_at')
    
    @staticmethod
    def get_answer_key_by_id(answer_key_id, user):
        """Get a specific answer key by ID"""
        return get_object_or_404(
            TestInformation, 
            id=answer_key_id, 
            user=user,
            status='active'
        )
    
    @staticmethod
    def get_students_for_course(course_id, user):
        """Get all students assigned to a specific course"""
        try:
            course = Courses.objects.get(id=course_id, user=user)
            students = Students.objects.filter(
                assigned_courses__course=course
            ).order_by('last_name', 'first_name')
            
            return students
        except Courses.DoesNotExist:
            return Students.objects.none()
    
    @staticmethod
    def get_grading_overview_stats(user):
        """Get overview statistics for grading dashboard"""
        # Total tests graded (tests with at least one result)
        total_tests_graded = TestInformation.objects.filter(
            user=user,
            test_results__isnull=False
        ).distinct().count()
        
        # Total students assessed
        total_students_assessed = TestResult.objects.filter(
            test_information__user=user
        ).values('student').distinct().count()
        
        # Overall average score
        overall_average = TestResult.objects.filter(
            test_information__user=user
        ).aggregate(avg_score=Avg('score'))['avg_score'] or 0
        
        # Most recent grading session
        latest_result = TestResult.objects.filter(
            test_information__user=user
        ).select_related('test_information').order_by('-created_at').first()
        
        return {
            'total_tests_graded': total_tests_graded,
            'total_students_assessed': total_students_assessed,
            'overall_average': round(overall_average, 1),
            'latest_grading_session': {
                'test_name': latest_result.test_information.test_name if latest_result else None,
                'date': latest_result.created_at if latest_result else None
            }
        }
    
    @staticmethod
    def get_grade_distribution(user):
        """Get grade distribution statistics"""
        results = TestResult.objects.filter(test_information__user=user)
        
        if not results.exists():
            return {
                'A': 0, 'B': 0, 'C': 0, 'D': 0, 'F': 0
            }
        
        total_results = results.count()
        
        # Count results by grade ranges
        grade_counts = {
            'A': results.filter(score__gte=90).count(),
            'B': results.filter(score__gte=80, score__lt=90).count(),
            'C': results.filter(score__gte=70, score__lt=80).count(),
            'D': results.filter(score__gte=60, score__lt=70).count(),
            'F': results.filter(score__lt=60).count(),
        }
        
        # Convert to percentages
        grade_distribution = {}
        for grade, count in grade_counts.items():
            percentage = round((count / total_results) * 100, 1) if total_results > 0 else 0
            grade_distribution[grade] = percentage
        
        return grade_distribution
    
    @staticmethod
    def get_grading_history(user, time_filter='all'):
        """Get grading history with optional time filtering"""
        from django.utils import timezone
        from datetime import datetime, timedelta
        
        queryset = TestResult.objects.filter(
            test_information__user=user
        ).select_related('test_information', 'test_information__course', 'student')
        
        # Apply time filter
        if time_filter == 'week':
            week_ago = timezone.now() - timedelta(days=7)
            queryset = queryset.filter(created_at__gte=week_ago)
        elif time_filter == 'month':
            month_ago = timezone.now() - timedelta(days=30)
            queryset = queryset.filter(created_at__gte=month_ago)
        
        # Group by test and calculate stats
        grading_sessions = []
        test_groups = {}
        
        for result in queryset:
            test_id = result.test_information.id
            if test_id not in test_groups:
                test_groups[test_id] = {
                    'test_info': result.test_information,
                    'students': [],
                    'scores': [],
                    'latest_date': result.created_at
                }
            
            test_groups[test_id]['students'].append(result.student)
            test_groups[test_id]['scores'].append(result.score)
            
            # Update latest date
            if result.created_at > test_groups[test_id]['latest_date']:
                test_groups[test_id]['latest_date'] = result.created_at
        
        # Convert to list format
        for test_id, data in test_groups.items():
            avg_score = sum(data['scores']) / len(data['scores']) if data['scores'] else 0
            
            grading_sessions.append({
                'test_info': data['test_info'],
                'student_count': len(data['students']),
                'average_score': round(avg_score, 1),
                'graded_date': data['latest_date'],
                'sections': GradeTestService._get_sections_from_students(data['students'])
            })
        
        # Sort by most recent first
        grading_sessions.sort(key=lambda x: x['graded_date'], reverse=True)
        
        return grading_sessions
    
    @staticmethod
    def _get_sections_from_students(students):
        """Extract unique sections from a list of students"""
        sections = set()
        for student in students:
            if student.section:
                sections.add(student.section)
        
        if not sections:
            return "Not specified"
        elif len(sections) == 1:
            return list(sections)[0]
        else:
            return " & ".join(sorted(sections))
    
    @staticmethod
    def validate_grading_session_data(data):
        """Validate data for starting a grading session"""
        errors = {}
        
        # Required fields
        if not data.get('answer_key_id'):
            errors['answer_key'] = 'Please select an answer key'
        
        if not data.get('file_format'):
            errors['file_format'] = 'Please select a file format'
        
        # Validate file format
        valid_formats = ['pdf', 'csv', 'image']
        if data.get('file_format') not in valid_formats:
            errors['file_format'] = 'Invalid file format selected'
        
        # Validate uploaded files match format
        uploaded_files = data.get('uploaded_files', [])
        if uploaded_files:
            file_format = data.get('file_format')
            invalid_files = []
            
            for uploaded_file in uploaded_files:
                if not GradeTestService._validate_file_format(uploaded_file, file_format):
                    invalid_files.append(uploaded_file.name)
            
            if invalid_files:
                errors['uploaded_files'] = f'The following files do not match the selected format ({file_format}): {", ".join(invalid_files[:5])}{"..." if len(invalid_files) > 5 else ""}'
        
        return errors
    
    @staticmethod
    def _validate_file_format(uploaded_file, expected_format):
        """Validate if an uploaded file matches the expected format"""
        file_name = uploaded_file.name.lower()
        content_type = getattr(uploaded_file, 'content_type', '').lower()
        
        if expected_format == 'pdf':
            return (content_type == 'application/pdf' or 
                   file_name.endswith('.pdf'))
        
        elif expected_format == 'csv':
            return (content_type == 'text/csv' or 
                   content_type == 'application/csv' or
                   file_name.endswith('.csv'))
        
        elif expected_format == 'image':
            return (content_type.startswith('image/') or 
                   file_name.endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp')))
        
        return False
    
    @staticmethod
    def create_grading_session(user, session_data):
        """Create a new grading session"""
        try:
            # Get the answer key
            answer_key = GradeTestService.get_answer_key_by_id(
                session_data['answer_key_id'], 
                user
            )
            
            # Get students for the course (if specified)
            students = []
            if answer_key.course:
                students = GradeTestService.get_students_for_course(
                    answer_key.course.id, 
                    user
                )
            
            # Process uploaded files if any
            uploaded_files = session_data.get('uploaded_files', [])
            processed_files = []
            
            for uploaded_file in uploaded_files:
                # Process each uploaded file based on format
                file_result = GradeTestService._process_uploaded_answer_sheet(
                    uploaded_file, 
                    answer_key, 
                    session_data['file_format']
                )
                processed_files.append(file_result)
            
            return {
                'success': True,
                'answer_key': answer_key,
                'students': list(students),
                'processed_files': processed_files,
                'session_id': f"session_{answer_key.id}_{timezone.now().strftime('%Y%m%d_%H%M%S')}"
            }
            
        except Exception as e:
            logger.error(f"Error creating grading session: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def _process_uploaded_answer_sheet(uploaded_file, answer_key, file_format):
        """Process an individual uploaded answer sheet"""
        try:
            # This would integrate with existing image processing service
            from .file_processing_service import FileProcessingService
            
            result = FileProcessingService.process_uploaded_file(
                uploaded_file=uploaded_file,
                test_type=answer_key.test_type,
                question_count=answer_key.question_count,
                processing_options={
                    'auto_detect_format': True,
                    'enhance_image': True
                }
            )
            
            return {
                'filename': uploaded_file.name,
                'file_size': uploaded_file.size,
                'processing_result': result,
                'detected_student': None,  # Would be implemented with student detection
                'confidence': result.get('confidence_scores', {}) if result.get('success') else {}
            }
            
        except Exception as e:
            return {
                'filename': uploaded_file.name,
                'file_size': uploaded_file.size,
                'processing_result': {'success': False, 'error': str(e)},
                'detected_student': None,
                'confidence': {}
            }
    
    @staticmethod
    def get_filter_options(user):
        """Get all filter options for the grade test page"""
        return {
            'courses': GradeTestService.get_user_courses(user),
            'academic_years': GradeTestService.get_unique_academic_years(user),
            'semesters': GradeTestService.get_unique_semesters(user)
        }
    
    @staticmethod
    def get_course_details(course_id, user):
        """Get detailed information about a course"""
        try:
            course = Courses.objects.get(id=course_id, user=user)
            students = GradeTestService.get_students_for_course(course_id, user)
            answer_keys = TestInformation.objects.filter(
                course=course,
                user=user,
                status='active'
            ).count()
            
            return {
                'course': course,
                'student_count': students.count(),
                'answer_keys_count': answer_keys,
                'sections': list(students.values_list('section', flat=True).distinct().filter(section__isnull=False))
            }
        except Courses.DoesNotExist:
            return None
