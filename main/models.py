from django.db import models

# Create your models here.

class Sharer(models.Model):
    status = models.IntegerField()
    twitter_id = models.BigIntegerField(null=True)
    twitter_screen_name = models.CharField(max_length=63)
    twitter_list_id = models.BigIntegerField(null=True)
    verified = models.BooleanField()
    category = models.IntegerField()
    name = models.CharField(max_length=255)
    profile = models.CharField(max_length=1023)
    metadata_change_date = models.DateTimeField(null=True)
    previous_metadata = models.TextField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class Author(models.Model):
    status = models.IntegerField()
    name = models.CharField(max_length=255)
    is_collaboration = models.BooleanField()
    metadata = models.TextField()
    current_credibility = models.IntegerField()
    total_credibility = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class Collaboration(models.Model):
    partnership = models.ForeignKey(Author, on_delete = models.CASCADE, related_name='collaborators')
    individual = models.ForeignKey(Author, on_delete = models.CASCADE, related_name='collaborations')

class Publication(models.Model):
    status = models.IntegerField()
    name = models.CharField(max_length=255)
    url = models.URLField()
    url_policy = models.CharField(max_length=255)
    average_credibility = models.IntegerField()
    total_credibility = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class MetadataParser(models.Model):
    status = models.IntegerField()
    name = models.CharField(max_length=255)
    contents = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
class PublicationParser(models.Model):
    publication = models.ForeignKey(Publication, on_delete = models.PROTECT)
    parser = models.ForeignKey(MetadataParser, on_delete = models.PROTECT)
    status = models.IntegerField()
    as_of = models.DateTimeField('date published')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class Article(models.Model):
    publication = models.ForeignKey(Publication, null=True, on_delete = models.SET_NULL)
    author = models.ForeignKey(Author, null=True, on_delete = models.SET_NULL)
    status = models.IntegerField()
    language = models.CharField(max_length = 5)
    url = models.URLField()
    initial_url = models.URLField(null=True)
    title = models.CharField(max_length=255)
    contents = models.TextField()
    metadata = models.TextField()
    published_at = models.DateTimeField(null=True)
    first_published_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class Share(models.Model):
    sharer = models.ForeignKey(Sharer, on_delete=models.PROTECT)
    status = models.IntegerField()
    twitter_id = models.BigIntegerField(null=True)
    source = models.IntegerField(null=True)
    language = models.CharField(max_length = 5)
    article = models.ForeignKey(Article, null=True, on_delete = models.SET_NULL)
    text = models.CharField(max_length=4095)
    url = models.URLField()
    sentiment = models.CharField(null = True, max_length=1023)
    net_sentiment = models.DecimalField(null = True, decimal_places = 2, max_digits = 4)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class Tranche(models.Model):
    status = models.IntegerField()
    sender = models.BigIntegerField()
    receiver = models.BigIntegerField()
    quantity = models.BigIntegerField()
    category = models.IntegerField()
    type = models.IntegerField()
    tags = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class Error(models.Model):
    status = models.IntegerField()
    type = models.IntegerField()
    name = models.CharField(max_length=255)
    data = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
