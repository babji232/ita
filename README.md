# ITA Associates - Data Engineer Assessment (Django + MySQL)

## 1. Setup (one time)
```bash
python -m venv venv
venv\Scripts\activate          # Windows   (Linux/Mac: source venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env         # Linux/Mac: cp .env.example .env   -> then edit DB password etc.
```
(`mysqlclient` on Windows may need a wheel; alternative: `pip install pymysql` and add
`import pymysql; pymysql.install_as_MySQLdb()` at the top of `manage.py`.)

## 2. MySQL database
```bash
mysql -u root -p < create_database.sql
python manage.py makemigrations exam
python manage.py migrate
```

## 3. Load questions and create admin
```bash
python manage.py import_questions            # loads data/questions.csv (600 questions)
python manage.py create_admin admin@itaassociates.co.uk "StrongPass@123"
python manage.py runserver
```
Open http://127.0.0.1:8000/

## 4. Email
Leave EMAIL_HOST_USER empty in `.env` -> OTP and reports print in the terminal (dev).
For Gmail: set EMAIL_HOST_USER and an App Password in EMAIL_HOST_PASSWORD.
Retry failed report emails: `python manage.py retry_reports` (cron) or Admin > Reports > Retry.

## Pages
Home | Student Register | Student Login | Admin Login | Student dashboard | Exam | Result |
Admin: Dashboard, Candidates (roll number list/edit), Results (filter + CSV/Excel export),
Questions (add/edit/archive/CSV import), Reports, Settings, Audit.
Django's built-in admin is at /django-admin/.
