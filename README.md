# student-interview-tracker

Django app where admins manage students and groups, and students track interviews, rounds and outcomes.

## Run locally

1. Create a virtualenv and install dependencies:
   ```bash
   python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. Create the PostgreSQL database (`createdb interview_db`), then configure the environment:
   ```bash
   cp .env.example .env     # edit SECRET_KEY and DATABASE_URL
   ```
   `.env` is loaded automatically. If `DATABASE_URL` is unset, SQLite is used as a fallback.
3. `python manage.py migrate`
4. `python manage.py seed_demo_data`
5. `python manage.py runserver`
6. `python manage.py test`

Demo logins (password `demo12345`): `admin`, `alice`, `bob`, `carol`.

## Notes

- Roles: `User.is_admin` / `User.is_student`. Login redirects to `/admin/dashboard/` or `/student/dashboard/`. Django's own admin lives at `/django-admin/`.
- Admins only see and manage groups they created. Students only see and edit their own interviews (others return 404).
- Admins can browse student profiles for their own groups. Removing a student from a group deletes that group’s interviews and rounds for the student while preserving interviews in other groups.
- Interview records can include an HR contact name, phone number, and email address.
- Rounds are added via AJAX (CSRF token sent in the `X-CSRFToken` header). The final result can only be set once all rounds are cleared or rejected; adding a new round reopens the interview.
- The responsive interface is served from `static/css/app.css` with lightweight interactions in `static/js/app.js`; no frontend build step is required. Google Fonts are optional, with system font fallbacks when they are unavailable.
- `python manage.py createsuperuser` creates a user that is automatically flagged `is_admin`.
