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
- `MEDIA_STORAGE_BACKEND`: a dotted Python path to an installed Django storage backend
- `MEDIA_STORAGE_OPTIONS`: a JSON object of options accepted by that backend
- `MEDIA_ROOT`: for Django's `django.core.files.storage.FileSystemStorage`, the absolute mount path of a Render Persistent Disk (for example, `/var/data`)

This project does not include an S3-compatible backend or `django-storages` dependency. The supported Render disk configuration uses Django's built-in `django.core.files.storage.FileSystemStorage` with `MEDIA_ROOT` explicitly set to the Persistent Disk mount path. Do not set `MEDIA_ROOT` to the service's ephemeral application directory. Production settings fail fast if filesystem media storage is selected without an explicit absolute `MEDIA_ROOT`; if backend options include `location`, it must match `MEDIA_ROOT`.

In the Render dashboard, open the web service's **Disks** settings and attach a Persistent Disk. Set its mount path (for example, `/var/data`), then set `MEDIA_ROOT` to that exact path. Set `MEDIA_STORAGE_BACKEND=django.core.files.storage.FileSystemStorage` and `MEDIA_STORAGE_OPTIONS={}` in the service environment. The disk must be attached to the web service that runs the application. For an alternative object-storage provider, install and configure that provider's Django storage backend explicitly; its dotted backend path and provider credentials/options must be configured in Render's environment manager.

Access to Django Admin is restricted to active superusers; `is_staff=True` by itself does not grant access. Existing franchise-account flags are not changed automatically. Before deployment, review franchise-linked accounts in the target database and correct only confirmed misconfigured accounts, preserving legitimate superuser accounts.

If TLS terminates at a trusted reverse proxy, set `USE_X_FORWARDED_PROTO=True` only when the application is reachable exclusively through a proxy that overwrites `X-Forwarded-Proto`. Configure the proxy to serve HTTPS and forward the canonical host. Test redirects before enabling HSTS for the production domain.

## Deployment and operations

Provision PostgreSQL and durable media storage, then run `python manage.py migrate` and `python manage.py collectstatic --noinput` as deployment steps. `collectstatic` writes static assets to `STATIC_ROOT` and uses `whitenoise.storage.CompressedManifestStaticFilesStorage`; it does not use `MEDIA_ROOT`. Serve `config.wsgi:application` with a production WSGI server. This repository intentionally serves media through Django only in `DEBUG` mode; production media URLs must resolve through the configured storage backend/web server.

Set up monitored database and media backups, test restoration, configure application error logging/alerts, verify outbound email delivery and recovery links, and remove all SAMPLE DATA before launch. Confirm client-approved contact details, university affiliations, fees, testimonials, and legal text before publishing.
