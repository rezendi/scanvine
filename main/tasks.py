import datetime, os, traceback
import html, json, urllib3
import twitter # https://raw.githubusercontent.com/bear/python-twitter/master/twitter/api.py
from django.utils import timezone
from django.db.models import Q, Sum, Avg, IntegerField
from django.db.models.functions import Abs, Cast
from django.contrib.postgres.fields.jsonb import KeyTextTransform
from celery import shared_task, group, signature
from bs4 import BeautifulSoup
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
                  access_token_secret=os.getenv('TWITTER_TOKEN_SECRET', ''),
                  tweet_mode='extended')
#                 sleep_on_rate_limit=True)

import boto3
comprehend = boto3.client(service_name='comprehend',
                          aws_access_key_id=os.getenv('AWS_API_KEY', ''),
                          aws_secret_access_key=os.getenv('AWS_API_SECRET', ''),
                          region_name='us-west-2')

http = urllib3.PoolManager(10, timeout=30.0)
# are these really necessary?
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/72.0.3626.121 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/12.1.1 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/64.0.3282.140 Safari/537.36 Edge/17.17134',
    'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:54.0) Gecko/20100101 Firefox/54.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/69.0.3497.100 Safari/537.36 OPR/56.0.3051.52',
]


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
                       name=n.name.replace('\x00',''), profile=n.description.replace('\x00',''), category=0, verified=True)
            s.save()
        log_job(job, "New sharers: %s" % len(new), Job.Status.COMPLETED)
        log_job(job, "%s" % verified_cursor, Job.Status.COMPLETED)
    except Exception as ex:
        log_job(job, "Potential sharer fetch error %s" % ex, Job.Status.ERROR)


LIST_IDS = [1259645675878281217, 1259645744249581569, 1259645776315117568, 1259645804853080064, 1259645832619372544]

# Take users from the DB, add them to our Twitter list if not there already
@shared_task(rate_limit="30/h")
def ingest_sharers():
    job = launch_job("ingest_sharers")
    category = timezone.now().microsecond % len(LIST_IDS)
    # TODO clean back up
    category = 0 if category in [1,2] else category
    category = 4 if category == 3 else category
    twitter_list_id = LIST_IDS[category]
    try:
        selected = Sharer.objects.filter(category=category, status=Sharer.Status.SELECTED).order_by("-twitter_id")[0:99]
        if selected:
            selected_ids = [s.twitter_id for s in selected]
            retval = api.CreateListsMember(list_id=twitter_list_id, user_id=selected_ids)
            log_job(job, "add retval %s" % retval)
            for s in selected:
              s.status = Sharer.Status.LISTED
              s.twitter_list_id = twitter_list_id
              s.save()    
        log_job(job, "Added to list %s: %s" % (category, len(selected)), Job.Status.COMPLETED)
    except Exception as ex:
        log_job(job, traceback.format_exc())
        log_job(job, "Ingest sharers error %s" % ex, Job.Status.ERROR)
        raise ex

@shared_task(rate_limit="30/h")
def regurgitate_sharers():
    job = launch_job("regurgitate_sharers")
    category = timezone.now().microsecond % len(LIST_IDS)
    twitter_list_id = LIST_IDS[category]
    deselected = Sharer.objects.filter(category=category).filter(status=Sharer.Status.DESELECTED, twitter_list_id__isnull=False)[0:99]
    if deselected:
        deselected_ids = [s.twitter_id for s in deselected]
        retval = api.DestroyListsMember(list_id=twitter_list_id, user_id=deselected_ids)
        log_job(job, "del retval %s" % retval)
        for s in deselected:
          s.twitter_list_id = None
          s.save()    
        log_job(job, "Removed from list %s: %s" % (category, len(deselected)), Job.Status.COMPLETED)

