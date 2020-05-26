import datetime, os, traceback
import twitter # https://raw.githubusercontent.com/bear/python-twitter/master/twitter/api.py
from celery import shared_task, group, signature
from .models import *

# Launch Twitter API
api = twitter.Api(consumer_key=os.getenv('TWITTER_API_KEY', ''),
                  consumer_secret=os.getenv('TWITTER_API_SECRET', ''),
                  access_token_key=os.getenv('TWITTER_TOKEN_KEY', ''),
                  access_token_secret=os.getenv('TWITTER_TOKEN_SECRET', ''),
                  tweet_mode='extended',
                  sleep_on_rate_limit=True)

LIST_IDS = [1259645675878281217, 1259645744249581569, 1259645776315117568, 1259645804853080064, 1259645832619372544]

# Get a tranche of verified users, add them to the DB if not there
# https://developer.twitter.com/en/docs/tweets/data-dictionary/overview/user-object
@shared_task(rate_limit="30/h")
def get_potential_sharers():
    job = launch_job("get_potential_sharers")
    verified_cursor = -1
    log_job(job, "-1", Job.Status.COMPLETED) # remove when we want to do this again
    return # remove when we want to do this again
    previous_jobs = Job.objects.filter(status=Job.Status.COMPLETED).filter(name="get_potential_sharers").order_by("-created_at")
    if previous_jobs:
        previous_actions = previous_jobs[0].actions
        verified_cursor_string = previous_actions.partition("\n")[0]
        verified_cursor = int (verified_cursor_string)
    if verified_cursor == 0:
        log_job(job, "Cursor at end", Job.Status.COMPLETED)
        return
    try:
        (verified_cursor, previous_cursor, users) = api.GetFriendsPaged(screen_name='verified', cursor = verified_cursor, skip_status = True)
        log_job(job, "Potential new sharers: %s" % len(users))
        new = [u for u in users if not Sharer.objects.filter(twitter_id=u.id)]
        log_job(job, "New sharers: %s" % len(new))
        for n in new:
            s = Sharer(status=Sharer.Status.CREATED, twitter_id=n.id, twitter_screen_name = n.screen_name.replace('\x00',''),
                       name=n.name.replace('\x00',''), profile=n.description.replace('\x00',''), category=-1, verified=True)
            s.save()
        log_job(job, "New sharers: %s" % len(new), Job.Status.COMPLETED)
        log_job(job, "%s" % verified_cursor, Job.Status.COMPLETED)
    except Exception as ex:
        log_job(job, "Potential sharer fetch error %s" % ex, Job.Status.ERROR)


@shared_task(rate_limit="1/m")
def get_lists():
    job = launch_job("get_lists")
    category = datetime.datetime.now().microsecond % len(LIST_IDS)
    sharers = Sharer.objects.filter(status=Sharer.Status.LISTED).exclude(metadata__has_key='lists_processed')[:1]
    if not sharers:
        log_job(job, "all done", Job.Status.COMPLETED)
        return
    sharer = sharers[0]
    tlists = api.GetMemberships(user_id=sharer.twitter_id, count=1000) #TODO maybe more than 1K?
    external_lists = []
    for tlist in tlists:
        existing = List.objects.filter(twitter_id = tlist.id)
        list = existing[0] if existing else List(status = 0, twitter_id=tlist.id)
        key = "cat_%s" % category
        list.metadata[key] = list.metadata[key] + 1 if key in list.metadata else 1
        list.save()
        external_lists.append(tlist.id)
    sharer.metadata['external_lists'] = external_lists
    sharer.metadata['lists_processed'] = "true"
    sharer.save()
    log_job(job, "got %s lists for %s" % (len(tlists), sharer.twitter_screen_name), Job.Status.COMPLETED)


@shared_task(rate_limit="1/m")
def get_list_members():
    job = launch_job("get_list_members")
    lists = List.objects.filter(status=0)[:1]
    if not lists:
        log_job(job, "all done", Job.Status.COMPLETED)
        return
    list = lists[0]
    (next, prev, listed) = api.GetListMembersPaged(list_id=list.twitter_id, count=5000, skip_status=True, include_entities=False) # TODO maybe more than 5K?
    for l in listed:
        existing = Sharer.objects.filter(twitter_id=l.id)
        if existing:
            sharer = existing[0]
            if not 'external_lists' in sharer.metadata:
                sharer.metadata['external_lists'] = []
            if not list.twitter_id in sharer.metadata['external_lists']:
                sharer.metadata['external_lists'].append(list.twitter_id)
        else:
            sharer = Sharer(status=Sharer.Status.SUGGESTED, twitter_id=l.id, twitter_screen_name=l.screen_name, category=Sharer.Category.NONE,
                            name=l.name, profile=l.description, verified=l.verified, metadata = {"external_lists":[list.twitter_id]})
        sharer.save()
    list.status = 1
    list.save()
    log_job(job, "got %s members for list %" % (len(listed), list.twitter_id), Job.Status.COMPLETED)


@shared_task(rate_limit="1/m")
def recommend_members():
    job = launch_job("recommend_members")


@shared_task(rate_limit="1/m")
def clean_up_jobs(date=datetime.datetime.utcnow().date(), days=7):
    job = launch_job("clean_up_jobs")
    cutoff = date - datetime.timedelta(days=days)
    to_delete = Job.objects.filter(created_at__lte=cutoff)
    log_job(job, "cutoff %s deleting %s jobs" % (cutoff, to_delete.count()))
    to_delete.delete()
    log_job(job, "cleanup complete", Job.Status.COMPLETED)


# Utility functions
def launch_job(name):
    job = Job(status = Job.Status.LAUNCHED, name=name, actions='')
    job.save()
    return job

def log_job(job, action, status = None):
    print(action)
    job.status = status if status else job.status
    job.actions = action + " \n" + job.actions
    job.save()
