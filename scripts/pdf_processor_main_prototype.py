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

    def __init__(self, dpi=600):
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

    def process_pdf(self, pdf_path, question_count=100, test_type='multiple_choice_4', output_dir=None, corner_adjustment=None):
        """
        Process a single PDF and return extracted student info and answers.
        Optionally fine-tune corners before perspective correction.
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
            # Always fine-tune corners (use default if no adjustment provided)
            corners = self.fine_tune_corners(image, corners, corner_adjustment)
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


    def fine_tune_corners(self, image, initial_corners, adjustment=None):
        """
        Fine-tune corner positions for better perspective correction
        
        Args:
            image: PIL Image or numpy array
            initial_corners: List of 4 corner points [(x,y), ...]
            adjustment: Dictionary with corner adjustments {'tl': (dx, dy), 'tr': (dx, dy), etc.}
            
        Returns:
            Adjusted corner points
        """
        try:
            if adjustment is None:
                # Default fine-tuning based on your PDF analysis
                adjustment = {
                    'tl': (60, 50),  # Move top-left up and left
                    'tr': (-60, 50),   # Move top-right up and right
                    'bl': (60, -50),   # Move bottom-left down and left
                    'br': (-60, -50)     # Move bottom-right down and right
                }
            
            adjusted_corners = []
            corner_labels = ['tl', 'tr', 'bl', 'br']
            
            for i, (x, y) in enumerate(initial_corners):
                label = corner_labels[i]
                if label in adjustment:
                    dx, dy = adjustment[label]
                    new_x = max(0, min(x + dx, image.width if hasattr(image, 'width') else image.shape[1] - 1))
                    new_y = max(0, min(y + dy, image.height if hasattr(image, 'height') else image.shape[0] - 1))
                    adjusted_corners.append((new_x, new_y))
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.info(f"Adjusted {label}: ({x}, {y}) -> ({new_x}, {new_y})")
                else:
                    adjusted_corners.append((x, y))
            
            return adjusted_corners
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error fine-tuning corners: {str(e)}")
            return initial_corners


    def save_mapping_debug_image(self, pdf_path, output_path, question_count=100, test_type='multiple_choice_4', cut=False):
        """
        Generate and save a debug image showing detected corners and answer grid mapping.
        Adds borders on the corner visualization for easier fine-tuning.
        Always uses fine-tuned corners (default or provided).
        If cut=True, also saves the cut *corner region* (bounding box of corners) with overlays (output_path will be suffixed with '_cut').
        Args:
            pdf_path: Path to the PDF file.
            output_path: Where to save the debug image (PNG/JPG).
            question_count: Number of questions.
            test_type: Test type.
            cut: If True, also save the cut corner region with overlays.
        """
        image = self.convert_pdf_to_image(pdf_path)
        if image is None:
            raise Exception("Failed to convert PDF to image.")

        corners = self.detect_corner_markers(image)
        # Always fine-tune corners (use default adjustment if none provided)
        corners = self.fine_tune_corners(image, corners)
        corrected_image = self.apply_perspective_correction(image, corners)
        if corrected_image is None:
            raise Exception("Failed to apply perspective correction.")

        # Draw detected corners and borders on original image
        orig_img = np.array(image).copy()
        # Draw circles at corners
        for (x, y) in corners:
            cv2.circle(orig_img, (int(x), int(y)), 20, (0, 0, 255), 4)
        cv2.putText(orig_img, "Detected Corners", (30, 60), cv2.FONT_HERSHEY_SIMPLEX, 2, (0,0,255), 4)
        # Draw border connecting corners (polygon)
        pts = np.array(corners, dtype=np.int32).reshape((-1,1,2))
        cv2.polylines(orig_img, [pts], isClosed=True, color=(0,255,255), thickness=4)
        # Draw small rectangles at each corner for easier visual reference
        for (x, y) in corners:
            cv2.rectangle(orig_img, (int(x)-25, int(y)-25), (int(x)+25, int(y)+25), (255,0,255), 2)
        # Draw bounding box (axis-aligned) around all corners
        xs = [int(x) for (x, y) in corners]
        ys = [int(y) for (x, y) in corners]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        cv2.rectangle(orig_img, (min_x, min_y), (max_x, max_y), (0, 128, 255), 2)
        # Draw vertical and horizontal lines through each corner
        for (x, y) in corners:
            cv2.line(orig_img, (int(x), 0), (int(x), orig_img.shape[0]), (128, 255, 128), 1)
            cv2.line(orig_img, (0, int(y)), (orig_img.shape[1], int(y)), (128, 255, 128), 1)

        # Draw answer grid on corrected image
        grid_img = corrected_image.copy()
        if CONFIG_AVAILABLE:
            grid_config = get_answer_grid_config()
            column_areas = get_column_areas()
            COLUMN_CONF = COLUMN_CONFIG
        else:
            answer_processor = StudentAnswerProcessor()
            grid_config = answer_processor._get_fallback_config()
            column_areas = {}
            COLUMN_CONF = grid_config['columns']

        # Draw grid rectangle
        grid = grid_config['grid']
        cv2.rectangle(grid_img, (grid['x'], grid['y']),
                      (grid['x']+grid['width'], grid['y']+grid['height']),
                      (0,255,0), 4)
        cv2.putText(grid_img, "Answer Grid", (grid['x'], grid['y']-10), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,255,0), 2)

        # Draw column areas
        for idx, area in column_areas.items():
            cv2.rectangle(grid_img, (area['x'], area['y']),
                          (area['x']+area['width'], area['y']+area['height']),
                          (255,0,0), 2)
            cv2.putText(grid_img, f"Col {idx+1}", (area['x'], area['y']+30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255,0,0), 2)

        # Save both images side by side
        h = max(orig_img.shape[0], grid_img.shape[0])
        w = orig_img.shape[1] + grid_img.shape[1]
        debug_img = np.zeros((h, w, 3), dtype=np.uint8)
        debug_img[:orig_img.shape[0], :orig_img.shape[1]] = orig_img
        debug_img[:grid_img.shape[0], orig_img.shape[1]:] = grid_img

        cv2.imwrite(output_path, debug_img)

        # --- Save cut corner region with overlays if requested ---
        if cut:
            # Cut the original image to the bounding box of the corners (with a small margin)
            margin = 20
            cut_min_x = max(min_x - margin, 0)
            cut_max_x = min(max_x + margin, orig_img.shape[1])
            cut_min_y = max(min_y - margin, 0)
            cut_max_y = min(max_y + margin, orig_img.shape[0])
            cut_img = orig_img[cut_min_y:cut_max_y, cut_min_x:cut_max_x].copy()
            # Optionally, re-draw the corners and polygon on the cut image (shifted coordinates)
            shifted_corners = [(x - cut_min_x, y - cut_min_y) for (x, y) in corners]
            for (x, y) in shifted_corners:
                cv2.circle(cut_img, (int(x), int(y)), 20, (0, 0, 255), 4)
                cv2.rectangle(cut_img, (int(x)-25, int(y)-25), (int(x)+25, int(y)+25), (255,0,255), 2)
            pts_cut = np.array(shifted_corners, dtype=np.int32).reshape((-1,1,2))
            cv2.polylines(cut_img, [pts_cut], isClosed=True, color=(0,255,255), thickness=4)
            cv2.rectangle(cut_img, (0, 0), (cut_img.shape[1]-1, cut_img.shape[0]-1), (0, 128, 255), 2)
            for (x, y) in shifted_corners:
                cv2.line(cut_img, (int(x), 0), (int(x), cut_img.shape[0]), (128, 255, 128), 1)
                cv2.line(cut_img, (0, int(y)), (cut_img.shape[1], int(y)), (128, 255, 128), 1)
            cut_output_path = output_path.replace('.png', '_cutcorners.png').replace('.jpg', '_cutcorners.jpg')
            cv2.imwrite(cut_output_path, cut_img)

    def save_student_fields_debug_image(self, pdf_path, output_path):
        """
        Generate and save a debug image showing the student info region and the bounding boxes
        for name, id, course, and section fields for fine-tuning.
        """
        image = self.convert_pdf_to_image(pdf_path)
        if image is None:
            raise Exception("Failed to convert PDF to image.")

        # Use the same fine-tuned corners as in process_pdf
        corners = self.detect_corner_markers(image)
        corners = self.fine_tune_corners(image, corners)
        corrected_image = self.apply_perspective_correction(image, corners)
        if corrected_image is None:
            raise Exception("Failed to apply perspective correction.")

        # Draw on a copy of the corrected image
        debug_img = corrected_image.copy()

        # Get student region and field coordinates
        try:
            from scripts.field_coordinates_config import (
                get_student_region_config,
                FIELD_COORDINATES
            )
        except ImportError:
            raise Exception("field_coordinates_config.py not found.")

        student_region = get_student_region_config()
        x0, y0, w0, h0 = student_region['x'], student_region['y'], student_region['width'], student_region['height']
        # Draw student info region
        cv2.rectangle(debug_img, (x0, y0), (x0 + w0, y0 + h0), (0, 255, 255), 3)
        cv2.putText(debug_img, "Student Info Region", (x0 + 10, y0 + 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)

        # Draw each field box
        colors = {
            'name': (0, 255, 0),
            'id': (255, 0, 0),
            'course': (0, 128, 255),
            'section': (255, 0, 255)
        }
        for field, box in FIELD_COORDINATES.items():
            fx = x0 + box['x']
            fy = y0 + box['y']
            fw = box['width']
            fh = box['height']
            color = colors.get(field, (255, 255, 255))
            cv2.rectangle(debug_img, (fx, fy), (fx + fw, fy + fh), color, 3)
            cv2.putText(debug_img, field.upper(), (fx + 5, fy + 35), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)

        cv2.imwrite(output_path, debug_img)

