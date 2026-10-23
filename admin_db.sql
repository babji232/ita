-- =====================================================================
-- ITA Assessment : ADMIN DATABASE FILE  (MySQL)
-- Run AFTER:  python manage.py migrate      (creates table auth_user)
-- Use:        USE ita_assessment;   (or your DB_NAME from .env)
-- =====================================================================
-- Admins live in table  auth_user  with  is_staff = 1.
-- The "Add Admin" page in the admin panel writes to this same table,
-- and Admin Login reads from it, so both stay in sync.
-- =====================================================================

USE ita_assessment;

-- 1) Separate admin table view: shows ONLY admins (like a dedicated admin table)
CREATE OR REPLACE VIEW admin_users AS
SELECT id,
       first_name  AS name,
       email,
       IF(is_active = 1, 'Active', 'Disabled') AS status,
       IF(is_superuser = 1, 'Super admin', 'Admin') AS role,
       last_login,
       date_joined AS created_at
FROM   auth_user
WHERE  is_staff = 1;

-- 2) See all admins
SELECT * FROM admin_users ORDER BY id;

-- 3) Add an admin directly from SQL (optional).
--    The password below is a Django hash of:  ChangeMe#12345   -> change it after first login.
--    Login uses the email, so username and email must be the same value.
-- INSERT INTO auth_user
--   (password, is_superuser, username, first_name, last_name, email, is_staff, is_active, date_joined)
-- VALUES
--   ('pbkdf2_sha256$1500000$r0flGDBo8C8J3wQ2EjfVeI$up4v72RaGBkLlbJSkQUyKhHjlOS9qLdLd7xq12LiCgw=',
--    0, 'newadmin@gmail.com', 'New Admin', '', 'newadmin@gmail.com', 1, 1, NOW(6));

-- 4) Edit an admin (name / disable / enable)
-- UPDATE auth_user SET first_name = 'New Name'  WHERE email = 'newadmin@gmail.com' AND is_staff = 1;
-- UPDATE auth_user SET is_active = 0            WHERE email = 'newadmin@gmail.com' AND is_staff = 1;
-- UPDATE auth_user SET is_active = 1            WHERE email = 'newadmin@gmail.com' AND is_staff = 1;

-- 5) Delete an admin (keep at least one active admin!)
-- DELETE FROM auth_user WHERE email = 'newadmin@gmail.com' AND is_staff = 1;

-- NOTE: to set/change a password, do NOT type plain text in SQL. Use the Edit page in the
-- admin panel, or run:   python manage.py create_admin email@gmail.com NewPassword#123
