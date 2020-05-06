import datetime, os
import json, urllib3
import twitter # https://raw.githubusercontent.com/bear/python-twitter/master/twitter/api.py
from celery import shared_task, group, signature
from . import article_parsers
from .models import *

if not 'DJANGO_SECRET_KEY' in os.environ:
    from dotenv import load_dotenv
    project_folder = os.path.expanduser('~/dev/private/scanvine')
    load_dotenv(os.path.join(project_folder, '.env'))

# Launch Twitter API
api = twitter.Api(consumer_key=os.getenv('TWITTER_API_KEY', ''),
                  consumer_secret=os.getenv('TWITTER_API_SECRET', ''),
                  access_token_key=os.getenv('TWITTER_TOKEN_KEY', ''),
                  access_token_secret=os.getenv('TWITTER_TOKEN_SECRET', ''))
#                 sleep_on_rate_limit=True)

http = urllib3.PoolManager()


# Get a tranche of verified users, add them to the DB if not there
# https://developer.twitter.com/en/docs/tweets/data-dictionary/overview/user-object
@shared_task(rate_limit="30/h")
def get_potential_sharer_ids():
    job = launch_job("get_potential_sharer_ids")
    # verified_ids_cursor = -1 # TODO move this to runtime scope
    # (verified_ids_cursor, previous_cusor, verified_ids) = api.GetFriendIDs(screen_name='verified', count=5000, cursor = verified_ids_cursor)
    (next, prev, members) = api.GetListMembersPaged(list_id=2129346)
    verified_ids = [u.id for u in members]
    chunks = [verified_ids[i:i + 100] for i in range(0, len(verified_ids), 100)]
    for chunk in chunks:
        add_new_sharers.signature((chunk,)).apply_async()
    log_job(job, "Potential new sharers: %s" % len(verified_ids), Job.Status.COMPLETED)


# Take users from the DB, add them to our Twitter list if not there already
@shared_task(rate_limit="30/h")
def ingest_sharers():
    job = launch_job("ingest_sharers")
    sharers = Sharer.objects.filter(status=Sharer.Status.CREATED)[0:99]
    (next, prev, listed) = api.GetListMembersPaged(list_id=LIST_ID, count=5000, include_entities=False, skip_status=True)
    listed_ids = [u.id for u in listed]
    new_to_list = [s.twitter_id for s in sharers if not s.twitter_id in listed_ids]
    if new_to_list:
        list = api.CreateListsMember(list_id=LIST_ID, user_id=new_to_list)
        for s in sharers:
          s.status = Sharer.Status.LISTED
          s.save()    
    log_job(job, "New to list: %s" % len(new_to_list), Job.Status.COMPLETED)


# Get a tranche of verified users, add them to the DB if not there
# https://developer.twitter.com/en/docs/tweets/data-dictionary/overview/user-object
@shared_task(rate_limit="10/m")
def add_new_sharers(verified_ids):
    job = launch_job("add_new_sharers")
    users = api.UsersLookup(user_id=verified_ids[0:99], include_entities=False)
    filtered = get_sharers_from_users(users)
    new = [f for f in filtered if len(Sharer.objects.filter(twitter_id=f['id']))==0]
    for n in new:
      s = Sharer(twitter_id=n['id'], status=Sharer.Status.CREATED, name=n['name'],
                 twitter_screen_name = n['screen_name'], profile=n['desc'], category=0, verified=True)
      s.save()
    log_job(job, "New sharers: %s" % len(new), Job.Status.COMPLETED)


LIST_ID = 1255581634486648833

# Take users from our Twitter list, add them to the DB if not there already
@shared_task(rate_limit="6/m")
def refresh_sharers():
    job = launch_job("refresh_sharers")
    (next, prev, listed) = api.GetListMembersPaged(list_id=LIST_ID, count=5000, include_entities=False, skip_status=True)
    filtered = get_sharers_from_users(listed)
    new = [f for f in filtered if len(Sharer.objects.filter(twitter_id=f['id']))==0]
    for n in new:
      s = Sharer(twitter_id=n['id'], status=Sharer.Status.LISTED, name=n['name'],
                 twitter_screen_name = n['screen_name'], profile=n['desc'], category=0, verified=True)
      s.save()
    log_job(job, "New sharers: %s" % len(new), Job.Status.COMPLETED)


