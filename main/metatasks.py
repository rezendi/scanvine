import datetime, os, traceback
import twitter # https://raw.githubusercontent.com/bear/python-twitter/master/twitter/api.py
from celery import shared_task, group, signature
from .models import *
from .views import get_article_query

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
                       name=n.name.replace('\x00',''), profile=n.description.replace('\x00',''), category=-1, verified=n.verified, protected=n.protected)
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
    try:
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
    except Exception as ex:
        sharer.metadata['lists_processed'] = "true"
        sharer.save()
        log_job(job, traceback.format_exc())
        log_job(job, "Get lists error % for %s" % (ex, sharer.twitter_screen_name), Job.Status.ERROR)
        raise ex


@shared_task(rate_limit="1/m")
def get_list_members():
    job = launch_job("get_list_members")
    lists = List.objects.filter(status=0).order_by("-id")[:1]
    if not lists:
        log_job(job, "all done", Job.Status.COMPLETED)
        return
    list = lists[0]
    try:
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
                                name=l.name, profile=l.description, verified=l.verified, protected=l.protected, metadata = {"external_lists":[list.twitter_id]})
            sharer.save()
        list.status = 1
        list.save()
        log_job(job, "got %s members for list %s" % (len(listed), list.twitter_id), Job.Status.COMPLETED)
    except Exception as ex:
        list.status = -1
        list.save()
        log_job(job, traceback.format_exc())
        log_job(job, "Get list members error %s for %s" % (ex, list.twitter_id), Job.Status.ERROR)
        raise ex


@shared_task(rate_limit="1/m")
def clean_up(date=datetime.datetime.utcnow(), days=7):
    job = launch_job("clean_up")
    cutoff = date - datetime.timedelta(days=days)
    to_delete = Job.objects.filter(created_at__lt=cutoff)
    log_job(job, "cutoff %s deleting %s jobs" % (cutoff, to_delete.count()))
    to_delete.delete()

    # now, clear out the contents for articles more than 30 days old.
    # (We already have the metadata and can re-fetch and are not an archive.)
    # TODO maybe also Article.objects.annotate(shares=Count('share__pk', distinct=True)).filter(shares=0).delete()
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=30)
    to_truncate = Article.objects.filter(created_at__lt=cutoff).exclude(contents='')
    log_job(job, "cutoff %s truncating %s articles" % (cutoff, to_truncate.count()))
    fetcher = lazy_bulk_fetch(100, to_truncate.count(), lambda: to_truncate)
    for batch in fetcher:
        for article in batch:
            article.contents = ''
            article.save()
    log_job(job, "cleanup complete", Job.Status.COMPLETED)


@shared_task(rate_limit="5/h")
def auto_tweet():
    # get ID of last autotweeted article
    job = launch_job("auto_tweet")
    last_id = None
    previous_jobs = Job.objects.filter(status=Job.Status.COMPLETED).filter(name="auto_tweet").order_by("-created_at")[0:10]
    if previous_jobs:
        for action in previous_jobs[0].actions.split("\n"):
            if action.startswith("article_id="):
                last_id = int(action.partition("=")[2])
    log_job(job, "last_id=%s" % last_id)

    # check latest top article
    query = get_article_query()
    top = query.order_by("-buzz")[:1]
    if not top:
        log_job(job, "No top article found!", Job.Status.ERROR)
        return
    article = top[0]
    
    # if different, tweet new one
    if article.id != last_id:
        status_text = "“%s” %s by %s in %s via scanvine.com" % (article.title, article.url, article.author, article.publication)
        status = api.PostUpdate(status_text)
        log_job(job, "tweet_id=%s" % status.id)
        log_job(job, "article_id=%s" % article.id, Job.Status.COMPLETED)


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

def lazy_bulk_fetch(max_obj, max_count, fetch_func, start=0):
    counter = start
    while counter < max_count:
        yield fetch_func()[counter:counter + max_obj]
        counter += max_obj


# Sharer identification functions

# For each category, get the lists with the largest number of existing sharers from that category.
# Number of existing sharers is that list's weight
# For each potential sharer, total the weights of such lists they're members of, add to metadata
# (Use this instead of total list memberships as input with profile to neural net; if future iterations, store and use list size, too)
# Add search to get sharers with min weight, ordered by weight

from django.db.models import IntegerField
from django.db.models.functions import Cast
from django.contrib.postgres.fields.jsonb import KeyTextTransform

def weight_sharers():
    category_lists = {}
    for category in range(0,5):
        category_lists[category] = {}
        key = 'cat_%s' % category
        weighted_lists = List.objects.annotate(
            weight = Cast(KeyTextTransform(key, 'metadata'), IntegerField()),
        ).filter(weight__gt=2)
        for list in weighted_lists:
            category_lists[category][list.twitter_id] = list.weight

    fetcher = lazy_bulk_fetch(1000, Sharer.objects.count(), lambda: Sharer.objects.all())
    for batch in fetcher:
        for sharer in batch:
            if not 'external_lists' in sharer.metadata:
                continue
            weighted = False
            list_weights = {0:0,1:0,2:0,3:0,4:0}
            sharer_list_ids = sharer.metadata['external_lists']
            for list_id in sharer_list_ids:
                for category in range(0,5):
                    if list_id in category_lists[category]:
                        list_weights[category] = list_weights[category] + category_lists[category][list_id]
                        weighted = True
            if weighted:
                sharer.metadata['list_weights'] = list_weights
                if sharer.status == Sharer.Status.SUGGESTED:
                    sharer.status = Sharer.Status.RECOMMENDED
                sharer.save()
        

# Data dump functions

import csv

def dump_profiles_and_lists():
    with open('sharers.csv', 'w') as csvfile:
        writer = csv.writer(csvfile, quoting=csv.QUOTE_MINIMAL)
        fetcher = lazy_bulk_fetch(10000, Sharer.objects.count(), lambda: Sharer.objects.all().values('profile','metadata','category'))
        for batch in fetcher:
            for sharer in batch:
                lists = sharer['metadata']['external_lists'] if 'external_lists' in sharer['metadata'] else []
                writer.writerow([sharer['profile'], lists, sharer['category']])
            

def dump_caategorized_profiles_and_lists():
  with open('sharers.csv') as infile:
        with open('sharers-categorized.csv', 'w') as outfile:
            writer = csv.writer(outfile, quoting=csv.QUOTE_MINIMAL)
            reader = csv.reader(infile)
            for row in reader:
                category = int(row[2])
                if category > 0:
                    writer.writerow(row)
 