"""
CheckMate PDF Processor - Student Answer Processing Module

This module handles the extraction and processing of student answers from 
PDF answer sheets using bubble detection and OCR techniques.
"""

import cv2
import numpy as np
import logging

# Configure logging
logger = logging.getLogger(__name__)

# Import configuration
try:
    from field_coordinates_config import (
        get_answer_grid_config,
        get_column_areas,
        get_column_header_areas,  # Always import header areas
    )
    CONFIG_AVAILABLE = True
except ImportError:
    CONFIG_AVAILABLE = False
    logger.warning("field_coordinates_config.py not found. Using default coordinates.")

class StudentAnswerProcessor:
    """
    Specialized class for processing student answers from answer sheets
    """
    
    def __init__(self):
        self.debug_images = []
        logger.info("StudentAnswerProcessor initialized (bubble detection removed)")
    
    def extract_student_answers(self, corrected_image, question_count, test_type, output_dir=None):
        """
        Extract student answers from the answer section
        
        Args:
            corrected_image: Perspective corrected image
            question_count: Number of questions in the test
            test_type: Type of test (multiple_choice_4, multiple_choice_5, true_false)
            output_dir: Directory to save debug images (optional)
            
        Returns:
            Dictionary with extracted answer grid region and layout
        """
        try:
            logger.info(f"Extracting answer grid for {question_count} questions, type: {test_type}")
            
            # Clear previous debug images
            self.debug_images = []
            
            # Convert to grayscale if needed
            if len(corrected_image.shape) == 3:
                gray = cv2.cvtColor(corrected_image, cv2.COLOR_RGB2GRAY)
            else:
                gray = corrected_image.copy()
            
            # Get configuration
            if CONFIG_AVAILABLE:
                grid_config = get_answer_grid_config()
                column_areas = get_column_areas()
            else:
                grid_config = self._get_fallback_config()
                column_areas = None

            # Extract answer grid region
            answer_grid = self._extract_answer_grid(gray, grid_config)
            self.debug_images.append(('01_answer_grid', answer_grid))

            # Extract each column area from the answer grid using manual column areas
            extracted_columns = {}
            if column_areas:
                for col_idx, area in column_areas.items():
                    x = area['x'] - grid_config['grid']['x']
                    y = area['y'] - grid_config['grid']['y']
                    w = area['width']
                    h = area['height']
                    x = max(0, min(x, answer_grid.shape[1] - 1))
                    y = max(0, min(y, answer_grid.shape[0] - 1))
                    w = min(w, answer_grid.shape[1] - x)
                    h = min(h, answer_grid.shape[0] - y)
                    extracted_columns[col_idx] = answer_grid[y:y+h, x:x+w]
                    self.debug_images.append((f'column_{col_idx}_area', extracted_columns[col_idx]))

            # Save debug images
            if output_dir:
                self.save_debug_images(output_dir)

            result = {
                'answer_grid': answer_grid,
                'column_areas': list(column_areas.keys()) if column_areas else [],
                'success': True
            }
            
            logger.info(f"Answer grid extracted: {answer_grid.shape}")
            return result
            
        except Exception as e:
            logger.error(f"Error extracting student answers: {str(e)}")
            return {
                'answer_grid': None,
                'error': str(e),
                'success': False
            }
    
    def _extract_answer_grid(self, gray_image, grid_config):
        """Extract the answer grid region from the image"""
        grid = grid_config['grid']
        x, y, w, h = grid['x'], grid['y'], grid['width'], grid['height']
        
        # Ensure coordinates are within image bounds
        height, width = gray_image.shape
        x = max(0, min(x, width - 1))
        y = max(0, min(y, height - 1))
        w = min(w, width - x)
        h = min(h, height - y)
        
        answer_grid = gray_image[y:y+h, x:x+w]
        logger.info(f"Extracted answer grid: {answer_grid.shape}")
        return answer_grid

    def _get_fallback_config(self):
        """Fallback configuration when config file not available"""
        return {
            'grid': {
                'x': 30, 'y': 600, 'width': 2420, 'height': 2500,
                'columns': 4, 'max_questions_per_column': 25
            },
            'columns': {
                'column_width': 605, 'header_height': 25,
                'question_row_height': 14, 'question_start_y': 40
            }
        }
    
    def save_debug_images(self, output_dir):
        """Save debug images for answer processing"""
        try:
            import os
            # Create answer debug subdirectory
            answer_debug_dir = os.path.join(output_dir, 'answer_debug')
            os.makedirs(answer_debug_dir, exist_ok=True)
            
            for stage_name, debug_img in self.debug_images:
                filename = f"{stage_name}.png"
                filepath = os.path.join(answer_debug_dir, filename)
                
                # Save image
                cv2.imwrite(filepath, debug_img)
                logger.info(f"Saved answer debug image: {filepath}")
                
        except Exception as e:
            logger.error(f"Error saving answer debug images: {str(e)}")
    
    def validate_answers(self, detected_answers, answer_key):
        """
        Validate detected answers against answer key
        
        Args:
            detected_answers: Dictionary of detected student answers
            answer_key: Dictionary of correct answers
            
        Returns:
            Validation results with scores
        """
        # TODO: Implement answer validation
        logger.info("Answer validation - implementation pending")
        return {
            'correct_count': 0,
            'total_questions': len(answer_key),
            'score_percentage': 0.0,
            'detailed_results': {}
        }
    
    def _get_bubble_coords(self, column, question_num, choice_index, grid_config):
        """Get bubble coordinates relative to the grid"""
        try:
            if CONFIG_AVAILABLE:
                # Use configuration-based coordinates
                coords = get_bubble_coordinates(column, question_num, choice_index, 'multiple_choice_4')
                # Convert to grid-relative coordinates
                grid = grid_config['grid']
                return {
                    'x': coords['x'] - grid['x'],
                    'y': coords['y'] - grid['y'], 
                    'radius': coords['radius']
                }
            else:
                # Fallback coordinate calculation
                return self._calculate_fallback_bubble_coords(column, question_num, choice_index)
                
        except Exception as e:
            logger.error(f"Error getting bubble coordinates: {str(e)}")
            return None
    
    def _detect_bubble_fill(self, processed_grid, bubble_coords, grid_config):
        """Detect if a bubble is filled"""
        try:
            x, y, radius = bubble_coords['x'], bubble_coords['y'], bubble_coords['radius']
            
            # Create circular mask
            mask = np.zeros(processed_grid.shape, dtype=np.uint8)
            cv2.circle(mask, (int(x), int(y)), radius, 255, -1)
            
            # Extract bubble region
            bubble_region = cv2.bitwise_and(processed_grid, mask)
            
            # Calculate fill ratio
            total_pixels = np.sum(mask == 255)
            filled_pixels = np.sum(bubble_region == 255)
            fill_ratio = filled_pixels / total_pixels if total_pixels > 0 else 0
            
            # Calculate confidence based on fill pattern
            confidence = self._calculate_bubble_confidence(bubble_region, mask, fill_ratio)
            
            return fill_ratio, confidence
            
        except Exception as e:
            logger.error(f"Error detecting bubble fill: {str(e)}")
            return 0.0, 0.0
    
    def _calculate_bubble_confidence(self, bubble_region, mask, fill_ratio):
        """Calculate confidence score for bubble detection"""
        try:
            # Base confidence from fill ratio
            if fill_ratio > 0.8:
                confidence = 0.9
            elif fill_ratio > 0.6:
                confidence = 0.8
            elif fill_ratio > 0.4:
                confidence = 0.6
            elif fill_ratio > 0.2:
                confidence = 0.3
            else:
                confidence = 0.1
            
            # Adjust based on fill pattern uniformity
            bubble_pixels = bubble_region[mask == 255]
            if len(bubble_pixels) > 0:
                uniformity = 1.0 - (np.std(bubble_pixels) / 255.0)
                confidence *= (0.5 + 0.5 * uniformity)
            
            return min(1.0, max(0.0, confidence))
            
        except Exception as e:
            logger.error(f"Error calculating bubble confidence: {str(e)}")
            return 0.5
    
    def _determine_answer(self, question_answers, detection_config):
        """Determine the final answer for a question"""
        try:
            filled_threshold = detection_config['filled_threshold']
            
            # Find bubbles above threshold
            filled_bubbles = [(choice, ratio, conf) for choice, ratio, conf in question_answers 
                            if ratio > filled_threshold]
            
            if len(filled_bubbles) == 0:
                # No answer detected
                return None, 0.0
            elif len(filled_bubbles) == 1:
                # Single answer (ideal case)
                choice, ratio, conf = filled_bubbles[0]
                return choice, conf
            else:
                # Multiple answers - choose highest fill ratio but reduce confidence
                filled_bubbles.sort(key=lambda x: x[1], reverse=True)
                choice, ratio, conf = filled_bubbles[0]
                penalty = detection_config.get('multiple_answers_penalty', 0.5)
                return choice, conf * penalty
                
        except Exception as e:
            logger.error(f"Error determining answer: {str(e)}")
            return None, 0.0
    
    def _get_fallback_config(self):
        """Fallback configuration when config file not available"""
        return {
            'grid': {
                'x': 30, 'y': 600, 'width': 2420, 'height': 2500,
                'columns': 4, 'max_questions_per_column': 25
            },
            'columns': {
                'column_width': 605, 'header_height': 25,
                'question_row_height': 14, 'question_start_y': 40
            },
            'bubbles': {
                'radius': 5, 'spacing': 16, 'start_x_offset': 30
            },
            'detection': {
                'filled_threshold': 0.6, 'confidence_threshold': 0.7,
                'multiple_answers_penalty': 0.5
            }
        }
    
    def _calculate_fallback_bubble_coords(self, column, question_num, choice_index):
        """Fallback bubble coordinate calculation"""
        # Basic calculation for fallback
        questions_per_col = 25
        question_in_col = ((question_num - 1) % questions_per_col)
        
        x = 30 + (column * 605) + 30 + (choice_index * 16)
        y = 40 + (question_in_col * 14)
        
        return {'x': x, 'y': y, 'radius': 5}

    def get_column_header_images(self, corrected_image):
        """
        Extract header images for each column using manually defined header areas.
        Returns a dict: {col_idx: header_img}
        """
        if not CONFIG_AVAILABLE:
            logger.error("Configuration not available. Cannot extract headers.")
            return {}

        import cv2
        header_areas = get_column_header_areas()
        header_imgs = {}
        # Convert to grayscale for consistency
        if len(corrected_image.shape) == 3:
            gray = cv2.cvtColor(corrected_image, cv2.COLOR_RGB2GRAY)
        else:
            gray = corrected_image.copy()
        height, width = gray.shape
        for col_idx, area in header_areas.items():
            x, y, w, h = area['x'], area['y'], area['width'], area['height']
            x = max(0, min(x, width - 1))
            y = max(0, min(y, height - 1))
            w = min(w, width - x)
            h = min(h, height - y)
            header_imgs[col_idx] = gray[y:y+h, x:x+w]
        return header_imgs

    def map_rows_in_column(self, column_img, num_questions=25, debug=False, output_path=None, col_idx=None):
        """
        Map each row (question) in a column image using OpenCV.
        Tries to automatically detect row boundaries using horizontal projection.
        Falls back to fixed row height if detection fails.
        """
        import numpy as np
        import cv2

        h, w = column_img.shape

        # Use header height from config if available, else fallback
        header_height = 0
        if CONFIG_AVAILABLE and col_idx is not None:
            from field_coordinates_config import get_column_header_areas
            header_areas = get_column_header_areas()
            if col_idx in header_areas:
                header_height = header_areas[col_idx]['height']
        if not header_height or header_height >= h:
            header_height = int(h * 0.06)

        # Crop out header area for row detection
        answer_area = column_img[header_height:, :]
        answer_h = answer_area.shape[0]

        # Horizontal projection (sum of black pixels per row)
        proj = np.sum(255 - answer_area, axis=1)
        proj_norm = (proj - np.min(proj)) / (np.max(proj) - np.min(proj) + 1e-6)

        # Find valleys (gaps) between rows using local minima
        from scipy.signal import find_peaks
        # Invert projection so valleys become peaks
        inv_proj = 1 - proj_norm
        peaks, _ = find_peaks(inv_proj, distance=answer_h // num_questions // 2, prominence=0.1)

        # If we find enough valleys, use them as row boundaries
        row_boxes = []
        if len(peaks) >= num_questions - 1:
            # Use detected valleys to split rows
            boundaries = [0] + sorted(peaks.tolist()) + [answer_h]
            # If too many, pick the best num_questions-1
            if len(boundaries) > num_questions + 1:
                # Uniformly sample boundaries
                idxs = np.linspace(0, len(boundaries)-1, num_questions+1, dtype=int)
                boundaries = [boundaries[i] for i in idxs]
            for i in range(num_questions):
                y1 = header_height + boundaries[i]
                y2 = header_height + boundaries[i+1]
                row_boxes.append((y1, y2))
        else:
            # Fallback: fixed row height
            row_height = answer_h // num_questions
            for i in range(num_questions):
                y1 = header_height + i * row_height
                y2 = header_height + (i + 1) * row_height if i < num_questions - 1 else h
                row_boxes.append((y1, y2))

        # Debug visualization
        if debug and output_path:
            debug_img = cv2.cvtColor(column_img, cv2.COLOR_GRAY2BGR)
            for idx, (y1, y2) in enumerate(row_boxes):
                cv2.rectangle(debug_img, (0, y1), (w-1, y2), (0, 0, 255), 2)
                cv2.putText(debug_img, f"Q{idx+1}", (5, y1+20), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,0,0), 2)
            cv2.imwrite(output_path, debug_img)
            logger.info(f"Saved row mapping debug image: {output_path}")

        return row_boxes

    def debug_column_row_mapping(self, column_img, num_questions=25, output_path=None, col_idx=None, corrected_image=None):
        """
        Visualize and save the row mapping for a column image, including the header area.

        Args:
            column_img: Grayscale image of a single answer column.
            num_questions: Number of questions (rows) in the column.
            output_path: Path to save the debug image.
            col_idx: Column index (0-based) to fetch header area from config.
            corrected_image: (Optional) Full corrected image to extract header from config.
        """
        # Draw row mapping as before
        row_boxes = self.map_rows_in_column(column_img, num_questions=num_questions, col_idx=col_idx)
        h, w = column_img.shape

        # Determine the starting question number for this column
        question_numbers = []
        if CONFIG_AVAILABLE and col_idx is not None:
            from field_coordinates_config import COLUMN_CONFIG
            max_per_col = COLUMN_CONFIG.get('max_questions_per_column', 25)
            start_question = col_idx * max_per_col + 1
            question_numbers = [start_question + i for i in range(num_questions)]
        else:
            question_numbers = [i + 1 for i in range(num_questions)]

        debug_img = cv2.cvtColor(column_img, cv2.COLOR_GRAY2BGR)
        for idx, (y1, y2) in enumerate(row_boxes):
            cv2.rectangle(debug_img, (0, y1), (w-1, y2), (0, 0, 255), 2)
            cv2.putText(debug_img, f"Q{question_numbers[idx]}", (5, y1+20), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,0,0), 2)

        # Draw header area if col_idx and corrected_image are provided
        if col_idx is not None and corrected_image is not None and CONFIG_AVAILABLE:
            from field_coordinates_config import get_column_header_areas
            header_areas = get_column_header_areas()
            if col_idx in header_areas:
                area = header_areas[col_idx]
                w_header, h_header = area['width'], area['height']
                cv2.rectangle(debug_img, (0, 0), (w_header-1, h_header-1), (0, 255, 255), 2)
                cv2.putText(debug_img, "HEADER", (5, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 128, 255), 2)

        if output_path:
            cv2.imwrite(output_path, debug_img)
            logger.info(f"Saved column row mapping debug image: {output_path}")
        return debug_img

    def detect_answers_in_column(self, column_img, col_idx, num_questions=25, choices=4, debug=False, output_path=None,
                                 vertical_spacing=None):
        """
        Detect filled answers for each question row in a column image.
        For each row, use a fixed initial bubble x/y and fixed spacing for all bubbles.
        Optionally specify vertical_spacing to adjust bubble y-position within each row.
        Automatically creates a debug image showing bubble detection for every call.
        Fix: Ensure last row always reaches the bottom of the column image.
        Args:
            column_img: Grayscale image of a single answer column.
            col_idx: Column index (0-based).
            num_questions: Number of questions (rows) in the column.
            choices: Number of choices per question (A-D).
            debug: If True, saves debug image.
            output_path: Path to save debug image.
            vertical_spacing: (Optional) If set, vertical distance between bubbles in a row (for vertical bubble layouts).
        """
        import cv2
        import numpy as np
        import os

        h, w = column_img.shape

        # Use header height from config if available, else fallback
        header_height = 65
        column_width = w
        if CONFIG_AVAILABLE and col_idx is not None:
            from field_coordinates_config import get_column_header_areas, COLUMN_CONFIG
            header_areas = get_column_header_areas()
            if col_idx in header_areas:
                header_height = header_areas[col_idx].get('height', 0)
            column_width = COLUMN_CONFIG.get('column_width', w)
        if not header_height or header_height >= h:
            header_height = int(h * 0.06)

        # Fixed row mapping: ensure last row reaches the bottom
        answer_area_height = h - header_height
        row_boxes = []
        for i in range(num_questions):
            y1 = header_height + i * (answer_area_height // num_questions)
            if i == num_questions - 1:
                y2 = h  # Last row goes to the bottom
            else:
                y2 = header_height + (i + 1) * (answer_area_height // num_questions)
            row_boxes.append((y1, y2))

        # --- Use hard-coded bubble placement per column if desired ---
        if col_idx == 0:
            initial_bubble_x = 40
            bubble_spacing = 70
        elif col_idx == 1:
            initial_bubble_x = 40
            bubble_spacing = 70
        elif col_idx == 2:
            initial_bubble_x = 45
            bubble_spacing = 70
        elif col_idx == 3:
            initial_bubble_x = 38
            bubble_spacing = 70
        else:
            initial_bubble_x = int(column_width * 0.25)
            bubble_spacing = int(column_width * 0.21)
        bubble_y_offset = 0
        bubble_radius = int(min(row_boxes[0][1] - row_boxes[0][0], column_width // choices) * 0.25)

        detected_answers = []
        debug_img = cv2.cvtColor(column_img, cv2.COLOR_GRAY2BGR)

        # --- FIX: Use evenly spaced vertical positions for bubbles in each row ---
        for q_idx, (y1, y2) in enumerate(row_boxes):
            row_img = column_img[y1:y2, :]
            row_h, row_w = row_img.shape

            cx = initial_bubble_x
            # Evenly distribute bubbles vertically in the row (centered)
            total_bubble_height = (choices - 1) * bubble_radius * 2
            start_y = (row_h - total_bubble_height) // 2 + bubble_radius

            bubble_centers = []
            for i in range(choices):
                bx = cx + i * bubble_spacing
                by = int(row_h // 2)  # Default: all bubbles on the same y
                # For vertical spacing, distribute bubbles vertically
                if vertical_spacing is not None:
                    by = int(start_y + i * vertical_spacing)
                bubble_centers.append((int(bx), by))

            bubble_fill_ratios = []
            for c_idx, (bx, by) in enumerate(bubble_centers):
                bx = int(np.clip(bx, bubble_radius, row_w - bubble_radius - 1))
                by = int(np.clip(by, bubble_radius, row_h - bubble_radius - 1))
                mask = np.zeros_like(row_img, dtype=np.uint8)
                cv2.circle(mask, (bx, by), bubble_radius, 255, -1)
                bubble_region = cv2.bitwise_and(row_img, row_img, mask=mask)
                # Calculate fill ratio: ratio of dark pixels (filled) to total pixels in the bubble
                total_pixels = np.sum(mask == 255)
                filled_pixels = np.sum(bubble_region[mask == 255] < 180)
                fill_ratio = filled_pixels / total_pixels if total_pixels > 0 else 0
                bubble_fill_ratios.append(fill_ratio)
                color = (0, 255, 0) if fill_ratio >= 0.8 else (0, 0, 255)
                cv2.circle(debug_img, (bx, y1 + by), bubble_radius, color, 2)
                cv2.putText(debug_img, chr(65+c_idx), (bx-8, y1 + by - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

            if not bubble_fill_ratios:
                detected_answers.append(None)
                cv2.putText(debug_img, "?", (10, y1 + row_h // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                continue

            # Find bubbles with at least 80% fill
            filled_indices = [i for i, ratio in enumerate(bubble_fill_ratios) if ratio >= 0.75]
            if len(filled_indices) == 1:
                min_idx = filled_indices[0]
                detected_answers.append(chr(65 + min_idx))
                bx, by = bubble_centers[min_idx]
                cv2.putText(debug_img, chr(65 + min_idx), (10, y1 + by + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,0), 2)
            else:
                detected_answers.append(None)
                cv2.putText(debug_img, "?", (10, y1 + row_h // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,0,255), 2)

        if output_path is None:
            output_path = f"column_{col_idx+1}_answers_debug.png"
        cv2.imwrite(output_path, debug_img)
        logger.info(f"Saved answer detection debug image: {output_path}")

        return detected_answers
    
    def debug_bubble_detection(self, column_img, col_idx, num_questions=25, choices=4, output_path=None):
            """
            Visualize and save the detected bubble centers and filled status for each row in a column.
            Draws all candidate bubbles, highlights the detected answer, and marks ambiguous/empty rows.
            """
            import cv2
            import numpy as np

            row_boxes = self.map_rows_in_column(column_img, num_questions=num_questions, col_idx=col_idx)
            h, w = column_img.shape

            # Try to find bubble centers in the first row
            first_row_img = column_img[row_boxes[0][0]:row_boxes[0][1], :]
            _, thresh = cv2.threshold(first_row_img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            bubble_centers_x = []
            for cnt in contours:
                (x, y), radius = cv2.minEnclosingCircle(cnt)
                if 10 < radius < 40:
                    bubble_centers_x.append(int(x))
            bubble_centers_x = sorted(bubble_centers_x)
            if len(bubble_centers_x) == choices:
                bubble_xs = bubble_centers_x
            else:
                if CONFIG_AVAILABLE:
                    from field_coordinates_config import COLUMN_CONFIG
                    col_w = COLUMN_CONFIG.get('column_width', w)
                    margin_x = int(col_w * 0.12)
                    margin_x_end = int(col_w * 0.88)
                    bubble_xs = np.linspace(margin_x, margin_x_end, choices)
                else:
                    bubble_xs = np.linspace(int(w*0.15), int(w*0.85), choices)

            debug_img = cv2.cvtColor(column_img, cv2.COLOR_GRAY2BGR)
            detected_answers = []

            for q_idx, (y1, y2) in enumerate(row_boxes):
                row_img = column_img[y1:y2, :]
                bubble_scores = []
                bubble_centers = []
                for c_idx, bx in enumerate(bubble_xs):
                    by = (y2 + y1) // 2
                    radius = int(min((y2-y1), w//choices) * 0.38)
                    mask = np.zeros_like(row_img, dtype=np.uint8)
                    cv2.circle(mask, (int(bx), (y2-y1)//2), radius, 255, -1)
                    bubble_region = cv2.bitwise_and(row_img, row_img, mask=mask)
                    mean_val = cv2.mean(bubble_region, mask=mask)[0]
                    bubble_scores.append(mean_val)
                    bubble_centers.append((int(bx), by, radius))
                    # Draw all candidate bubbles
                    cv2.circle(debug_img, (int(bx), by), radius, (200, 200, 200), 1)
                    cv2.putText(debug_img, chr(65+c_idx), (int(bx)-8, by-8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180,180,180), 1)

                min_idx = int(np.argmin(bubble_scores))
                min_val = bubble_scores[min_idx]
                others = [v for i, v in enumerate(bubble_scores) if i != min_idx]
                # Highlight detected answer if confident
                if min_val < 180 and (np.mean(others) - min_val > 25):
                    detected_answers.append(chr(65 + min_idx))
                    bx, by, radius = bubble_centers[min_idx]
                    cv2.circle(debug_img, (bx, by), radius, (0, 255, 0), 2)
                    cv2.putText(debug_img, chr(65 + min_idx), (bx-8, by+radius+18), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,0), 2)
                else:
                    detected_answers.append(None)
                    # Mark ambiguous/empty row
                    for bx, by, radius in bubble_centers:
                        cv2.circle(debug_img, (bx, by), radius, (0, 0, 255), 1)
                    cv2.putText(debug_img, "?", (10, y1+25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,0,255), 2)

            if output_path:
                cv2.imwrite(output_path, debug_img)
                logger.info(f"Saved bubble detection debug image: {output_path}")

            return detected_answers

if __name__ == "__main__":
    # Remove CLI/testing code, this file is now a service module only.
    pass
    # Usage: python pdf_processor_stud_answer.py <column_img_path> <col_idx> [--debug]
    if len(sys.argv) < 3:
        print("Usage: python pdf_processor_stud_answer.py <column_img_path> <col_idx> [--debug]")
        sys.exit(1)
    img_path = sys.argv[1]
    col_idx = int(sys.argv[2])
    debug = "--debug" in sys.argv

    # Check if file exists before loading
    if not os.path.isfile(img_path):
        print(f"Error: File '{img_path}' does not exist. Please check the file path.")
        sys.exit(1)

    img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        print(f"Error: Could not load image '{img_path}'. Please check the file format and integrity.")
        sys.exit(1)
    processor = StudentAnswerProcessor()
    answers = processor.detect_answers_in_column(
        img, col_idx, num_questions=25, choices=4, debug=debug,
        output_path="column_{}_answers_debug.png".format(col_idx+1) if debug else None
    )
    for i, ans in enumerate(answers, 1):
        print(f"Q{i}: {ans}")

# Usage example for debugging bubble detection in a column:
# (Assume you have already extracted the column image as `col_img` and know its column index `col_idx`)
#
# import cv2
# from scripts.pdf_processor_stud_answer import StudentAnswerProcessor
#
# # Load your column image (grayscale)
# col_img = cv2.imread(r"D:\YUKI\ADET\Checkmate\column_row_debug\column_1_header_rows_debug.png", cv2.IMREAD_GRAYSCALE)
# processor = StudentAnswerProcessor()
# processor.debug_bubble_detection(
#     column_img=col_img,           # Grayscale image of a single answer column
#     col_idx=0,                    # Column index (0-based, so 0 for column_1)
#     num_questions=25,             # Number of questions in this column
#     choices=4,                    # Number of choices per question (A-D)
#     output_path="col1_bubble_debug.png"  # Output path for debug image
# )
#
# This will save an image showing all candidate bubbles, highlight the detected answer,
# and mark ambiguous/empty rows for visual inspection.
#
# This will save an image showing all candidate bubbles, highlight the detected answer,
# and mark ambiguous/empty rows for visual inspection.
# col_img = cv2.imread(r"D:\YUKI\ADET\Checkmate\column_row_debug\column_1_header_rows_debug.png", cv2.IMREAD_GRAYSCALE)
# processor = StudentAnswerProcessor()
# processor.debug_bubble_detection(
#     column_img=col_img,           # Grayscale image of a single answer column
#     col_idx=0,                    # Column index (0-based, so 0 for column_1)
#     num_questions=25,             # Number of questions in this column
#     choices=4,                    # Number of choices per question (A-D)
#     output_path="col1_bubble_debug.png"  # Output path for debug image
# )
#
# This will save an image showing all candidate bubbles, highlight the detected answer,
# and mark ambiguous/empty rows for visual inspection.
#
# This will save an image showing all candidate bubbles, highlight the detected answer,
# and mark ambiguous/empty rows for visual inspection.
# This will save an image showing all candidate bubbles, highlight the detected answer,
# and mark ambiguous/empty rows for visual inspection.
    processor = StudentAnswerProcessor()
    answers = processor.detect_answers_in_column(
        img, col_idx, num_questions=25, choices=4, debug=debug,
        output_path="column_{}_answers_debug.png".format(col_idx+1) if debug else None
    )
    for i, ans in enumerate(answers, 1):
        print(f"Q{i}: {ans}")

# Usage example for debugging bubble detection in a column:
# (Assume you have already extracted the column image as `col_img` and know its column index `col_idx`)
#
# import cv2
# from scripts.pdf_processor_stud_answer import StudentAnswerProcessor
#
# # Load your column image (grayscale)
# col_img = cv2.imread(r"D:\YUKI\ADET\Checkmate\column_row_debug\column_1_header_rows_debug.png", cv2.IMREAD_GRAYSCALE)
# processor = StudentAnswerProcessor()
# processor.debug_bubble_detection(
#     column_img=col_img,           # Grayscale image of a single answer column
#     col_idx=0,                    # Column index (0-based, so 0 for column_1)
#     num_questions=25,             # Number of questions in this column
#     choices=4,                    # Number of choices per question (A-D)
#     output_path="col1_bubble_debug.png"  # Output path for debug image
# )
#
# This will save an image showing all candidate bubbles, highlight the detected answer,
# and mark ambiguous/empty rows for visual inspection.
#
# This will save an image showing all candidate bubbles, highlight the detected answer,
# and mark ambiguous/empty rows for visual inspection.
# col_img = cv2.imread(r"D:\YUKI\ADET\Checkmate\column_row_debug\column_1_header_rows_debug.png", cv2.IMREAD_GRAYSCALE)
# processor = StudentAnswerProcessor()
# processor.debug_bubble_detection(
#     column_img=col_img,           # Grayscale image of a single answer column
#     col_idx=0,                    # Column index (0-based, so 0 for column_1)
#     num_questions=25,             # Number of questions in this column
#     choices=4,                    # Number of choices per question (A-D)
#     output_path="col1_bubble_debug.png"  # Output path for debug image
# )
#
# This will save an image showing all candidate bubbles, highlight the detected answer,
# and mark ambiguous/empty rows for visual inspection.
#
# This will save an image showing all candidate bubbles, highlight the detected answer,
# and mark ambiguous/empty rows for visual inspection.
