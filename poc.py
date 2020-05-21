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
    if 'SCANVINE_ENV' in os.environ:
        print('environ %s' % os.environ['SCANVINE_ENV'])
        if os.environ['SCANVINE_ENV']=='production':
            raise Exception("Running POC in production!")
            settings.DATABASES = {
                'default': {
                    'ENGINE':   'django.db.backends.postgresql_psycopg2',
                    'NAME':     os.environ['POSTGRES_DB'],
                    'USER':     os.environ['POSTGRES_USER'],
                    'PASSWORD': os.environ['POSTGRES_PASSWORD'],
                    'HOST':     os.environ['POSTGRES_HOST'],
                    'PORT':     os.environ['POSTGRES_PORT'],
                    'OPTIONS': {'sslmode': os.environ['POSTGRES_SSL_MODE']},
                }
            }
        else:
            settings.DATABASES = {
                'default': {
                    'ENGINE':   'django.db.backends.postgresql_psycopg2',
                    'NAME':     'postgres',
                    'USER':     'postgres',
                    'PASSWORD': 'mysecretpassword',
                    'HOST':     'localhost',
                    'PORT':     '5432',
                }
            }

    django.setup()
    celery = Celery('scanvine', backend='rpc://')

# Launch Twitter API
import twitter
api = twitter.Api(consumer_key=os.getenv('TWITTER_API_KEY', ''),
                  consumer_secret=os.getenv('TWITTER_API_SECRET', ''),
                  access_token_key=os.getenv('TWITTER_TOKEN_KEY', ''),
                  access_token_secret=os.getenv('TWITTER_TOKEN_SECRET', ''),
                  tweet_mode='extended')
#                 sleep_on_rate_limit=True)

from main import tasks

# actual code

from django.utils import timezone
print("tz %s" % timezone.now().microsecond)
