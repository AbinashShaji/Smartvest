## SmartVest Deployment Notes (Render)

### Why Gunicorn is required
Flask's built-in development server is for local debugging only. Render should run a production WSGI server (`gunicorn`) for stable process management and concurrency.

### Environment Variables
Set these in Render dashboard:

- `SECRET_KEY` (required)
- `SMARTVEST_DB_PATH` (recommended, e.g. `/opt/render/project/src/instance/smartvest.db`)
- `SMARTVEST_UPLOAD_DIR` (recommended, e.g. `/opt/render/project/src/uploads`)
- `SMARTVEST_ADMIN_USERNAME` (optional bootstrap)
- `SMARTVEST_ADMIN_EMAIL` (optional bootstrap)
- `SMARTVEST_ADMIN_PASSWORD` (optional bootstrap)
- `FLASK_ENV=production`

### Start Command
This repo includes a `Procfile`:

`web: gunicorn app:app`

### Important SQLite note
SQLite works for small workloads but does not scale for high write concurrency across multiple instances. Use a single instance and persistent disk, or migrate to PostgreSQL when scaling up.
