import datetime
from django.http import HttpResponse
from django.template import loader
from .models import *

SORT_BY = {
    'dc':'-created_at',
    'oc':'-created_at',
    'ds':'-total_credibility',
    'os':'total_credibility',
    'da':'-average_credibility',
    'a':'average_credibility',
}

CATEGORIES = {
    'health':0,
    'science':1,
    'tech':2,
    'business':3,
    'media':4,
}

def index(request):
    template = loader.get_template('main/index.html')
    page_size = int(request.GET.get('s', '10'))
    articles = Article.objects.filter(status=Article.Status.AUTHOR_ASSOCIATED).order_by('-total_credibility')[:page_size]
    context = {
        'category': 'Top',
        'articles': articles,
    }
    return HttpResponse(template.render(context, request))

def author(request, author_id):
    template = loader.get_template('main/author.html')
    page_size = int(request.GET.get('s', '10'))
    author = Author.objects.get(id=author_id)
    context = {
        'author': author,
        'articles': Article.objects.filter(author_id=author_id).order_by("-total_credibility")[:page_size]
    }
    return HttpResponse(template.render(context, request))

def publication(request, publication_id):
    template = loader.get_template('main/publication.html')
    page_size = int(request.GET.get('s', '10'))
    publication = Publication.objects.get(id=publication_id)
    context = {
        'publication': publication,
        'articles': Article.objects.filter(publication_id=publication_id).order_by("-total_credibility")[:page_size]
    }
    return HttpResponse(template.render(context, request))

def authors(request):
    template = loader.get_template('main/authors.html')
    page_size = int(request.GET.get('s', '10'))
    sort = request.GET.get('o', 'ds')
    authors = Author.objects.all().order_by(SORT_BY[sort])[:page_size]
    for author in authors:
        author.total_articles = Article.objects.filter(author_id=author.id).count()
        latest = Article.objects.filter(author_id=author.id).order_by("-created_at")[:1]
        author.latest = latest[0] if latest else None
    context = {
        'authors': authors,
    }
    return HttpResponse(template.render(context, request))

def publications(request):
    template = loader.get_template('main/publications.html')
    page_size = int(request.GET.get('s', '10'))
    sort = request.GET.get('o', 'ds')
    publications = Publication.objects.all().order_by(SORT_BY[sort])[:page_size]
    for publication in publications:
        publication.total_articles = Article.objects.filter(publication_id=publication.id).count()
        latest = Article.objects.filter(publication_id=publication.id).order_by('-created_at')[:1]
        publication.latest = latest[0] if latest else None
    context = {
        'publications': publications,
    }
    return HttpResponse(template.render(context, request))

def category(request, category):
    template = loader.get_template('main/index.html')
    category_id = CATEGORIES[category.lower()]
    page_size = int(request.GET.get('s', '10'))
    end_date = datetime.datetime.utcnow().date() + datetime.timedelta(days=1)
    start_date = end_date - datetime.timedelta(days=7)
    raw = Article.objects.filter(status=Article.Status.AUTHOR_ASSOCIATED).filter(created_at__range=(start_date, end_date)).order_by('-total_credibility')
    articles = []
    for a in raw:
        shares = Share.objects.filter(article_id=a.id)
        for s in shares:
            if s.sharer.category == category_id:
                articles.append(a)
        if len(articles) >= page_size:
            break
    context = {
        'category': category.title(),
        'articles': articles,
    }
    return HttpResponse(template.render(context, request))
    
def article(request, article_id):
    template = loader.get_template('main/article.html')
    article = Article.objects.get(id=article_id)
    context = {
        'article': article,
    }
    return HttpResponse(template.render(context, request))

    