# Get users from our Twitter list, add them to the DB if not there already, fix those tagged as listed
@shared_task(rate_limit="6/m")
def refresh_sharers():
    job = launch_job("refresh_sharers")
    category = timezone.now().microsecond % len(LIST_IDS)
    (next, prev, listed) = api.GetListMembersPaged(list_id=LIST_IDS[category], count=4000, include_entities=False, skip_status=True)
    log_job(job, "total in category %s %s" % (category, len(listed)))
    new = [l for l in listed if len(Sharer.objects.filter(twitter_id=l.id))==0]
    for n in new:
        s = Sharer(status=Sharer.Status.LISTED, twitter_id=n.id, twitter_list_id=LIST_IDS[category], category=category,
                   twitter_screen_name=n.screen_name, name=n.name, profile=n.description, verified=True)
        s.save()
    log_job(job, "New sharers: %s" % len(new))

    # move those not actually listed to selected
    ids =[l.id for l in listed]
    mislabelled_listed = Sharer.objects.filter(status=Sharer.Status.LISTED,category=category).exclude(twitter_id__in=ids)
    for sharer in mislabelled_listed:
        sharer.twitter_list_id = None
        sharer.status = Sharer.Status.SELECTED
        sharer.save()
    log_job(job, "Mislabelled listed sharers: %s" % len(mislabelled_listed))

    # move those actually listed to listed
    mislabelled_selected = Sharer.objects.exclude(status=Sharer.Status.LISTED).filter(category=category, twitter_id__in=ids)
    for sharer in mislabelled_selected:
        sharer.twitter_list_id = LIST_IDS[category]
        sharer.status = Sharer.Status.LISTED
        sharer.save()
    log_job(job, "Mislabelled selected sharers: %s" % len(mislabelled_selected))

    log_job(job, "Category %s refreshed" % category, Job.Status.COMPLETED)


# Get list statuses, filter those with external links
@shared_task(rate_limit="30/m")
def fetch_shares():
    job = launch_job("fetch_shares")
    since_id = None
    list_id = LIST_IDS[0]
    try:
        # get data from previous job, if any
        previous_jobs = Job.objects.filter(status=Job.Status.COMPLETED).filter(name="fetch_shares").order_by("-created_at")[0:10]
        if previous_jobs:
            for action in previous_jobs[0].actions.split("\n"):
                if action.startswith("list_id="):
                    latest_list_id = int(action.partition("=")[2])
                    idx = LIST_IDS.index(latest_list_id) if latest_list_id in LIST_IDS else -1
                    list_id = LIST_IDS[(idx+1) % len(LIST_IDS)]
        log_job(job, "list_id=%s" % list_id)

        previous_jobs = Job.objects.filter(status=Job.Status.COMPLETED).filter(name="fetch_shares").filter(actions__iregex=r"%s" % list_id).order_by("-created_at")[0:1]
        if previous_jobs:
            for action in previous_jobs[0].actions.split("\n"):
                if action.startswith("max_id="):
                    since_id = int(action.partition("=")[2])
    
        # fetch the timeline, log its values
        timeline = api.GetListTimeline(list_id=list_id, count = 200, since_id = since_id, include_rts=True, include_entities = True, return_json=True)
        log_job(job, "Got %s unfiltered tweets from list %s" % (len(timeline), LIST_IDS.index(list_id)))
        tweets = []
        for t in timeline:
            urls = t['entities']['urls']
            if 'quoted_status' in t:
                urls += t['quoted_status']['entities']['urls']
            if 'retweeted_status' in t:
                urls += t['retweeted_status']['entities']['urls']
            urls = [u['expanded_url'] for u in urls]
            urls = [u for u in urls if not u.startswith("https://twitter.com/") and not u.startswith("https://mobile.twitter.com/")]
            if urls:
                user = t['user']
                tweet = {'id':t['id'], 'user_id':user['id'], 'screen_name':user['screen_name'], 'text':t['full_text'], 'urls':urls}
                tweets.append(tweet)
        log_job(job, "external link tweets %s" % len(tweets))
        if timeline:
            log_job(job, "max_id=%s" % timeline[0]['id'])
            log_job(job, "min_id=%s" % timeline[-1]['id'])
        elif since_id:
            log_job(job, "max_id=%s" % since_id)
    
        # Store new shares to DB
        count = 0
        for tweet in tweets:
            # TODO: handle multiple viable URLs by picking best one
            url = clean_up_url(tweet['urls'][0])
        
            # get existing share, if any, for idempotency
            existing = Share.objects.filter(twitter_id=tweet['id'])
            if existing:
                log_job(job, "Share already found %s" % tweet['id'])
                continue
            sharer = Sharer.objects.filter(twitter_id=tweet['user_id'], status=Sharer.Status.LISTED)
            if not sharer:
                log_job(job, "Sharer not found %s %s" % (tweet['user_id'], tweet['screen_name']))
                continue
            sharer = sharer[0]
            if len(str(url))>=1024:
                url = str(url)[0:1023]
            s = Share(source=0, language='en', status=Share.Status.CREATED, category=sharer.category,
                      sharer_id = sharer.id, twitter_id = tweet['id'], text=tweet['text'], url=url)
            s.save()
            count += 1
    
        log_job(job, "new shares %s" % count, Job.Status.COMPLETED)
        
        # Launch follow-up job to fetch associated articles
        if count > 0:
            associate_articles.signature().apply_async()

    except Exception as ex:
        log_job(job, traceback.format_exc())
        log_job(job, "Fetch shares error %s" % ex, Job.Status.ERROR)
        raise ex

