import os
import json
import urllib3
import twitter # https://raw.githubusercontent.com/bear/python-twitter/master/twitter/api.py
from celery import shared_task, group, signature
from .article_parsers import *
from .models import *

if not 'DJANGO_SECRET_KEY' in os.environ:
    from dotenv import load_dotenv
    project_folder = os.path.expanduser('~/dev/private/scanvine')
    load_dotenv(os.path.join(project_folder, '.env'))

# Launch Twitter API - TODO move this to TwitterService?
api = twitter.Api(consumer_key=os.getenv('TWITTER_API_KEY', ''),
                  consumer_secret=os.getenv('TWITTER_API_SECRET', ''),
                  access_token_key=os.getenv('TWITTER_TOKEN_KEY', ''),
                  access_token_secret=os.getenv('TWITTER_TOKEN_SECRET', ''))
#                 sleep_on_rate_limit=True)

http = urllib3.PoolManager()


# Get a tranche of verified users, add them to the DB if not there
# https://developer.twitter.com/en/docs/tweets/data-dictionary/overview/user-object
@shared_task
def get_potential_sharer_ids():
    job = log_job("get_potential_sharer_ids")
    # verified_ids_cursor = -1 # TODO move this to runtime scope
    # (verified_ids_cursor, previous_cusor, verified_ids) = api.GetFriendIDs(screen_name='verified', count=5000, cursor = verified_ids_cursor)
    (next, prev, members) = api.GetListMembersPaged(list_id=2129346)
    verified_ids = [u.id for u in members]
    chunks = [verified_ids[i:i + 100] for i in range(0, len(verified_ids), 100)]
    for chunk in chunks:
        add_new_sharers.signature((chunk,)).apply_async
    log_job("Potentialew sharers: %s" % len(verified_ids), job, Job.Status.COMPLETED)

# Get a tranche of verified users, add them to the DB if not there
# https://developer.twitter.com/en/docs/tweets/data-dictionary/overview/user-object
@shared_task
def add_new_sharers(verified_ids):
    job = log_job("add_new_sharers")
    users = api.UsersLookup(user_id=verified_ids[0:99], include_entities=False)
    filtered = get_sharers_from_users(users)
    new = [f for f in filtered if len(Sharer.objects.filter(twitter_id=f['id']))==0]
    for n in new:
      s = Sharer(twitter_id=n['id'], status=Sharer.Status.CREATED, name=n['name'],
                 twitter_screen_name = n['screen_name'], profile=n['desc'], category=0, verified=True)
      s.save()
    log_job("New sharers: %s" % len(new), job, Job.Status.COMPLETED)


LIST_ID = 1255581634486648833

# Take users from the DB, add them to our Twitter list if not there already
@shared_task
def refresh_sharers():
    job = log_job("refresh_sharers")
    (next, prev, listed) = api.GetListMembersPaged(list_id=LIST_ID, count=5000, include_entities=False, skip_status=True)
    filtered = get_sharers_from_users(listed)
    new = [f for f in filtered if len(Sharer.objects.filter(twitter_id=f['id']))==0]
    for n in new:
      s = Sharer(twitter_id=n['id'], status=Sharer.Status.LISTED, name=n['name'],
                 twitter_screen_name = n['screen_name'], profile=n['desc'], category=0, verified=True)
      s.save()
    log_job("New sharers: %s" % len(new), job, Job.Status.COMPLETED)


# Take users from the DB, add them to our Twitter list if not there already
@shared_task
def ingest_sharers():
    job = log_job("ingest_sharers")
    sharers = Sharer.objects.filter(status=Sharer.Status.CREATED)[0:99]
    (next, prev, listed) = api.GetListMembersPaged(list_id=LIST_ID, count=5000, include_entities=False, skip_status=True)
    listed_ids = [u.id for u in listed]
    new_to_list = [s.twitter_id for s in sharers if not s.twitter_id in listed_ids]
    if new_to_list:
        list = api.CreateListsMember(list_id=LIST_ID, user_id=new_to_list)
        for s in sharers:
          s.status = Sharer.Status.LISTED
          s.save()    
    log_job("New to list: %s" % len(new_to_list), job, Job.Status.COMPLETED)


