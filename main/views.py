import datetime
from django.http import HttpResponse
from django.template import loader
from .models import *
from django.db.models.functions import Cast
from django.contrib.postgres.fields.jsonb import KeyTextTransform

SORT_BY = {
    'dc':'-created_at',
    'oc':'-created_at',
    'ds':'-total_credibility',
    'os':'total_credibility',
    'da':'-average_credibility',
    'a':'average_credibility',
}

def index(request):
    template = loader.get_template('main/index.html')
    page_size = int(request.GET.get('s', '10'))
    days = int(request.GET.get('d', '3'))
    end_date = datetime.datetime.utcnow().date() + datetime.timedelta(days=1)
    start_date = end_date - datetime.timedelta(days=days)
    articles = Article.objects.filter(status=Article.Status.AUTHOR_ASSOCIATED).filter(created_at__range=(start_date, end_date)).defer('contents','metadata')
    context = {
        'category': 'Top',
        'articles': articles.order_by('-total_credibility')[:page_size],
    }
    return HttpResponse(template.render(context, request))

def author(request, author_id):
    template = loader.get_template('main/author.html')
    page_size = int(request.GET.get('s', '10'))
    days = int(request.GET.get('d', '0'))
    author = Author.objects.get(id=author_id)
    articles = Article.objects.filter(author_id=author_id)
    if days > 0:
        end_date = datetime.datetime.utcnow().date() + datetime.timedelta(days=1)
        start_date = end_date - datetime.timedelta(days=days)
        articles = articles.filter(created_at__range=(start_date, end_date)).defer('contents','metadata')
    context = {
        'author': author,
        'articles': articles.order_by('-total_credibility')[:page_size]
    }
    return HttpResponse(template.render(context, request))

def publication(request, publication_id):
    template = loader.get_template('main/publication.html')
    page_size = int(request.GET.get('s', '10'))
    days = int(request.GET.get('d', '7'))
    publication = Publication.objects.get(id=publication_id)
    articles = Article.objects.filter(publication_id=publication_id)
    if days > 0:
        end_date = datetime.datetime.utcnow().date() + datetime.timedelta(days=1)
        start_date = end_date - datetime.timedelta(days=days)
        articles = articles.filter(created_at__range=(start_date, end_date)).defer('contents','metadata')
    context = {
        'publication': publication,
        'articles': articles.order_by('-total_credibility')[:page_size]
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
    template = loader.get_template('main/category.html')
    category_key = category.lower()
    page_size = int(request.GET.get('s', '10'))
    days = int(request.GET.get('d', '3'))
    end_date = datetime.datetime.utcnow().date() + datetime.timedelta(days=1)
    start_date = end_date - datetime.timedelta(days=days)

    articles = Article.objects.annotate(
        score=Cast(
            KeyTextTransform(category_key, 'scores'), models.IntegerField()
        )
    ).filter(status=Article.Status.AUTHOR_ASSOCIATED).filter(created_at__range=(start_date, end_date)).defer('contents','metadata').order_by("-score")[:page_size]

    for article in articles:
        article.score = round(article.score/1000)

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
        'shares': Share.objects.filter(article_id=article.id)
    }
    return HttpResponse(template.render(context, request))

def buzz(request):
    template = loader.get_template('main/index.html')
    page_size = int(request.GET.get('s', '10'))
    days = int(request.GET.get('d', '3'))
    end_date = datetime.datetime.utcnow().date() + datetime.timedelta(days=1)
    start_date = end_date - datetime.timedelta(days=days)
    order_by = 'score' if request.GET.get('o')=='r' else '-score'
    articles = Article.objects.annotate(
        score=Cast(
            KeyTextTransform('publisher_average', 'scores'), models.IntegerField()
        )
    ).filter(status=Article.Status.AUTHOR_ASSOCIATED).filter(created_at__range=(start_date, end_date)).defer('contents','metadata').order_by(order_by)[:page_size]
    
    for article in articles:
        print("score %s" % article.scores)
    context = {
        'category': 'Buzz',
        'articles': articles,
    }
    return HttpResponse(template.render(context, request))
    

