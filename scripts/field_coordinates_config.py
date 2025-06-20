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
        'y': 120,         # Y position within student region (top row)
        'width': 1050,    # Field width
        'height': 90     # Field height
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
        'height': 65     # Field height
    },
    
    'section': {
        'x': 1450,       # X position for section field (right side)
        'y': 210,        # Y position for bottom row
        'width': 950,    # Field width
        'height': 65     # Field height
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
    'x': 50,           # Start X position of answer grid (closer to left edge)
    'y': 680,          # Start Y position (much higher - right after student info)
    'width': 2380,      # Total width of answer grid (much smaller)
    'height': 1680,     # Total height of answer grid 
    'columns': 4,      # Default number of columns
    'max_questions_per_column': 25,  # Maximum questions per column
    'max_questions_per_page': 100    # Maximum questions per page
}

# COLUMN SPECIFICATIONS
COLUMN_CONFIG = {
    'column_width': 595,        # Width of each column (570/4)
    'column_spacing': 0,        # Additional spacing between columns
    'header_height': 90,        # Height of column headers (Q1-25, etc.)
    'question_row_height': 60,  # Height of each question row
    'question_start_y': 190,     # Y offset from column top to first question
    'max_questions_per_column': 25  # Maximum questions per column
}

# BUBBLE SPECIFICATIONS  
BUBBLE_CONFIG = {
    'radius': 8,               # Bubble radius in pixels (smaller)
    'spacing': 72,             # Horizontal spacing between bubbles (tighter)
    'start_x_offset': 153,      # X offset from column start to first bubble
    'choices': {
        'multiple_choice_4': ['A', 'B', 'C', 'D'],
        'multiple_choice_5': ['A', 'B', 'C', 'D', 'E'], 
        'true_false': ['T', 'F']
    }
}

# DETECTION THRESHOLDS
DETECTION_CONFIG = {
    'filled_threshold': 0.3,    # Lower threshold for bubble detection
    'confidence_threshold': 0.4, # Lower confidence threshold  
    'multiple_answers_penalty': 0.5,  # Confidence penalty for multiple answers
    'no_answer_threshold': 0.15   # Maximum fill ratio to consider empty
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
        'columns': COLUMN_CONFIG.copy(),
        'bubbles': BUBBLE_CONFIG.copy(),
        'detection': DETECTION_CONFIG.copy()
    }

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

def get_bubble_coordinates(column, question_num, choice_index, test_type):
    """Calculate exact bubble coordinates"""
    grid_config = get_answer_grid_config()
    
    # Get column position
    column_width = grid_config['columns']['column_width']
    col_x = grid_config['grid']['x'] + (column * column_width)
    
    # Get question row position within column
    questions_per_col = grid_config['columns']['max_questions_per_column']
    question_in_col = ((question_num - 1) % questions_per_col)
    row_height = grid_config['columns']['question_row_height']
    question_start_y = grid_config['columns']['question_start_y']
    
    question_y = (grid_config['grid']['y'] + question_start_y + 
                  (question_in_col * row_height))
    
    # Get bubble position within row
    bubble_start_x = col_x + grid_config['bubbles']['start_x_offset']
    bubble_spacing = grid_config['bubbles']['spacing']
    bubble_x = bubble_start_x + (choice_index * bubble_spacing)
    
    return {
        'x': bubble_x,
        'y': question_y,
        'radius': grid_config['bubbles']['radius']
    }

if __name__ == "__main__":
    # Quick test of configuration
    print_current_config()
    
    # Example of how to adjust coordinates
    # adjust_field_coordinates('name', x=125, width=850)
    # print_current_config()
