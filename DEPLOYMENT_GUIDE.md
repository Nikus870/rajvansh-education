# Deployment Guide

## Required production configuration

Set these values through the hosting provider's secret/environment manager; do not commit production credentials:

- `DEBUG=False`
- `SECRET_KEY`: unique, high-entropy value
- `ALLOWED_HOSTS`: comma-separated production hostnames
- `CSRF_TRUSTED_ORIGINS`: comma-separated HTTPS origins, including scheme
- `DATABASE_URL`: PostgreSQL URL (`postgresql://user:password@host:port/database`)
- `SECURE_SSL_REDIRECT=True`
- `SESSION_COOKIE_SECURE=True`
- `CSRF_COOKIE_SECURE=True`
- `EMAIL_BACKEND`: a configured private backend; the default production backend is SMTP
- `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS` (or SSL), and a verified `DEFAULT_FROM_EMAIL`
- `MEDIA_STORAGE_BACKEND`: a durable Django storage backend, with provider options in `MEDIA_STORAGE_OPTIONS` as a JSON object

Production settings fail fast when the secret, host list, PostgreSQL URL, private email backend/sender, or durable media backend is not configured. The console email backend and local filesystem media storage are development-only.

Access to Django Admin is restricted to active superusers; `is_staff=True` by itself does not grant access. Existing franchise-account flags are not changed automatically. Before deployment, review franchise-linked accounts in the target database and correct only confirmed misconfigured accounts, preserving legitimate superuser accounts.

If TLS terminates at a trusted reverse proxy, set `USE_X_FORWARDED_PROTO=True` only when the application is reachable exclusively through a proxy that overwrites `X-Forwarded-Proto`. Configure the proxy to serve HTTPS and forward the canonical host. Test redirects before enabling HSTS for the production domain.

## Deployment and operations

Provision PostgreSQL and durable media storage, then run `python manage.py migrate` and `python manage.py collectstatic --noinput` as deployment steps. Serve `config.wsgi:application` with a production WSGI server. This repository intentionally serves media through Django only in `DEBUG` mode; production media URLs must resolve through the configured storage backend/web server.

Set up monitored database and media backups, test restoration, configure application error logging/alerts, verify outbound email delivery and recovery links, and remove all SAMPLE DATA before launch. Confirm client-approved contact details, university affiliations, fees, testimonials, and legal text before publishing.