@shared_task
def associate_articles():
    job = launch_job("associate_articles")
    shares = Share.objects.filter(status=Share.Status.CREATED)
    for share in shares:
        s = associate_article.signature((share.id,))
        s.apply_async()
    log_job(job, "associating %s articles" % len(shares), Job.Status.COMPLETED)


@shared_task(rate_limit="1/s")
def associate_article(share_id, force_refetch=False):
    job = launch_job("associate_article")
    share = Share.objects.get(id=share_id)
    existing = Article.objects.filter(initial_url=share.url)
    existing = Article.objects.filter(url=share.url) if not existing else existing
    if existing:
        share.article_id = existing[0].id
        share.status = Share.Status.ARTICLE_ASSOCIATED
        share.save()
        if not force_refetch:
            log_job(job, "article exists for %s" % share.url, Job.Status.COMPLETED)
            return
    try:
        # let's get the url, the final url, and the final final url
        url = existing[0].initial_url if existing else share.url
        log_job(job, "Fetching %s" % url)
        r = http.request('GET', share.url, headers={'User-Agent': USER_AGENTS[timezone.now().microsecond % len(USER_AGENTS)]})
        contents = r.data.decode('utf-8') # TODO other encodings
        final_url = clean_up_url(r.geturl(), contents)
        final_host = urllib3.util.parse_url(final_url).host
        if final_host is None:
            initial_host = urllib3.util.parse_url(share.url).host
            initial_host = "medium.com" if initial_host == "link.medium.com" else initial_host
            final_url = "https://%s%s" % (initial_host, final_url)
        if final_host != urllib3.util.parse_url(r.geturl()).host:
            r = http.request('GET', final_url, headers={'User-Agent': USER_AGENTS[timezone.now().microsecond % len(USER_AGENTS)]})
            contents = r.data.decode('utf-8')
        if final_url.find("/amp") > 0:
            soup = BeautifulSoup(contents, "html.parser")
            canonical_link = soup.find("link", {"rel":"canonical"})
            if canonical_link and 'href' in canonical_link.attrs:
                final_url = canonical_link['href']
                r = http.request('GET', final_url, headers={'User-Agent': USER_AGENTS[timezone.now().microsecond % len(USER_AGENTS)]})
                contents = r.data.decode('utf-8')

        print("Accessing article, final_url %s" % final_url)
        existing = Article.objects.filter(url=final_url) if not existing else existing
        article = existing[0] if existing else Article(status=Article.Status.CREATED, language='en', url = final_url, initial_url=share.url, title='', metadata='')
        article.contents=contents
        article.url=final_url
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
def reparse_articles():
    job = launch_job("reparse_articles")
    previous_jobs = Job.objects.filter(status=Job.Status.COMPLETED).filter(name="reparse_articles").order_by("-created_at")
    if previous_jobs:
        last_id_string = previous_jobs[0].actions.partition("\n")[0]
        last_id_string = '' if not last_id_string else last_id_string
        last_id = int("".join(filter(str.isdigit, last_id_string)))
    page_size = 100
    articles = Article.objects.filter(status__gt=Article.Status.CREATED)
    if last_id:
        articles = articles.filter(id__lt=last_id)
    articles = articles.order_by("-id")[:page_size]
    log_job(job, "Reparsing %s articles" % len(articles), Job.Status.COMPLETED)
    new_last_id = last_id
    for article in articles:
        if len(article.title) > 32:
            duplicates = Article.objects.exclude(Q(id=article.id) | Q(status=Article.Status.POTENTIAL_DUPLICATE)).filter(title=article.title)
            if duplicates:
                article.status = Article.Status.POTENTIAL_DUPLICATE
                article.save()
        new_last_id = article.id
        if article.status > Article.Status.CREATED: # if not a duplicate
            s = parse_article_metadata.signature((article.id,))
            s.apply_async()
    if len(articles) < page_size:
        new_last_id='0'
    log_job(job, "%s" % new_last_id, Job.Status.COMPLETED)
        

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

        if not article.contents:
            log_job(job, "No contents in article %s" % article.id, Job.Status.ERROR)
            article.status = Article.Status.METADATA_PARSE_ERROR
            return

        metadata = parse_article(article.contents, domain)
        pub_name = metadata['sv_publication'] if 'sv_publication' in metadata else ''
        if pub_name and not publication.name:
            publication.name = pub_name.title()
            publication.save()

        article.metadata = metadata if metadata else article.metadata
        article.title = html.unescape(metadata['sv_title'].strip()) if 'sv_title' in metadata and metadata['sv_title'] else article.title
        article.published_at = datetime.datetime.fromisoformat(metadata['sv_pub_date']) if 'sv_pub_date' in metadata else article.published_at
        article.thumbnail_url = metadata['sv_image'] if 'sv_image' in metadata and len(metadata['sv_image'])<1024 else ''
        author = article_parsers.get_author_for(metadata, article.publication)
        if author:
            article.author_id = author.id
            log_job(job, "Author %s associated to article %s" % (author.name, article.url))
            article.status = Article.Status.AUTHOR_ASSOCIATED
        else:
            article.author_id = None
            article.status = Article.Status.AUTHOR_NOT_FOUND if article.author == None else Article.Status.AUTHOR_ASSOCIATED
        article.save()

        if author and len(author.name) > 6:
            for share in Share.objects.filter(article_id=article.id):
                if share.sharer_id and share.sharer.name == author.name:
                    Tranche.objects.filter(receiver=share.id).delete()
                    share.status = Share.Status.SELF_SHARE
                    share.save()

    except Exception as ex2:
        log_job(job, "Article parse error %s" % ex2, Job.Status.ERROR)
        article.status = Article.Status.METADATA_PARSE_ERROR
        article.save()
        raise ex2

    log_job(job, "Parsed %s" % article.url, Job.Status.COMPLETED)


