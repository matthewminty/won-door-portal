# Won-Door Portal

Internal CRM and job management system for Won-Door Australia & New Zealand.

## Quick Start (Railway Deployment)

### 1. Push to GitHub

Create a new repository on GitHub (e.g. `won-door-portal`), then:

```bash
cd won-door-portal
git init
git add .
git commit -m "Phase 1: scaffold, auth, region system"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/won-door-portal.git
git push -u origin main
```

### 2. Set up Railway

1. Go to [railway.com](https://railway.com) and log in
2. Click **"New Project"** → **"Deploy from GitHub Repo"**
3. Select your `won-door-portal` repository
4. Railway will detect it's a Python app and start building

### 3. Add a Postgres Database

1. In your Railway project, click **"+ New"** → **"Database"** → **"PostgreSQL"**
2. Railway automatically sets the `DATABASE_URL` environment variable

### 4. Set Environment Variables

In Railway, go to your web service → **Variables** tab. Add:

| Variable | Value |
|----------|-------|
| `SECRET_KEY` | (generate a random string — e.g. `python -c "import secrets; print(secrets.token_hex(32))"`) |
| `FLASK_APP` | `wsgi.py` |

The `DATABASE_URL` is already set by the Postgres plugin.

### 5. Deploy

Railway will auto-deploy when you push to `main`. The start command in `railway.toml` will:
1. Run database migrations (`flask db upgrade`)
2. Start Gunicorn

### 6. First Login

- **URL:** Your Railway-provided URL (e.g. `won-door-portal.up.railway.app`)
- Log in with the credentials set up via `flask create-admin`.

## Local Development

```bash
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
export FLASK_APP=wsgi.py
export DATABASE_URL=sqlite:///portal.db
flask db upgrade
flask run
```

## Project Structure

```
portal/
├── app/
│   ├── __init__.py          # App factory
│   ├── models.py            # All database models
│   ├── cli.py               # CLI commands (seed, create-admin)
│   ├── blueprints/
│   │   ├── auth/            # Login, logout, profile
│   │   ├── dashboard/       # Landing page
│   │   ├── pipeline/        # Lead tracking (Phase 2)
│   │   ├── jobs/            # Job management (Phase 4)
│   │   └── contacts/        # Address book (Phase 5)
│   ├── static/
│   │   ├── css/portal.css   # Full design system
│   │   └── js/portal.js     # UI interactions
│   └── templates/
│       ├── layouts/base.html # App shell
│       ├── auth/            # Login, profile pages
│       ├── dashboard/       # Dashboard page
│       ├── pipeline/        # Pipeline pages
│       ├── jobs/            # Job pages
│       └── contacts/        # Contact pages
├── migrations/              # Alembic migrations
├── wsgi.py                  # WSGI entry point
├── requirements.txt         # Python dependencies
├── Procfile                 # Process definition
├── railway.toml             # Railway config
└── .python-version          # Python 3.12
```
