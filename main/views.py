import datetime
from django.shortcuts import render
from django.utils.timezone import make_aware
from django.db.models import F
from django.contrib.postgres.fields.jsonb import KeyTextTransform
from .models import *
from .tasks import clean_up_url

SORT_BY = {
    'dc':'-created_at',
    'oc':'-created_at',
    'ds':'-total_credibility',
    'os':'total_credibility',
    'da':'-average_credibility',
    'a':'average_credibility',
}

def index_view(request):
    query = request.GET.get('search', '')
    if query:
        return search_view(request)
    page_size = int(request.GET.get('s', '20'))
    days = int(request.GET.get('d', '3'))
    end_date = make_aware(datetime.datetime.now()) + datetime.timedelta(minutes=5)
    start_date = end_date - datetime.timedelta(days=days)
    articles = Article.objects.select_related('publication').annotate(buzz=(F('total_credibility') - F('publication__average_credibility')) / 1000).filter(
        status=Article.Status.AUTHOR_ASSOCIATED).filter(created_at__range=(start_date, end_date)
    ).defer('contents','metadata').order_by('-total_credibility')[:page_size]
    context = {
        'category': 'Top',
        'articles': articles,
    }
    return render(request, 'main/index.html', context)

def buzz_view(request):
    page_size = int(request.GET.get('s', '20'))
    days = int(request.GET.get('d', '3'))
    end_date = make_aware(datetime.datetime.now()) + datetime.timedelta(minutes=5)
    start_date = end_date - datetime.timedelta(days=days)
    order_by = 'buzz' if request.GET.get('o')=='r' else '-buzz'
    articles = Article.objects.select_related('publication').annotate(buzz=(F('total_credibility') - F('publication__average_credibility')) / 1000).filter(
        status=Article.Status.AUTHOR_ASSOCIATED).filter(created_at__range=(start_date, end_date)
    ).defer('contents','metadata').order_by(order_by)[:page_size]
    
    context = {
        'category': 'Buzz',
        'articles': articles,
    }
    return render(request, 'main/index.html', context)
    
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

def category_view(request, category):
    category_key = category.lower()
    page_size = int(request.GET.get('s', '20'))
    days = int(request.GET.get('d', '3'))
    end_date = make_aware(datetime.datetime.now()) + datetime.timedelta(minutes=5)
    start_date = end_date - datetime.timedelta(days=days)

    articles = Article.objects.annotate(
        score=KeyTextTransform(category_key, 'scores')
    ).filter(status=Article.Status.AUTHOR_ASSOCIATED).filter(created_at__range=(start_date, end_date)).defer('contents','metadata').order_by("-score")[:page_size]

    for article in articles:
        article.score = round(int(article.score)/1000)

    context = {
        'category': category.title(),
        'articles': articles,
    }
    return render(request, 'main/category.html', context)
    
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

