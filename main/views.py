import datetime, math
from django.shortcuts import render
from django.utils import timezone
from django.db.models import F, Q, IntegerField, Subquery, Count, Sum
from django.db.models.functions import Cast, Coalesce, Sqrt, Greatest
from django.contrib.postgres.fields.jsonb import KeyTextTransform
from .models import *
from .tasks import clean_up_url

CATEGORIES = ['health','science','tech','business','media']

def index_view(request, category=None, scoring=None, days=None):
    query = request.GET.get('search', '')
    if query:
        return search_view(request)

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
    query = Article.objects.select_related('publication').annotate(
        score = Cast(KeyTextTransform(category, 'scores'), IntegerField()),
        shares = Cast(KeyTextTransform('%s_shares' % category, 'scores'), IntegerField()),
        pub_average_score = Cast(KeyTextTransform(category, 'publication__scores'), IntegerField()),
        pub_article_count = Greatest( Cast(KeyTextTransform('%s_count' % category, 'publication__scores'), IntegerField()), 1),
        buzz = F('score') - F('pub_average_score'),
        odd = F('buzz') / F('pub_article_count'),
        our_date = Coalesce(F('published_at'), F('created_at')),
    ).filter(status=Article.Status.AUTHOR_ASSOCIATED)
    if scoring not in ["odd","latest","new"] and request.GET.get('single','')!="true":
        query = query.filter(shares__gt=1)
    if scoring != "latest":
        query = query.filter(our_date__range=(start_date,end_date))
    query = query.defer('contents','metadata')

    articles = []

    if scoring=='latest':
        articles = query.order_by("-our_date")[:page_size]

    if scoring=='shares':
        articles = query.order_by("-shares")[:page_size]

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

    category = 'all' if category=='total' else category
    (category_links, scoring_links, timing_links) = get_links(category, scoring, delta)
    category = '' if category=='all' else category
    
    if request.GET.get('svd','')=='t':
        for array in [category_links, scoring_links, timing_links]:
            for vals in array:
                vals['href'] = vals['href'] + "?svd=t" if vals['href']!='no' else vals['href']

    if request.GET.get('v','')=='t':
        suffix = '&v=t' if request.GET.get('svd','')=='t' else '?v=t'
        for array in [category_links, scoring_links, timing_links]:
            for vals in array:
                vals['href'] = vals['href'] + suffix if vals['href']!='no' else vals['href']
    
    short = {"Science":"Sci", "Business": "Biz"}
    short_links = [dict(c, **{"name":short[c['name']]}) if c['name'] in short else c for c in category_links]

    context = {
        'category': category.title(),
        'scoring' : scoring.title(),
        'days' : days,
        'category_links': category_links,
        'scoring_links' : scoring_links,
        'timing_links' : timing_links,
        'short_links': short_links,
        'articles': articles,
    }
    return render(request, 'main/index.html', context)

def alt_buzz(article, category):
    if article.score <= 0 or article.publication.average_credibility==0:
        return 0
    total_pub_articles = article.publication.total_credibility / article.publication.average_credibility
    total_pub_category_score = total_pub_articles * article.publication.scores[category]
    if total_pub_category_score == 0:
        return article.score
    fraction = article.score / total_pub_category_score
    return math.sqrt(fraction) * article.score

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
    shares = list(Share.objects.filter(article_id=article.id).distinct('sharer_id'))
    shares.sort(key=lambda s:s.category)
    context = {
        'article': article,
        'shares': shares,
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


def authors_view(request, category=None, publication_id = None):
    page_size = int(request.GET.get('s', '20'))
    page_size = 20 if page_size > 256 else page_size
    sort = request.GET.get('o', '-total_credibility')
    min = int(request.GET.get('min', '1'))
    all = request.GET.get('all', '')
    authors = Author.objects.annotate(article_count=Count('article')).filter(article_count__gte=min)
    if not all:
        authors = authors.filter(is_collective=False)
    if publication_id:
        pub_author_ids = Article.objects.filter(publication_id=publication_id).distinct('author_id').values('author_id')
        authors = authors.filter(id__in=pub_author_ids)
    if category:
        sort ="-category_score"
        authors = authors.annotate(
            category_score = Sum(Cast(KeyTextTransform(category, 'article__scores'), IntegerField())),
            article_count = Greatest(Count('article__pk'),1),
            average_score = F('category_score') / F('article_count')
        ).filter(category_score__isnull=False)
    authors = authors.order_by(sort)[:page_size]
    for author in authors:
        if category:
            author.category_score = author.category_score // 1000
            author.average_score = author.average_score // 1000
        latest = Article.objects.filter(author_id=author.id).order_by("-created_at")[:1]
        author.latest = latest[0] if latest else None

    (category_links, scoring_links, timing_links) = get_links()
    context = {
        'authors': authors,
        'category': category,
        'category_links': category_links,
        'scoring_links' : scoring_links,
        'timing_links' : timing_links,
    }
    return render(request, 'main/authors.html', context)


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


def publications_view(request, category=None):
    page_size = int(request.GET.get('s', '20'))
    page_size = 20 if page_size > 256 else page_size
    sort = request.GET.get('o', '-average_credibility')
    min = int(request.GET.get('min', '2'))
    publications = Publication.objects.annotate(article_count=Count('article'))
    if category:
        sort ="-average_score"
        publications = publications.annotate(
            category_score = Sum(Cast(KeyTextTransform(category, 'article__scores'), IntegerField())),
            article_count = Greatest(Count('article__pk'),1),
            average_score = F('category_score') / F('article_count')
        ).filter(category_score__isnull=False)
    publications = publications.filter(article_count__gte=min).order_by(sort)[:page_size]
    for publication in publications:
        if category:
            publication.category_score = publication.category_score // 1000
            publication.average_score = publication.average_score // 1000
        latest = Article.objects.filter(publication_id=publication.id).order_by('-created_at')[:1]
        publication.latest = latest[0] if latest else None

    (category_links, scoring_links, timing_links) = get_links()
    context = {
        'category': category,
        'publications': publications,
        'category_links': category_links,
        'scoring_links' : scoring_links,
        'timing_links' : timing_links,
    }
    return render(request, 'main/publications.html', context)


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
