# CheckMate - Answer Key Management System

A Django-based web application for creating, managing, and processing answer keys for multiple choice and true/false tests.

## Features

### ✨ Core Functionality
- **Manual Answer Key Creation** - Create answer keys by entering answers manually
- **Image Upload Processing** - Upload answer key images and extract answers automatically
- **Multiple Test Types** - Support for Multiple Choice (A-D, A-E) and True/False questions
- **Course Management** - Organize tests by courses with academic year and semester tracking
- **Student Management** - Manage student records and enrollments

### 📊 Answer Key Management
- **Print Options** - Print answer keys or blank answer sheets
- **Multiple Formats** - Export as CSV or print-ready formats
- **Review System** - Review and correct extracted answers before saving
- **Confidence Scoring** - See confidence levels for automatically extracted answers

### 🎨 User Interface
- **Modern Design** - Clean, responsive Bootstrap-based interface
- **Easy Navigation** - Intuitive tabbed interface for different creation methods
- **Real-time Preview** - Preview images before processing
- **Status Tracking** - Track draft vs active answer keys

## Requirements

- Python 3.8+
- Django 4.2+
- Modern web browser

## Installation

### 1. Clone the Repository
```bash
git clone <repository-url>
cd Checkmate
```

### 2. Create Virtual Environment
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Database Setup
```bash
python manage.py makemigrations
python manage.py migrate
```

### 5. Create Superuser
```bash
python manage.py createsuperuser
```

### 6. Run Development Server
```bash
python manage.py runserver
```

Visit `http://127.0.0.1:8000` to access the application.

## Usage

### Creating Answer Keys

#### Manual Entry
1. Go to **Answer Keys** page
2. Select **Manual Entry** tab
3. Fill in test details (name, course, type, question count)
4. Click **Create Answer Key**
5. Enter answers for each question
6. Save the answer key

#### Image Upload
1. Go to **Answer Keys** page
2. Select **Upload Image** tab
3. Fill in test details
4. Upload a clear image of your answer key
5. Choose processing options
6. Review extracted answers
7. Make corrections if needed and save

### Managing Courses
1. Go to **Courses** page
2. Add new courses with code, name, and academic details
3. Edit or delete existing courses
4. View course statistics

### Managing Students
1. Go to **Students** page
2. Add student records with ID, name, and course enrollment
3. Import students from CSV files
4. Edit or remove student records

### Printing Answer Keys
- **Answer Key Mode** - Shows filled bubbles for correct answers (for instructors)
- **Blank Sheet Mode** - Shows empty bubbles for all options (for students)

## Batch Processing

To process all PDFs in a directory and output results as JSON, run:

```bash
python scripts/pdf_processor_main_prototype.py d:\YUKI\ADET\Checkmate\pdf_directory
```

You can also specify multiple files or directories:

```bash
python scripts/pdf_processor_main_prototype.py file1.pdf file2.pdf dir1 dir2
```

The output will be a JSON array with student info and answers for each PDF.

## Project Structure

```
Checkmate/
├── main/                   # Main Django app
│   ├── models.py          # Database models
│   ├── views.py           # View functions
│   ├── forms.py           # Django forms
│   ├── urls.py            # URL patterns
│   └── services/          # Business logic services
├── templates/             # HTML templates
├── static/               # CSS, JS, images
├── media/                # Uploaded files
├── checkmate/            # Django project settings
└── manage.py             # Django management script
```

## Configuration

### Settings
Main configuration is in `checkmate/settings.py`:
- Database settings
- Media file handling
- Static file configuration
- Security settings

### Environment Variables
Create a `.env` file for sensitive settings:
```
DEBUG=True
SECRET_KEY=your-secret-key-here
DATABASE_URL=your-database-url
```

## Troubleshooting

### Common Issues

#### Import Errors
If you encounter module import errors:
```bash
pip install --upgrade pip
pip install -r requirements.txt --force-reinstall
```

#### Database Issues
Reset database:
```bash
python manage.py flush
python manage.py makemigrations
python manage.py migrate
```

#### Image Processing Issues
The system uses basic image processing. For better accuracy, ensure:
- Clear, high-contrast images
- Properly filled bubbles
- Good lighting when taking photos

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is licensed under the MIT License.

## Support

For issues and questions:
- Check the troubleshooting section
- Review the Django documentation
- Create an issue in the repository

---

**CheckMate** - Making answer key management simple and efficient! 🎯