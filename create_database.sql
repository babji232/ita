-- Run once as MySQL root:  mysql -u root -p < create_database.sql
CREATE DATABASE IF NOT EXISTS ita_assessment CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'ita_user'@'localhost' IDENTIFIED BY 'ChangeMe@123';
GRANT ALL PRIVILEGES ON ita_assessment.* TO 'ita_user'@'localhost';
FLUSH PRIVILEGES;
-- Tables are created by Django:  python manage.py makemigrations exam && python manage.py migrate
