"""
CheckMate PDF Processor - Field Coordinates Configuration

This file contains the exact pixel coordinates for extracting student information
fields from the CheckMate answer sheet template.

Coordinates are relative to the student info region defined in pdf_processor.py

To find the right coordinates:
1. Use the debug commands to test individual fields:
   python pdf_processor.py "path/to/pdf" --x 0 --y 300 --width 2600 --height 300 --debug-field name
2. Adjust the coordinates below based on the debug output
3. Test with the normal extraction command

COORDINATE FORMAT:
Each field has: x, y, width, height (in pixels)
- x: pixels from left edge of student region
- y: pixels from top edge of student region  
- width: field width in pixels
- height: field height in pixels
"""

# STUDENT INFO REGION COORDINATES
# These define the overall area containing all student fields
STUDENT_REGION = {
    'x': 0,         # Usually 0 (full width)
    'y': 300,       # Distance from top of page
    'width': 2600,  # Width of student info area
    'height': 300   # Height of student info area
}

# INDIVIDUAL FIELD COORDINATES
# These are relative to the STUDENT_REGION defined above
# Based on your successful debugging results:

FIELD_COORDINATES = {
    'name': {
        'x': 200,        # X position within student region
        'y': 90,         # Y position within student region
        'width': 1000,   # Field width
        'height': 90     # Field height
    },
    
    'id': {
        'x': 1350,       # X position for ID field (right side)
        'y': 80,         # Y position within student region
        'width': 1000,   # Field width
        'height': 100    # Field height
    },
    
    'course': {
        'x': 200,        # X position for course field - moved slightly right
        'y': 175,        # Y position for bottom row - moved up
        'width': 1000,    # Field width - increased
        'height': 80     # Field height - increased
    },
    
    'section': {
        'x': 1450,       # X position for section field (right side)
        'y': 170,        # Y position for bottom row - moved up
        'width': 800,    # Field width - increased
        'height': 80     # Field height - increased
    }
}

# OCR CONFIGURATION
# Fine-tune OCR settings for each field type
OCR_CONFIG = {
    'name': {
        'psm_mode': 6,  # Page segmentation mode (6 = uniform block of text - better for multiple words)
        'whitelist': '',  # No whitelist for names to allow better space detection
        'scaling_factor': 4,  # How much to scale up image before OCR
        'padding': 30        # Padding around text region
    },
    
    'id': {
        'psm_mode': 8,   # 8 = single word (for IDs without spaces)
        'whitelist': '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-',
        'scaling_factor': 4,
        'padding': 30
    },
    
    'course': {
        'psm_mode': 8,   # 8 = single word
        'whitelist': '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz',
        'scaling_factor': 4,
        'padding': 30
    },
    
    'section': {
        'psm_mode': 6,   # 6 = uniform block of text (to allow spaces)
        'whitelist': '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz- ',
        'scaling_factor': 4,
        'padding': 30
    }
}

# PREPROCESSING SETTINGS
PREPROCESSING = {
    'student_region_scaling': 2,    # How much to scale the student region
    'enhance_contrast': True,       # Apply contrast enhancement
    'gaussian_blur': True,          # Apply Gaussian blur
    'morphological_ops': True,      # Apply morphological operations
    'adaptive_threshold': True      # Use adaptive thresholding
}

# VALIDATION SETTINGS
VALIDATION = {
    'min_text_length': {
        'name': 2,      # Minimum characters for name
        'id': 5,        # Minimum characters for ID  
        'course': 2,    # Minimum characters for course
        'section': 1    # Minimum characters for section
    },
    
    'expected_patterns': {
        'id': r'^\d{4}-\d{5}-[A-Z]{2}-\d+$',  # Expected ID format
        'course': r'^[A-Z]{2,4}\d{2,4}$',     # Expected course format
        'section': r'^[A-Z]{2,4}\s*\d+-\d+$'  # Expected section format
    }
}

# DEBUGGING SETTINGS
DEBUG = {
    'save_debug_images': True,      # Save intermediate processing images
    'log_coordinates': True,        # Log coordinate calculations
    'show_confidence_scores': True, # Show OCR confidence scores
    'verbose_logging': True         # Enable detailed logging
}

def get_field_config(field_name):
    """Get configuration for a specific field"""
    return {
        'coordinates': FIELD_COORDINATES.get(field_name, {}),
        'ocr': OCR_CONFIG.get(field_name, {}),
        'validation': {
            'min_length': VALIDATION['min_text_length'].get(field_name, 1),
            'pattern': VALIDATION['expected_patterns'].get(field_name, None)
        }
    }

def get_student_region_config():
    """Get student region configuration"""
    return STUDENT_REGION.copy()

def get_preprocessing_config():
    """Get preprocessing configuration"""
    return PREPROCESSING.copy()

# QUICK ADJUSTMENT FUNCTIONS
def adjust_field_coordinates(field_name, x=None, y=None, width=None, height=None):
    """Quickly adjust coordinates for a field"""
    if field_name not in FIELD_COORDINATES:
        print(f"Warning: Field '{field_name}' not found in configuration")
        return
    
    field = FIELD_COORDINATES[field_name]
    if x is not None:
        field['x'] = x
    if y is not None:
        field['y'] = y
    if width is not None:
        field['width'] = width
    if height is not None:
        field['height'] = height
    
    print(f"Updated {field_name} coordinates: {field}")

def print_current_config():
    """Print current configuration for debugging"""
    print("=== CURRENT FIELD CONFIGURATION ===")
    print(f"Student Region: {STUDENT_REGION}")
    print()
    for field_name, coords in FIELD_COORDINATES.items():
        print(f"{field_name.upper()}: {coords}")
    print()

if __name__ == "__main__":
    # Quick test of configuration
    print_current_config()
    
    # Example of how to adjust coordinates
    # adjust_field_coordinates('name', x=125, width=850)
    # print_current_config()
