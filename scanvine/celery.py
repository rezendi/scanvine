import os
from celery import Celery

# set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'scanvine.settings')

app = Celery('scanvine', broker = 'amqp://guest:guest@localhost:5672', backend = 'rpc://')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# set rate limit for tasks to avoid Twitter rate limiting
app.control.rate_limit('main.tasks.get_potential_sharer_ids', '1/m')
app.control.rate_limit('main.tasks.add_new_sharers', '20/m')
app.control.rate_limit('main.tasks.ingest_sharers', '40/h')
app.control.rate_limit('main.tasks.fetch_shares', '1/s')

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    print('Request: {0!r}'.format(self.request))