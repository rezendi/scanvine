import datetime, os
import json, urllib3
import twitter # https://raw.githubusercontent.com/bear/python-twitter/master/twitter/api.py
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
                  access_token_secret=os.getenv('TWITTER_TOKEN_SECRET', ''))
#                 sleep_on_rate_limit=True)

http = urllib3.PoolManager()
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
    category = datetime.datetime.now().microsecond % len(LIST_IDS)
    twitter_list_id = LIST_IDS[category]
    selected = Sharer.objects.filter(category=category).filter(status=Sharer.Status.SELECTED)[0:100]
    if selected:
        selected_ids = [s.twitter_id for s in selected]
        list = api.CreateListsMember(list_id=twitter_list_id, user_id=selected_ids)
        for s in selected:
          s.status = Sharer.Status.LISTED
          s.twitter_list_id = twitter_list_id
          s.save()    
    log_job(job, "Added to list %s - %s: %s" % (category, twitter_list_id, len(selected)), Job.Status.COMPLETED)

# Take users from our Twitter list, add them to the DB if not there already
@shared_task(rate_limit="6/m")
def refresh_sharers():
    job = launch_job("refresh_sharers")
    category = datetime.datetime.now().microsecond % len(LIST_IDS)
    (next, prev, listed) = api.GetListMembersPaged(list_id=LIST_IDS[category], count=5000, include_entities=False, skip_status=True)
    new = [f for f in listed if len(Sharer.objects.filter(twitter_id=f.id))==0]
    for n in new:
        s = Sharer(status=Sharer.Status.LISTED, twitter_id=n.id, twitter_list_id=LIST_IDS[category], category=category,
                   twitter_screen_name=n.screen_name, name=n.name, profile=n.description, verified=True)
        s.save()
    log_job(job, "New sharers for category %s: %s" % (category, len(new)), Job.Status.COMPLETED)


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
        timeline = api.GetListTimeline(list_id=list_id, count = 200, since_id = since_id, include_rts=True, return_json=True)
        log_job(job, "Got %s unfiltered tweets from list %s" % (len(timeline), LIST_IDS.index(list_id)))
        tweets = [{'id':t['id'], 'user_id':t['user']['id'], 'screen_name':t['user']['screen_name'],
                          'text':t['text'], 'urls':t['entities']['urls']} for t in timeline if len(t['entities']['urls'])>0]
        tweets = [t for t in tweets if json.dumps(t['urls'][0]['expanded_url']).find('twitter.com')<0]
        log_job(job, "new link tweets %s" % len(tweets))
        if timeline:
            log_job(job, "max_id=%s" % timeline[0]['id'])
            log_job(job, "min_id=%s" % timeline[-1]['id'])
        elif since_id:
            log_job(job, "max_id=%s" % since_id)
    
        # Store new shares to DB
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
        
        # Launch follow-up job to fetch associated articles
        if count > 0:
            associate_articles.signature().apply_async()

    except Exception as ex:
        log_job(job, "Fetch shares error %s" % ex, Job.Status.ERROR)

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
    if existing:
        share.article_id = existing[0].id
        share.status = Share.Status.ARTICLE_ASSOCIATED
        share.save()
        if not force_refetch:
            log_job(job, "article exists for %s" % share.url, Job.Status.COMPLETED)
            return
    try:
        log_job(job, "Fetching %s" % share.url)
        r = http.request('GET', share.url, headers={'User-Agent': USER_AGENTS[datetime.datetime.now().microsecond % len(USER_AGENTS)]})
        html = r.data.decode('utf-8')
        final_url = clean_up_url(r.geturl(), html)
        final_host = urllib3.util.parse_url(final_url).host
        if final_host is None:
            initial_host = urllib3.util.parse_url(share.url).host
            initial_host = "medium.com" if initial_host == "link.medium.com" else initial_host
            final_url = "https://%s%s" % (initial_host, final_url)
            print("final_url %s" % final_url)
        if final_host != urllib3.util.parse_url(r.geturl()).host:
            r = http.request('GET', final_url, headers={'User-Agent': USER_AGENTS[datetime.datetime.now().microsecond % len(USER_AGENTS)]})
            html = r.data.decode('utf-8')
        article = existing[0] if existing else Article(status=Article.Status.CREATED, language='en', url = final_url, initial_url=share.url, title='', metadata='')
        article.contents=html
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

        metadata = parse_article(article.contents, domain)
        pub_name = metadata['sv_publication'] if 'sv_publication' in metadata else ''
        if pub_name and not publication.name:
            publication.name = pub_name.title()
            publication.save()

        article.metadata = metadata if metadata else article.metadata
        article.title = metadata['sv_title'].strip() if 'sv_title' in metadata else article.title
        author = article_parsers.get_author_for(metadata, article.publication)
        if author:
            article.author_id = author.id
            log_job(job, "Author %s associated to article %s" % (author.name, article.url))
            article.status = Article.Status.AUTHOR_ASSOCIATED
        else:
            article.status = Article.Status.AUTHOR_NOT_FOUND if article.author == None else Article.Status.AUTHOR_ASSOCIATED
        article.save()
    except Exception as ex2:
        log_job(job, "Article parse error %s" % ex2, Job.Status.ERROR)
        article.status = Article.Status.METADATA_PARSE_ERROR
        article.save()
        raise ex2

    log_job(job, "Parsed %s" % article.url, Job.Status.COMPLETED)


