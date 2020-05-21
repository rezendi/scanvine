import datetime, math
from django.shortcuts import render
from django.utils import timezone
from django.db.models import F, Q, IntegerField, Subquery
from django.db.models.functions import Cast, Coalesce
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
    days = int(days) if days else 1
    scoring = 'top' if scoring != "raw" and scoring != "odd" and scoring != "latest" else scoring
    end_date = timezone.now() + datetime.timedelta(minutes=5)
    start_date = end_date - datetime.timedelta(days=days)
    print("end_date %s" % end_date)
    category = 'total' if not category or category not in CATEGORIES else category
    articles_query = Article.objects.select_related('publication').annotate(
        score=Cast(KeyTextTransform(category, 'scores'), IntegerField()),
        pub_category_average=Cast(KeyTextTransform(category, 'publication__scores'), IntegerField()),
        buzz=(F('score') - F('pub_category_average')),
        pub_article_count=Cast(KeyTextTransform('%s_count' % category, 'publication__scores'), IntegerField()),
        odd=(F('score') / (F('pub_article_count')+1)),
    ).filter(status=Article.Status.AUTHOR_ASSOCIATED, odd__isnull=False).filter(
        Q(published_at__range=(start_date, end_date)) | Q(published_at__isnull=True, created_at__range=(start_date,end_date))
    ).defer('contents','metadata')

    articles = []
    if scoring=='latest':
        articles = articles_query.order_by(Coalesce(F('published_at'),F('created_at')).desc())[:page_size]

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

    (category_links, scoring_links, timing_links) = get_links(category, scoring, days)
    
    if request.GET.get('svd','')=='true':
        for array in [category_links, scoring_links, timing_links]:
            for vals in array:
                vals['href'] = vals['href'] + "?svd=true" if vals['href']!='no' else vals['href']

    category = '' if category=='total' else category
    
    context = {
        'category': category.title(),
        'scoring' : scoring.title(),
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

def get_links(category='all', scoring='top', days=1):
    category_links = [{'name':'All', 'href': 'no' if category in ['all','total'] else 'all/%s/%s' % (scoring,days)}]
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
    return (category_links, scoring_links, timing_links)


def author_view(request, author_id):
    page_size = int(request.GET.get('s', '20'))
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
        print("partner_ids %s" % partner_ids)
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


def article_view(request, article_id):
    article = Article.objects.get(id=article_id)
    (category_links, scoring_links, timing_links) = get_links()
    context = {
        'article': article,
        'shares': Share.objects.filter(article_id=article.id).distinct('sharer_id'),
        'category_links': category_links,
        'scoring_links' : scoring_links,
        'timing_links' : timing_links,
    }
    return render(request, 'main/article.html', context)


def publication_view(request, publication_id):
    page_size = int(request.GET.get('s', '20'))
    days = int(request.GET.get('d', '7'))
    publication = Publication.objects.get(id=publication_id)
    articles = Article.objects.filter(publication_id=publication_id)
    article_count = articles.count()
    if days > 0:
        end_date = timezone.now() + datetime.timedelta(minutes=5)
        start_date = end_date - datetime.timedelta(days=days)
        articles = articles.filter(created_at__range=(start_date, end_date)).defer('contents','metadata')

    (category_links, scoring_links, timing_links) = get_links()
    context = {
        'publication' : publication,
        'articles' : articles.order_by('-total_credibility')[:page_size],
        'article_count' : article_count,
        'category_links': category_links,
        'scoring_links' : scoring_links,
        'timing_links' : timing_links,
    }
    return render(request, 'main/publication.html', context)

def authors_view(request, category=None, publication_id = None):
    page_size = int(request.GET.get('s', '20'))
    sort = request.GET.get('o', '-average_credibility')
    authors = Author.objects.all()
    if publication_id:
        pub_author_ids = Article.objects.filter(publication_id=publication_id).distinct('author_id').values('author_id')
        authors = authors.filter(id__in=pub_author_ids)
    if category:
        # TODO: really we need some kind of GROUP BY aggregate here
        category_id = CATEGORIES.index(category)
        cat_article_ids = Share.objects.filter(status__gte=Share.Status.CREATED, category=category_id).distinct('article_id').values('article_id')
        cat_author_ids = Article.objects.filter(id__in=cat_article_ids).distinct('author_id').values('author_id')
        authors = authors.filter(id__in=cat_author_ids)
    authors = authors.order_by(sort)[:page_size]
    for author in authors:
        author.total_articles = Article.objects.filter(author_id=author.id).count()
        latest = Article.objects.filter(author_id=author.id).order_by("-created_at")[:1]
        author.latest = latest[0] if latest else None

    (category_links, scoring_links, timing_links) = get_links()
    context = {
        'authors': authors,
        'category_links': category_links,
        'scoring_links' : scoring_links,
        'timing_links' : timing_links,
    }
    return render(request, 'main/authors.html', context)


def publications_view(request):
    page_size = int(request.GET.get('s', '20'))
    sort = request.GET.get('o', '-average_credibility')
    publications = Publication.objects.all().order_by(sort)[:page_size]
    for publication in publications:
        publication.total_articles = Article.objects.filter(publication_id=publication.id).count()
        latest = Article.objects.filter(publication_id=publication.id).order_by('-created_at')[:1]
        publication.latest = latest[0] if latest else None

    (category_links, scoring_links, timing_links) = get_links()
    context = {
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
    category_id = CATEGORIES.index(category)
    page_size = int(request.GET.get('s', '100'))
    shares = Share.objects.filter(category=category_id).order_by("created_at")[:page_size]
    context = {
        'category' : category.title(),
        'shares' : shares,
    }
    return render(request, 'main/shares.html', context)
