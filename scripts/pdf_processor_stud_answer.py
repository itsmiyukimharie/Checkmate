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
        calculate_column_layout,
        get_bubble_coordinates,
        BUBBLE_CONFIG
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
        logger.info("StudentAnswerProcessor initialized with bubble detection")
    
    def extract_student_answers(self, corrected_image, question_count, test_type, output_dir=None):
        """
        Extract student answers from the answer section
        
        Args:
            corrected_image: Perspective corrected image
            question_count: Number of questions in the test
            test_type: Type of test (multiple_choice_4, multiple_choice_5, true_false)
            output_dir: Directory to save debug images (optional)
            
        Returns:
            Dictionary with extracted answers
        """
        try:
            logger.info(f"Extracting answers for {question_count} questions, type: {test_type}")
            
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
                layout = calculate_column_layout(question_count)
                choices = grid_config['bubbles']['choices'][test_type]
            else:
                # Fallback configuration
                grid_config = self._get_fallback_config()
                layout = self._calculate_fallback_layout(question_count)
                choices = ['A', 'B', 'C', 'D'] if test_type == 'multiple_choice_4' else ['A', 'B', 'C', 'D', 'E'] if test_type == 'multiple_choice_5' else ['T', 'F']
            
            # Extract answer grid region
            answer_grid = self._extract_answer_grid(gray, grid_config)
            self.debug_images.append(('01_answer_grid', answer_grid))
            
            # Preprocess for bubble detection
            processed_grid = self._preprocess_for_bubbles(answer_grid)
            self.debug_images.append(('02_processed_grid', processed_grid))
            
            # Detect answers for each question
            detected_answers = {}
            confidence_scores = {}
            
            for col_info in layout['column_ranges']:
                logger.info(f"Processing column {col_info['column']}: Q{col_info['start_question']}-{col_info['end_question']}")
                
                col_answers, col_confidence = self._process_column(
                    processed_grid, col_info, choices, test_type, grid_config
                )
                
                detected_answers.update(col_answers)
                confidence_scores.update(col_confidence)
            
            # Save debug images
            if output_dir:
                self.save_debug_images(output_dir)
            
            result = {
                'answers': detected_answers,
                'confidence_scores': confidence_scores,
                'total_detected': len(detected_answers),
                'layout': layout,
                'test_type': test_type,
                'success': True
            }
            
            logger.info(f"Successfully detected {len(detected_answers)} answers")
            return result
            
        except Exception as e:
            logger.error(f"Error extracting student answers: {str(e)}")
            return {
                'answers': {},
                'confidence_scores': {},
                'total_detected': 0,
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
    
    def _preprocess_for_bubbles(self, answer_grid):
        """Preprocess the answer grid for bubble detection"""
        try:
            # Enhance contrast
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            enhanced = clahe.apply(answer_grid)
            
            # Gaussian blur to reduce noise
            blurred = cv2.GaussianBlur(enhanced, (3, 3), 0)
            
            # Binary threshold for bubble detection
            _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            
            logger.info("Answer grid preprocessed for bubble detection")
            return binary
            
        except Exception as e:
            logger.error(f"Error in preprocessing: {str(e)}")
            return answer_grid
    
    def _process_column(self, processed_grid, col_info, choices, test_type, grid_config):
        """Process a single column of questions"""
        answers = {}
        confidence_scores = {}
        
        try:
            column = col_info['column']
            
            # Create visualization for this column
            height, width = processed_grid.shape
            col_debug = cv2.cvtColor(processed_grid, cv2.COLOR_GRAY2RGB)
            
            for q_num in range(col_info['start_question'], col_info['end_question'] + 1):
                # Detect bubbles for this question
                question_answers = []
                question_confidences = []
                
                for choice_idx, choice in enumerate(choices):
                    bubble_coords = self._get_bubble_coords(column, q_num, choice_idx, grid_config)
                    
                    if bubble_coords:
                        fill_ratio, confidence = self._detect_bubble_fill(
                            processed_grid, bubble_coords, grid_config
                        )
                        
                        question_answers.append((choice, fill_ratio, confidence))
                        question_confidences.append(confidence)
                        
                        # Draw bubble on debug image
                        cv2.circle(col_debug, 
                                 (int(bubble_coords['x']), int(bubble_coords['y'])), 
                                 bubble_coords['radius'] + 2, 
                                 (0, 255, 0) if fill_ratio > grid_config['detection']['filled_threshold'] else (255, 0, 0), 
                                 2)
                        
                        # Add text labels
                        cv2.putText(col_debug, f"Q{q_num}", 
                                  (int(bubble_coords['x'] - 20), int(bubble_coords['y'])), 
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 255, 255), 1)
                
                # Determine the answer for this question
                detected_answer, answer_confidence = self._determine_answer(
                    question_answers, grid_config['detection']
                )
                
                if detected_answer:
                    answers[q_num] = detected_answer
                    confidence_scores[q_num] = answer_confidence
                    logger.debug(f"Q{q_num}: {detected_answer} (confidence: {answer_confidence:.2f})")
            
            # Save column debug image
            self.debug_images.append((f'03_column_{column}_detection', col_debug))
            
            return answers, confidence_scores
            
        except Exception as e:
            logger.error(f"Error processing column {col_info['column']}: {str(e)}")
            return {}, {}
    
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
    
    def _calculate_fallback_layout(self, question_count):
        """Fallback layout calculation"""
        questions_per_column = 25
        columns_needed = min(4, (question_count + questions_per_column - 1) // questions_per_column)
        
        layout = {'columns': columns_needed, 'column_ranges': []}
        
        for col in range(columns_needed):
            start_q = col * questions_per_column + 1
            end_q = min(start_q + questions_per_column - 1, question_count)
            if start_q <= question_count:
                layout['column_ranges'].append({
                    'column': col, 'start_question': start_q, 
                    'end_question': end_q, 'question_count': end_q - start_q + 1
                })
        
        return layout
    
    def _calculate_fallback_bubble_coords(self, column, question_num, choice_index):
        """Fallback bubble coordinate calculation"""
        # Basic calculation for fallback
        questions_per_col = 25
        question_in_col = ((question_num - 1) % questions_per_col)
        
        x = 30 + (column * 605) + 30 + (choice_index * 16)
        y = 40 + (question_in_col * 14)
        
        return {'x': x, 'y': y, 'radius': 5}
    
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
