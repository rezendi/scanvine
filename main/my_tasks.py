import datetime, os, traceback
import twitter # https://raw.githubusercontent.com/bear/python-twitter/master/twitter/api.py
from django.contrib.auth.models import User
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
    
# Get list statuses, filter those with external links
@shared_task(rate_limit="30/m")
def fetch_my_back_shares(user_id):
    job = launch_job("fetch_my_back_shares")
    try:
        instances = UserSocialAuth.objects.filter(provider='twitter', user_id=user_id)
        if not instances:
            return log_job(job, "User %s extra data not found" % user_id, Job.Status.ERROR)
        instance = instances[0]
        access = instance.extra_data['access_token']
        api = get_api(access['oauth_token'], access['oauth_token_secret'])
        max_id = instance.extra_data['back_max_id'] if 'back_max_id' in instance.extra_data else None
        print("max_id %s" % max_id)
        
        # fetch the timeline, log its values
        timeline = api.GetHomeTimeline(count = 200, max_id = max_id, include_entities=True)
        tweets = []
        for t in timeline:
            urls = t.urls
            urls += t.quoted_status.urls if t.quoted_status else []
            urls += t.retweeted_status.urls if t.retweeted_status else []
            urls = [u.expanded_url for u in urls]
            urls = [cleaan_up_url(u) for u in urls if not u.startswith("https://twitter.com/") and not u.startswith("https://mobile.twitter.com/")]
            if urls:
                t.urls = urls
                tweets.append(t)
        log_job(job, "tweets %s external links %s max_id %s for %s" % (len(timeline), len(tweets), max_id, access['screen_name']) )
        instance.extra_data['back_max_id'] = timeline[-1].id if len(timeline) > 0 else None
        print("new_max_id %s" % instance.extra_data['back_max_id'])
        instance.save()
    
        # Store new shares to DB
        count = 0
        category = Sharer.Category.PERSONAL
        for t in tweets:
            url = clean_up_url(t.urls[0])
            existing = Share.objects.filter(twitter_id=t.id)
            if existing:
                log_job(job, "Share already found %s" % t.id)
                continue
            sharers = Sharer.objects.filter(twitter_id=t.user.id)
            if sharers:
                sharer = sharers[0]
            else:
                sharer = Sharer(status = Sharer.Status.CREATED, twitter_id=t.user.id, twitter_screen_name=t.user.screen_name,
                                name=t.user.name, profile = t.user.description, category=category, verified = t.user.verified)
                sharer.save()
            share = Share(source=1, status = Share.Status.CREATED, category=category, language='en',
                          sharer_id = sharer.id, twitter_id = t.id, text=t.full_text, url=url)
            share.save()
            feedshare = FeedShare(user_id=user_id, share_id = share.id)
            feedshare.save()
            count += 1
        log_job(job, "new shares %s" % count, Job.Status.COMPLETED)
        
        # Launch follow-up job to fetch associated articles
        if count > 0:
            associate_feed_articles.signature((user_id,)).apply_async()

    except Exception as ex:
        log_job(job, traceback.format_exc())
        log_job(job, "Fetch my back shares error %s" % ex, Job.Status.ERROR)
        raise ex


@shared_task
def associate_feed_articles(user_id):
    job = launch_job("associate_articles")
    shares = Share.objects.prefetch_related('feed_shares').filter(source=1, status=Share.Status.CREATED, feed_shares__user_id=user_id)
    for share in shares:
        associate_article.signature((share.id,)).apply_async()
    log_job(job, "associating %s articles" % len(shares), Job.Status.COMPLETED)


