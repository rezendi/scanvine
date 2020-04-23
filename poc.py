import yaml
import twitter
import json
import urllib3
from bs4 import BeautifulSoup
import boto3

import django, os
from django.conf import settings
if not settings.configured:
    settings.configure(DEBUG=True)
    settings.BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    settings.INSTALLED_APPS = [ 'public.apps.PublicConfig']
    settings.DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': os.path.join(settings.BASE_DIR, 'db.sqlite3'),
        }
    }
    django.setup()

print ("base_dir %s", settings.BASE_DIR)

# https://raw.githubusercontent.com/bear/python-twitter/master/twitter/api.py

# Launch API
keys_file = open(".keys.yaml")
parsed_keys = yaml.load(keys_file, Loader=yaml.SafeLoader)
api = twitter.Api(consumer_key=parsed_keys['API_KEY'],
                  consumer_secret=parsed_keys['API_SECRET'],
                  access_token_key=parsed_keys['TOKEN_KEY'],
                  access_token_secret=parsed_keys['TOKEN_SECRET'])
#                 sleep_on_rate_limit=True)
# api.CreateList('test', 'private', 'Proof of concept')

# Get some verified users, add them to the list
if False:
  ids = api.GetFriendIDs(screen_name='verified', count=5000, total_count=5000)
  users = api.UsersLookup(user_id=ids[0:99], include_entities=False)
  # https://developer.twitter.com/en/docs/tweets/data-dictionary/overview/user-object
  filtered = [{'id':u.id, 'name':u.name, 'desc':u.description, 'v':u.verified} for u in users if not u.protected]
  filtered_ids = [f['id'] for f in filtered]
  api.CreateListsMember(owner_screen_name='scanvine', slug='test', user_id=filtered_ids)

# Get list statuses, filter those with external links
timeline = api.GetListTimeline(owner_screen_name='scanvine', slug='test', count = 400, include_rts=1, return_json=True)
link_statuses = [{'status':t['text'], 'urls':t['entities']['urls']} for t in timeline if len(t['entities']['urls'])>0]
link_statuses = [l for l in link_statuses if json.dumps(l['urls'][0]['expanded_url']).find('twitter')<0]

# Fetch those articles, pull their authors
articles = []
http = urllib3.PoolManager()
for status in link_statuses:
    url = status['urls'][0]['expanded_url']
    try:
        r = http.request('GET', url)
        html = r.data.decode('utf-8')
        soup = BeautifulSoup(html, "html.parser")
        article = {'text':status['status'], 'url':r.geturl(), 'html':html}
        article['initial_url'] = url if url != article['url'] else None
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
        articles.append(article)
    except:
        print("Error handling %s", url)

from public.models import *

# Save the articles

for article in articles:
    a = Article(status=0, url = article['url'], title = article.get('title', ''), contents = article['html'], metadata = {'author': article.get('author', '')})
    a.save()

# Analyze the sentiment

sentiments = []
comprehend = boto3.client(service_name='comprehend')
for article in articles:
    sentiment = comprehend.detect_sentiment(Text=article['text'], LanguageCode='en')
    article['sentiment'] = sentiment['SentimentScore']

# Save the sharer, share, author, etc. to DB as well


