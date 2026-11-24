#!/usr/bin/env bash
set -euo pipefail

python manage.py migrate

gunicorn scheduler.wsgi:application --bind "0.0.0.0:${PORT}" --workers 2 --timeout 120 &
web_pid=$!

celery -A scheduler worker --loglevel=INFO --pool=solo --concurrency=1 &
worker_pid=$!

celery -A scheduler beat --loglevel=INFO &
beat_pid=$!

shutdown() {
  kill "$web_pid" "$worker_pid" "$beat_pid" 2>/dev/null || true
  wait || true
}

trap shutdown TERM INT EXIT
wait -n "$web_pid" "$worker_pid" "$beat_pid"
exit $?
