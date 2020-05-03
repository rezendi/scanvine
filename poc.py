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

from main.models import *
import twitter # https://raw.githubusercontent.com/bear/python-twitter/master/twitter/api.py

api = twitter.Api(consumer_key=os.getenv('TWITTER_API_KEY', ''),
                  consumer_secret=os.getenv('TWITTER_API_SECRET', ''),
                  access_token_key=os.getenv('TWITTER_TOKEN_KEY', ''),
                  access_token_secret=os.getenv('TWITTER_TOKEN_SECRET', ''))

verified_ids_cursor = -1
(verified_ids_cursor, previous_cusor, verified_ids) = api.GetFriendIDs(screen_name='verified', count=200, cursor = verified_ids_cursor)
print ("verified IDs %s" % verified_ids)

from main import tasks

# result = tasks.get_potential_sharer_ids.delay()
# output = result.wait(timeout=None, interval=0.5)

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

