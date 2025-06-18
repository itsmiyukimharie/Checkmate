# Quick setup
git clone <repository-url>
cd Checkmate
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver