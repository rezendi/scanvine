import os
import json
import twitter # https://raw.githubusercontent.com/bear/python-twitter/master/twitter/api.py
from celery import shared_task, group, signature
from .models import *

# Launch Twitter API - TODO move this to TwitterService
api = twitter.Api(consumer_key=os.getenv('TWITTER_API_KEY', ''),
                  consumer_secret=os.getenv('TWITTER_API_SECRET', ''),
                  access_token_key=os.getenv('TWITTER_TOKEN_KEY', ''),
                  access_token_secret=os.getenv('TWITTER_TOKEN_SECRET', ''))
#                 sleep_on_rate_limit=True)


# Get some verified users, add them to the DB
# https://developer.twitter.com/en/docs/tweets/data-dictionary/overview/user-object
@shared_task
def update_sharers_list():
    ids = api.GetFriendIDs(screen_name='verified', count=5000, total_count=5000)
    users = api.UsersLookup(user_id=ids[0:99], include_entities=False)
    filtered = [{'id':u.id, 'name':u.name, 'screen_name':u.screen_name, 'desc':u.description, 'v':u.verified} for u in users if not u.protected]
    new = [f for f in filtered if len(Sharer.objects.filter(twitter_id=f['id']))==0]
    for n in new:
      s = Sharer(twitter_id=n['id'], status=0, name=n['name'], twitter_screen_name = n['screen_name'], profile=n['desc'], category=0, verified=True)
      s.save()
    
    # Take users from the DB, add them to a Twitter list
    sharers = Sharer.objects.filter(status=0)[0:99]
    for s in sharers:
      list = api.CreateListsMember(list_id=1254145545246916608, user_id=s.twitter_id)
      s.status = Sharer.LISTED
      s.save()    

@shared_task
def get_poc_sharers_list():
    next, prev, users = api.GetListMembersPaged(list_id=15084461, count=500, skip_status=True)
    filtered = [{'id':u.id, 'name':u.name, 'screen_name':u.screen_name, 'desc':u.description, 'v':u.verified} for u in users if not u.protected]
    new = [f for f in filtered if len(Sharer.objects.filter(twitter_id=f['id']))==0]
    for n in new:
      s = Sharer(twitter_id=n['id'], status=Sharer.LISTED, name=n['name'], twitter_screen_name = n['screen_name'], profile=n['desc'], category=0, verified=True)
      s.save()


# Get list statuses, filter those with external links
@shared_task
def fetch_shares():
    # timeline = api.GetListTimeline(owner_screen_name='scanvine', slug='verified', count = 400, include_rts=1, return_json=True)
    timeline = api.GetListTimeline(list_id=15084461, count = 400, include_rts=1, return_json=True)
    link_statuses = [{'id':t['id'], 'user_id':t['user']['id'], 'text':t['text'], 'urls':t['entities']['urls']} for t in timeline if len(t['entities']['urls'])>0]
    link_statuses = [l for l in link_statuses if json.dumps(l['urls'][0]['expanded_url']).find('twitter')<0]
    
    # Fetch those articles, pull their authors
    for status in link_statuses:
        # print('status %s' % status['text'])
        # TODO: handle multiple URLs
        url = status['urls'][0]['expanded_url']
        # TODO: filter out url cruft more elegantly
        url = url.partition("?")[0]
    
        # get existing share, if any, for idempotency
        existing = Share.objects.filter(twitter_id=status['id'])
        if existing:
            continue
        else:
            sharer = Sharer.objects.get(twitter_id=status['user_id'])
            s = Share(source=0, language='en', status=0, sharer_id = sharer.id, twitter_id = status['id'], text=status['text'], url=url)
            s.save()


@shared_task
def associate_articles():
    jobs = []
    for share in Share.objects.filter(status=0):
        existing = Article.objects.filter(initial_url=share.url)
        if existing:
            continue
        s = signature(associate_article(share.id))
        jobs.append(s)
    job = group(jobs)
    job.apply_async()

def associate_article(share_id):
    import urllib3
    share = Share.objects.get(id=share_id)
    http = urllib3.PoolManager()
    try:
        r = http.request('GET', share.url)
        html = r.data.decode('utf-8')
    except:
         share.status = Share.FETCH_ERROR
         share.save()
         raise

    article = Article(status=0, language='en', url = r.geturl(), initial_url=share.url, contents=html, title=None, metadata=None)
    article.save()
    share.article_id = article.id
    share.status = Share.ARTICLE_ASSOCIATED
    share.save()
    s = signature(parse_article_metadata(article.id))
    s.apply_async()


@shared_task
def parse_article_metadata(article_id):
    from bs4 import BeautifulSoup
    article = Article.objects.get(id=article_id)
    author_name = None
    try:
        html = article.contents
        soup = BeautifulSoup(html, "html.parser")
        if html.find("application/ld+json") > 0:
            article.metadata = "".join(soup.find("script", {"type":"application/ld+json"}).contents)
        if html.find("npr-vars") > 0:
            npr = "".join(soup.find("script", {"id":"npr-vars"}).contents)
            article.metadata = npr.partition("NPR.serverVars = ")[2][:-2]

        # TODO replace with various different metadata parsers
        meta = json.loads(article.metadata)
        article.title = meta['headline'] if 'headline' in meta else article.title
        article.title = meta['title'] if 'title' in meta else article.title        
        if 'byline' in meta:
            author_name = meta['byline']
        if 'name' in meta:
            author_name = meta['name']
        if 'author' in meta:
            inner = meta['author']
            if type(inner) is list:
                subinner = inner[0]
                if type(subinner) is dict:
                    author_name = subinner['name']
                else:
                    author_name = subinner
            if type(inner) is dict:
                author=inner['name']
            else:
                author=inner
    except:
        print("Metadata parse error")
        article.status = Article.METADATA_PARSE_ERROR
        article.save()

    if author_name:
        existing = Author.objects.filter(name=author_name)
        if not existing:
            author=Author(status=0, name=author_name, is_collaboration=False, metadata='{}', current_credibility=0, total_credibility=0)
            author.save()
            article.author_id = author.id
            article.status = article.AUTHOR_ASSOCIATED
            article.save()
    else:
         article.status = Article.AUTHOR_NOT_FOUND
         article.save()


# Get sentiment from AWS
@shared_task
def analyze_sentiment():
    import boto3
    sentiments = []
    comprehend = boto3.client(service_name='comprehend')
    for share in Share.objects.filter(status = Share.ARTICLE_ASSOCIATED):
        sentiment = comprehend.detect_sentiment(Text=share.text, LanguageCode=share.language)
        score = sentiment['SentimentScore']
        share.sentiment = score
        # very basic sentiment math
        share.net_sentiment = score['Positive'] - score['Negative']
        share.net_sentiment = 0.0 if score['Neutral'] > 0.5 else share.net_sentiment
        share.net_sentiment = -0.01 if score['Mixed'] > 0.5 else share.net_sentiment #flag for later
        share.status = Share.SENTIMENT_CALCULATED
        share.save()


# crude initial algorithm:
# for each sharer, get list of shares
# shares with +ve or -ve get 2 points, mixed/neutral get 1 point, total N points
# 5040 credibility/day for maximum divisibility, N points means 5040/N cred for that share, truncate
@shared_task
def allocate_credibility():
    for sharer in Sharer.objects.all():
        shares = Share.objects.filter(sharer_id=sharer.id, net_sentiment__isnull=False)
        if not shares.exists():
            continue
        total_points = 0
        for s in shares:
            total_points += 2 if abs(s.net_sentiment) > 50 else 1
        if total_points==0:
            continue
        cred_per_point = 5040 // total_points
        for share in shares:
            points = 2 if abs(share.net_sentiment) > 50 else 1
            share_cred = cred_per_point * points
            article = share.article
            if not article:
                continue
            author = article.author
            if not author:
                continue
            t = Tranche(status=0, tags='', sender=sharer.id, receiver=author.id, quantity = share_cred, category=sharer.category, type=author.status)
            t.save()
            
