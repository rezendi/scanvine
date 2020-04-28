from django.db import models

# Create your models here.

class Sharer(models.Model):
    status = models.IntegerField(db_index=True)
    category = models.IntegerField()
    twitter_list_id = models.BigIntegerField(null=True)
    twitter_id = models.BigIntegerField(null=True, db_index=True)
    twitter_screen_name = models.CharField(max_length=63)
    verified = models.BooleanField()
    name = models.CharField(max_length=255)
    profile = models.CharField(max_length=1023)
    metadata_change_date = models.DateTimeField(null=True, blank=True)
    previous_metadata = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    #statuses
    LISTED = 1

class Author(models.Model):
    status = models.IntegerField(db_index=True)
    name = models.CharField(max_length=255)
    is_collaboration = models.BooleanField()
    metadata = models.TextField()
    current_credibility = models.IntegerField()
    total_credibility = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

class Collaboration(models.Model):
    partnership = models.ForeignKey(Author, on_delete = models.CASCADE, related_name='collaborators')
    individual = models.ForeignKey(Author, on_delete = models.CASCADE, related_name='collaborations')

# might need to break this down into separate publication and site tables
class Publication(models.Model):
    status = models.IntegerField(db_index=True)
    name = models.CharField(max_length=255)
    url = models.URLField()
    url_policy = models.CharField(max_length=255, blank=True, default='')
    average_credibility = models.IntegerField()
    total_credibility = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

class MetadataParser(models.Model):
    status = models.IntegerField()
    name = models.CharField(max_length=255)
    contents = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    
class PublicationParser(models.Model):
    publication = models.ForeignKey(Publication, on_delete = models.PROTECT)
    parser = models.ForeignKey(MetadataParser, on_delete = models.PROTECT)
    status = models.IntegerField()
    as_of = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

class Article(models.Model):
    publication = models.ForeignKey(Publication, null=True, blank=True, on_delete = models.SET_NULL)
    author = models.ForeignKey(Author, null=True, blank=True, on_delete = models.SET_NULL)
    language = models.CharField(max_length = 5, db_index=True)
    status = models.IntegerField(db_index=True)
    url = models.URLField(db_index=True)
    initial_url = models.URLField(null=True, blank=True)
    title = models.CharField(blank=True, max_length=255)
    contents = models.TextField()
    metadata = models.TextField(blank=True, default='')
    published_at = models.DateTimeField(null=True, blank=True, db_index=True)
    first_published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)
    #statuses
    METADATA_PARSED = 1
    AUTHOR_ASSOCIATED = 2
    #error statuses
    METADATA_PARSE_ERROR = -1
    AUTHOR_NOT_FOUND = -1

class Share(models.Model):
    sharer = models.ForeignKey(Sharer, on_delete=models.PROTECT)
    article = models.ForeignKey(Article, null=True, blank=True, on_delete = models.SET_NULL)
    status = models.IntegerField(db_index=True)
    twitter_id = models.BigIntegerField(null=True, db_index=True)
    source = models.IntegerField(default=0, db_index=True)
    language = models.CharField(max_length = 5, db_index=True)
    text = models.CharField(max_length=4095)
    url = models.URLField()
    sentiment = models.CharField(blank = True, max_length=1023)
    net_sentiment = models.DecimalField(null = True, decimal_places = 2, max_digits = 4, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    #statuses
    ARTICLE_ASSOCIATED = 1
    SENTIMENT_CALCULATED = 2
    CREDIBILITY_ALLOCATED = 3
    #error statuses
    FETCH_ERROR = -1
    ARTICLE_ERROR = -2

class Tranche(models.Model):
    source = models.IntegerField()
    status = models.IntegerField()
    sender = models.BigIntegerField(db_index=True)
    receiver = models.BigIntegerField(db_index=True)
    quantity = models.BigIntegerField()
    category = models.IntegerField()
    type = models.IntegerField()
    tags = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
