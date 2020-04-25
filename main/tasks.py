from celery import shared_task
import json
from .models import *
import yaml
import twitter # https://raw.githubusercontent.com/bear/python-twitter/master/twitter/api.py

# Launch Twitter API - TODO move this to TwitterService
keys_file = open(".keys.yaml")
parsed_keys = yaml.load(keys_file, Loader=yaml.SafeLoader)
api = twitter.Api(consumer_key=parsed_keys['API_KEY'],
                  consumer_secret=parsed_keys['API_SECRET'],
                  access_token_key=parsed_keys['TOKEN_KEY'],
                  access_token_secret=parsed_keys['TOKEN_SECRET'])
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
    import urllib3
    from bs4 import BeautifulSoup
    http = urllib3.PoolManager()
    for share in Share.objects.filter(status=0):
        existing = Article.objects.filter(initial_url=share.url)
        if existing:
            continue
        r = http.request('GET', share.url)
        html = r.data.decode('utf-8')
        soup = BeautifulSoup(html, "html.parser")
        article = {'url':r.geturl(), 'initial_url':share.url, 'html':html, 'status':0}
        try:
            if html.find("application/ld+json") > 0:
                ld = json.loads("".join(soup.find("script", {"type":"application/ld+json"}).contents))
                article['title'] = ld['headline'] if 'headline' in ld else ''
                article['title'] = ld['title'] if 'title' in ld else article['title']
                article['author'] = ld['author'] if 'author' in ld else ''
                article['author'] = article['author']['name'] if type(article['author']) is dict else article['author']
            if html.find("npr-vars") > 0:
                npr = "".join(soup.find("script", {"id":"npr-vars"}).contents)
                npr = npr.partition("NPR.serverVars = ")[2]
                npr = npr[:-2]
                npr = json.loads(npr)
                article['author'] = npr['byline'] if 'byline' in npr else article['author']
        except:
            article['status'] = Article.PARSING_ERROR
    
        a = Article(status=article['status'], language='en', url = share.url, initial_url=article['initial_url'],
                    title = article.get('title', ''), contents = article['html'],
                    metadata = json.dumps({'author': article.get('author', '')}))
        a.save()

        share.article_id = a.id
        share.status = Share.ARTICLE_ERROR
        share.save()


@shared_task
def associate_authors():
    for article in Article.objects.filter(status=0):
        meta = json.loads(article.metadata)
        name = ''
        if 'name' in meta:
            name = meta['name']
        if 'author' in meta:
            inner = meta['author']
            if type(inner) is list:
                subinner = inner[0]
                if type(subinner) is dict:
                    name = subinner['name']
                else:
                    name = subinner
            if type(inner) is dict:
                name=inner['name']
            else:
                name=inner
        if name != '':
            existing = Author.objects.filter(name=name)
            if not existing:
                author=Author(status=0, name=name, is_collaboration=False, metadata='{}', current_credibility=0, total_credibility=0)
                author.save()
                article.author_id = author.id
                article.status = article.AUTHOR_ASSOCIATED
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
            
