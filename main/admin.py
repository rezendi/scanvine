from django.contrib import admin
from django.urls import path
from django.shortcuts import redirect
from django.db.models import Count, IntegerField
from django.db.models.functions import Cast
from django.contrib.postgres.fields.jsonb import KeyTextTransform
from celery import Celery
from .models import *
from .tasks import *
from .metatasks import *

admin.site.site_header = admin.site.site_title = "Scanvine"
admin.site.index_title = "Administration"
 
class ScanvineAdmin(admin.ModelAdmin):
    list_per_page = 100
    ordering = ('-created_at',)
    list_filter = ('status', 'created_at', 'updated_at')


@admin.register(Sharer)
class SharerAdmin(ScanvineAdmin):
    change_form_template = "admin/sharer_change_form.html"
    list_display = ('id', 'twitter_screen_name', 'name', 'profile')
    list_filter = ('status', 'category', 'protected', 'created_at', 'updated_at')
    search_fields = ('twitter_screen_name', 'name', 'profile')
    actions = ['deselect','select','health','science','tech','business','four']
    readonly_fields= ('created_at','updated_at')
    fields = (
        ('status','category'),
        'twitter_screen_name',
        'name',
        'profile',
        ('twitter_id','twitter_list_id','verified','protected'),
        ('created_at','updated_at'),
        'metadata'
    )

    def deselect(modeladmin, request, queryset):
        for obj in queryset:
            obj.status = Sharer.Status.DESELECTED
            obj.save()

    def select(modeladmin, request, queryset):
        for obj in queryset:
            obj.status = Sharer.Status.SELECTED
            obj.save()

    def health(modeladmin, request, queryset):
        for obj in queryset:
            obj.category = Sharer.Category.HEALTH
            obj.save()

    def science(modeladmin, request, queryset):
        for obj in queryset:
            obj.category = Sharer.Category.SCIENCE
            obj.save()

    def tech(modeladmin, request, queryset):
        for obj in queryset:
            obj.category = Sharer.Category.TECH
            obj.save()

    def business(modeladmin, request, queryset):
        for obj in queryset:
            obj.category = Sharer.Category.BUSINESS
            obj.save()

    def four(modeladmin, request, queryset):
        for obj in queryset:
            obj.category = Sharer.Category.MEDIA
            obj.save()

    def get_search_results(self, request, queryset, search_term):
        if (search_term.startswith("add:")):
            twitter_id = search_term.rpartition(":")[2].rpartition("/")[2]
            sharer_id = add_sharer(twitter_id)
            return (Sharer.objects.filter(id=sharer_id), False)
        if (search_term.startswith("weighted")):
            terms = search_term.partition(" ")
            base_term = terms[2]
            (base_results, bool) = super().get_search_results(request, queryset, base_term)
            weight_term = terms[0]
            category = weight_term.partition(":")[2]
            queryset = base_results.annotate(
                list_weights = KeyTextTransform('list_weights', 'metadata')
            ).annotate(
                weight = Cast(KeyTextTransform(category, 'list_weights'), IntegerField())
            ).filter(weight__gt=0).filter(status=Sharer.Status.RECOMMENDED).order_by("-weight")
            return (queryset, bool)
        return super().get_search_results(request, queryset, search_term)

    def get_actions(self, request):
        actions = super().get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions


@admin.register(Article)
class ArticleAdmin(ScanvineAdmin):
    change_form_template = "admin/article_change_form.html"
    list_display = ('id', 'title', 'status', 'publication', 'created_at',)
    list_filter = ('status', 'created_at')
    search_fields = ('title', 'metadata')
    raw_id_fields = ("publication", 'author')
    excluse = ('content')
    actions = ['reparse']
    readonly_fields= ('created_at','updated_at')
    fieldsets = (
        (None, {
            'fields': ( 'title', ('publication', 'author'), ('status', 'language'), 'url', 'thumbnail_url', 'total_credibility', ('created_at','updated_at','published_at') )
        }),
        ('Metadata', {
            'classes': ('collapse',),
            'fields': ('initial_url','metadata','scores',),
        }),
    )
    
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
        if search_term == "empty":
            query = Article.objects.annotate(
                shares=Count('share__pk', distinct=True),
            ).filter(shares=0)
            return (query, True)
        return super().get_search_results(request, queryset, search_term)


@admin.register(Author)
class AuthorAdmin(ScanvineAdmin):
    change_form_template = "admin/author_change_form.html"
    list_display = ('id', 'name', 'twitter_screen_name', 'created_at',)
    search_fields = ('name',)
    readonly_fields= ('created_at','updated_at')
    fields = (
        ('status','is_collaboration', 'is_collective'),
        'name',
        'twitter_screen_name',
        'twitter_id',
        ('total_credibility','current_credibility'),
        ('created_at','updated_at'),
        'metadata',
    )

    def get_search_results(self, request, queryset, search_term):
        if search_term == "empty":
            query = Author.objects.annotate(
                articles=Count('article__pk', distinct=True),
                collabs=Count('collaborations__partnership', distinct=True),
            ).filter(articles=0, collabs=0)
            return (query, True)
        return super().get_search_results(request, queryset, search_term)


