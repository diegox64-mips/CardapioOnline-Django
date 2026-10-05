#!/bin/sh
set -e

python manage.py migrate --noinput

if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
    python manage.py shell -c "
import os
from django.contrib.auth import get_user_model
User = get_user_model()
username = os.environ.get('DJANGO_SUPERUSER_USERNAME')
if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username, os.environ.get('DJANGO_SUPERUSER_EMAIL', ''), os.environ.get('DJANGO_SUPERUSER_PASSWORD'))
    print('Superuser created')
" || true
fi

exec "$@"
