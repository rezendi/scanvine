import ast, datetime, math
from django.shortcuts import render, redirect
from django.utils import timezone
from django.db.models import F, Q, IntegerField, Subquery, Count, Sum, Case, When
from django.db.models.functions import Cast, Coalesce, Sqrt, Greatest
from django.contrib.postgres.fields.jsonb import KeyTextTransform
from .models import *
from .tasks import clean_up_url
from .my_tasks import fetch_my_back_shares

CATEGORIES = ['health','science','tech','business','media']

def index_view(request, category=None, scoring=None, days=None):
    query = request.GET.get('search', '')
    if query:
        return search_view(request)

    only_free = request.GET.get('pw', '')=='no'
    page_size = int(request.GET.get('s', '20'))
    page_size = 20 if page_size > 256 else page_size
    delta = int(scoring) if scoring and not days and scoring.isnumeric() else days
    delta = int(delta) if delta else 1
    scoring = 'top' if scoring not in ["raw","odd","latest","new","shares"] else scoring
    end_date = timezone.now() + datetime.timedelta(minutes=5)
    start_date = end_date - datetime.timedelta(days=delta)
    if scoring=="new":
        delta = int(days) if days else 3
        start_date = end_date - datetime.timedelta(hours=delta)
    category = 'total' if not category or category not in CATEGORIES else category

    query = get_article_query(category)

    # filter
    if only_free:
        query = query.filter(publication__is_paywalled=False)
    if scoring not in ["odd","latest","new"] and request.GET.get('single','') != "true":
        query = query.filter(share_count__gt=1)
    if scoring != "latest":
        query = query.filter(our_date__range=(start_date,end_date))

    # order
    articles = []
    if scoring=='latest':
        articles = query.order_by("-our_date")[:page_size]
    if scoring=='shares':
        articles = query.order_by("-share_count")[:page_size]
    if scoring=='raw' or scoring=='new':
        articles = query.order_by("-score")[:page_size]
    if scoring=='odd':
        articles = query.order_by("-odd")[:page_size]
        for article in articles:
            article.raw = article.score
            article.score = article.odd
    if scoring=='top':
        articles = query.order_by("-buzz")[:page_size]
        for article in articles:
            article.raw = article.score
            article.score = article.buzz

    # links, category to display
    category = 'all' if category=='total' else category
    (category_links, scoring_links, timing_links) = get_links(category, scoring, delta)
    category = '' if category=='all' else category

    # link suffixes
    if request.GET.get('svd','')=='t':
        for array in [category_links, scoring_links, timing_links]:
            for vals in array:
                vals['href'] = vals['href'] + "?svd=t" if vals['href']!='no' else vals['href']

    if request.GET.get('v','')=='t':
        suffix = '&v=t' if request.GET.get('svd','')=='t' else '?v=t'
        for array in [category_links, scoring_links, timing_links]:
            for vals in array:
                vals['href'] = vals['href'] + suffix if vals['href']!='no' else vals['href']

    # shorter mobile links    
    short = {"Science":"Sci", "Business": "Biz"}
    short_links = [dict(c, **{"name":short[c['name']]}) if c['name'] in short else c for c in category_links]
    short = {"30 hours":"30", "3 days":""}
    short_timing_links = [dict(t, **{"name":short[t['name']]}) if t['name'] in short else t for t in timing_links]

    context = {
        'category': category.title(),
        'scoring' : scoring.title(),
        'category_links': category_links,
        'scoring_links' : scoring_links,
        'timing_links' : timing_links,
        'short_timing_links' : short_timing_links,
        'short_links': short_links,
        'articles': articles,
        'only_free' : only_free,
        'path' : request.path,
    }
    return render(request, 'main/index.html', context)

def get_article_query(category='total'):
    query = Article.objects.select_related('publication').annotate(
        score = Cast(KeyTextTransform(category, 'scores'), IntegerField()),
        share_count = Cast(KeyTextTransform('%s_shares' % category, 'scores'), IntegerField()),
        pub_average_score = Cast(KeyTextTransform(category, 'publication__scores'), IntegerField()),
        pub_article_count = Greatest( Cast(KeyTextTransform('%s_count' % category, 'publication__scores'), IntegerField()), 1),
        buzz = F('score') - F('pub_average_score'),
        odd = F('buzz') / F('pub_article_count'),
        our_date = Coalesce(F('published_at'), F('created_at')),
    ).filter(status__in=[Article.Status.AUTHOR_ASSOCIATED, Article.Status.AUTHOR_NOT_FOUND]).defer('contents','metadata')
    return query