# Get list statuses, filter those with external links
@shared_task(rate_limit="30/m")
def fetch_shares():
    job = launch_job("fetch_shares")
    timeline = api.GetListTimeline(list_id=LIST_ID, count = 200, include_rts=True, return_json=True)
    log_job(job, "Got %s unfiltered statuses" % len(timeline))
    tweets = [{'id':t['id'], 'user_id':t['user']['id'], 'screen_name':t['user']['screen_name'],
                      'text':t['text'], 'urls':t['entities']['urls']} for t in timeline if len(t['entities']['urls'])>0]
    tweets = [t for t in tweets if json.dumps(t['urls'][0]['expanded_url']).find('twitter')<0]
    log_job(job, "new statuses %s" % len(tweets), Job.Status.LAUNCHED)

    # Fetch those articles, pull their authors
    count = 0
    for tweet in tweets:
        # TODO: handle multiple URLs by picking best one
        url = tweet['urls'][0]['expanded_url']
        url = clean_up_url(url)
    
        # get existing share, if any, for idempotency
        existing = Share.objects.filter(twitter_id=tweet['id'])
        if existing:
            log_job(job, "Share already found %s" % tweet['id'])
            continue
        sharer = Sharer.objects.filter(twitter_id=tweet['user_id'])
        if not sharer:
            log_job(job, "Sharer not found %s %s" % (tweet['user_id'], tweet['screen_name']))
            continue
        sharer = sharer[0]
        s = Share(source=0, language='en', status=Share.Status.CREATED,
                  sharer_id = sharer.id, twitter_id = tweet['id'], text=tweet['text'], url=url)
        s.save()
        count += 1

    log_job(job, "new shares %s" % count, Job.Status.COMPLETED)
    if count > 0:
        associate_articles.signature().apply_async()

@shared_task
def associate_articles():
    job = launch_job("associate_articles")
    shares = Share.objects.filter(status=Share.Status.CREATED)
    for share in shares:
        s = associate_article.signature((share.id,))
        s.apply_async()
    log_job(job, "associating %s articles" % len(shares), Job.Status.COMPLETED)


@shared_task(rate_limit="1/s")
def associate_article(share_id):
    job = launch_job("associate_article")
    share = Share.objects.get(id=share_id)
    existing = Article.objects.filter(initial_url=share.url)
    if existing:
        log_job(job, "existing %s" % share.url, Job.Status.COMPLETED)
        return
    try:
        log_job(job, "Fetching %s" % share.url)
        r = http.request('GET', share.url)
        html = r.data.decode('utf-8')
        final_url =  clean_up_url(r.geturl())
        article = Article(status=Article.Status.CREATED, language='en', url = final_url, initial_url=share.url, contents=html, title='', metadata='')
        article.save()
        share.article_id = article.id
        share.status = Share.Status.ARTICLE_ASSOCIATED
        share.save()
        s = parse_article_metadata.signature((article.id,))
        s.apply_async()
        log_job(job, "associated %s" % share.url, Job.Status.COMPLETED)
    except Exception as ex:
        log_job(job, "Article fetch error %s" % ex, Job.Status.ERROR)
        share.status = Share.Status.FETCH_ERROR
        share.save()


@shared_task()
def parse_unparsed_articles():
    job = launch_job("parse_unparsed_articles")
    articles = Article.objects.filter(status__lte=Article.Status.CREATED)
    for article in articles:
        s = parse_article_metadata.signature((article.id,))
        s.apply_async()
    log_job(job, "parsing %s articles" % len(articles), Job.Status.COMPLETED)
        

@shared_task()
def reparse_publication_articles(publication_id):
    job = launch_job("reparse_publication_articles")
    articles = Article.objects.filter(publication_id = publication_id)
    for article in articles:
        s = parse_article_metadata.signature((article.id,))
        s.apply_async()
    log_job(job, "parsing %s articles" % len(articles), Job.Status.COMPLETED)
        