# Get sentiment from AWS
@shared_task(rate_limit="12/m")
def analyze_sentiment():
    try:
        job = launch_job("analyze_sentiment")
        sentiments = []
        shares = Share.objects.filter(status = Share.Status.ARTICLE_ASSOCIATED).filter(language='en')[0:25]
        if not shares:
            log_job(job, "No new shares to analyze", Job.Status.COMPLETED)
            return
        texts = [s.text for s in shares]
        print("Calling AWS")
        sentiments = comprehend.batch_detect_sentiment(TextList=texts, LanguageCode='en')
        for result in sentiments['ResultList']:
            idx = result['Index']
            share = shares[idx]
            share.calculate_sentiment(result['SentimentScore'])
            share.status = Share.Status.SENTIMENT_CALCULATED
            share.save()
        for error in sentiments['ErrorList']:
            log_job(job, "Sentiment error %s" % result['ErrorMessage'])
            idx = result['Index']
            share = shares[idx]
            share.status = Share.Status.SENTIMENT_ERROR
            share.sentiment = str(result)
            share.save()
        job_status = Job.Status.ERROR if len(sentiments['ErrorList']) > 0 and len(sentiments['ResultList']) == 0 else Job.Status.COMPLETED
        log_job(job, "analyzed %s sentiments %s errors" % (len(sentiments['ResultList']), len(sentiments['ErrorList'])), job_status)
    except Exception as ex:
        log_job(job, "Analyze sentiment error %s" % ex, Job.Status.ERROR)
        raise ex


