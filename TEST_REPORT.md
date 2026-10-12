# Testing Report

## Verification completed

- `.\.venv\Scripts\python.exe manage.py test` — **PASS**, all 45 tests passed, including franchise login navigation, authenticated-superuser behavior, role-safe `next` redirects, admin approval, account activation, superuser-only Admin access, inactive accounts, and owner/staff tenant isolation. Django created and destroyed an isolated test database; the configured application database was not used.
- `.\.venv\Scripts\python.exe manage.py check` — **PASS**, no issues reported.
- `.\.venv\Scripts\python.exe manage.py makemigrations --check` — **PASS**, no changes detected.
- `git diff --check` — **PASS**, no whitespace errors.

The test runner applied the project migrations to its temporary test database. No migration was created or applied to the existing application database during this work.

## Production verification still required

Production readiness depends on client/hosting configuration and cannot be verified locally without the corresponding services and approved content:

- Set production `SECRET_KEY`, `DEBUG=False`, `ALLOWED_HOSTS`, and `CSRF_TRUSTED_ORIGINS`.
- Provision and test PostgreSQL, SMTP delivery, durable media storage, HTTPS/reverse-proxy settings, and backups.
- Run deployment migrations and `collectstatic` in the intended hosting environment.
- Verify production email delivery and account-activation/password-reset links.
- Review client-approved contact details, affiliations, fees, testimonials, legal text, and existing uploaded media.
- Perform browser-based visual checks at desktop, tablet, and mobile sizes.
