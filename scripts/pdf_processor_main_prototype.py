"""
CheckmateService: Service class for extracting student info and answers from PDF answer sheets.
Designed for integration with a web application.
"""

import os
import pdf2image
import cv2
import numpy as np
from PIL import Image

from scripts.pdf_processor_stud_info import StudentInfoExtractor
from scripts.pdf_processor_stud_answer import StudentAnswerProcessor

try:
    from scripts.field_coordinates_config import (
        get_answer_grid_config,
        get_column_areas,
        COLUMN_CONFIG
    )
    CONFIG_AVAILABLE = True
except ImportError:
    CONFIG_AVAILABLE = False

class CheckmateService:
    """
    Service class for extracting student info and answers from PDF answer sheets.
    """

    def __init__(self, dpi=300):
        self.dpi = dpi

    def convert_pdf_to_image(self, pdf_path):
        images = pdf2image.convert_from_path(
            pdf_path,
            dpi=self.dpi,
            first_page=1,
            last_page=1,
            fmt='RGB'
        )
        if not images:
            return None
        return images[0]

    def detect_corner_markers(self, image):
        # Minimal version: use the logic from main processor
        if isinstance(image, Image.Image):
            img_array = np.array(image)
        else:
            img_array = image.copy()
        if len(img_array.shape) == 3:
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        else:
            gray = img_array.copy()
        height, width = gray.shape
        corner_size = 100
        margin = 30
        corner_regions = [
            (margin, margin),  # TL
            (width - corner_size - margin, margin),  # TR
            (margin, height - corner_size - margin),  # BL
            (width - corner_size - margin, height - corner_size - margin)  # BR
        ]
        corners_found = []
        for x, y in corner_regions:
            region = gray[y:y+corner_size, x:x+corner_size]
            blurred = cv2.GaussianBlur(region, (5, 5), 0)
            _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                largest_contour = max(contours, key=cv2.contourArea)
                M = cv2.moments(largest_contour)
                if M["m00"] != 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                else:
                    cx, cy = corner_size // 2, corner_size // 2
                corner_x = x + cx
                corner_y = y + cy
            else:
                min_loc = np.unravel_index(np.argmin(region), region.shape)
                corner_x = x + min_loc[1]
                corner_y = y + min_loc[0]
            corners_found.append((corner_x, corner_y))
        if len(corners_found) == 4:
            return corners_found
        # fallback
        margin = 50
        return [
            (margin, margin),
            (width - margin, margin),
            (margin, height - margin),
            (width - margin, height - margin)
        ]

    def apply_perspective_correction(self, image, corners, target_width=2480, target_height=3508):
        if isinstance(image, Image.Image):
            img_array = np.array(image)
        else:
            img_array = image.copy()
        src_points = np.array([
            corners[0], corners[1], corners[2], corners[3]
        ], dtype=np.float32)
        dst_points = np.array([
            [0, 0],
            [target_width-1, 0],
            [0, target_height-1],
            [target_width-1, target_height-1]
        ], dtype=np.float32)
        matrix = cv2.getPerspectiveTransform(src_points, dst_points)
        corrected = cv2.warpPerspective(
            img_array,
            matrix,
            (target_width, target_height),
            flags=cv2.INTER_LINEAR
        )
        return corrected

    def process_pdf(self, pdf_path, question_count=100, test_type='multiple_choice_4', output_dir=None):
        """
        Process a single PDF and return extracted student info and answers.
        Args:
            pdf_path: Path to the PDF file.
            question_count: Number of questions.
            test_type: Test type ('multiple_choice_4', 'multiple_choice_5', 'true_false').
            output_dir: Optional directory to save debug images.
        Returns:
            Dict with keys: success, student_info, answers, error, total_detected
        """
        result = {
            "pdf_path": pdf_path,
            "success": False,
            "student_info": None,
            "answers": None,
            "error": None,
            "total_detected": 0
        }
        try:
            image = self.convert_pdf_to_image(pdf_path)
            if image is None:
                result["error"] = "Failed to convert PDF to image."
                return result

            corners = self.detect_corner_markers(image)
            corrected_image = self.apply_perspective_correction(image, corners)
            if corrected_image is None:
                result["error"] = "Failed to apply perspective correction."
                return result

            # Student Info
            student_info_extractor = StudentInfoExtractor()
            student_info = student_info_extractor.extract_student_info(corrected_image, output_dir)

            # Student Answers
            answer_processor = StudentAnswerProcessor()
            answer_result = answer_processor.extract_student_answers(
                corrected_image, question_count, test_type, output_dir
            )

            answers = {}
            total_detected = 0
            if answer_result and answer_result.get('success'):
                if CONFIG_AVAILABLE:
                    grid_config = get_answer_grid_config()
                    column_areas = get_column_areas()
                    COLUMN_CONF = COLUMN_CONFIG
                else:
                    grid_config = answer_processor._get_fallback_config()
                    column_areas = {}
                    COLUMN_CONF = grid_config['columns']
                answer_grid = answer_result['answer_grid']
                for col_idx, area in column_areas.items():
                    x = area['x'] - grid_config['grid']['x']
                    y = area['y'] - grid_config['grid']['y']
                    w = area['width']
                    h = area['height']
                    x = max(0, min(x, answer_grid.shape[1] - 1))
                    y = max(0, min(y, answer_grid.shape[0] - 1))
                    w = min(w, answer_grid.shape[1] - x)
                    h = min(h, answer_grid.shape[0] - y)
                    col_img = answer_grid[y:y+h, x:x+w]
                    max_per_col = COLUMN_CONF.get('max_questions_per_column', 25)
                    start_q = col_idx * max_per_col + 1
                    end_q = min(start_q + max_per_col - 1, question_count)
                    num_q = end_q - start_q + 1

                    # Detect number of choices by counting circles in first row
                    first_row_height = int(col_img.shape[0] / num_q)
                    first_row_img = col_img[0:first_row_height, :]
                    _, thresh = cv2.threshold(first_row_img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
                    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    bubble_radii = []
                    for cnt in contours:
                        (x_c, y_c), radius = cv2.minEnclosingCircle(cnt)
                        if 10 < radius < 40:
                            bubble_radii.append(radius)
                    detected_choices = len(bubble_radii)
                    # Fallback if detection fails
                    if detected_choices < 2 or detected_choices > 5:
                        if test_type == "multiple_choice_4":
                            detected_choices = 4
                        elif test_type == "multiple_choice_5":
                            detected_choices = 5
                        elif test_type == "true_false":
                            detected_choices = 2
                        else:
                            detected_choices = 4

                    # Set choice labels
                    if detected_choices == 2:
                        choice_labels = ['T', 'F']
                    elif detected_choices == 5:
                        choice_labels = ['A', 'B', 'C', 'D', 'E']
                    else:
                        choice_labels = ['A', 'B', 'C', 'D']

                    col_answers = answer_processor.detect_answers_in_column(
                        col_img, col_idx, num_questions=num_q, choices=detected_choices, debug=False
                    )
                    for i, ans in enumerate(col_answers):
                        qnum = start_q + i
                        # Always map to T/F if detected_choices==2
                        if detected_choices == 2:
                            if ans is not None and isinstance(ans, str) and ans in ['A', 'B']:
                                answers[qnum] = choice_labels[0] if ans == 'A' else choice_labels[1]
                            elif ans is not None and ans in choice_labels:
                                answers[qnum] = ans
                            else:
                                answers[qnum] = ans
                        else:
                            if ans is not None and ans in choice_labels:
                                answers[qnum] = ans
                            elif ans is not None and isinstance(ans, int) and 0 <= ans < len(choice_labels):
                                answers[qnum] = choice_labels[ans]
                            else:
                                answers[qnum] = ans
                        if ans is not None:
                            total_detected += 1

            result["success"] = True
            result["student_info"] = student_info
            result["answers"] = answers
            result["total_detected"] = total_detected
            return result
        except Exception as e:
            result["error"] = str(e)
            return result

    def process_pdfs(self, pdf_paths, question_count=100, test_type='multiple_choice_4', output_dir=None):
        """
        Batch process multiple PDFs.
        Args:
            pdf_paths: List of PDF file paths.
            question_count: Number of questions.
            test_type: Test type.
            output_dir: Optional directory to save debug images.
        Returns:
            List of result dicts.
        """
        results = []
        for pdf_path in pdf_paths:
            result = self.process_pdf(pdf_path, question_count, test_type, output_dir)
            results.append(result)
        return results