@shared_task
def parse_article_metadata(article_id):
    job = launch_job("parse_article_metadata")
    article = Article.objects.get(id=article_id)
    log_job(job, "Parsing article %s" % article.url)
    domain = None
    try:
        parsed = urllib3.util.parse_url(article.url)
        domain = parsed.host
        publication = None
        existing = Publication.objects.filter(domain__iexact=domain)
        if existing:
            publication = existing[0]
        else:
            log_job(job, "Creating publication for %s url %s" % (domain, article.url))
            publication = Publication(status=0, name='', domain=domain, average_credibility=0, total_credibility=0)
            publication.save()
        article.publication = publication
        article.status = Article.Status.PUBLISHER_ASSOCIATED
        article.save()
    except Exception as ex1:
        log_job(job, "Publication parse error %s" % ex1)
        article.status = Article.Status.PUBLICATION_PARSE_ERROR
        article.save()

    html = article.contents
    try:
        metadata = parse_article(domain, html)
        article.metadata = metadata if metadata else article.metadata
        article.title = metadata['sv_title'].strip() if 'sv_title' in metadata else article.title
        author = article_parsers.get_author_for(metadata)
        if author:
            article.author_id = author.id
            log_job(job, "Author %s associated to article %s" % (author.name, article.url))
            article.status = Article.Status.AUTHOR_ASSOCIATED
        else:
            article.status = Article.Status.AUTHOR_NOT_FOUND if article.author == None else Article.Status.AUTHOR_ASSOCIATED
        article.save()
    except Exception as ex2:
        log_job(job, "Metadata parse error %s" % ex2, Job.Status.ERROR)
        article.status = Article.Status.METADATA_PARSE_ERROR
        article.save()
        raise ex2

    log_job(job, "Parsed %s" % article.url, Job.Status.COMPLETED)


# Get sentiment from AWS
@shared_task(rate_limit="30/m")
def analyze_sentiment():
    job = launch_job("analyze_sentiment")
    import boto3
    sentiments = []
    comprehend = boto3.client(service_name='comprehend')
    shares = Share.objects.filter(status = Share.Status.ARTICLE_ASSOCIATED)
    for share in shares:
        print("Calling AWS")
        sentiment = comprehend.detect_sentiment(Text=share.text, LanguageCode=share.language)
        score = sentiment['SentimentScore']
        share.sentiment = score
        # very very basic sentiment math
        share.net_sentiment = score['Positive'] - score['Negative'] 
        share.net_sentiment = 0.0 if score['Neutral'] > 0.75 else share.net_sentiment
        share.net_sentiment = -0.01 if score['Mixed'] > 0.75 else share.net_sentiment #flag for later
        share.status = Share.Status.SENTIMENT_CALCULATED
        share.save()
    log_job(job, "analyzed %s sentiments" % len(shares), Job.Status.COMPLETED)


# for each sharer, get list of shares. Shares with +ve or -ve get 2 points, mixed/neutral get 1 point, total N points
# 5040 credibility/day to allocate for maximum divisibility, N points means 5040/N cred for that share, truncate
@shared_task
def allocate_credibility(year=0, month=0, day=0):
    job = launch_job("allocate_credibility")
    date = datetime.date(year, month, day) if year>0 and month>0 and day>0 else datetime.date.today() - datetime.timedelta(days = 1)
    log_job(job, "date %s" % date)
    for sharer in Sharer.objects.all():
        shares = Share.objects.filter(sharer_id=sharer.id, status=Share.Status.SENTIMENT_CALCULATED, net_sentiment__isnull=False, created_at=date)
        if not shares:
            continue
        total_points = 0
        for s in shares:
            total_points += s.share_points()
        if total_points==0:
            continue
        cred_per_point = 5040 // total_points
        for share in shares:
            article = share.article
            author = share.author
            if not share.article or not share.author:
                continue
            share_cred = cred_per_point * s.share_points()
            t = Tranche(source=0, status=0, type=0, tags='', category=sharer.category, sender=sharer.id, receiver=share.id, quantity = share_cred)
            t.save()
            s.status = Share.Status.CREDIBILITY_ALLOCATED
            s.save()
    log_job(job, "allocated", Job.Status.COMPLETED)


# for each share with credibility allocated: get publication and author associated with that share, calculate accordingly
@shared_task
def set_reputations():
    shares = Share.objects.filter(status=Share.Status.CREDIBILITY_ALLOCATED)
    for share in shares:
        tranche = Tranche.objects.get(receiver=share.id)
        article = share.article
        author = article.author
        if author is not None:
            author.total_credibility += tranche.quantity
            author.current_credibility += tranche.quantity
            author.save()
        publication = article.publication
        if publication is not None:
            publication.total_credibility += tranche.quantity
            publication.average_credibility += publication.total_credibility / Article.objects.count(publication_id=publication.id)
            publication.save()
        share.status = Share.Status.AGGREGATES_UPDATED