def get_links(category='all', scoring='top', days=1):
    scoring_links = [
        {'name':'Top', 'href': 'no' if scoring=='top' else '%s/top/%s' % (category,days)},
        {'name':'Odd', 'href': 'no' if scoring=='odd' else '%s/odd/%s' % (category,days)},
        {'name':'New', 'href': 'no' if scoring=='new' else '%s/new/%s' % (category,days)},
    ]
    category_links = [{'name':'All', 'href': 'no' if category in ['all','total'] else 'all/%s/%s' % (scoring,days)}]
    category_links+= [{'name':c.title(), 'href': 'no' if category==c else '%s/%s/%s' % (c,scoring,days)} for c in CATEGORIES]
    timing_links = [
        {'name':'Today' if scoring!='new' else '1 hour', 'href': 'no' if days==1 else '%s/%s/1' % (category,scoring)},
        {'name':'3 days' if scoring!='new' else '3 hours', 'href': 'no' if days==3 else '%s/%s/3' % (category,scoring)},
        {'name':'Week' if scoring!='new' else '7 hours', 'href': 'no' if days==7 else '%s/%s/7' % (category,scoring)},
        {'name':'Month' if scoring!='new' else '30 hours', 'href': 'no' if days==30 else '%s/%s/30' % (category,scoring)},
    ]
    return (category_links, scoring_links, timing_links)


def article_view(request, article_id):
    article = Article.objects.get(id=article_id)
    (category_links, scoring_links, timing_links) = get_links()
    shares = Share.objects.filter(source=0, article_id=article.id).distinct('sharer_id')
    categories = []
    for category in CATEGORIES:
        categories.append({'name':category.title(),'shares':[]})
    for share in shares:
        categories[share.category]['shares'].append(share)
    
    if article.metadata:
        try:
            meta = ast.literal_eval(article.metadata)
            article.description = meta['description'] if 'description' in meta else 'n/a'
        except Exception as ex:
            print("JSON exception %s" % ex)

    context = {
        'article': article,
        'categories' : categories,
        'category_links': category_links,
        'scoring_links' : scoring_links,
        'timing_links' : timing_links,
    }
    return render(request, 'main/article.html', context)


def author_view(request, author_id):
    page_size = int(request.GET.get('s', '20'))
    page_size = 20 if page_size > 256 else page_size
    days = int(request.GET.get('d', '0'))
    author = Author.objects.get(id=author_id)
    collaboration_ids = Collaboration.objects.filter(individual_id=author_id).values('partnership_id')
    articles = Article.objects.filter(Q(author_id=author_id) | Q(author_id__in=collaboration_ids))
    article_count = articles.count()
    if days > 0:
        end_date = timezone.now() + datetime.timedelta(minutes=5)
        start_date = end_date - datetime.timedelta(days=days)
        articles = articles.filter(created_at__range=(start_date, end_date)).defer('contents','metadata')

    if author.is_collaboration:
        partner_ids = Collaboration.objects.filter(partnership_id=author_id).values('individual_id')
        authors = Author.objects.filter(id__in=partner_ids)
    else:
        authors = [author]

    (category_links, scoring_links, timing_links) = get_links()
    context = {
        'collaboration' : author.is_collaboration,
        'base_author' : author,
        'authors': authors,
        'articles': articles.order_by('-total_credibility')[:page_size],
        'article_count' : article_count,
        'category_links': category_links,
        'scoring_links' : scoring_links,
        'timing_links' : timing_links,
    }
    return render(request, 'main/author.html', context)


def authors_view(request, category=None, scoring = None, publication_id = None):
    page_size = int(request.GET.get('s', '100'))
    page_size = 20 if page_size > 256 else page_size
    sort = request.GET.get('o', '-total_credibility')
    min = int(request.GET.get('min', '1'))
    all = request.GET.get('all', '')
    authors = Author.objects.annotate(
        article_count=Count('article__pk', distinct=True),
        collaboration_count = Count('collaborations__pk', distinct=True),
        total_count = F('article_count') + F('collaboration_count'),
    )

    if not all:
        authors = authors.filter(is_collective=False)
    if publication_id:
        pub_author_ids = Article.objects.filter(publication_id=publication_id).distinct('author_id').values('author_id')
        authors = authors.filter(id__in=pub_author_ids)
    if category in ["top","average"]:
        scoring = category
        category = None
    scoring = 'top' if scoring is None else scoring
    sort = '-average_credibility' if scoring=='average' else sort

    if category:
        sort ="-category_score"
        authors = authors.annotate(
            category_score = Sum(Cast(KeyTextTransform(category, 'article__scores'), IntegerField())),
            category_count = Sum(Cast(KeyTextTransform("%s_shares" % category, 'article__scores'), IntegerField())),
            article_divisor = Greatest('category_count',1),
            average_score = F('category_score') / F('article_divisor'),
        )
        authors = authors.filter(category_score__isnull=False)
        
    authors=authors.filter(total_count__gte=min).order_by(sort)[:page_size]
    for author in authors:
        if category:
            author.category_score = author.category_score // 1000
            author.average_score = author.average_score // 1000
        top = Article.objects.filter(author_id=author.id).order_by("-total_credibility")[:1]
        if not top:
            collab_ids = Collaboration.objects.filter(individual=author.id).values('partnership')
            top = Article.objects.filter(author_id__in=collab_ids).order_by("-total_credibility")[:1]
        if top:
            author.top = top[0]

    (category_links, scoring_links, timing_links) = get_authors_links(category, scoring, publication_id)
    context = {
        'authors': authors,
        'category': category,
        'category_links': category_links,
        'scoring_links' : scoring_links,
        'timing_links' : timing_links,
    }
    return render(request, 'main/authors.html', context)

