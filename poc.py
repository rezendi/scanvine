import django, os
from django.conf import settings
if not settings.configured:
    settings.configure(DEBUG=True)
    settings.BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    settings.INSTALLED_APPS = [ 'main.apps.MainConfig', 'django_celery_results']
    settings.DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': os.path.join(settings.BASE_DIR, 'db.sqlite3'),
        }
    }
    settings.CELERY_RESULT_BACKEND = 'django-db'
    django.setup()

from main.models import *
from main import tasks

# result = tasks.update_sharers_list.delay()
# output = result.wait(timeout=None, interval=0.5)

# result = tasks.get_poc_sharers_list.delay()
# output = result.wait(timeout=None, interval=0.5)

# result = tasks.fetch_shares.delay()
# output = result.wait(timeout=None, interval=0.5)

# result = tasks.associate_articles.delay()
# output = result.wait(timeout=None, interval=0.5)

# result = tasks.associate_authors.delay()
# output = result.wait(timeout=None, interval=0.5)

if False:
    tasks.analyze_sentiment.delay()
    output = result.wait(timeout=None, interval=0.5)

result = tasks.allocate_credibility.delay()
output = result.wait(timeout=None, interval=0.5)

