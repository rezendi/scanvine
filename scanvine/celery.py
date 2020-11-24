import os
from celery import Celery

# set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'scanvine.settings')

# set rate limit for tasks to avoid Twitter rate limiting

app = Celery('scanvine',
             broker = 'amqp://guest:guest@localhost:5672',
             backend = 'rpc://')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()

app.conf.task_routes = {
    'main.tasks.ingest_sharers'                 : {'queue': 'twitter'},
    'main.tasks.regurgitate_sharers'            : {'queue': 'twitter'},
    'main.tasks.refresh_sharers'                : {'queue': 'twitter'},
    'main.tasks.fetch_shares'                   : {'queue': 'twitter'},
    'main.tasks.get_twitter_thread'             : {'queue': 'twitter'},
    'main.metatasks.auto_tweet'                 : {'queue': 'twitter'},

    'main.tasks.associate_article'              : {'queue': 'fetch'},

    'main.tasks.associate_articles'             : {'queue': 'orchestrate'},
    'main.tasks.parse_unparsed_articles'        : {'queue': 'orchestrate'},

    'main.tasks.reparse_articles'               : {'queue': 'internal'},
    'main.tasks.reparse_publication_articles'   : {'queue': 'internal'},
    'main.tasks.parse_article_metadata'         : {'queue': 'internal'},
    'main.metatasks.clean_up'                   : {'queue': 'internal'},

    'main.tasks.analyze_sentiment'              : {'queue': 'scoring'},
    'main.tasks.allocate_credibility'           : {'queue': 'scoring'},
    'main.tasks.set_scores'                     : {'queue': 'scoring'},
    'main.tasks.do_publication_aggregates'      : {'queue': 'scoring'},
}

if 'SCANVINE_ENV' in os.environ and os.environ['SCANVINE_ENV']=='production':
    app.conf.task_always_eager = False
    if False:
        app.conf.beat_schedule = {
            'add-every-30-seconds': {
                'task': 'main.tasks.fetch_shares',
                'schedule': 60.0,
            },
            'add-every-180-seconds': {
                'task': 'main.tasks.analyze_sentiment',
                'schedule': 183.0,
            },
            'add-every-300-seconds': {
                'task': 'main.tasks.associate_articles',
                'schedule': 303.0,
            },
            'add-every-450-seconds': {
                'task': 'main.tasks.reparse_articles',
                'schedule': 459.0,
            },
            'add-every-1200-seconds': {
                'task': 'main.tasks.allocate_credibility',
                'schedule': 1212.0,
            },
            'add-every-1200-seconds-2': {
                'task': 'main.metatasks.auto_tweet',
                'schedule': 1223.0,
            },
            'add-every-2400-seconds': {
                'task': 'main.tasks.refresh_sharers',
                'schedule': 2448.0,
            },
            'add-every-9000-seconds': {
                'task': 'main.metatasks.clean_up',
                'schedule': 9009.0,
            },
            'add-every-9000-seconds-2': {
                'task': 'main.tasks.parse_unparsed_articles',
                'schedule': 9199.0,
            },
            'add-every-10800-seconds': {
                'task': 'main.tasks.ingest_sharers',
                'schedule': 10801.0,
            },
            'add-every-12000-seconds-3': {
                'task': 'main.tasks.regurgitate_sharers',
                'schedule': 12199.0,
            },
        }
    else:
        app.conf.beat_schedule = {}
else:
    app.conf.task_always_eager = True

@app.task(bind=True)
def debug_task(self):
    print('Request: {0!r}'.format(self.request))