# for each sharer, get list of shares. Shares with +ve or -ve get 2 points, mixed/neutral get 1 point, total N points
# 5040 credibility/day to allocate for maximum divisibility, N points means 5040/N cred for that share, truncate
@shared_task(rate_limit="1/m", soft_time_limit=1800)
def allocate_credibility(date=timezone.now(), days=7):
    job = launch_job("allocate_credibility")
    end_date = date + datetime.timedelta(minutes=5) # in case DB time off from server time
    start_date = end_date - datetime.timedelta(days=days)
    log_job(job, "date range %s - %s" % (start_date, end_date))
    cred_per_point = 1008
    try:
        total_sharers = current_sharer_id = total_cred = 0
        shares = Share.objects.annotate(abs_sentiment = Abs("net_sentiment")).filter(
            status__gte=Share.Status.SENTIMENT_CALCULATED, created_at__range=(start_date, end_date)
        ).order_by("sharer_id", "-abs_sentiment")
        log_job(job, "total shares analyzed %s" % len(shares))
        for share in shares:
            if share.sharer_id != current_sharer_id:
                article_ids = set()
                total_sharers
            current_sharer_id = share.sharer_id
            existing = Tranche.objects.filter(sender=share.sharer_id, receiver=share.id)
            if share.article_id in article_ids:
                if existing:
                    existing[0].delete()
                continue
            share_cred = cred_per_point * share.share_points()
            article_ids.add(share.article_id)
            total_cred += share_cred
            if existing:
                tranche = existing[0]
                if tranche.category != share.category or tranche.quantity != share_cred:
                    tranche.category = share.category
                    tranche.quantity = share_cred
                    tranche.save()
            else:
                tranche = Tranche(source=0, status=0, type=0, tags='', category=share.category, sender=share.sharer_id, receiver=share.id, quantity = share_cred)
                tranche.save()
            share.status = Share.Status.CREDIBILITY_ALLOCATED
            share.save()
    except Exception as ex:
        log_job(job, traceback.format_exc())
        log_job(job, "Allocate credibility error %s" % ex, Job.Status.ERROR)
        raise ex
    log_job(job, "allocated %s to %s sharers" % (total_cred, total_sharers), Job.Status.COMPLETED)



CATEGORIES = ['health', 'science', 'tech', 'business', 'media']
# for each share with credibility allocated: get publication and author associated with that share, calculate accordingly
@shared_task(rate_limit="1/m", soft_time_limit=1800)
def set_scores(date=timezone.now(), days=30):
    job = launch_job("set_scores")
    end_date = date + datetime.timedelta(minutes=5) # in case DB time off from server time
    start_date = end_date - datetime.timedelta(days=days)
    log_job(job, "date range %s - %s" % (start_date, end_date))
    articles_dict = {}
    authors_dict = {}
    publications_dict = {}
    total_quantity = 0
    total_tranches = 0
    try:
        #TODO do this as a big three-table join
        shares = Share.objects.filter(status=Share.Status.CREDIBILITY_ALLOCATED).filter(created_at__range=(start_date, end_date)).values('id','sharer_id','article_id')
        log_job(job, "shares %s" % len(shares))
        for share in shares:
            tranches = Tranche.objects.filter(sender=share['sharer_id'], receiver=share['id'])
            if not tranches:
                continue
            if len(tranches) > 1:
                log_job(job, "Extraneous tranche found for %s %s" % (share['sharer_id'], share['id']))
            total_tranches += 1
            tranche = tranches[0]
            article_id = share['article_id']
            if not article_id in articles_dict:
                articles_dict[article_id] = {}
                for key in ['total'] + CATEGORIES:
                    articles_dict[article_id][key] = 0
            articles_dict[article_id]['total'] = articles_dict[article_id]['total'] + tranche.quantity
            category = CATEGORIES[tranche.category]
            articles_dict[article_id][category] = articles_dict[article_id][category] + tranche.quantity
            total_quantity += tranche.quantity
    
        log_job(job, "articles %s" % len(articles_dict))
        for article in Article.objects.filter(id__in=articles_dict.keys(), author_id__isnull=False).defer('url','initial_url','title','contents','metadata'):
            amount = articles_dict[article.id]['total']
            article.total_credibility = amount
            article.scores = articles_dict[article.id]
            article.save()

            # allocate author scores
            author_id = article.author_id
            author_ids = [author_id]
            author_amount = amount
            collaborators = Collaboration.objects.filter(partnership_id=author_id)
            if collaborators:
                author_ids = [c.individual_id for c in collaborators]
                author_ids = [author_id] if not author_ids else author_ids
                author_amount = amount / len(author_ids)
            for author_id in author_ids:
                if not author_id in authors_dict:
                    authors_dict[author_id] = {'c':0,'t':0}
                authors_dict[author_id]['t'] = authors_dict[author_id]['t'] + author_amount
                authors_dict[author_id]['c'] = authors_dict[author_id]['c'] + 1

        log_job(job, "authors %s" % len(authors_dict))
        for author in Author.objects.filter(id__in=authors_dict.keys()).defer('name','twitter_id','twitter_screen_name','metadata'):
            author.total_credibility = authors_dict[author.id]['t']
            author.current_credibility = authors_dict[author.id]['t'] # TODO spendability
            total_articles = authors_dict[author.id]['c']
            author.average_credibility = 0 if total_articles==0 else author.total_credibility / total_articles
            author.save()

        # TODO split this out into its own job, probably
        log_job(job, "publications %s" % Publication.objects.count())
        for publication in Publication.objects.all():
            articles = Article.objects.filter(publication_id=publication.id)
            total_articles = articles.count()
            total_credibility = articles.aggregate(Sum('total_credibility'))['total_credibility__sum']
            publication.total_credibility = int(total_credibility if total_credibility else 0)
            publication.average_credibility = 0 if total_articles==0 else publication.total_credibility / total_articles
            
            #TODO combine these queries
            for category in ['total'] + CATEGORIES:
                category_average_score = articles.annotate(
                    score=Cast(KeyTextTransform(category, 'scores'), IntegerField())
                ).aggregate(Avg('score'))['score__avg']
                publication.scores[category] = int(category_average_score if category_average_score else 0)
                category_count = articles.annotate(
                    category_score=Cast(KeyTextTransform(category, 'scores'), IntegerField())
                ).filter(**{'category_score__gt': 0}).count()
                publication.scores["%s_count" % category] = int(category_count if category_count else 0)
            publication.save()

        log_job(job, "Allocated %s total %s tranches" % (total_quantity, total_tranches), Job.Status.COMPLETED)

    except Exception as ex:
        log_job(job, traceback.format_exc())
        log_job(job, "Set scores error %s" % ex, Job.Status.ERROR)
        raise ex

