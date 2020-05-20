import datetime, math
from django.shortcuts import render
from django.utils.timezone import make_aware
from django.db.models import F, Q, IntegerField
from django.db.models.functions import Cast
from django.contrib.postgres.fields.jsonb import KeyTextTransform
from .models import *
from .tasks import clean_up_url

CATEGORIES = ['health','science','tech','business','media']

def index_view(request, category=None, scoring=None, days=None):
    query = request.GET.get('search', '')
    if query:
        return search_view(request)

    page_size = int(request.GET.get('s', '20'))
    days = int(scoring) if scoring and not days and scoring.isnumeric() else days
    days = int(days) if days else 3
    scoring = 'top' if scoring != "raw" and scoring != "odd" else scoring
    end_date = make_aware(datetime.datetime.now()) + datetime.timedelta(minutes=5)
    start_date = end_date - datetime.timedelta(days=days)
    category = 'total' if not category or category not in CATEGORIES else category
    articles_query = Article.objects.select_related('publication').annotate(
        score=Cast(KeyTextTransform(category, 'scores'), IntegerField()),
        pub_category_average=Cast(KeyTextTransform(category, 'publication__scores'), IntegerField()),
        buzz=(F('score') - F('pub_category_average')),
        pub_article_count=Cast(KeyTextTransform('%s_count' % category, 'publication__scores'), IntegerField()),
        odd=(F('score') / (F('pub_article_count')+1)),
    ).filter(status=Article.Status.AUTHOR_ASSOCIATED).filter(
        Q(published_at__range=(start_date, end_date)) | Q(published_at__isnull=True, created_at__range=(start_date,end_date))
    ).defer('contents','metadata')

    articles = []
    if scoring=='raw':
        articles = articles_query.order_by("-score")[:page_size]

    if scoring=='odd':
        articles = articles_query.order_by("-odd")[:page_size]

    if scoring=='top':
        # we can't (easily) do the publications-with-few-articles special case handling in DB, so do it here
        articles1 = articles_query.order_by("-buzz")[:page_size] # default list
        articles2 = articles_query.order_by("-score")[:page_size] # may have entries to insert
        articles = []
        for article in articles1:
            article.score = article.buzz
            articles.append(article)
        for article in articles2:
            if not article.id in [a.id for a in articles1]:
                article.score = int(max(article.buzz, alt_buzz(article, category)))
                articles.append(article)
        articles.sort(key = lambda L: L.score, reverse=True)

    for article in articles:
        article.score = int(article.score) // 1000
    
    category = 'all' if category=='total' else category
    
    category_links = [{'name':'All', 'href': 'no' if category=='all' else 'all/%s/%s' % (scoring,days)}]
    category_links+= [{'name':c.title(), 'href': 'no' if category==c else '%s/%s/%s' % (c,scoring,days)} for c in CATEGORIES]
    scoring_links = [
        {'name':'Top', 'href': 'no' if scoring=='top' else '%s/top/%s' % (category,days)},
        {'name':'Raw', 'href': 'no' if scoring=='raw' else '%s/raw/%s' % (category,days)},
        {'name':'Odd', 'href': 'no' if scoring=='odd' else '%s/odd/%s' % (category,days)},
    ]
    timing_links = [
        {'name':'Today', 'href': 'no' if days==1 else '%s/%s/1' % (category,scoring)},
        {'name':'3 days', 'href': 'no' if days==3 else '%s/%s/3' % (category,scoring)},
        {'name':'Week', 'href': 'no' if days==7 else '%s/%s/7' % (category,scoring)},
        {'name':'Month', 'href': 'no' if days==30 else '%s/%s/30' % (category,scoring)},
    ]
    
    if request.GET.get('svd','')=='true':
        for array in [category_links, scoring_links, timing_links]:
            for vals in array:
                vals['href'] = vals['href'] + "?svd=true"

    context = {
        'category': category.title(),
        'scoring' : scoring,
        'days' : days,
        'category_links': category_links,
        'scoring_links' : scoring_links,
        'timing_links' : timing_links,
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


def author_view(request, author_id):
    page_size = int(request.GET.get('s', '20'))
    days = int(request.GET.get('d', '0'))
    author = Author.objects.get(id=author_id)
    articles = Article.objects.filter(author_id=author_id)
    article_count = articles.count()
    if days > 0:
        end_date = make_aware(datetime.datetime.now()) + datetime.timedelta(minutes=5)
        start_date = end_date - datetime.timedelta(days=days)
        articles = articles.filter(created_at__range=(start_date, end_date)).defer('contents','metadata')
    context = {
        'author': author,
        'articles': articles.order_by('-total_credibility')[:page_size],
        'article_count' : article_count,
    }
    return render(request, 'main/author.html', context)

def publication_view(request, publication_id):
    page_size = int(request.GET.get('s', '20'))
    days = int(request.GET.get('d', '7'))
    publication = Publication.objects.get(id=publication_id)
    articles = Article.objects.filter(publication_id=publication_id)
    article_count = articles.count()
    if days > 0:
        end_date = make_aware(datetime.datetime.now()) + datetime.timedelta(minutes=5)
        start_date = end_date - datetime.timedelta(days=days)
        articles = articles.filter(created_at__range=(start_date, end_date)).defer('contents','metadata')
    context = {
        'publication' : publication,
        'articles' : articles.order_by('-total_credibility')[:page_size],
        'article_count' : article_count,
    }
    return render(request, 'main/publication.html', context)

def authors_view(request):
    page_size = int(request.GET.get('s', '20'))
    sort = request.GET.get('o', 'ds')
    authors = Author.objects.all().order_by(SORT_BY[sort])[:page_size]
    for author in authors:
        author.total_articles = Article.objects.filter(author_id=author.id).count()
        latest = Article.objects.filter(author_id=author.id).order_by("-created_at")[:1]
        author.latest = latest[0] if latest else None
    context = {
        'authors': authors,
    }
    return render(request, 'main/authors.html', context)

def publications_view(request):
    page_size = int(request.GET.get('s', '20'))
    sort = request.GET.get('o', 'ds')
    publications = Publication.objects.all().order_by(SORT_BY[sort])[:page_size]
    for publication in publications:
        publication.total_articles = Article.objects.filter(publication_id=publication.id).count()
        latest = Article.objects.filter(publication_id=publication.id).order_by('-created_at')[:1]
        publication.latest = latest[0] if latest else None
    context = {
        'publications': publications,
    }
    return render(request, 'main/publications.html', context)

def article_view(request, article_id):
    article = Article.objects.get(id=article_id)
    context = {
        'article': article,
        'shares': Share.objects.filter(article_id=article.id)
    }
    return render(request, 'main/article.html', context)

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

    context = {
        'authors' : authors,
        'articles' : articles,
        'publications' : publications,
    }
    return render(request, template, context)

