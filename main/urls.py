from django.urls import path
from . import views

app_name = 'main'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('test-overview/', views.test_overview, name='test_overview'),
    path('answer-keys/', views.answer_keys, name='answer_keys'),
    path('grade-test/', views.grade_test, name='grade_test'),
    path('export-results/', views.export_results, name='export_results'),
    path('analytics/', views.analytics, name='analytics'),
    path('landingpage/', views.landingpage, name='landingpage'),
]
