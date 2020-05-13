from django.http import HttpResponse
from django.template import loader
from .models import *

def index(request):
    template = loader.get_template('main/index.html')
    articles = Article.objects.filter(status=Article.Status.AUTHOR_ASSOCIATED).order_by('-total_credibility')[:10]
    authors = Author.objects.order_by('-total_credibility')[:10]
    context = {
        'articles': articles,
        'authors': authors,
    }
    return HttpResponse(template.render(context, request))

def author(request, author_id):
    template = loader.get_template('main/author.html')
    author = Author.objects.get(id=author_id)
    context = {
        'author': author,
        'articles': Article.objects.filter(author_id=author_id).order_by("-total_credibility")[:10]
    }
    return HttpResponse(template.render(context, request))

def publication(request, publication_id):
    template = loader.get_template('main/publication.html')
    publication = Publication.objects.get(id=publication_id)
    context = {
        'publication': publication,
        'articles': Article.objects.filter(publication_id=publication_id).order_by("-total_credibility")[:10]
    }
    return HttpResponse(template.render(context, request))

def authors(request):
    template = loader.get_template('main/authors.html')
    authors = Author.objects.all().order_by('-total_credibility')[:10]
    for author in authors:
        author.total_articles = Article.objects.filter(author_id=author.id).count()
        author.latest = Article.objects.filter(author_id=author.id).order_by("-created_at")[:1][0]
    context = {
        'authors': authors,
    }
    return HttpResponse(template.render(context, request))

def publications(request):
    template = loader.get_template('main/publications.html')
    publications = Publication.objects.all().order_by('-total_credibility')[:10]
    for publication in publications:
        publication.total_articles = Article.objects.filter(publication_id=publication.id).count()
        publication.latest = Article.objects.filter(publication_id=publication.id).order_by("-created_at")[:1][0]
    context = {
        'publications': publications,
    }
    return HttpResponse(template.render(context, request))