# Get list statuses, filter those with external links
@shared_task
def fetch_shares():
    job = log_job("fetch_shares")
    timeline = api.GetListTimeline(list_id=LIST_ID, count = 200, include_rts=True, return_json=True)
    print("Got %s unfiltered statuses" % len(timeline))
    link_statuses = [{'id':t['id'], 'user_id':t['user']['id'], 'screen_name':t['user']['screen_name'],
                      'text':t['text'], 'urls':t['entities']['urls']} for t in timeline if len(t['entities']['urls'])>0]
    link_statuses = [l for l in link_statuses if json.dumps(l['urls'][0]['expanded_url']).find('twitter')<0]

    log_job("new statuses %s" % len(link_statuses), job, Job.Status.LAUNCHED)

    # Fetch those articles, pull their authors
    new_share_count = 0
    for status in link_statuses:
        # print('status %s' % status['text'])
        # TODO: handle multiple URLs
        url = status['urls'][0]['expanded_url']
        # TODO: filter out url cruft more elegantly, depending on site eg not for YouTube
        url = url.partition("?")[0]
    
        # get existing share, if any, for idempotency
        existing = Share.objects.filter(twitter_id=status['id'])
        if existing:
            continue
        sharer = Sharer.objects.filter(twitter_id=status['user_id'])
        if not sharer:
            print("Sharer not found %s %s" % (status['user_id'], status['screen_name']))
            continue
        sharer = sharer[0]
        s = Share(source=0, language='en', status=Share.Status.CREATED,
                  sharer_id = sharer.id, twitter_id = status['id'], text=status['text'], url=url)
        s.save()
        new_share_count += 1

    log_job("new shares %s" % new_share_count, job, Job.Status.COMPLETED)


@shared_task
def associate_articles():
    job = log_job("associate_articles")
    for share in Share.objects.filter(status=Share.Status.CREATED):
        s = associate_article.signature((share.id,))
        s.apply_async()


@shared_task
def associate_article(share_id):
    job = log_job("associate_article")
    share = Share.objects.get(id=share_id)
    existing = Article.objects.filter(initial_url=share.url)
    if existing:
        job = log_job("existing %s" % share.url, job, Job.Status.COMPLETED)
        return
    try:
        print("Fetching %s" % share.url)
        r = http.request('GET', share.url)
        html = r.data.decode('utf-8')
        article = Article(status=Article.Status.CREATED, language='en', url = r.geturl(), initial_url=share.url, contents=html, title='', metadata='')
        article.save()
        share.article_id = article.id
        share.status = Share.Status.ARTICLE_ASSOCIATED
        share.save()
        s = parse_article_metadata.signature((article.id,))
        s.apply_async()
        log_job("associated %s" % share.url, job, Job.Status.COMPLETED)
    except Exception as ex:
        print("Article fetch error %s" % ex)
        share.status = Share.Status.FETCH_ERROR
        share.save()
        log_job("error %s" % ex, job, Job.Status.COMPLETED)


@shared_task()
def parse_unparsed_articles():
    job = log_job("parse_unparsed_articles")
    articles = Article.objects.filter(status__lte=Article.Status.CREATED)
    for article in articles:
        s = parse_article_metadata.signature((article.id,))
        s.apply_async()
    log_job("parsed %s articles" % len(articles), job, Job.Status.COMPLETED)
        

