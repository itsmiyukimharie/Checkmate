# CheckMate PDF Student Answer Sheet Processing Algorithm

This document explains the algorithm used by CheckMate to process student answer sheets in PDF format using OCR and OpenCV.

---

## Overview

CheckMate processes scanned or photographed answer sheets (PDFs) to extract student answers and information using a combination of OpenCV (for image processing and bubble detection) and OCR (for text extraction as fallback). The main steps are:

1. **PDF to Image Conversion**
2. **Image Preprocessing**
3. **Answer Grid Detection**
4. **Bubble Detection and Answer Extraction**
5. **Student Info Extraction (OCR)**
6. **Result Validation and Output**

---

## Detailed Steps

### 1. PDF to Image Conversion

- The uploaded PDF is converted to one or more images (one per page) using a PDF-to-image library.
- Each image is processed individually.

### 2. Image Preprocessing

- The image is converted to grayscale for easier processing.
- Optional enhancements (contrast, sharpening) are applied using OpenCV to improve bubble and text visibility.
- Perspective correction may be applied if the sheet is skewed.

### 3. Answer Grid Detection

- The region of the image containing the answer grid is located using either:
  - Predefined coordinates from a config file (if available), or
  - Fallback hardcoded coordinates.
- The answer grid is cropped from the main image for further analysis.

### 4. Bubble Detection and Answer Extraction

- The answer grid is divided into columns and rows based on the test layout (e.g., 4 columns, 25 questions per column).
- For each question row:
  - The expected positions of answer bubbles (A-E) are calculated.
  - For each bubble:
    - A circular mask is applied at the expected location.
    - The fill ratio (how dark the bubble is) is computed.
    - If the fill ratio exceeds a threshold (e.g., 75%), the bubble is considered filled.
  - If exactly one bubble is filled, that answer is recorded.
  - If multiple or no bubbles are filled, the answer is marked as ambiguous or blank.
- Debug images can be saved at each stage for troubleshooting.

### 5. Student Info Extraction (OCR)

- The region containing student information (name, ID, section) is cropped using predefined or fallback coordinates.
- OCR (Optical Character Recognition) is applied to this region to extract text fields.
- If OCR fails or is ambiguous, the fields may be left blank or flagged for manual review.

### 6. Result Validation and Output

- The extracted answers are compared against the answer key (if available) to compute scores.
- Confidence scores are assigned based on bubble fill ratios and OCR quality.
- The final output includes:
  - Extracted answers per question
  - Student information (from OCR or database lookup)
  - Score and percentage
  - Debug images (if enabled)
  - Any errors or warnings encountered during processing

---

## Key Technologies Used

- **OpenCV**: For image processing, grid/bubble detection, and enhancements.
- **OCR (e.g., Tesseract)**: For extracting student info text.
- **PDF-to-Image**: For converting PDF pages to images.
- **Django**: For web integration and result storage.

---

## Example Code Reference

See [`scripts/pdf_processor_stud_answer.py`](scripts/pdf_processor_stud_answer.py) for the main implementation of answer grid extraction and bubble detection.

---

## Notes

- The algorithm is robust to minor misalignments and noise but works best with clear, high-contrast scans.
- Manual review is recommended for low-confidence results or when OCR fails to extract student info reliably.
- The system can be extended to support different answer sheet layouts by updating the configuration.