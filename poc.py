import yaml
import json
import urllib3

import twitter # https://raw.githubusercontent.com/bear/python-twitter/master/twitter/api.py
from bs4 import BeautifulSoup
import boto3

import django, os
from django.conf import settings
if not settings.configured:
    settings.configure(DEBUG=True)
    settings.BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    settings.INSTALLED_APPS = [ 'main.apps.MainConfig']
    settings.DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': os.path.join(settings.BASE_DIR, 'db.sqlite3'),
        }
    }
    django.setup()

from main.models import *

# Launch API
keys_file = open(".keys.yaml")
parsed_keys = yaml.load(keys_file, Loader=yaml.SafeLoader)
api = twitter.Api(consumer_key=parsed_keys['API_KEY'],
                  consumer_secret=parsed_keys['API_SECRET'],
                  access_token_key=parsed_keys['TOKEN_KEY'],
                  access_token_secret=parsed_keys['TOKEN_SECRET'])
#                 sleep_on_rate_limit=True)
api.CreateList('verified', 'private', 'Proof of concept')

# Get some verified users, add them to the DB
# https://developer.twitter.com/en/docs/tweets/data-dictionary/overview/user-object
users = []
if False:
    ids = api.GetFriendIDs(screen_name='verified', count=1000)
    users = api.UsersLookup(user_id=ids[0:99], include_entities=False)
    filtered = [{'id':u.id, 'name':u.name, 'screen_name':u.screen_name, 'desc':u.description, 'v':u.verified} for u in users if not u.protected]
    new = [f for f in filtered if len(Sharer.objects.filter(twitter_id=f['id']))==0]
    for n in new:
      s = Sharer(twitter_id=n['id'], status=0, name=n['name'], twitter_screen_name = n['screen_name'], profile=n['desc'], category=0, verified=True)
      s.save()
    
    # Take users from the DB, add them to a Twitter list
    sharers = Sharer.objects.filter(status=0)[0:99]
    for s in sharers:
      list = api.CreateListsMember(owner_screen_name='scanvine', slug='verified', user_id=s.twitter_id)
      s.status=1
      s.save()    

if True:
    next, prev, users = api.GetListMembersPaged(list_id=15084461, count=500, skip_status=True)
    filtered = [{'id':u.id, 'name':u.name, 'screen_name':u.screen_name, 'desc':u.description, 'v':u.verified} for u in users if not u.protected]
    new = [f for f in filtered if len(Sharer.objects.filter(twitter_id=f['id']))==0]
    for n in new:
      s = Sharer(twitter_id=n['id'], status=0, name=n['name'], twitter_screen_name = n['screen_name'], profile=n['desc'], category=0, verified=True)
      s.save()

    

# Get list statuses, filter those with external links
# timeline = api.GetListTimeline(owner_screen_name='scanvine', slug='verified', count = 400, include_rts=1, return_json=True)
timeline = api.GetListTimeline(list_id=15084461, count = 400, include_rts=1, return_json=True)
link_statuses = [{'id':t['id'], 'user_id':t['user']['id'], 'text':t['text'], 'urls':t['entities']['urls']} for t in timeline if len(t['entities']['urls'])>0]
link_statuses = [l for l in link_statuses if json.dumps(l['urls'][0]['expanded_url']).find('twitter')<0]

# Fetch those articles, pull their authors
articles = []
shares = []
http = urllib3.PoolManager()
for status in link_statuses:
    print('status %s' % status['text'])
    url = status['urls'][0]['expanded_url']
    # TODO: handle multiple URLs
    # TODO: filter out url cruft

    s = None
    existing = Share.objects.filter(twitter_id=status['id'])
    if existing:
        s = existing[0]
    else:
        sharer = Sharer.objects.get(twitter_id=status['user_id'])
        s = Share(source=0, language='en', status=0, sharer_id = sharer.id, twitter_id = status['id'], text=status['text'], url=url)
        s.save()
    shares.append(s)

    a = None
    existing = Article.objects.filter(initial_url=url)
    if existing:
        a = existing[0]
    else:
        try:
            r = http.request('GET', url)
            html = r.data.decode('utf-8')
            soup = BeautifulSoup(html, "html.parser")
            article = {'text':status['text'], 'url':r.geturl(), 'initial_url':url, 'html':html}
            print(url)
            if html.find("application/ld+json") > 0:
                ld = json.loads("".join(soup.find("script", {"type":"application/ld+json"}).contents))
                article['url'] = ld['url'] if 'url' in ld else url
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
    
            a = Article(status=0, language='en', url = article['url'], title = article.get('title', ''), contents = article['html'], metadata = {'author': article.get('author', '')})
            a.save()
        except:
            raise

    s.article_id = a.id
    s.status = 1
    s.save()

# Analyze the sentiment

sentiments = []
comprehend = boto3.client(service_name='comprehend')
for share in shares:
    sentiment = comprehend.detect_sentiment(Text=share.text, LanguageCode=share.language)
    score = sentiment['SentimentScore']
    share.sentiment = score
    # very basic sentiment math
    share.net_sentiment = score['Positive'] - score['Negative']
    share.net_sentiment = 0.0 if score['Neutral'] > 0.5 else share.net_sentiment
    share.net_sentiment = -0.01 if score['Mixed'] > 0.5 else share.net_sentiment #flag for later
    share.status=1
    share.save()


