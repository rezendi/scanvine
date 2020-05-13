from django.http import HttpResponse
from django.template import loader
from .models import *

def index(request):
    template = loader.get_template('main/index.html')
    page_size = int(request.GET.get('s', '10'))
    articles = Article.objects.filter(status=Article.Status.AUTHOR_ASSOCIATED).order_by('-total_credibility')[:page_size]
    authors = Author.objects.order_by('-total_credibility')[:10]
    context = {
        'articles': articles,
        'authors': authors,
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
    authors = Author.objects.all().order_by('-total_credibility')[:page_size]
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
    publications = Publication.objects.all().order_by('-total_credibility')[0:page_size]
    for publication in publications:
        publication.total_articles = Article.objects.filter(publication_id=publication.id).count()
        latest = Article.objects.filter(publication_id=publication.id).order_by("-created_at")[:1]
        publication.latest = latest[0] if latest else None
    context = {
        'publications': publications,
    }
    return HttpResponse(template.render(context, request))
