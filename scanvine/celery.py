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

if 'SCANVINE_ENV' in os.environ and os.environ['SCANVINE_ENV']=='production':
        app.conf.beat_schedule = {
            'add-every-30-seconds': {
                'task': 'main.tasks.fetch_shares',
                'schedule': 30.0,
            },
            'add-every-150-seconds': {
                'task': 'main.tasks.analyze_sentiment',
                'schedule': 151.0,
            },
            'add-every-300-seconds': {
                'task': 'main.tasks.associate_articles',
                'schedule': 303.0,
            },
            'add-every-900-seconds': {
                'task': 'main.tasks.ingest_sharers',
                'schedule': 909.0,
            },
            'add-every-900-seconds-2': {
                'task': 'main.tasks.parse_unparsed',
                'schedule': 927.0,
            },
            'add-every-1200-seconds': {
                'task': 'main.tasks.allocate_credibility',
                'schedule': 1212.0,
            },
            'add-every-1500-seconds': {
                'task': 'main.tasks.set_reputations',
                'schedule': 1515.0,
            },
            'add-every-9000-seconds': {
                'task': 'main.tasks.clean_up_jobs',
                'schedule': 9090.0,
            },
        }
else:
    app.conf.beat_schedule = {
        'add-every-30-seconds': {
            'task': 'main.tasks.fetch_shares',
            'schedule': 30.0,
        },
    }
    
@app.task(bind=True)
def debug_task(self):
    print('Request: {0!r}'.format(self.request))