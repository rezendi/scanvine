from django.contrib import admin
from django.urls import path
from django.shortcuts import redirect
from celery import Celery
from .tasks import *
from .models import *

admin.site.site_header = admin.site.site_title = "Scanvine"
admin.site.index_title = "Administration"
 
class ScanvineAdmin(admin.ModelAdmin):
    list_per_page = 100
    ordering = ('-created_at',)
    list_filter = ('status', 'created_at', 'updated_at')


@admin.register(Sharer)
class SharerAdmin(ScanvineAdmin):
    list_display = ('id', 'twitter_screen_name', 'name', 'profile')
    list_filter = ('status', 'category', 'created_at')
    search_fields = ('twitter_screen_name', 'name', 'profile')
    exclude = ('metadata_change_date','previous_metadata')
    actions = ['deselect','list']

    def deselect(modeladmin, request, queryset):
        for obj in queryset:
            obj.status = Sharer.Status.DESELECTED
            obj.save()

    def list(modeladmin, request, queryset):
        for obj in queryset:
            obj.status = Sharer.Status.LISTED
            obj.save()

    def get_search_results(self, request, queryset, search_term):
        if (search_term.startswith("add:")):
            twitter_id = search_term.rpartition(":")[2].rpartition("/")[2]
            add_sharer(int(twitter_id))
            return super().get_search_results(request, queryset, '')
        return super().get_search_results(request, queryset, search_term)



@admin.register(Article)
class ArticleAdmin(ScanvineAdmin):
    change_form_template = "admin/article_change_form.html"
    list_display = ('id', 'title', 'status', 'publication', 'created_at',)
    list_filter = ('status', 'created_at')
    search_fields = ('title', 'contents')
    raw_id_fields = ("publication", 'author')
    exclude = ('contents',)
    actions = ['reparse']
    
    def response_change(self, request, obj):
        if "_reparse" in request.POST:
            parse_article_metadata(obj.id)
            return redirect('/admin/main/article/%s/' % obj.id)
        if "_refetch" in request.POST:
            shares = Share.objects.filter(article_id=obj.id)
            if shares:
                associate_article(shares[0].id, force_refetch=True)
        return super().response_change(request, obj)

    def reparse(modeladmin, request, queryset):
        for obj in queryset:
            parse_article_metadata(obj.id)

    def get_search_results(self, request, queryset, search_term):
        if search_term == "multiple":
            singles = {}
            multis = {}
            for share in Share.objects.all():
                if not share.article_id:
                    continue
                if share.article_id in singles and not share.article_id in multis:
                    multis[share.article_id] = True
                if not share.article_id in singles:
                    singles[share.article_id] = True
            return (Article.objects.filter(id__in=multis.keys()), True)
        return super().get_search_results(request, queryset, search_term)


@admin.register(Author)
class AuthorAdmin(ScanvineAdmin):
    change_form_template = "admin/author_change_form.html"
    list_display = ('id', 'name', 'created_at',)
    search_fields = ('name',)
    view_on_site = True

    def get_search_results(self, request, queryset, search_term):
        if search_term == "empty":
            empty_ids= []
            for author in Author.objects.all():
                articles = Article.objects.filter(author_id=author.id)
                collaborations = Collaboration.objects.filter(individual=author.id)
                if not articles and not collaborations:
                    empty_ids.append(author.id)
            return (Author.objects.filter(id__in=empty_ids), True)
        return super().get_search_results(request, queryset, search_term)


admin.site.register(Collaboration)


@admin.register(Publication)
class PublicationAdmin(ScanvineAdmin):
    change_form_template = "admin/publication_change_form.html"
    list_display = ('id', 'domain', 'name', 'average_credibility', 'total_credibility')
    search_fields = ('name',)

    def response_change(self, request, obj):
        if "_reparse" in request.POST:
            reparse_publication_articles(obj.id)
            return redirect('/admin/main/publication/%s/' % obj.id)
        return super().response_change(request, obj)


@admin.register(Share)
class ShareAdmin(ScanvineAdmin):
    change_form_template = "admin/share_change_form.html"
    list_display = ('id', 'sharer', 'status', 'net_sentiment', 'url')
    search_fields = ('text',)
    raw_id_fields = ("sharer", 'article')
    actions = ['make_published']
    
    def get_search_results(self, request, queryset, search_term):
        if (search_term.startswith("add:")):
            tweet_id = search_term.rpartition(":")[2].rpartition("/")[2]
            share_id = add_tweet(int(tweet_id))
            return (Share.objects.filter(id=share_id), False)
        return super().get_search_results(request, queryset, search_term)

    def response_change(self, request, obj):
        if "_reparse" in request.POST:
            reparse_share(obj.id)
            return redirect('/admin/main/share/%s/' % obj.id)
        return super().response_change(request, obj)
 

@admin.register(Tranche)
class TrancheAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'tags')
    list_display = ('id', 'quantity', 'tags', 'created_at',)
    search_fields = ('tags',)


