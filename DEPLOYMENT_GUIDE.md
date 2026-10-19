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
- `MEDIA_ROOT`: for Django's `django.core.files.storage.FileSystemStorage`, an explicit absolute directory
- `CERTIFICATE_STORAGE_ROOT`: an absolute, durable private directory outside `MEDIA_ROOT`

### Render Free Web Service (no Persistent Disk)

The project uses PostgreSQL through `DATABASE_URL`; do not change this to SQLite on Render. Testimonial photos are optional, but approved course certificates must be retained.

For a Free Web Service, set these Render environment variables:

```text
MEDIA_STORAGE_BACKEND=django.core.files.storage.FileSystemStorage
MEDIA_STORAGE_OPTIONS={}
MEDIA_ROOT=/tmp/rajvans-media
```

`MEDIA_ROOT` must be explicitly set to an absolute path. `/tmp/rajvans-media` is writable without a paid disk, but Render's service filesystem is ephemeral: uploaded testimonial photos can disappear on restart, redeploy, or instance replacement and are not shared between instances. Do not treat this as durable storage or use it for files that must be retained. The current project does not include an S3-compatible backend or `django-storages`; no external object-storage credentials are assumed or supplied.

Certificate PDFs use a separate private filesystem storage, not `MEDIA_ROOT` or the default public media storage. Production must set `CERTIFICATE_STORAGE_ROOT` to an absolute, writable, durable directory outside `MEDIA_ROOT`. The setting is required when `DEBUG=False`; a deployment without persistent private storage must not enable certificate approvals. Certificate downloads are served only by authenticated application views, and the private directory must not be exposed by the web server or a static/media file server.

The media URL route is enabled only with `DEBUG=True`. Therefore, on production Render, testimonial photos stored in the ephemeral directory are not served by the app's current URL configuration. Do not rely on testimonial photo uploads/display on the Free setup; omit photos until durable object storage or a separately configured media-serving solution is adopted. This does not affect site pages, enquiries, franchise operations, student records, authentication, or Django Admin.

For deployments with durable storage, attach a Render Persistent Disk (paid plan), use sibling paths such as `MEDIA_ROOT=/var/data/public-media` and `CERTIFICATE_STORAGE_ROOT=/var/data/private-certificates`, and keep the private directory unserved. Set the same `MEDIA_STORAGE_BACKEND` and `MEDIA_STORAGE_OPTIONS` values above. If backend options include `location`, it must match `MEDIA_ROOT`. Production settings reject FileSystemStorage when `MEDIA_ROOT` is absent or not absolute; they do not silently fall back to a project-directory media folder.

Access to Django Admin is restricted to active superusers; `is_staff=True` by itself does not grant access. Existing franchise-account flags are not changed automatically. Before deployment, review franchise-linked accounts in the target database and correct only confirmed misconfigured accounts, preserving legitimate superuser accounts.

If TLS terminates at a trusted reverse proxy, set `USE_X_FORWARDED_PROTO=True` only when the application is reachable exclusively through a proxy that overwrites `X-Forwarded-Proto`. Configure the proxy to serve HTTPS and forward the canonical host. Test redirects before enabling HSTS for the production domain.

## Deployment and operations

Run `python manage.py migrate` and `python manage.py collectstatic --noinput` as deployment steps. `collectstatic` writes static assets to `STATIC_ROOT` and uses Django 5.2's `STORAGES["staticfiles"]` setting with `whitenoise.storage.CompressedManifestStaticFilesStorage`; it is independent of `MEDIA_ROOT` and requires no Persistent Disk. Serve `config.wsgi:application` with a production WSGI server. Production media URLs must resolve through a deliberately configured storage backend/media server; this project only adds Django's development media route when `DEBUG=True`. Back up `CERTIFICATE_STORAGE_ROOT` together with the database so approved certificate records remain downloadable after recovery.

For certificate review, a superuser opens **Admin → Franchise → Certificate requests**, records the eligibility evidence source and checks **Eligibility verified**, saves the record, then selects the pending request and runs **Approve selected verified certificate requests**. Approval fails unless both the verification flag and evidence note are present. Use the reject action for pending requests; use the revoke action to invalidate an issued certificate. Approved PDFs are downloaded through the protected admin or franchise portal view, not from a media URL.

Set up monitored database and media backups, test restoration, configure application error logging/alerts, verify outbound email delivery and recovery links, and remove all SAMPLE DATA before launch. Confirm client-approved contact details, university affiliations, fees, testimonials, and legal text before publishing.
