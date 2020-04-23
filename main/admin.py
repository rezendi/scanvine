from django.contrib import admin

from .models import *

admin.site.register(Sharer)
admin.site.register(Author)
admin.site.register(Collaboration)
admin.site.register(Publication)
admin.site.register(MetadataParser)
admin.site.register(PublicationParser)
admin.site.register(Article)
admin.site.register(Share)
admin.site.register(Tranche)
admin.site.register(Error)
