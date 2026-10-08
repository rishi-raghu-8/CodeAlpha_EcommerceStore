# Simple E-Commerce Store

A beginner-friendly full-stack e-commerce website built with Django, SQLite, HTML, CSS and JavaScript.

Built as a task for the **CodeAlpha** internship.

## Tech Stack
- Backend: Python, Django 5.2
- Database: SQLite
- Frontend: HTML, CSS, JavaScript (Django templates)
- Image uploads: Pillow

## Features
- Product listing
- Product details
- Shopping cart using Django sessions
- User registration, login and logout
- Checkout and order creation
- Order history
- Stock management
- Django admin panel
- Responsive frontend

## Setup

### Windows
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py seed_products
python manage.py runserver
```

Open http://127.0.0.1:8000/

Admin: http://127.0.0.1:8000/admin/

## Project Structure
```
manage.py
requirements.txt
ecommerce/   # project settings and root URLs
store/       # app: models, views, forms, admin, seed command
templates/store/
static/css, static/js
```

## Screenshots
Add screenshots of the home page, cart and order history here.

## Notes
This project uses SQLite and does not include real payment gateway integration.
