# Rajvans Group of Educations

Production-style Django website for courses, universities, career consultation, student enquiries and franchise partners. No real client facts are fabricated.

## Quick start (Windows PowerShell)
```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```
Open `/` and `/admin/`. Optional demo data: `python manage.py load_demo_data`. Demo data is clearly labelled SAMPLE DATA and must be replaced before production.

## Apps
`core` global settings/admission/statistics; `courses` categories/courses/filtering; `universities` affiliations; `inquiries` enquiries/consultations/contact; `franchise` registration/auth/dashboard; `content` FAQs/testimonials/pages.

## Production
Use `DEBUG=False`, strong `SECRET_KEY`, correct `ALLOWED_HOSTS`, HTTPS/secure cookies, PostgreSQL through `DATABASE_URL`, `collectstatic`, durable media storage and regular backups.
