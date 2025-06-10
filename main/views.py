from django.shortcuts import render
from django.http import HttpResponse

def dashboard(request):
    """Dashboard page - main entry point"""
    context = {
        'page_title': 'Dashboard',
        'current_page': 'dashboard'
    }
    return render(request, 'main/dashboard.html', context)

def test_overview(request):
    """Test Management Section - View test overview"""
    context = {
        'page_title': 'Test Overview',
        'current_page': 'test_overview'
    }
    return render(request, 'main/test_overview.html', context)

def answer_keys(request):
    """Answer Keys Management - Upload or create answer keys"""
    context = {
        'page_title': 'Manage Answer Keys',
        'current_page': 'answer_keys'
    }
    return render(request, 'main/answer_keys.html', context)

def grade_test(request):
    """Grade Test - Upload answer sheets and process grading"""
    context = {
        'page_title': 'Grade Test',
        'current_page': 'grade_test'
    }
    return render(request, 'main/grade_test.html', context)

def export_results(request):
    """Export Results - Download results as CSV/PDF"""
    context = {
        'page_title': 'Export Results',
        'current_page': 'export_results'
    }
    return render(request, 'main/export_results.html', context)

def analytics(request):
    """Performance Analytics - View common mistakes and trends"""
    context = {
        'page_title': 'Performance Analytics',
        'current_page': 'analytics'
    }
    return render(request, 'main/analytics.html', context)
