# Setup Guide
1. Install Python.
2. Extract ZIP and open the folder in VS Code.
3. `py -3.13 -m venv .venv`
4. `.\.venv\Scripts\Activate.ps1`
5. `pip install -r requirements.txt`
6. `Copy-Item .env.example .env`
7. `python manage.py migrate`
8. `python manage.py createsuperuser`
9. `python manage.py runserver`
10. Visit `http://127.0.0.1:8000/` and `/admin/`.
11. Optional: `python manage.py load_demo_data`.
12. In Admin configure Website Settings, Admission Settings and Statistics, then add verified courses/universities and approved content.
