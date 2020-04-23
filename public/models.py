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

class Author(models.Model):
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
    url = models.URLField()
    title = models.CharField(max_length=255)
    contents = models.TextField()
    metadata = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class Share(models.Model):
    source = models.ForeignKey(Source, on_delete=models.PROTECT)
    sharer = models.ForeignKey(Sharer, on_delete=models.PROTECT)
    article = models.ForeignKey(Article, null=True, on_delete = models.SET_NULL)
    status = models.IntegerField()
    text = models.CharField(max_length=4095)
    url = models.URLField()
    sentiment = models.CharField(max_length=1023)
    net_sentiment = models.DecimalField(decimal_places = 2, max_digits = 4)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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