@shared_task
def recalculate_credibility(share_id, new_quantity):
    tranche = Tranche.objects.get(receiver=share_id)
    old_quantity = tranche_quantity
    tranche.quantity = new_quantity
    tranche.save()
    article = share.article
    author = article.author
    if author is not None:
        author.total_credibility += new_quantity - old_quantity
        author.current_credibility += new_quantity - old_quantity
        author.save()
        publication = article.publication
    if publication is not None:
        publication.total_credibility += new_quantity - old_quantity
        publication.average_credibility += publication.total_credibility / Publication.objects.count()
        publication.save()
    
    

from bs4 import BeautifulSoup
def parse_article(domain, html):
    soup = BeautifulSoup(html, "html.parser")
    metadata = {'sv_title' : soup.title.string}
    
    # default to generic parsing by meta tags and application-LD
    default_parser_rule_string = '[{"method":"meta_parser"}, {"method":"json_ld_parser"}]'
    default_parser_rules = json.loads(default_parser_rule_string)
    
    # can override on per-publication basis
    parser_rules = default_parser_rules
    publications = Publication.objects.filter(domain__iexact=domain)
    if publications:
        parser_rule_string = publications[0].parser_rules
        if parser_rule_string:
            parser_rules = default_parser_rules + json.loads(parser_rule_string)

    author = None
    for rule in parser_rules:
        parser = getattr(article_parsers, rule['method'])
        retval = parser(soup=soup)
        author = get_author_from(metadata, retval)
        metadata.update(retval)

    print("author %s" % author)
    if author:
        metadata['sv_author'] = author

    return metadata

def get_sharers_from_users(users):
    filtered = [{'id':u.id, 'name':u.name, 'screen_name':u.screen_name, 'desc':u.description, 'v':u.verified} for u in users if not u.protected]
    # TODO: only get desired users
    return filtered

def get_author_from(existing, metadata):
    oldval = existing['sv_author'] if 'sv_author' in existing else None
    newval = metadata['sv_author'] if 'sv_author' in metadata else None
    print("newval %s" % newval)
    if not newval:
        return oldval
    if type(newval) is list:
        names = [x['name'] if type(x) is dict and 'name' in x else x for x in inner]
        return names[0] if len(names)==1 else ','.join(names)
    elif type(newval) is dict:
        newval = newval['name'] if 'name' in newval else None
    if not oldval:
        return newval
    if newval.startswith("[") or newval.startswith("{"):
        return oldval
    return newval
    
    
def launch_job(name):
    job = Job(status = Job.Status.LAUNCHED, name=name, actions='')
    job.save()
    return job

def log_job(job, action, status = None):
    if status is not None:
        job.status = status
    job.actions = action + " \n" + job.actions
    job.save();
    print(action)

def clean_up_url(url):
    # TODO: filter out url cruft more elegantly, depending on site
    if url.find("youtube.com") >= 0:
        return url
    return url.partition("?")[0]

def add_tweet(tweet_id):
    tweet = api.GetStatus(tweet_id, include_entities=True)
    sharer = Sharer.objects.filter(twitter_id=tweet.user.id)
    if sharer:
        sharer = sharer[0]
    else:
        sharer = Sharer(twitter_id=tweet.user.id, status=Sharer.Status.CREATED, name=tweet.user.name,
                 twitter_screen_name = tweet.user.screen_name, profile=tweet.user.description, category=0, verified=True)
        sharer.save()
    share = Share.objects.filter(twitter_id=tweet.id)
    if share:
        share = share[0]
    else:
        share = Share(source=0, language='en', status=Share.Status.CREATED, twitter_id = tweet.id)
    share.sharer_id = sharer.id
    share.text = tweet.text
    print("Urls %s" % tweet)
    share.url = tweet.urls[0].expanded_url
    share.save()
    associate_article(share.id)

def reparse_share(share_id):
    share = Share.objects.get(id=share_id)
    add_tweet(share.twitter_id)
