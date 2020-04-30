from django.contrib import admin
from django.urls import path
from django.shortcuts import redirect
from celery import Celery
from .tasks import *
from .models import *

class ScanvineAdmin(admin.ModelAdmin):
    list_per_page = 100
    ordering = ('-created_at',)
    list_filter = ('created_at', 'updated_at', 'status')

@admin.register(Sharer)
class SharerAdmin(ScanvineAdmin):
    list_display = ('twitter_screen_name', 'name', 'profile')
    search_fields = ('twitter_screen_name', 'name', 'profile')

@admin.register(Article)
class ArticleAdmin(ScanvineAdmin):
    change_form_template = "admin/article_change_form.html"
    list_display = ('id', 'title', 'status', 'publication', 'created_at',)
    list_filter = ('created_at', 'status')
    search_fields = ('title',)
    raw_id_fields = ("publication", 'author')

    def response_change(self, request, obj):
        print("obj %s" % obj.id)
        if "_reparse" in request.POST:
            parse_article_metadata.delay(obj.id)
            return redirect('/admin/main/article/%s/' % obj.id)
        return super().response_change(request, obj)

@admin.register(Author)
class AuthorAdmin(ScanvineAdmin):
    list_display = ('name', 'created_at',)
    search_fields = ('name',)
    view_on_site = True

admin.site.register(Collaboration)

@admin.register(Publication)
class PublicationAdmin(ScanvineAdmin):
    list_display = ('domain', 'name', 'average_credibility', 'total_credibility')
    search_fields = ('name',)

@admin.register(Share)
class ShareAdmin(ScanvineAdmin):
    list_display = ('sharer', 'status', 'url', 'article')
    search_fields = ('text',)
    raw_id_fields = ("sharer", 'article')

@admin.register(Tranche)
class TrancheAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'tags')
    search_fields = ('tags',)

@admin.register(Job)
class JobAdmin(ScanvineAdmin):
    change_list_template = 'admin/job_list.html'

    def changelist_view(self, request, extra_context=None):
        return super().changelist_view(request, extra_context=extra_context)

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path('add_new_sharers/',        self.add_new_sharers),
            path('refresh_sharers/',        self.refresh_sharers),
            path('ingest_sharers/',         self.ingest_sharers),
            path('fetch_shares/',           self.fetch_shares),
            path('associate_articles/',     self.associate_articles),
            path('parse_unparsed/',         self.parse_unparsed),
            path('analyze_sentiment/',      self.analyze_sentiment),
            path('allocate_credibility/',   self.allocate_credibility),
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


# cf https://medium.com/@hakibenita/how-to-turn-django-admin-into-a-lightweight-dashboard-a0e0bbf609ad
# possibly eventually https://stackoverflow.com/questions/5544629/retrieve-list-of-tasks-in-a-queue-in-celery/9369466#9369466