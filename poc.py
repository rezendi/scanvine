import django, os
from django.conf import settings
from celery import Celery

if not 'DJANGO_SECRET_KEY' in os.environ:
    from dotenv import load_dotenv
    project_folder = os.path.expanduser('~/dev/private/scanvine')
    load_dotenv(os.path.join(project_folder, '.env'))

if not settings.configured:
    settings.configure(DEBUG=True)
    settings.BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    settings.INSTALLED_APPS = [ 'main.apps.MainConfig']
    settings.DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': os.path.join(settings.BASE_DIR, 'db.sqlite3'),
        }
    }
    django.setup()
    celery = Celery('scanvine', backend='rpc://')

from main import tasks

#result = tasks.get_potential_sharers.delay()
#output = result.wait(timeout=None, interval=0.5)

tasks.promote_matching_sharers()
#tasks.fix_sharers()

# result = tasks.ingest_sharers.delay()
# output = result.wait(timeout=None, interval=0.5)

# result = tasks.fetch_shares.delay()
# output = result.wait(timeout=None, interval=0.5)

# result = tasks.associate_articles.delay()
# output = result.wait(timeout=None, interval=0.5)

# result = tasks.parse_unparsed_articles.delay()
# output = result.wait(timeout=None, interval=0.5)

# tasks.analyze_sentiment.delay()
# output = result.wait(timeout=None, interval=0.5)

# result = tasks.allocate_credibility.delay()
# output = result.wait(timeout=None, interval=0.5)

