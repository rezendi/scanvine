from django.contrib import admin

from .models import *

@admin.register(Sharer)
class SharerAdmin(admin.ModelAdmin):
    list_display = ('twitter_screen_name', 'name', 'profile')
    ordering = ('created_at',)
    search_fields = ('twitter_screen_name', 'name', 'profile')
    list_filter = ('created_at', 'updated_at')

@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'title',)
    ordering = ('created_at',)
    search_fields = ('title',)
    list_filter = ('created_at',)

@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'name',)
    ordering = ('created_at',)
    search_fields = ('name',)
    list_filter = ('created_at', 'updated_at')

admin.site.register(Collaboration)

@admin.register(Publication)
class PublicationAdmin(admin.ModelAdmin):
    list_display = ('name', 'url', 'average_credibility', 'total_credibility')
    ordering = ('-created_at',)
    search_fields = ('name',)
    list_filter = ('created_at', 'updated_at')

@admin.register(MetadataParser)
class MetadataParserAdmin(admin.ModelAdmin):
    list_display = ('name',)
    ordering = ('-created_at',)
    search_fields = ('contents',)
    list_filter = ('created_at', 'updated_at')

@admin.register(PublicationParser)
class PublicationParserAdmin(admin.ModelAdmin):
    list_display = ('publication', 'parser', 'as_of')
    ordering = ('-created_at',)
    list_filter = ('created_at', 'updated_at')

@admin.register(Share)
class ShareAdmin(admin.ModelAdmin):
    list_display = ('sharer', 'text', 'url', 'article')
    ordering = ('-created_at',)
    search_fields = ('text',)
    list_filter = ('created_at')
    list_filter = ('created_at',)

@admin.register(Tranche)
class TrancheAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'tags')
    ordering = ('-created_at',)
    search_fields = ('tags',)
    list_filter = ('created_at',)

# possibly eventually https://stackoverflow.com/questions/5544629/retrieve-list-of-tasks-in-a-queue-in-celery/9369466#9369466