from django.http import HttpResponse
from django.template import loader
from .models import *

def index(request):
    articles = Article.objects.order_by('-created_at')[:5]
    authors = Author.objects.order_by('-created_at')[:5]
    template = loader.get_template('main/index.html')
    context = {
        'articles': articles,
        'authors': authors,
    }
    return HttpResponse(template.render(context, request))
