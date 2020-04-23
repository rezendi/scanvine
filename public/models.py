from django.db import models

# Create your models here.

class Sharer(models.Model):
    status = models.IntegerField()
    verified = models.BooleanField()
    category = models.IntegerField()
    name = models.CharField(max_length=255)
    profile = models.CharField(max_length=1023)
    metadata_change_date = models.DateTimeField('date published')
    previous_metadata = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class Source(models.Model):
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class Share(models.Model):
    source = models.ForeignKey(Source)
    sharer = models.ForeignKey(Sharer)
    article = models.ForeignKey(Article, null=True)
    status = models.IntegerField()
    text = models.CharField(max_length=4095)
    url = models.URLField()
    sentiment = models.CharField(max_length=1023)
    net_sentiment = models.DecimalField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class Publication(models.Model):
    name = models.CharField(max_length=255)
    url = models.URLField()
    average_credibility = models.IntegerField()
    total_credibility = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class MetadataParser(models.Model):
    name = models.CharField(max_length=255)
    contents = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
class PublicationParser(models.Model):
    publication = models.ForeignKey(Publication)
    parser = models.ForeignKey(MetadataParser)
    status = models.IntegerField()
    as_of = models.DateTimeField('date published')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class Article(models.Model):
    publication = models.ForeignKey(Publication)
    author = models.ForeignKey(Author)
    status = models.IntegerField()
    url = models.URLField()
    title = models.CharField(max_length=255)
    contents = models.TextField()
    metadata = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class Author(models.Model):
    name = models.CharField(max_length=255)
    collaboration = models.BooleanField()
    metadata = models.TextField()
    current_credibility = models.IntegerField()
    total_credibility = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class Collaboration(models.Model):
    collaboration = models.ForeignKey(Author)
    author = models.ForeignKey(Author)

class Tranche(models.Model):
    sender = models.IntegerField()
    receiver = models.IntegerField()
    quantity = models.IntegerField()
    status = models.IntegerField()
    category = models.IntegerField()
    type = models.IntegerField()
    tags = models.CharField(max_length=255)

class Error(models.Model):
    type = models.IntegerField()
    status = models.IntegerField()
    name = models.CharField(max_length=255)
    data = models.TextField()
