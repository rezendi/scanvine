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
    settings.INSTALLED_APPS = [
        'main.apps.MainConfig',
        'social_django',
        'django.contrib.auth',
        'django.contrib.contenttypes',
    ]
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
                    'PASSWORD': 'grapevine',
                    'HOST':     'localhost',
                    'PORT':     '5432',
                }
            }

    django.setup()
    celery = Celery('scanvine', backend='rpc://')

import dateparser
from main.metatasks import *
from main.tasks import clean_up_url

POC_TWEET_ID = '1274784880757538822'
MIN_RETWEETS = 10

def get_thread_for(twitter_id):
    t = api.GetStatus(twitter_id, include_entities=True)
    if not t:
        return None
    if t.retweet_count < MIN_RETWEETS:
        return None
    handle = t.user.screen_name
    term = "from:%s to:%s" % (handle, handle)
    since = dateparser.parse(t.created_at.rpartition(" ")[0])
    since_str = since.strftime('%Y-%m-%d')
    until = since + datetime.timedelta(days=1)
    until_str = until.strftime('%Y-%m-%d')
    sr = api.GetSearch(term=term, since=since_str, until=until_str, since_id=t.id, count=100, result_type="recent", lang='en', include_entities = True)
    # reverse search results
    # assemble list of tweets based on in_reply_to_status_id values
    # 3 tweets or more means a viable thread, for now
    return sr

t = api.GetStatus(POC_TWEET_ID, include_entities=True)
possibles = [clean_up_url(u.expanded_url) for u in t.urls]
possibles = [p.replace("https://mobile.twitter.com", "https://twitter.com") for p in possibles]
possibles = list(set(possibles))
print("possibles %s" % possibles)
if possibles and possibles[0].startswith("https://twitter.com/"):
    possible = possibles[0]
    print ("possible %s" % possible)
    existing = Article.objects.filter(url = possible)
    if existing:
        print("thread already found")
    id = possibles[0].rpartition("/")[2]
    # this will be a job, max every 10 s
    thread = get_thread_for(id)
    if thread:
        # create article, add that to metadata as 'sv_thread_list'
        print("got thread %s" % thread)

