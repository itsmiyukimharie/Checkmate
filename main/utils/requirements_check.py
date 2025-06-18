"""
Utility to check for required packages
"""

def check_reportlab():
    """Check if ReportLab is available"""
    try:
        import reportlab
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate
        return True, "ReportLab is available"
    except ImportError as e:
        return False, f"ReportLab not available: {str(e)}"

def check_pillow():
    """Check if Pillow is available"""
    try:
        from PIL import Image
        return True, "Pillow is available"
    except ImportError as e:
        return False, f"Pillow not available: {str(e)}"

def get_missing_requirements():
    """Get list of missing requirements"""
    missing = []
    
    reportlab_ok, reportlab_msg = check_reportlab()
    if not reportlab_ok:
        missing.append({
            'package': 'reportlab',
            'install_command': 'pip install reportlab',
            'description': 'Required for PDF template generation'
        })
    
    pillow_ok, pillow_msg = check_pillow()
    if not pillow_ok:
        missing.append({
            'package': 'pillow',
            'install_command': 'pip install pillow',
            'description': 'Required for image processing'
        })
    
    return missing
