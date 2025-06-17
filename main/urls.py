from django.urls import path
from . import views

app_name = 'main'

urlpatterns = [
    path('', views.landingpage, name='landingpage'),
    path('login/', views.login, name='login'),
    path('signup/', views.signup, name='signup'),
    path('logout/', views.logout, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('students/', views.test_overview, name='student_management'),
    path('courses/', views.course_management, name='course_management'),
    path('answer-keys/', views.answer_keys, name='answer_keys'),
    path('answer-keys/enter/<int:test_id>/', views.enter_answers, name='enter_answers'),
    path('answer-keys/print/<int:test_id>/', views.print_answer_key, name='print_answer_key'),
    path('answer-keys/print-data/<int:test_id>/', views.print_answer_key_data, name='print_answer_key_data'),
    path('answer-keys/download/<int:test_id>/', views.download_answer_key, name='download_answer_key'),
    path('answer-keys/delete/<int:test_id>/', views.delete_test, name='delete_test'),
    path('grade-test/', views.grade_test, name='grade_test'),
    path('export-results/', views.export_results, name='export_results'),
    path('analytics/', views.analytics, name='analytics'),
    path('landingpage/', views.landingpage, name='landingpage'),
]
