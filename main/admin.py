from django.contrib import admin

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
    list_display = ('created_at', 'status', 'publication', 'title',)
    list_filter = ('created_at', 'publication')
    search_fields = ('title',)

@admin.register(Author)
class AuthorAdmin(ScanvineAdmin):
    list_display = ('created_at', 'name',)
    search_fields = ('name',)

admin.site.register(Collaboration)

@admin.register(Publication)
class PublicationAdmin(ScanvineAdmin):
    list_display = ('name', 'url', 'average_credibility', 'total_credibility')
    search_fields = ('name',)

@admin.register(MetadataParser)
class MetadataParserAdmin(ScanvineAdmin):
    list_display = ('name',)
    search_fields = ('contents',)

@admin.register(PublicationParser)
class PublicationParserAdmin(ScanvineAdmin):
    list_display = ('publication', 'parser', 'as_of')

@admin.register(Share)
class ShareAdmin(ScanvineAdmin):
    list_display = ('sharer', 'status', 'url', 'article')
    search_fields = ('text',)

@admin.register(Tranche)
class TrancheAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'tags')
    search_fields = ('tags',)

# possibly eventually https://stackoverflow.com/questions/5544629/retrieve-list-of-tasks-in-a-queue-in-celery/9369466#9369466