@admin.register(Job)
class JobAdmin(ScanvineAdmin):
    change_list_template = 'admin/job_list.html'
    list_display = ('id', 'name', 'status', 'created_at',)
    list_filter = ('status', 'name', 'created_at', 'updated_at')

    def changelist_view(self, request, extra_context=None):

        latest_jobs=[]
        job_names = Job.objects.values('name').distinct()
        for job_name in job_names:
            jobs = Job.objects.filter(name=job_name['name']).order_by("-created_at")[:1]
            if len(jobs)>0:
                latest_jobs.append(jobs[0])
        latest_jobs.sort(key=lambda j:j.created_at, reverse=True)

        counts = {
            'pubs' : Publication.objects.count(),
            'articles' : Article.objects.count(),
            'authored' : Article.objects.filter(status=Article.Status.AUTHOR_ASSOCIATED).count(),
            'authors' : Author.objects.count(),
            'shares' : Share.objects.filter(status__gte=Share.Status.CREATED).count(),
            'sharers' : Sharer.objects.filter(status=Sharer.Status.LISTED).count()
        }
        
        latest = {
            'publication' : Publication.objects.all().order_by("-created_at")[:1],
            'article' : Article.objects.order_by("-created_at")[:1],
            'author' : Author.objects.order_by("-created_at")[:1],
            'share' : Share.objects.order_by("-created_at")[:1],
            'sharer' : Sharer.objects.filter(status=Sharer.Status.LISTED).order_by("-updated_at")[:1],
        }
        for key, val in latest.items():
            latest[key] = latest[key][0] if val else None

        extra_context={
            'latest_jobs':latest_jobs,
            'counts' : counts,
            'latest' : latest,
        }
        return super().changelist_view(request, extra_context=extra_context)

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
#            path('add_new_sharers/',        self.add_new_sharers),
            path('ingest_sharers/',         self.ingest_sharers),
            path('refresh_sharers/',        self.refresh_sharers),
            path('fetch_shares/',           self.fetch_shares),
            path('associate_articles/',     self.associate_articles),
            path('parse_unparsed/',         self.parse_unparsed),
            path('analyze_sentiment/',      self.analyze_sentiment),
            path('allocate_credibility/',   self.allocate_credibility),
            path('set_reputations/',        self.set_reputations),
            path('clean_up_jobs/',          self.clean_up_jobs),
        ]
        return my_urls + urls
    
    def refresh_sharers(self, request):
        if request.user.is_superuser:
            refresh_sharers.delay()
            return redirect('/admin/main/job/')
        
    def ingest_sharers(self, request):
        if request.user.is_superuser:
            ingest_sharers.delay()
            return redirect('/admin/main/job/')

    def fetch_shares(self, request):
        if request.user.is_superuser:
            fetch_shares.delay()
            return redirect('/admin/main/job/')

    def associate_articles(self, request):
        if request.user.is_superuser:
            associate_articles.delay()
            return redirect('/admin/main/job/')

    def parse_unparsed(self, request):
        if request.user.is_superuser:
            parse_unparsed_articles.delay()
            return redirect('/admin/main/job/')

    def analyze_sentiment(self, request):
        if request.user.is_superuser:
            analyze_sentiment.delay()
            return redirect('/admin/main/job/')

    def allocate_credibility(self, request):
        if request.user.is_superuser:
            allocate_credibility.delay()
            return redirect('/admin/main/job/')

    def set_reputations(self, request):
        if request.user.is_superuser:
            set_reputations.delay()
            return redirect('/admin/main/job/')

    def clean_up_jobs(self, request):
        if request.user.is_superuser:
            clean_up_jobs.delay()
            return redirect('/admin/main/job/')

# cf https://medium.com/@hakibenita/how-to-turn-django-admin-into-a-lightweight-dashboard-a0e0bbf609ad
# possibly eventually https://stackoverflow.com/questions/5544629/retrieve-list-of-tasks-in-a-queue-in-celery/9369466#9369466

def add_sharer(sharer_id):
    sharers = Sharer.objects.filter(twitter_id=sharer_id)
    if sharers:
        sharer = sharers[0]
    else:
        user = api.GetUser(sharer_id, include_entities=False)
        sharer = Sharer(twitter_id=sharer_id, status=Sharer.Status.CREATED, name=user.name,
                 twitter_screen_name = user.screen_name, profile=user.description, category=0, verified=user.verified)
        sharer.save()
    return sharer

def add_tweet(tweet_id):
    tweet = api.GetStatus(tweet_id, include_entities=True)
    shares = Share.objects.filter(twitter_id=tweet.id)
    share = shares[0] if shares else Share(source=0, language='en', status=Share.Status.CREATED, twitter_id = tweet.id)
    sharer = add_sharer(tweet.user.id)
    share.sharer_id = sharer.id
    share.text = tweet.full_text
    if tweet.urls:
        share.url = tweet.urls[0].expanded_url
    share.save()
    associate_article(share.id, force_refetch=True)
    return share.id

def reparse_share(share_id):
    share = Share.objects.get(id=share_id)
    add_tweet(share.twitter_id)


