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

# possibly eventually https://stackoverflow.com/questions/5544629/retrieve-list-of-tasks-in-a-queue-in-celery/9369466#9369466