@shared_task(rate_limit="1/m")
def clean_up_jobs(date=datetime.datetime.utcnow().date(), days=7):
    job = launch_job("clean_up_jobs")
    cutoff = date - datetime.timedelta(days=days)
    to_delete = Job.objects.filter(created_at__lte=cutoff)
    log_job(job, "cutoff %s deleting %s jobs" % (cutoff, to_delete.count()))
    to_delete.delete()
    log_job(job, "cleanup complete", Job.Status.COMPLETED)


# Main article parser

def parse_article(contents, domain=''):
    soup = BeautifulSoup(contents, "html.parser")
    metadata = {'sv_title' : soup.title.string if soup.title else ''}
    
    # default to generic parsing by meta tags and application-LD
    default_parser_rule_string = '[{"method":"meta_parser"}, {"method":"json_ld_parser"}]'
    default_parser_rules = json.loads(default_parser_rule_string)
    
    # can override on per-publication basis
    parser_rules = default_parser_rules
    publications = Publication.objects.filter(domain__iexact=domain)
    if publications:
        parser_rule_string = publications[0].parser_rules
        if parser_rule_string:
            custom_rules = json.loads(parser_rule_string)
            parser_rules = default_parser_rules + custom_rules if type(custom_rules) is list else [custom_rules]

    author = None
    for rule in parser_rules:
        parser = getattr(article_parsers, rule['method'])
        if parser:
            retval = parser(soup=soup)
            print("rule author %s %s" % (rule, retval['sv_author'] if 'sv_author' in retval else ''))
            author = article_parsers.get_author_from(metadata, retval)
            metadata.update(retval) # we keep overwriting sv_author, but store the final version in author

    if author:
        metadata['sv_author'] = author

    return metadata


# Utility functions

def launch_job(name):
    job = Job(status = Job.Status.LAUNCHED, name=name, actions='')
    job.save()
    return job

def log_job(job, action, status = None):
    print(action)
    if status is not None:
        job.status = status
    job.actions = action + " \n" + job.actions
    job.save();

def clean_up_url(url, contents=None):
    # TODO: filter out url cruft more elegantly, depending on site
    if url.find("youtube.com") >= 0:
        return url.partition("#")[0].partition("&")[0]
    if url.startswith("https://apple.news/") and contents:
        soup = BeautifulSoup(contents, "html.parser")
        links = soup.find_all("a")
        return links[0].attrs['href'].partition("#")[0].partition("?")[0]
    return url.partition("#")[0].partition("?")[0]

