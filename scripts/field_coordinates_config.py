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
# Updated based on the PDF structure and text annotations

FIELD_COORDINATES = {
    'name': {
        'x': 220,        # X position within student region (left side)
        'y': 130,         # Y position within student region (top row)
        'width': 1050,    # Field width
        'height': 80     # Field height
    },
    
    'id': {
        'x': 1350,       # X position for ID field (right side)
        'y': 90,         # Y position within student region (top row)
        'width': 1050,    # Field width
        'height': 120     # Field height
    },
    
    'course': {
        'x': 245,         # X position for course field (left side)
        'y': 210,        # Y position for bottom row
        'width': 1050,    # Field width
        'height': 75     # Field height
    },
    
    'section': {
        'x': 1450,       # X position for section field (right side)
        'y': 210,        # Y position for bottom row
        'width': 950,    # Field width
        'height': 75     # Field height
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

# ANSWER GRID CONFIGURATION
ANSWER_GRID = {
    'x': 120,      # was 150, move slightly left
    'y': 760,      # was 780, move slightly up
    'width': 2250, # was 2200, make slightly wider
    'height': 1720,# was 1680, make slightly taller
    'columns': 4,
    'max_questions_per_column': 25,
    'max_questions_per_page': 100
}

# COLUMN SPECIFICATIONS
COLUMN_CONFIG = {
    'column_width': 520,    # was 450, make wider
    'column_spacing': 140,  # was 150, adjust spacing
    'header_height': 90,
    'question_row_height': 66, # was 60, slightly taller
    'question_start_y': 190,
    'max_questions_per_column': 25
}

# COLUMN AREAS (manual definition for each column in the answer grid)
COLUMN_AREAS = {
    0: {'x': 260,  'y': 950,  'width': 450, 'height': 1570},  # Column 1 (x +100)
    1: {'x': 850,  'y': 950,  'width': 450, 'height': 1570},  # Column 2 (x +100)
    2: {'x': 1440, 'y': 950,  'width': 450, 'height': 1570},  # Column 3 (x +100)
    3: {'x': 2040, 'y': 950,  'width': 450, 'height': 1570},  # Column 4 (x +100)
}

# COLUMN HEADER AREAS (manual definition for each column header in the answer grid)
COLUMN_HEADER_AREAS = {
    0: {'x': 260,  'y': 950,  'width': 450, 'height': 40},   # Header for Column 1
    1: {'x': 850,  'y': 950,  'width': 450, 'height': 40},   # Header for Column 2
    2: {'x': 1440, 'y': 950,  'width': 450, 'height': 40},   # Header for Column 3
    3: {'x': 2040, 'y': 950,  'width': 450, 'height': 40},   # Header for Column 4
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

def get_answer_grid_config():
    """Get answer grid configuration"""
    return {
        'grid': ANSWER_GRID.copy(),
        'columns': COLUMN_CONFIG.copy()
    }

def get_column_areas():
    """Get manually defined column areas"""
    return COLUMN_AREAS.copy()

def get_column_header_areas():
    """Get manually defined column header areas"""
    return COLUMN_HEADER_AREAS.copy()

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

def calculate_column_layout(question_count):
    """Calculate dynamic column layout based on question count"""
    questions_per_column = COLUMN_CONFIG['max_questions_per_column']
    columns_needed = min(4, (question_count + questions_per_column - 1) // questions_per_column)
    layout = {
        'columns': columns_needed,
        'questions_per_column': questions_per_column,
        'column_ranges': []
    }
    for col in range(columns_needed):
        start_q = col * questions_per_column + 1
        end_q = min(start_q + questions_per_column - 1, question_count)
        if start_q <= question_count:
            layout['column_ranges'].append({
                'column': col,
                'start_question': start_q,
                'end_question': end_q,
                'question_count': end_q - start_q + 1
            })
    return layout



if __name__ == "__main__":
    # Quick test of configuration
    print_current_config()
    
    # Example of how to adjust coordinates
    # adjust_field_coordinates('name', x=125, width=850)
    # print_current_config()

# NOTE: Use the mapping debug image (see save_mapping_debug_image in pdf_processor_main_prototype.py)
# to visually check and further fine-tune these coordinates for your specific scanned sheet.