@shared_task
def parse_article_metadata(article_id):
    job = log_job("parse_article_metadata")
    article = Article.objects.get(id=article_id)
    print("Parsing article %s" % article.url)
    domain = None
    try:
        parsed = urllib3.util.parse_url(article.url)
        domain = parsed.host
        publication = None
        existing = Publication.objects.filter(domain=domain)
        if existing:
            publication = existing[0]
        else:
            print("Creating publication for %s url %s" % (domain, article.url))
            publication = Publication(status=0, name='', domain=domain, average_credibility=0, total_credibility=0)
            publication.save()
        article.publication = publication
        article.status = Article.Status.PUBLISHER_ASSOCIATED
        article.save()
    except Exception as ex1:
        print("Publication parse error %s" % ex1)
        article.status = Article.Status.PUBLICATION_PARSE_ERROR
        article.save()

    html = article.contents
    try:
        metadata = parse_article(domain, html)
        article.metadata = metadata if metadata else article.metadata
        article.title = metadata['title'] if 'title' in metadata else article.title
        author_name = metadata['author'] if 'author' in metadata else None
        if author_name:
            author = None
            existing = Author.objects.filter(name=author_name)
            if existing:
                author = existing[0]
            if not existing:
                author=Author(status=Author.Status.CREATED, name=author_name, is_collaboration=False, metadata='{}', current_credibility=0, total_credibility=0)
                author.save()
            article.author_id = author.id
            print("Author associated to article %s" % article.url)
            article.status = Article.Status.AUTHOR_ASSOCIATED
        else:
            article.status = Article.Status.AUTHOR_NOT_FOUND if article.author == None else Article.Status.AUTHOR_ASSOCIATED
        article.save()
    except Exception as ex2:
        print("Metadata parse error %s for %s" % (ex2, article.url))
        article.status = Article.Status.METADATA_PARSE_ERROR
        article.save()
        raise ex2


# Get sentiment from AWS
@shared_task
def analyze_sentiment():
    job = log_job("analyze_sentiment")
    import boto3
    sentiments = []
    comprehend = boto3.client(service_name='comprehend')
    shares = Share.objects.filter(status = Share.Status.ARTICLE_ASSOCIATED)
    for share in shares:
        print("Calling AWS")
        sentiment = comprehend.detect_sentiment(Text=share.text, LanguageCode=share.language)
        score = sentiment['SentimentScore']
        share.sentiment = score
        # very basic sentiment math
        share.net_sentiment = score['Positive'] - score['Negative']
        share.net_sentiment = 0.0 if score['Neutral'] > 0.5 else share.net_sentiment
        share.net_sentiment = -0.01 if score['Mixed'] > 0.5 else share.net_sentiment #flag for later
        share.status = Share.Status.SENTIMENT_CALCULATED
        share.save()
    log_job("analyzed %s sentiments" % len(shares), job, Job.Status.COMPLETED)


# crude initial algorithm:
# for each sharer, get list of shares
# shares with +ve or -ve get 2 points, mixed/neutral get 1 point, total N points
# 5040 credibility/day for maximum divisibility, N points means 5040/N cred for that share, truncate
@shared_task
def allocate_credibility():
    job = log_job("allocate_credibility")
    for sharer in Sharer.objects.all():
        shares = Share.objects.filter(sharer_id=sharer.id, status=Share.Status.SENTIMENT_CALCULATED, net_sentiment__isnull=False)
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
            t = Tranche(source=0, status=0, tags='', sender=sharer.id, receiver=author.id, quantity = share_cred, category=sharer.category, type=author.status)
            t.save()
            s.status = Share.Status.CREDIBILITY_ALLOCATED
            s.save()
    log_job("allocated", job, Job.Status.COMPLETED)
            

from bs4 import BeautifulSoup
def parse_article(domain, html):
    soup = BeautifulSoup(html, "html.parser")
    metadata = {'title' : soup.title.string}
    
    # custom parsing not applicable, let's try generic parsing
    if html.find("application/ld+json") > 0:
        metadata.update(json_ld_parser(soup))
    
    if html.find("<meta ") > 0:
        metadata = meta_parser(soup)

    # get parser from db
    parser_rules = ''
    publications = Publication.objects.filter(domain=domain)
    if publications:
        parser_rules = publications[0].parser_rules
    #special case for dev/test
    parser_rules = "{'method':'npr_parser'}" if domain=='npr.org' and not publications else parser_rules
    if parser_rules:
        parser_values = json.loads(parser_rules)
        method = parser_values['method']
        parser = locals()[method]
        metadata.update(parser(soup))
    
    return metadata

def get_sharers_from_users(users):
    filtered = [{'id':u.id, 'name':u.name, 'screen_name':u.screen_name, 'desc':u.description, 'v':u.verified} for u in users if not u.protected]
    # TODO: only get desired users
    return filtered
    
def log_job(action, job = None, status = None):
    if job is None:
        job = Job(status = Job.Status.LAUNCHED, actions='')
    job.status = job.status if status == None else status
    job.actions = action + " \n" + job.actions
    job.save();
    return job