# Get sentiment from AWS
@shared_task(rate_limit="12/m")
def analyze_sentiment():
    job = launch_job("analyze_sentiment")
    import boto3
    sentiments = []
    comprehend = boto3.client(service_name='comprehend')
    shares = Share.objects.filter(status = Share.Status.ARTICLE_ASSOCIATED).filter(language='en')[0:25]
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
        log_job("Sentiment error %s" % result['ErrorMessage'])
        idx = result['Index']
        share = shares[idx]
        share.status = Share.Status.SENTIMENT_ERROR
        share.sentiment = str(result)
        share.save()
    log_job(job, "analyzed %s sentiments" % len(sentiments['ResultList']), Job.Status.COMPLETED)


# for each sharer, get list of shares. Shares with +ve or -ve get 2 points, mixed/neutral get 1 point, total N points
# 5040 credibility/day to allocate for maximum divisibility, N points means 5040/N cred for that share, truncate
@shared_task(rate_limit="1/s")
def allocate_credibility(date=datetime.datetime.utcnow().date(), days=7):
    job = launch_job("allocate_credibility")
    end_date = date + datetime.timedelta(days=1)
    start_date = end_date - datetime.timedelta(days=days)
    log_job(job, "date range %s - %s" % (start_date, end_date))
    total_points = 0
    for sharer in Sharer.objects.all():
        shares = Share.objects.filter(sharer_id=sharer.id, status=Share.Status.SENTIMENT_CALCULATED, net_sentiment__isnull=False,
                                      created_at__range=(start_date, end_date))
        if not shares:
            continue
        points = 0
        for s in shares:
            points += s.share_points()
        if points==0:
            continue
        total_points += points
        cred_per_point = 5040 * days // points
        for share in shares:
            article = share.article
            author = article.author if article else None
            if not article or not author:
                continue
            if author.name == sharer.name or author.twitter_id == sharer.twitter_id:
                continue
            share_cred = cred_per_point * s.share_points()
            existing = Tranche.objects.filter(sender=sharer.id, receiver=share.id)
            if existing:
                tranche = existing[0]
                tranche.category = sharer.category
                tranche.quantity = share_cred
                tranche.save()
            else:
                t = Tranche(source=0, status=0, type=0, tags='', category=sharer.category, sender=sharer.id, receiver=share.id, quantity = share_cred)
                t.save()
            s.status = Share.Status.CREDIBILITY_ALLOCATED
            s.save()
    log_job(job, "allocated %s" % total_points, Job.Status.COMPLETED)


# for each share with credibility allocated: get publication and author associated with that share, calculate accordingly
@shared_task(rate_limit="1/s")
def set_reputations():
    job = launch_job("set_reputations")
    articles = {}
    authors = {}
    publications = {}
    shares = Share.objects.filter(status=Share.Status.CREDIBILITY_ALLOCATED)
    for share in shares:
        tranches = Tranche.objects.filter(receiver=share.id)
        if not tranches:
            log_job(job, "Tranche not found %s" % share.id)
            continue
        if not share.article_id in articles:
            articles[share.article_id] = 0
        articles[share.article_id] = articles[share.article_id] + tranches[0].quantity

    for author_id in authors.keys():
        author = Author.objects.get(author_id) # TODO batch
        author.total_credibility = authors[author_id]
        author.current_credibility =authors[author_id] # TODO spendability
        author.save()

    for article_id in articles.keys():
        article = Article.objects.get(id=article_id) # TODO batch

        # TODO handle collaborations
        if not article.author_id in authors:
            authors[article.author_id] = 0
        authors[article.author_id] = authors[article.author_id] + articles[article_id]

        if not article.publication_id in publications:
            publications[article.publication_id] = {'t':0, 'a':0}
        publications[article.publication_id]['a'] = publications[article.publication_id]['a'] + 1
        publications[article.publication_id]['t'] = publications[article.publication_id]['t'] + articles[article_id]

    for publication_id in publications.keys():
        publication = Publication.objects.get(id=publication_id)
        publication.total_credibility = publications[publication_id]['t']
        publication.average_credibility = publication.total_credibility / publications[publication_id]['a']
        publication.save()

    log_job(job, "Allocated %s shares %s articles %s authors %s publications" % (len(shares), len(articles), len(authors), len (publications)), Job.Status.COMPLETED)