def get_authors_links(category, scoring, publication_id=None):
    base = 'authors'
    if publication_id is not None:
        base = 'publication_authors/%s' % publication_id
    category_links = [{'name':c.title(), 'href': 'no' if category==c else '%s/%s' % (base,c)} for c in CATEGORIES]
    if category is not None:
        base += '/%s' % category
    scoring_links = [
        {'name':'Top', 'href': 'no' if scoring=='top' else "%s/top" % base},
        {'name':'Average', 'href': 'no' if scoring=='average' else "%s/average" % base},
    ]
    if category is not None:
        scoring_links = [] # need to debug averages
    timing_links = []
    return (category_links, scoring_links, timing_links)


def publication_view(request, publication_id):
    page_size = int(request.GET.get('s', '20'))
    page_size = 20 if page_size > 256 else page_size
    days = int(request.GET.get('d', '0'))
    publication = Publication.objects.get(id=publication_id)
    articles = Article.objects.filter(publication_id=publication_id)
    article_count = articles.count()
    if days > 0:
        end_date = timezone.now() + datetime.timedelta(minutes=5)
        start_date = end_date - datetime.timedelta(days=days)
        articles = articles.filter(created_at__range=(start_date, end_date)).defer('contents','metadata')

    authors = Article.objects.filter(publication_id=publication.id).distinct('author_id')
    (category_links, scoring_links, timing_links) = get_links()
    context = {
        'publication' : publication,
        'author_count' : authors.count(),
        'articles' : articles.order_by('-total_credibility')[:page_size],
        'article_count' : article_count,
        'category_links': category_links,
        'scoring_links' : scoring_links,
        'timing_links' : timing_links,
    }
    return render(request, 'main/publication.html', context)


def publications_view(request, category=None, scoring=None):
    page_size = int(request.GET.get('s', '100'))
    page_size = 20 if page_size > 256 else page_size
    sort = request.GET.get('o', '-total_credibility')
    min = int(request.GET.get('min', '2'))
    publications = Publication.objects
    if category in ["top","average"]:
        scoring = category
        category = None
    scoring = 'top' if scoring is None else scoring
    sort = '-average_credibility' if scoring=='average' else sort

    if category:
        sort ="-average_score"
        publications = publications.annotate(
            category_score = Sum(Cast(KeyTextTransform(category, 'article__scores'), IntegerField())),
            article_count = Greatest(Count('article', distinct=True),1),
            average_score = F('category_score') / F('article_count')
        ).filter(category_score__isnull=False)
    publications = publications.annotate(article_count=Count('article', distinct=True)).filter(article_count__gte=min).order_by(sort)[:page_size]
    for publication in publications:
        if category:
            publication.category_score = publication.category_score // 1000
            publication.average_score = publication.average_score // 1000
        top = Article.objects.filter(publication_id=publication.id).order_by('-total_credibility')[:1]
        publication.top = top[0] if top else None

    (category_links, scoring_links, timing_links) = get_publications_links(category, scoring)
    context = {
        'category': category,
        'publications': publications,
        'category_links': category_links,
        'scoring_links' : scoring_links,
        'timing_links' : timing_links,
    }
    return render(request, 'main/publications.html', context)

def get_publications_links(category, scoring, publication_id=None):
    base = 'publications'
    category_links = [{'name':c.title(), 'href': 'no' if category==c else '%s/%s' % (base,c)} for c in CATEGORIES]
    category_links = [] # for now, need debugging
    if category is not None:
        base += '/%s' % category
    scoring_links = [
        {'name':'Top', 'href': 'no' if scoring=='top' else "%s/top" % base},
        {'name':'Average', 'href': 'no' if scoring=='average' else "%s/average" % base},
    ]
    timing_links = []
    return (category_links, scoring_links, timing_links)

