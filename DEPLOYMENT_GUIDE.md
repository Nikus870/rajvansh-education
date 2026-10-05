# Deployment Guide
Set `DEBUG=False`, a strong secret key, `ALLOWED_HOSTS`, HTTPS `CSRF_TRUSTED_ORIGINS`, `DATABASE_URL`, `SECURE_SSL_REDIRECT=True`, `SESSION_COOKIE_SECURE=True`, `CSRF_COOKIE_SECURE=True`.

Provision PostgreSQL and run `python manage.py migrate` and `python manage.py collectstatic --noinput`. Use `config.wsgi:application` with a production WSGI server. Keep media on persistent storage/object storage and back up database + media. Configure domain/DNS and HTTPS. Remove all SAMPLE DATA before launch.
