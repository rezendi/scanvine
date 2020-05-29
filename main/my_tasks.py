import datetime, os, time, traceback
import twitter # https://raw.githubusercontent.com/bear/python-twitter/master/twitter/api.py
from django.db.models import Count, IntegerField
from django.contrib.auth.models import User
from django.contrib.postgres.fields.jsonb import KeyTextTransform
from django.db.models.functions import Cast, Coalesce
from social_django.models import UserSocialAuth
from celery import shared_task, group, signature
from .models import *
from .tasks import *


def get_api(oauth_token, oauth_secret):
    return twitter.Api(consumer_key=os.getenv('TWITTER_API_KEY', ''),
                       consumer_secret=os.getenv('TWITTER_API_SECRET', ''),
                       access_token_key=oauth_token,
                       access_token_secret=oauth_secret,
                       tweet_mode='extended')

MAX_PERSONAL_SHARES=255

# Get list statuses, filter those with external links
@shared_task(rate_limit="20/m")
def fetch_my_back_shares(user_id):
    job = launch_job("fetch_my_back_shares")
    try:
        auths = UserSocialAuth.objects.filter(provider='twitter', user_id=user_id)
        if not auths:
            return log_job(job, "User %s extra data not found" % user_id, Job.Status.ERROR)
        auth = auths[0]

        existing_shares = FeedShare.objects.filter(user_id=user_id).count()
        if existing_shares >= MAX_PERSONAL_SHARES:
            log_job(job, "personal shares quota for %s" % auth['screen_name'], Job.Status.COMPLETED)
            if not 'back_filling' in auth.extra_data or auth.extra_data['back_filling'] != 'done':
                auth.extra_data['back_filling'] = 'done'
                auth.save()
            return

        access = auth.extra_data['access_token']
        api = get_api(access['oauth_token'], access['oauth_token_secret'])
        max_id = auth.extra_data['back_max_id'] if 'back_max_id' in auth.extra_data else None
        
        # fetch the timeline, log its values
        timeline = api.GetHomeTimeline(count = 20, max_id = max_id, include_entities=True)
        tweets = timeline_to_tweets(timeline)
        log_job(job, "tweets %s external links %s max_id %s for %s" % (len(timeline), len(tweets), max_id, access['screen_name']) )
        auth.extra_data['back_max_id'] = timeline[-1].id if timeline else None
        auth.extra_data['since_id'] = timeline[0].id if timeline and not 'since_id' in auth.extra_data else auth.extra_data['since_id']
        auth.extra_data['last_fetch'] = time.time()
        auth.save()
    
        # Store new shares to DB
        count = 0
        for t in tweets:
            existing = Share.objects.filter(twitter_id=t.id)
            if existing:
                log_job(job, "Share already found %s" % t.id)
                continue
            sharers = Sharer.objects.filter(twitter_id=t.user.id)
            if sharers:
                sharer = sharers[0]
            else:
                sharer = Sharer(status=Sharer.Status.CREATED, category=Sharer.Category.PERSONAL, twitter_id=t.user.id, name=t.user.name, 
                                twitter_screen_name=t.user.screen_name, profile = t.user.description, verified = t.user.verified)
                sharer.save()
            share = Share(source=1, status = Share.Status.CREATED, category=Sharer.Category.PERSONAL, language='en',
                          sharer_id = sharer.id, twitter_id = t.id, text=t.full_text, url=t.urls[0])
            share.save()
            FeedShare(user_id=user_id, share_id=share.id).save()
            count += 1
            if count + existing_shares >= MAX_PERSONAL_SHARES:
                break
        log_job(job, "new shares %s" % count, Job.Status.COMPLETED)
        
        # Launch follow-up jobs to fetch associated articles if any
        if count > 0:
            associate_feed_articles.signature((user_id,)).apply_async()
        # Get more back links, but let some articles get associated first
        fetch_my_back_shares.signature((user_id,)).apply_async(countdown=3)

    except Exception as ex:
        log_job(job, traceback.format_exc())
        log_job(job, "Fetch my back shares error %s" % ex, Job.Status.ERROR)
        raise ex