# Main article parser

def parse_article(html, domain=''):
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
            custom_rules = json.loads(parser_rule_string)
            parser_rules = default_parser_rules + custom_rules if type(custom_rules) is list else [custom_rules]

    author = None
    for rule in parser_rules:
        parser = getattr(article_parsers, rule['method'])
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
    if status is not None:
        job.status = status
    job.actions = action + " \n" + job.actions
    job.save();
    print(action)

def clean_up_url(url, html=None):
    # TODO: filter out url cruft more elegantly, depending on site
    if url.find("youtube.com") >= 0:
        return url
    if url.startswith("https://apple.news/") and html:
        soup = BeautifulSoup(html, "html.parser")
        links = soup.find_all("a")
        return links[0].attrs['href']
    return url.partition("?")[0]


# List management

HEALTH = "epidemiologist,virologist,immunologist,doctor,public health,chief medical,surgeon,cardiologist,ob/gyn,pediatrician,"
HEALTH+= "dermatologist,endocrinologist,gastroenterologist,infectious disease physician,nephrologist,ophthalmologist,"
HEALTH+= "pulmonologist,neurologist,nurse practitioner,radiologist,anesthesiologist,oncologist"
SCIENCE = "biologist,physicist,statistician,mathematician,chemistry+professor,biology+professor,physics+professor,mathematics+professor,"
SCIENCE+= "astrophysicist,astronomer,microbiologist,geneticist,geologist,seismologist,botanist,climatologist,hydrologist,ichthyologist,entomologist,"
SCIENCE+= "science+PhD|Ph.D.,chemistry+PhD|Ph.D.,physics+PhD|Ph.D.,biology+PhD|Ph.D.,"
TECH = "startup+investor,startups+investor,venture capitalist,vc,CTO,founder+tech,CEO+tech,CEO+software,CEO+hardware,"
TECH+= "cofounder,engineer+author,engineering+author,software+author,hardware+author,engineering+PhD|Ph.D.,"
BUSINESS ="economist,investor,fund manager,market analyst,financial analyst,"
MEDIA ="novelist,crime writer,crime author,thriller author,thriller writer,romance author,game writer,"
MEDIA+= "fantasy author,fantasy writer,science fiction author,writer of SF,SF author,screenwriter,scriptwriter,comics writer,"
MEDIA+= "TV writer,television writer,TV director,television director,Hollywood+director,"
MEDIA+= "movie producer,TV producer,television producer,showrunner,game producer,literary agent,talent agent,publisher,"

sections = [HEALTH, SCIENCE, TECH, BUSINESS, MEDIA]

def promote_matching_sharers():
    regex_prefix = "\y" if 'SCANVINE_ENV' in os.environ and os.environ['SCANVINE_ENV']=="production" else "\b"
    for idx, section in enumerate(sections):
        sharers = set()
        keywords = section.split(",")
        keywords = [k for k in keywords if len(k)>1]
        for keyword in keywords:
            matching = Sharer.objects.filter(status=Sharer.Status.CREATED)
            keys = [keyword] if keyword.find("+") < 0 else keyword.split("+")
            for key in keys:
                matching = matching.filter(profile__iregex=r"%s%s%s" % (regex_prefix, key, regex_prefix))
            print("keyword %s %s matches %s" % (idx, keyword, len(matching)))
            for match in matching:
                sharers.add(match.id)
                match.status = Sharer.Status.SELECTED
                match.category = idx
                match.save()
        print("total %s" % len(sharers))

def reset_sharers():
        matching = Sharer.objects.filter(status=Sharer.Status.SELECTED)
        for match in matching:
            match.status = Sharer.Status.CREATED
            match.save()

