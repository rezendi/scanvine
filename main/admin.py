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
    search_fields = ('twitter_screen_name', 'name', 'profile')

@admin.register(Article)
class ArticleAdmin(ScanvineAdmin):
    change_form_template = "admin/article_change_form.html"
    list_display = ('id', 'title', 'status', 'publication', 'created_at',)
    list_filter = ('status', 'created_at')
    search_fields = ('title',)
    raw_id_fields = ("publication", 'author')
    #   exclude = ('contents',)

    def response_change(self, request, obj):
        if "_reparse" in request.POST:
            parse_article_metadata(obj.id)
            return redirect('/admin/main/article/%s/' % obj.id)
        return super().response_change(request, obj)

@admin.register(Author)
class AuthorAdmin(ScanvineAdmin):
    change_form_template = "admin/author_change_form.html"
    list_display = ('id', 'name', 'created_at',)
    search_fields = ('name',)
    view_on_site = True

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
    list_display = ('id', 'sharer', 'status', 'url', 'article')
    search_fields = ('text',)
    raw_id_fields = ("sharer", 'article')

@admin.register(Tranche)
class TrancheAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'tags')
    list_display = ('id', 'quantity', 'tags', 'created_at',)
    search_fields = ('tags',)

@admin.register(Job)
class JobAdmin(ScanvineAdmin):
    change_list_template = 'admin/job_list.html'
    list_display = ('id', 'name', 'created_at',)
    list_filter = ('status', 'name', 'created_at', 'updated_at')

    def changelist_view(self, request, extra_context=None):

        latest_jobs=[]
        job_names = Job.objects.values('name').distinct()
        for job_name in job_names:
            jobs = Job.objects.filter(name=job_name['name'])[:1]
            if len(jobs)>0:
                latest_jobs.append(jobs[0])
        latest_jobs.sort(key=lambda j:j.created_at, reverse=True)

        counts = {
            'publications' : Publication.objects.count(),
            'articles' : Article.objects.count(),
            'authors' : Author.objects.count(),
            'share' : Share.objects.count(),
            'sharers' : Sharer.objects.count()
        }
        
        latest = {
            'publication' : Publication.objects.all().order_by("-created_at")[:1],
            'article' : Article.objects.order_by("-created_at")[:1],
            'author' : Author.objects.order_by("-created_at")[:1],
            'share' : Share.objects.order_by("-created_at")[:1],
            'sharer' : Sharer.objects.order_by("-created_at")[:1],
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
#            path('ingest_sharers/',         self.ingest_sharers),
            path('refresh_sharers/',        self.refresh_sharers),
            path('fetch_shares/',           self.fetch_shares),
            path('associate_articles/',     self.associate_articles),
            path('parse_unparsed/',         self.parse_unparsed),
            path('analyze_sentiment/',      self.analyze_sentiment),
            path('allocate_credibility/',   self.allocate_credibility),
            path('set_reputations/',        self.set_reputations),
        ]
        return my_urls + urls
    
    def add_new_sharers(self, request):
        get_potential_sharer_ids.delay()
        return redirect('/admin/main/job/')
        
    def refresh_sharers(self, request):
        refresh_sharers.delay()
        return redirect('/admin/main/job/')
        
    def ingest_sharers(self, request):
        ingest_sharers.delay()
        return redirect('/admin/main/job/')

    def fetch_shares(self, request):
        fetch_shares.delay()
        return redirect('/admin/main/job/')

    def associate_articles(self, request):
        associate_articles.delay()
        return redirect('/admin/main/job/')

    def parse_unparsed(self, request):
        parse_unparsed_articles.delay()
        return redirect('/admin/main/job/')

    def analyze_sentiment(self, request):
        analyze_sentiment.delay()
        return redirect('/admin/main/job/')

    def allocate_credibility(self, request):
        allocate_credibility.delay()
        return redirect('/admin/main/job/')

    def set_reputations(self, request):
        set_reputations.delay()
        return redirect('/admin/main/job/')


# cf https://medium.com/@hakibenita/how-to-turn-django-admin-into-a-lightweight-dashboard-a0e0bbf609ad
# possibly eventually https://stackoverflow.com/questions/5544629/retrieve-list-of-tasks-in-a-queue-in-celery/9369466#9369466