def search_view(request):
    query = request.GET.get('search', '').strip()
    template = ''
    articles = []
    authors = []
    publications = []

    if query.isnumeric() or (query.rpartition(":")[2]).rpartition("/")[2].isnumeric():
        query = int(query.rpartition(":")[2].rpartition("/")[2])
        shares = Share.objects.filter(twitter_id=query)
        if shares:
            return article_view(request, shares[0].id)

    words = query.split(" ")
    if len(words) < 5:
        authors = Author.objects.filter(name__icontains=query).order_by("-total_credibility")
        if authors:
            if len(authors)==1:
                return author_view(request, authors[0].id)
            for author in authors:
                author.total_articles = Article.objects.filter(author_id=author.id).count()
                latest = Article.objects.filter(author_id=author.id).order_by("-created_at")[:1]
                author.latest = latest[0] if latest else None
            template = 'main/authors.html'

    if query.startswith("pub:"):
        query = query.replace("pub:","")
        publications = Publication.objects.filter(name__icontains=query).order_by("-average_credibility")
        if not publications:
            publications = Publication.objects.filter(domain__icontains=query).order_by("-average_credibility")
        if publications:
            if len(publications)==1:
                return publication_view(request, publications[0].id)
            template = 'main/publications.html'

    if not template:
        urlquery = clean_up_url(query)
        articles = Article.objects.filter(url=urlquery).order_by("-total_credibility")
        if articles:
            if len(articles)==1:
                return article_view(request, articles[0].id)
        else:
            articles = Article.objects.filter(title__icontains=query).order_by("-total_credibility")
        if articles:
            if len(articles)==1:
                return article_view(request, articles[0].id)
        template = 'main/index.html'

    (category_links, scoring_links, timing_links) = get_links()
    context = {
        'search' : request.GET.get('search', ''),
        'authors' : authors,
        'articles' : articles,
        'publications' : publications,
        'category_links': category_links,
        'scoring_links' : scoring_links,
        'timing_links' : timing_links,
    }
    return render(request, template, context)


def shares_view(request, category):
    page_size = int(request.GET.get('s', '100'))
    sort = request.GET.get('o', '-created_at')
    shares = Share.objects.all()
    if category !='all':
        category_id = CATEGORIES.index(category)
        shares = shares.filter(category=category_id)
    delta = request.GET.get('delta', '')
    if delta:
        end_date = timezone.now() + datetime.timedelta(minutes=5)
        start_date = end_date - datetime.timedelta(hours=int(delta))
        shares = shares.filter(created_at__range=(start_date, end_date))
    shares = shares.order_by(sort)[:page_size]
    context = {
        'category' : category.title(),
        'shares' : shares,
    }
    return render(request, 'main/shares.html', context)


def my_view(request, screen_name = None):
    if request.user.is_anonymous:
        return redirect('/social/login/twitter')
    auths = request.user.social_auth.filter(provider='twitter')
    if not auths:
        return redirect('/social/login/twitter')
    auth = auths[0]
    if not screen_name:
        ed = auth.extra_data
        if not 'access_token' in ed or not 'screen_name' in ed['access_token'] or not ed['access_token']['screen_name']:
            return redirect('/main/')
        return redirect('/main/my/%s/' % ed['access_token']['screen_name'])

    page_size = int(request.GET.get('s', '40'))
    page_size = 40 if page_size > 256 else page_size
    ids = Share.objects.prefetch_related('feed_shares').filter(
        source=1, status=Share.Status.ARTICLE_ASSOCIATED, feed_shares__user_id=request.user.id
    ).values('id','article_id').order_by("-feed_shares__created_at")[:page_size]
    article_ids = [v['article_id'] for v in ids]
    preserved = Case(*[When(pk=pk, then=pos) for pos, pk in enumerate(article_ids)])
    articles = Article.objects.filter(id__in=article_ids).order_by(preserved)
    shares = Share.objects.filter(id__in=[v['id'] for v in ids])
    for article in articles:
        article.shares = [s for s in shares if s.article_id==article.id]

    if not 'back_filling' in auth.extra_data:
        auth.extra_data['back_filling'] = 'active'
        auth.save()
        fetch_my_back_shares.signature((request.user.id,)).apply_async()

    context = {
        'user' : auth,
        'articles' : articles,
    }
    return render(request, 'main/my.html', context)
