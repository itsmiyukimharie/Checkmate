# Answer Sheet Grading Script

This independent script grades answer sheets in PDF format using computer vision and OCR.

## Python Version Requirements

- **Python 3.8 or higher** (Tested with Python 3.12.9)
- Recommended: Python 3.11+ for best performance

## Features

- **PDF Processing**: Converts PDF answer sheets to images
- **OCR Text Extraction**: Uses Tesseract OCR to extract student name and ID
- **Bubble Detection**: Uses OpenCV to detect and analyze answer bubbles
- **Automatic Grading**: Compares student answers with answer key
- **Debug Output**: Saves images showing detected bubbles for debugging

## Installation

### 1. Python Dependencies

Install Python dependencies using the provided requirements file:
```bash
pip install -r requirements_grading.txt
```

**Or install manually:**
```bash
pip install opencv-python==4.10.0.84
pip install pytesseract==0.3.13
pip install pdf2image==1.17.0
pip install Pillow==10.4.0
pip install numpy==1.26.4
```

### 2. System Dependencies

#### Tesseract OCR Installation

**Windows:**
1. Download from https://github.com/UB-Mannheim/tesseract/wiki
2. Install to default location (`C:\Program Files\Tesseract-OCR\`)
3. Add to PATH or update script with tesseract path:
```python
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get update
sudo apt-get install tesseract-ocr
sudo apt-get install libtesseract-dev
```

**macOS:**
```bash
brew install tesseract
```

#### Poppler (for pdf2image)

**Windows:**
1. Download poppler from http://blog.alivate.com.au/poppler-windows/
2. Extract and add `bin` folder to PATH

**Linux:**
```bash
sudo apt-get install poppler-utils
```

**macOS:**
```bash
brew install poppler
```

### 3. Verify Installation

Run the script without arguments to verify all dependencies:
```bash
python grade_answer_sheet.py
```

Should show dependency check results:
```
✓ OpenCV version: 4.10.0
✓ Pillow version: 10.4.0
✓ NumPy version: 1.26.4
✓ PyTesseract version: 0.3.13
✓ pdf2image available
```

## Usage

1. Place your answer sheet PDF in the `pdf_directory` folder
2. Update the answer key in the script if needed
3. Run the grader:
```bash
python grade_answer_sheet.py
```

## Answer Key Configuration

Modify the `answer_key` dictionary in the script:

```python
self.answer_key = {
    1: 'A', 2: 'B', 3: 'C', 4: 'D', 5: 'A',
    # Add more questions as needed
}
```

## Output

The script generates:
- Console output with detailed results
- `grading_results.json`: JSON file with complete results
- `debug_bubbles.jpg`: Image showing detected bubbles

## Version Compatibility

### Tested Versions
- **Python 3.12.9**: ✅ Fully supported
- **Python 3.11.x**: ✅ Fully supported  
- **Python 3.10.x**: ✅ Supported
- **Python 3.9.x**: ✅ Supported
- **Python 3.8.x**: ✅ Minimum supported

### Package Versions
- **OpenCV 4.10.x**: Latest stable with Python 3.12 support
- **NumPy 1.26.x**: Optimized for Python 3.12
- **Pillow 10.4.x**: Latest with security fixes
- **PyTesseract 0.3.13**: Latest stable version
- **pdf2image 1.17.x**: Latest with improved error handling

## Troubleshooting

### Common Issues

1. **"No bubbles detected!"**
   - Check debug image to see what was detected
   - Adjust area and circularity parameters
   - Ensure PDF quality is good (300 DPI recommended)

2. **"ImportError: No module named 'cv2'"**
   - Install OpenCV: `pip install opencv-python==4.10.0.84`

3. **Tesseract not found**
   - Verify Tesseract installation
   - Update tesseract path in script
   - Add Tesseract to system PATH

4. **PDF conversion fails**
   - Install poppler utilities
   - Check PDF file permissions
   - Verify PDF is not corrupted

5. **Memory issues with large PDFs**
   - Reduce DPI in `pdf_to_images()` method
   - Process pages individually
   - Close unused image objects

### Performance Tips

- Use DPI 300 for good quality vs. speed balance
- Close large image objects after processing
- Consider processing multiple pages in batches
- Use SSD storage for temporary files

## Sample Output

```
Processing answer sheet: pdf_directory/Test.pdf
✓ OpenCV version: 4.10.0
✓ Pillow version: 10.4.0
✓ NumPy version: 1.26.4
✓ PyTesseract version: 0.3.13
✓ pdf2image available

Successfully converted PDF to 1 images
Extracted - Name: John Mathew Parocha, ID: 2024-05529-CM-0
Detected 80 potential bubbles
Organized bubbles into 20 questions
Q1: A selected (fill: 0.85)
Q2: B selected (fill: 0.72)
...

==================================================
ANSWER SHEET GRADING RESULTS
==================================================
Student Name: John Mathew Parocha
Student ID: 2024-05529-CM-0
Score: 85.0% (17/20)

DETAILED RESULTS:
--------------------------------------------------
Q 1: A          | Correct: A | ✓
Q 2: B          | Correct: B | ✓
Q 3: A          | Correct: C | ✗
...
==================================================

Results saved to grading_results.json
```
