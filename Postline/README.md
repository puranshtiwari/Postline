# Postline

Postline implements the **AI-Powered Social Media Scheduler** Full Stack Lab synopsis with React, Django, Django REST Framework and SQLite. Users can sign up, manage connected accounts, compose posts, ask Gemini for writing assistance, and queue posts for automatic publishing.

## Run locally

Requirements: Python 3.12 or newer and Node.js 22.12 or newer. Open a terminal in this folder. The commands below use Windows PowerShell.

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
npm.cmd --prefix frontend ci
npm.cmd --prefix frontend run build
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver
```

In a second terminal in the same folder, start the local fallback scheduler:

```powershell
.\.venv\Scripts\python.exe manage.py run_scheduler
```

For Celery Beat and a Celery worker on Windows, install and start Redis, then use three terminals:

```powershell
redis-server
\.venv\Scripts\celery.exe -A scheduler worker --loglevel=INFO --pool=solo
\.venv\Scripts\celery.exe -A scheduler beat --loglevel=INFO
```

Beat queues a due-post scan every 30 seconds. The worker and the fallback command both use the same database claim, so only the process that changes a schedule from `scheduled` to `publishing` may publish it.

Open http://127.0.0.1:8000 and create an account. On macOS or Linux, use `python3` to create the virtual environment, `./.venv/bin/python` to run Django commands, and `npm` in place of `npm.cmd`.

## Try the demo

1. Open **Accounts**, choose Facebook and select **Add demo Facebook account**.
2. Open **Composer**, choose the demo account, then write a caption or generate a demo suggestion. Select **Use as caption** and edit it before saving.
3. Choose a time a minute or two ahead and select **Schedule post**. The time picker uses the browser's timezone. Django stores timestamps in UTC.
4. Keep the worker running. The **Overview** refreshes every 12 seconds and shows the post as **Published** once the worker simulates delivery. A demo account never contacts Meta.
5. Try saving a draft, editing a scheduled post, or cancelling it from the dashboard.

The fallback command can run one scan for verification:

```powershell
\.venv\Scripts\python.exe manage.py run_scheduler --once
```

## Configure live integrations

Copy `.env.example` to `.env`. Keep the file and its secrets outside version control. Restart the web and worker processes after changing configuration.

- **Gemini** — set `GEMINI_API_KEY` and, if needed, `GEMINI_MODEL` to a model available to your Google AI project. The API handles captions, revisions, hashtags and ideas. `GEMINI_IMAGE_MODEL` controls image generation and defaults to `gemini-3.1-flash-image`. In demo mode without a key, the assistant uses labelled sample text and image placeholders. See the [Gemini text generation guide](https://ai.google.dev/gemini-api/docs/text-generation) and [image generation guide](https://ai.google.dev/gemini-api/docs/image-generation).
- **Meta** — generate an encryption key with `.\.venv\Scripts\python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` and set `TOKEN_KEY`. Keep a backup of this key to preserve access to saved tokens. Obtain a **Facebook Page access token** with `pages_show_list`, `pages_read_engagement`, and `pages_manage_posts` for the Page you manage. For Instagram via Facebook Login, use a linked professional Instagram profile and the needed Instagram scopes, including `instagram_basic` and `instagram_content_publish`. Meta app access, account permissions, and potential app review apply. Choose the platform in **Accounts** and enter the corresponding ID and Page token. Reconnecting the same ID updates the stored token. See the [Facebook Page Feed reference](https://developers.facebook.com/docs/graph-api/reference/page/feed/) and [Instagram content publishing guide](https://developers.facebook.com/docs/instagram-platform/instagram-api-with-facebook-login/content-publishing/).
- **Publishing media** — Facebook supports text and a single public HTTPS image URL. Instagram requires a publicly accessible JPEG URL. URLs must remain accessible to Meta at publish time.
- **Local image uploads** — the composer can upload a JPEG or PNG to Django's `media/` folder. Set `PUBLIC_MEDIA_BASE_URL` to the public HTTPS address of this server, such as `https://your-domain.example`, so Meta can fetch the saved image. A `localhost` URL works only for local previews and cannot be fetched by Instagram or Facebook.
- **Cloudflare image generation** — set `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN`, and `CLOUDFLARE_IMAGE_MODEL=@cf/black-forest-labs/flux-1-schnell`. Postline generates images with Cloudflare Workers AI, decodes the result, and saves it locally under `media/generated_images/`. The existing `Post.media` field stores the generated path. Create a token with Workers AI Run permission and keep it only in `.env`; `PUBLIC_MEDIA_BASE_URL` is still needed when Meta must fetch images from a deployed server. See the [Workers AI image model](https://developers.cloudflare.com/workers-ai/models/flux-1-schnell/).
- **AI images** — choose **Generate image** in the Composer assistant, enter a prompt, preview the result, and select **Use image** before scheduling. Cloudflare Workers AI is used when configured; in demo mode without an API key, a labelled placeholder is generated.
- Set `DEMO_MODE=0` to disable demo accounts and mock suggestions. Keep demo accounts out of live schedules. This project is configured for local development.

## Deploy to Railway with SQLite

The repository includes [railway.json](./railway.json), [Procfile](./Procfile), and [start_railway.sh](./start_railway.sh). Use one Railway application service for this SQLite deployment. Its `/data` volume must be visible to Django, Celery, and Beat, so the included start script runs all three processes in the same container. Add Redis as a separate Railway service.

```text
Build command: npm ci --prefix frontend && npm run build --prefix frontend && pip install -r requirements.txt && python manage.py collectstatic --noinput
Start command: bash start_railway.sh
```

In Railway, deploy the GitHub repository, add a Redis service, and reference its Redis connection URL in `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND`. Railway's Redis service exposes connection variables for other services; use the URL variable provided by the Redis service rather than copying a credential into source control. Add one persistent volume mounted at `/data` to the single application service. Railway volumes cannot be shared between services, which is why the web process, worker, and Beat run together in the same application container.

Set these variable names manually in Railway. Never commit their values:

```text
DJANGO_SECRET_KEY
DJANGO_DEBUG=0
DJANGO_ALLOWED_HOSTS
DJANGO_CSRF_TRUSTED_ORIGINS
DJANGO_SECURE_SSL_REDIRECT=1
DJANGO_HSTS_SECONDS=31536000
DEMO_MODE=0
DB_PATH=/data/db.sqlite3
MEDIA_ROOT=/data/media
PUBLIC_MEDIA_BASE_URL
CELERY_BROKER_URL
CELERY_RESULT_BACKEND
TOKEN_KEY
META_GRAPH_VERSION
GEMINI_API_KEY
GEMINI_MODEL
GEMINI_IMAGE_MODEL
CLOUDFLARE_ACCOUNT_ID
CLOUDFLARE_API_TOKEN
CLOUDFLARE_IMAGE_MODEL
```

Use your Railway public domain in `DJANGO_ALLOWED_HOSTS`, for example `your-app.up.railway.app`, in `DJANGO_CSRF_TRUSTED_ORIGINS` with the `https://` scheme, and in `PUBLIC_MEDIA_BASE_URL`. `PUBLIC_MEDIA_BASE_URL` must be the public HTTPS origin only, without `/media/` at the end. A generated or uploaded image is saved to `/data/media/`, and Postline publishes a URL such as `https://your-app.up.railway.app/media/generated_images/generated-...jpg`. Only the `post-media/` and `generated_images/` media paths are publicly served; other media paths return 404.

The application start script runs migrations, Gunicorn, one Celery worker, and Beat. Beat queues `publishing.tasks.scan_due_posts` every 30 seconds, and the worker claims each due schedule atomically in SQLite before contacting Meta. Keep the worker at `--concurrency=1` for this SQLite deployment. Do not run the local `run_scheduler` command at the same time as Beat in production.

### Migrate the local database and media safely

Stop local Django, the worker, and Beat first. From the project folder, create an archive containing only the database and media directory; do not include `.env`:

```powershell
tar -czf postline-data.tgz db.sqlite3 media
```

After the Railway web service is deployed and its volume is mounted, upload the archive with the Railway CLI:

```powershell
railway login
railway link
railway volume files upload .\postline-data.tgz /postline-data.tgz
railway ssh --service web
```

Inside the Railway shell, extract it into the mounted volume and remove the temporary archive:

```bash
tar -xzf /data/postline-data.tgz -C /data
rm /data/postline-data.tgz
python manage.py migrate
exit
```

If the local database or media files are not needed, skip this migration and let Django create a new empty `/data/db.sqlite3`. Back up the Railway volume before replacing existing files. Railway provides volume file upload/download and volume backups; confirm the active service and volume before any upload or replacement.

Railway's volume is mounted when the service starts, so the database and media must be placed on `/data`, not only generated during the build. See Railway's [volume documentation](https://docs.railway.com/volumes), [Redis documentation](https://docs.railway.com/databases/redis), and [start command documentation](https://docs.railway.com/deployments/start-command).

## Project structure

- `frontend/` — React sign-in, dashboard, composer, assistant, and account settings.
- `scheduler/` — Django settings and API routing.
- `publishing/` — models, REST validation, provider integrations, migrations, and scheduler command.

Django uses session cookies and CSRF protection. Each user sees their own posts and accounts. The worker claims due schedules before contacting Meta. A failed or interrupted publish shows an error in the dashboard. If provider delivery is uncertain, verify the destination before rescheduling.

