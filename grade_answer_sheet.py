#!/usr/bin/env python3
"""
CheckMate Answer Sheet Grader
Independent script for grading answer sheets in PDF format
Compatible with Python 3.12.9
"""

import sys
import cv2
import numpy as np
import pytesseract
import pdf2image
from PIL import Image
import re
import json
from pathlib import Path

# Check Python version
if sys.version_info < (3, 8):
    print("Error: This script requires Python 3.8 or higher")
    print(f"Current version: {sys.version}")
    sys.exit(1)

class AnswerSheetGrader:
    def __init__(self):
        # Configure tesseract path if needed (Windows)
        # Uncomment and modify path as needed:
        # pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
        
        # Answer key for testing (you can modify this)
        self.answer_key = {
            1: 'A', 2: 'B', 3: 'C', 4: 'D', 5: 'A',
            6: 'B', 7: 'C', 8: 'D', 9: 'A', 10: 'B',
            11: 'C', 12: 'D', 13: 'A', 14: 'B', 15: 'C',
            16: 'D', 17: 'A', 18: 'B', 19: 'C', 20: 'D'
        }
        
        # Choice mappings
        self.choices = ['A', 'B', 'C', 'D']
        
        # Check dependencies on initialization
        self._check_dependencies()
    
    def _check_dependencies(self):
        """Check if required dependencies are properly installed"""
        try:
            # Test OpenCV
            cv2.__version__
            print(f"✓ OpenCV version: {cv2.__version__}")
            
            # Test PIL/Pillow
            Image.__version__
            print(f"✓ Pillow version: {Image.__version__}")
            
            # Test numpy
            print(f"✓ NumPy version: {np.__version__}")
            
            # Test pytesseract
            print(f"✓ PyTesseract version: {pytesseract.__version__}")
            
            # Test pdf2image
            print(f"✓ pdf2image available")
            
        except ImportError as e:
            print(f"✗ Missing dependency: {e}")
            print("Please install required packages:")
            print("pip install -r requirements_grading.txt")
            sys.exit(1)
        except Exception as e:
            print(f"⚠ Warning: {e}")
    
    def pdf_to_images(self, pdf_path):
        """Convert PDF to images"""
        try:
            # Convert PDF to PIL images
            images = pdf2image.convert_from_path(pdf_path, dpi=300)
            print(f"Successfully converted PDF to {len(images)} images")
            return images
        except Exception as e:
            print(f"Error converting PDF: {str(e)}")
            return None
    
    def extract_student_info(self, image):
        """Extract student name and ID using OCR"""
        try:
            # Convert PIL to OpenCV format
            opencv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            
            # Focus on the student info section (approximate region)
            height, width = opencv_image.shape[:2]
            # Student info is typically in the upper portion
            student_section = opencv_image[int(height*0.1):int(height*0.25), :]
            
            # Preprocess for better OCR
            gray = cv2.cvtColor(student_section, cv2.COLOR_BGR2GRAY)
            
            # Apply threshold to get better text recognition
            _, thresh = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
            
            # Use OCR to extract text
            text = pytesseract.image_to_string(thresh, config='--psm 6')
            
            # Extract name and ID using regex patterns
            name_pattern = r'Name:\s*([A-Za-z\s]+?)(?:\n|ID:)'
            id_pattern = r'ID:\s*([A-Za-z0-9\-]+)'
            
            name_match = re.search(name_pattern, text, re.IGNORECASE)
            id_match = re.search(id_pattern, text, re.IGNORECASE)
            
            student_name = name_match.group(1).strip() if name_match else "Unknown"
            student_id = id_match.group(1).strip() if id_match else "Unknown"
            
            print(f"Extracted - Name: {student_name}, ID: {student_id}")
            return student_name, student_id
            
        except Exception as e:
            print(f"Error extracting student info: {str(e)}")
            return "Unknown", "Unknown"
    
    def detect_bubbles(self, image):
        """Detect answer bubbles in the image"""
        try:
            # Convert PIL to OpenCV format
            opencv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            gray = cv2.cvtColor(opencv_image, cv2.COLOR_BGR2GRAY)
            
            # Apply threshold
            _, thresh = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY_INV)
            
            # Find contours
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            bubbles = []
            for contour in contours:
                # Calculate area and check if it's a reasonable bubble size
                area = cv2.contourArea(contour)
                if 50 < area < 500:  # Adjust these values based on your PDF
                    # Check if contour is roughly circular
                    perimeter = cv2.arcLength(contour, True)
                    if perimeter > 0:
                        circularity = 4 * np.pi * area / (perimeter * perimeter)
                        if circularity > 0.5:  # Reasonably circular
                            x, y, w, h = cv2.boundingRect(contour)
                            center_x = x + w // 2
                            center_y = y + h // 2
                            bubbles.append({
                                'center': (center_x, center_y),
                                'area': area,
                                'contour': contour,
                                'bbox': (x, y, w, h)
                            })
            
            print(f"Detected {len(bubbles)} potential bubbles")
            return bubbles
            
        except Exception as e:
            print(f"Error detecting bubbles: {str(e)}")
            return []
    
    def check_bubble_filled(self, image, bubble):
        """Check if a bubble is filled"""
        try:
            # Convert PIL to OpenCV format
            opencv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            gray = cv2.cvtColor(opencv_image, cv2.COLOR_BGR2GRAY)
            
            # Extract bubble region
            x, y, w, h = bubble['bbox']
            bubble_region = gray[y:y+h, x:x+w]
            
            # Calculate the percentage of dark pixels
            _, thresh = cv2.threshold(bubble_region, 127, 255, cv2.THRESH_BINARY)
            dark_pixels = np.sum(thresh == 0)
            total_pixels = bubble_region.size
            
            fill_percentage = dark_pixels / total_pixels if total_pixels > 0 else 0
            
            # Consider bubble filled if more than 30% is dark
            return fill_percentage > 0.3, fill_percentage
            
        except Exception as e:
            print(f"Error checking bubble fill: {str(e)}")
            return False, 0.0
    
    def organize_bubbles_into_grid(self, bubbles):
        """Organize detected bubbles into a question-choice grid"""
        if not bubbles:
            return {}
        
        # Sort bubbles by Y coordinate (top to bottom) then X coordinate (left to right)
        sorted_bubbles = sorted(bubbles, key=lambda b: (b['center'][1], b['center'][0]))
        
        # Group bubbles into rows (questions)
        rows = []
        current_row = [sorted_bubbles[0]]
        row_y = sorted_bubbles[0]['center'][1]
        
        for bubble in sorted_bubbles[1:]:
            # If bubble is roughly on the same row (within tolerance)
            if abs(bubble['center'][1] - row_y) < 20:  # Adjust tolerance as needed
                current_row.append(bubble)
            else:
                # Start new row
                rows.append(current_row)
                current_row = [bubble]
                row_y = bubble['center'][1]
        
        # Add the last row
        if current_row:
            rows.append(current_row)
        
        # Organize into question-choice structure
        questions = {}
        for i, row in enumerate(rows):
            if len(row) == len(self.choices):  # Should have 4 bubbles for A, B, C, D
                question_num = i + 1
                # Sort row bubbles by X coordinate (left to right)
                row_sorted = sorted(row, key=lambda b: b['center'][0])
                questions[question_num] = {
                    choice: bubble for choice, bubble in zip(self.choices, row_sorted)
                }
        
        print(f"Organized bubbles into {len(questions)} questions")
        return questions
    
    def extract_answers(self, image, questions):
        """Extract student answers from the organized questions"""
        student_answers = {}
        
        for question_num, choices_bubbles in questions.items():
            selected_choices = []
            
            for choice, bubble in choices_bubbles.items():
                is_filled, fill_percentage = self.check_bubble_filled(image, bubble)
                if is_filled:
                    selected_choices.append(choice)
                    print(f"Q{question_num}: {choice} selected (fill: {fill_percentage:.2f})")
            
            # Handle multiple selections or no selection
            if len(selected_choices) == 1:
                student_answers[question_num] = selected_choices[0]
            elif len(selected_choices) > 1:
                student_answers[question_num] = f"MULTIPLE ({','.join(selected_choices)})"
            else:
                student_answers[question_num] = "NO_ANSWER"
        
        return student_answers
    
    def grade_answers(self, student_answers):
        """Grade the student answers against the answer key"""
        total_questions = len(self.answer_key)
        correct_answers = 0
        results = {}
        
        for question_num in range(1, total_questions + 1):
            correct_answer = self.answer_key.get(question_num)
            student_answer = student_answers.get(question_num, "NO_ANSWER")
            
            is_correct = student_answer == correct_answer
            if is_correct:
                correct_answers += 1
            
            results[question_num] = {
                'correct_answer': correct_answer,
                'student_answer': student_answer,
                'is_correct': is_correct
            }
        
        score = (correct_answers / total_questions) * 100
        return score, results, correct_answers, total_questions
    
    def save_debug_image(self, image, bubbles, filename="debug_bubbles.jpg"):
        """Save an image with detected bubbles marked for debugging"""
        try:
            # Convert PIL to OpenCV format
            opencv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            
            # Draw detected bubbles
            for i, bubble in enumerate(bubbles):
                center = bubble['center']
                cv2.circle(opencv_image, center, 10, (0, 255, 0), 2)
                cv2.putText(opencv_image, str(i), (center[0]-5, center[1]+5), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
            
            cv2.imwrite(filename, opencv_image)
            print(f"Debug image saved as {filename}")
            
        except Exception as e:
            print(f"Error saving debug image: {str(e)}")
    
    def process_answer_sheet(self, pdf_path):
        """Main method to process the answer sheet"""
        print(f"Processing answer sheet: {pdf_path}")
        
        # Convert PDF to images
        images = self.pdf_to_images(pdf_path)
        if not images:
            return None
        
        # Process first page (assuming single page answer sheet)
        image = images[0]
        
        # Extract student information
        student_name, student_id = self.extract_student_info(image)
        
        # Detect bubbles
        bubbles = self.detect_bubbles(image)
        
        if not bubbles:
            print("No bubbles detected!")
            return None
        
        # Save debug image
        self.save_debug_image(image, bubbles)
        
        # Organize bubbles into grid
        questions = self.organize_bubbles_into_grid(bubbles)
        
        if not questions:
            print("Could not organize bubbles into questions!")
            return None
        
        # Extract student answers
        student_answers = self.extract_answers(image, questions)
        
        # Grade answers
        score, results, correct, total = self.grade_answers(student_answers)
        
        # Compile final results
        final_results = {
            'student_name': student_name,
            'student_id': student_id,
            'score': score,
            'correct_answers': correct,
            'total_questions': total,
            'answers': student_answers,
            'detailed_results': results
        }
        
        return final_results
    
    def print_results(self, results):
        """Print the grading results in a formatted way"""
        if not results:
            print("No results to display!")
            return
        
        print("\n" + "="*50)
        print("ANSWER SHEET GRADING RESULTS")
        print("="*50)
        print(f"Student Name: {results['student_name']}")
        print(f"Student ID: {results['student_id']}")
        print(f"Score: {results['score']:.1f}% ({results['correct_answers']}/{results['total_questions']})")
        print("\n" + "-"*50)
        print("DETAILED RESULTS:")
        print("-"*50)
        
        for question_num in sorted(results['detailed_results'].keys()):
            detail = results['detailed_results'][question_num]
            status = "✓" if detail['is_correct'] else "✗"
            print(f"Q{question_num:2d}: {detail['student_answer']:10} | Correct: {detail['correct_answer']} | {status}")
        
        print("="*50)

def main():
    """Main function to run the grader"""
    grader = AnswerSheetGrader()
    
    # Path to your test PDF
    pdf_path = "pdf_directory/Test.pdf"
    
    # Check if file exists
    if not Path(pdf_path).exists():
        print(f"Error: PDF file not found at {pdf_path}")
        return
    
    # Process the answer sheet
    results = grader.process_answer_sheet(pdf_path)
    
    # Print results
    grader.print_results(results)
    
    # Save results to JSON file
    if results:
        with open("grading_results.json", "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to grading_results.json")

if __name__ == "__main__":
    main()
