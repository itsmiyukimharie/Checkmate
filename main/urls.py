from django.urls import path
from . import views

app_name = 'main'

urlpatterns = [
    path('', views.landingpage, name='landingpage'),
    path('login/', views.login, name='login'),
    path('signup/', views.signup, name='signup'),
    path('logout/', views.logout, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('students/', views.student_management, name='student_management'),
    path('students/add/', views.add_student, name='add_student'),
    path('students/edit/<int:student_id>/', views.edit_student, name='edit_student'),
    path('students/delete/<int:student_id>/', views.delete_student, name='delete_student'),
    path('students/<int:student_id>/courses/', views.get_student_courses, name='get_student_courses'),
    path('courses/', views.course_management, name='course_management'),
    path('courses/add/', views.add_course, name='add_course'),
    path('courses/edit/<int:course_id>/', views.edit_course, name='edit_course'),
    path('courses/delete/<int:course_id>/', views.delete_course, name='delete_course'),
    path('answer-keys/', views.answer_keys, name='answer_keys'),
    path('answer-keys/upload/', views.upload_answer_key, name='upload_answer_key'),
    path('answer-keys/review-upload/', views.review_upload, name='review_upload'),
    path('answer-keys/enter/<int:test_id>/', views.enter_answers, name='enter_answers'),
    path('answer-keys/print/<int:test_id>/', views.print_answer_key, name='print_answer_key'),
    path('answer-keys/print-data/<int:test_id>/', views.print_answer_key_data, name='print_answer_key_data'),
    path('answer-keys/download/<int:test_id>/', views.download_answer_key, name='download_answer_key'),
    path('answer-keys/delete/<int:test_id>/', views.delete_test, name='delete_test'),
    path('grade-test/', views.grade_test, name='grade_test'),
    path('grade-test/filter-answer-keys/', views.get_filtered_answer_keys, name='get_filtered_answer_keys'),
    path('grade-test/course-students/', views.get_course_students, name='get_course_students'),
    path('grade-test/history/', views.get_grading_history, name='get_grading_history'),
    path('export-results/', views.export_results, name='export_results'),
    path('analytics/', views.analytics, name='analytics'),
    path('landingpage/', views.landingpage, name='landingpage'),
    path('answer-keys/download-template/', views.download_template, name='download_template'),
    path('process-answer-sheets-pdf/', views.process_answer_sheets_pdf, name='process_answer_sheets_pdf'),
]