admin.site.register(Collaboration)


@admin.register(Publication)
class PublicationAdmin(ScanvineAdmin):
    change_form_template = "admin/publication_change_form.html"
    list_display = ('id', 'domain', 'name', 'average_credibility', 'total_credibility')
    search_fields = ('name','domain')
    readonly_fields= ('created_at','updated_at')
    fields = (
        ('status','name'),
        ('domain', 'is_paywalled'),
        'url_policy',
        'parser_rules',
        ('average_credibility', 'total_credibility'),
        ('created_at','updated_at'),
        'scores'
    )

    def response_change(self, request, obj):
        if "_reparse" in request.POST:
            reparse_publication_articles(obj.id)
            return redirect('/admin/main/publication/%s/' % obj.id)
        return super().response_change(request, obj)


@admin.register(Share)
class ShareAdmin(ScanvineAdmin):
    change_form_template = "admin/share_change_form.html"
    list_display = ('id', 'sharer', 'status', 'net_sentiment', 'created_at', 'url')
    list_filter = ('status', 'category', 'created_at', 'updated_at')
    search_fields = ('text','url')
    raw_id_fields = ("sharer", 'article')
    actions = ['make_published']
    readonly_fields= ('created_at','updated_at')
    fields = (
        'sharer',
        'article',
        ('status', 'category'),
        'twitter_id',
        'text',
        ('source','language'),
        ('net_sentiment', 'sentiment'),
        ('created_at','updated_at')
    )
    
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
    list_display = ('id', 'quantity', 'tags', 'sender', 'receiver', 'created_at',)
    search_fields = ('tags',)


@admin.register(Job)
class JobAdmin(ScanvineAdmin):
    change_list_template = 'admin/job_list.html'
    list_display = ('id', 'name', 'status', 'created_at', 'updated_at')
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
            path('set_scores/',             self.set_scores),
            path('reparse_articles/',       self.reparse_articles),
            path('clean_up_jobs/',          self.clean_up_jobs),
            path('get_lists/',              self.get_lists),
            path('get_list_members/',       self.get_list_members),
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

    def set_scores(self, request):
        if request.user.is_superuser:
            set_scores.delay()
            return redirect('/admin/main/job/')

    def reparse_articles(self, request):
        if request.user.is_superuser:
            reparse_articles.delay()
            return redirect('/admin/main/job/')

    def clean_up_jobs(self, request):
        if request.user.is_superuser:
            clean_up_jobs.delay()
            return redirect('/admin/main/job/')

    def get_lists(self, request):
        if request.user.is_superuser:
            get_lists.delay()
            return redirect('/admin/main/job/')

    def get_list_members(self, request):
        if request.user.is_superuser:
            get_list_members.delay()
            return redirect('/admin/main/job/')


@admin.register(List)
class ListAdmin(ScanvineAdmin):
    list_display = ('id', 'twitter_id', 'metadata')


# Utility methods

def add_sharer(arg):
    sharer_id = None
    screen_name = None
    if arg.isnumeric():
        sharer_id = int(arg)
        existing = Sharer.objects.filter(twitter_id=sharer_id)
    else:
        screen_name = arg
        existing = Sharer.objects.filter(twitter_screen_name__iexact=screen_name)

    if existing:
        sharer = existing[0]
    else:
        user = api.GetUser(user_id=sharer_id, screen_name=screen_name, include_entities=False)
        sharer = Sharer(twitter_id=user.id, name=user.name, twitter_screen_name = user.screen_name, protected=user.protected,
                        profile=user.description, verified=user.verified, status=Sharer.Status.CREATED, category=-1)
        sharer.save()
    return sharer.id if sharer else None

def add_tweet(tweet_id):
    tweet = api.GetStatus(tweet_id, include_entities=True)
    # print("tweet %s" % tweet)
    urls = []
    if tweet.urls:
        urls += [u.expanded_url for u in tweet.urls]
    if tweet.quoted_status and tweet.quoted_status.urls:
        urls += [u.expanded_url for u in tweet.quoted_status.urls]
    if tweet.retweeted_status and tweet.retweeted_status.urls:
        urls += [u.expanded_url for u in tweet.retweeted_status.urls]
    urls = [u for u in urls if not u.startswith("https://twitter.com/") and not u.startswith("https://mobile.twitter.com/")]
    if not urls:
        print("No URL in share, bailing out")
        return

    shares = Share.objects.filter(twitter_id=tweet.id)
    share = shares[0] if shares else Share(source=0, language='en', status=Share.Status.CREATED, twitter_id = tweet.id)
    share.url = urls[0]
    share.text = tweet.full_text
    sharer_id = add_sharer(tweet.user.id_str)
    share.sharer_id = sharer_id
    share.save()
    associate_article(share.id, force_refetch=True)
    return share.id

def reparse_share(share_id):
    share = Share.objects.get(id=share_id)
    add_tweet(share.twitter_id)