@shared_task(rate_limit="1/m")
def launch_fetch_my_shares():
    job = launch_job("launch_fetch_my_shares")
    now = int(time.time())
    auths = UserSocialAuth.objects.annotate(
        last_fetch = Coalesce( Cast(KeyTextTransform('last_fetch', 'extra_data'), IntegerField()), 0)
    ).filter(last_fetch__gt=0, last_fetch__lt=now-15*60)
    for auth in auths:
        fetch_my_shares.signature((auth.user_id,)).apply_async()
    if len(auths) > 0:
        log_job(job, "launched fetches for %s users" % len(auths), Job.Status.COMPLETED)


# Get list statuses, filter those with external links
@shared_task(rate_limit="20/m")
def fetch_my_shares(user_id):
    job = launch_job("fetch_my_shares")
    try:
        auths = UserSocialAuth.objects.filter(provider='twitter', user_id=user_id)
        if not auths:
            return log_job(job, "User %s extra data not found" % user_id, Job.Status.ERROR)
        auth = auths[0]
        access = auth.extra_data['access_token']
        api = get_api(access['oauth_token'], access['oauth_token_secret'])
        since_id = auth.extra_data['since_id'] if 'since_id' in auth.extra_data else None
        
        # fetch the timeline, log its values
        timeline = api.GetHomeTimeline(count = 200, since_id = since_id, include_entities=True)
        tweets = timeline_to_tweets(timeline)
        log_job(job, "tweets %s external links %s since_id %s for %s" % (len(timeline), len(tweets), since_id, access['screen_name']) )
        auth.extra_data['since_id'] = timeline[0].id if timeline else auth.extra_data['since_id'] if 'since_id' in auth.extra_data else None
        auth.extra_data['last_fetch'] = time.time()
        auth.save()
    
        # Store new shares to DB
        count = 0
        for t in tweets:
            existing = Share.objects.filter(twitter_id=t.id)
            if existing:
                log_job(job, "Share already found %s" % t.id)
                continue
            sharers = Sharer.objects.filter(twitter_id=t.user.id)
            if sharers:
                sharer = sharers[0]
            else:
                sharer = Sharer(status=Sharer.Status.CREATED, category=Sharer.Category.PERSONAL, twitter_id=t.user.id, name=t.user.name, 
                                twitter_screen_name=t.user.screen_name, profile = t.user.description, verified = t.user.verified)
                sharer.save()
            share = Share(source=1, status = Share.Status.CREATED, category=Sharer.Category.PERSONAL, language='en',
                          sharer_id = sharer.id, twitter_id = t.id, text=t.full_text, url=t.urls[0])
            share.save()
            FeedShare(user_id=user_id, share_id=share.id).save()
            count += 1

        # Launch follow-up job to fetch associated articles if any
        if count > 0:
            associate_feed_articles.signature((user_id,)).apply_async()

        # Clear up old personal shares and sharers.
        # TODO start keeping all this data instead...
        existing_shares = FeedShare.objects.filter(user_id=user_id).count()
        log_job(job, "existing shares %s" % existing_shares)
        if existing_shares > MAX_PERSONAL_SHARES:
            last = FeedShare.objects.filter(user_id=user_id).order_by('-created_at')[MAX_PERSONAL_SHARES:MAX_PERSONAL_SHARES+1][0]
            share_ids_to_delete = FeedShare.objects.filter(user_id=user_id, created_at__lt=last.created_at).values('share_id')
            shares_to_delete = Share.objects.filter(category=Sharer.Category.PERSONAL, id__in=share_ids_to_delete)
            log_job(job, "deleting %s shares" % shares_to_delete.count())
            sharer_ids = shares_to_delete.values('sharer_id')
            shares_to_delete.delete()
            sharers_to_delete = Sharer.objects.annotate(share_count=Count('share__pk'))
            sharers_to_delete = sharers_to_delete.filter(category=Sharer.Category.PERSONAL, id__in=sharer_ids, share_count=0)
            log_job(job, "deleting %s sharers" % sharers_to_delete.count())
            sharers_to_delete.delete()

        log_job(job, "new shares %s" % count, Job.Status.COMPLETED)
        
            
    except Exception as ex:
        log_job(job, traceback.format_exc())
        log_job(job, "Fetch my shares error %s" % ex, Job.Status.ERROR)
        raise ex


@shared_task
def associate_feed_articles(user_id):
    job = launch_job("associate_articles")
    shares = Share.objects.prefetch_related('feed_shares').filter(source=1, status=Share.Status.CREATED, feed_shares__user_id=user_id)
    for share in shares:
        associate_article.signature((share.id,)).apply_async()
    log_job(job, "associating %s articles" % len(shares), Job.Status.COMPLETED)


