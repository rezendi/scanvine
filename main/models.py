from django.db import models
from django.contrib.auth.models import User
from django.contrib.postgres.fields import JSONField

# Create your models here.

def emptydict():
    return {}

class Sharer(models.Model):
    class Status(models.IntegerChoices):
        LISTED = 2
        SELECTED = 1
        CREATED = 0
        DESELECTED = -1
        DISABLED = -2
        SUGGESTED = -3
        RECOMMENDED = -4
    
    class Category(models.IntegerChoices):
        PERSONAL = -2
        NONE = -1
        HEALTH = 0
        SCIENCE = 1
        TECH = 2
        BUSINESS = 3
        MEDIA = 4

    status = models.IntegerField(choices=Status.choices, db_index=True)
    category = models.IntegerField(choices=Category.choices, db_index=True)
    twitter_list_id = models.BigIntegerField(null=True, blank=True)
    twitter_id = models.BigIntegerField(null=True, db_index=True)
    twitter_screen_name = models.CharField(max_length=63, blank=True, default='')
    verified = models.BooleanField()
    name = models.CharField(max_length=255)
    profile = models.CharField(max_length=1023)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    metadata = JSONField(default=emptydict)

    def __str__(self):
        return "%s (%s)" % (self.twitter_screen_name, self.id)


class Author(models.Model):
    class Status(models.IntegerChoices):
        CREATED = 0

    status = models.IntegerField(db_index=True, choices=Status.choices)
    name = models.CharField(max_length=511, db_index=True)
    is_collaboration = models.BooleanField(db_index=True)
    twitter_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    twitter_screen_name = models.CharField(max_length=63, blank=True, default='')
    metadata = models.TextField(blank=True, default='')
    current_credibility = models.BigIntegerField()
    total_credibility = models.BigIntegerField(default=0, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    average_credibility = models.BigIntegerField(default=0, db_index=True)
    is_collective = models.BooleanField(default=False, db_index=True)

    def __str__(self):
        return self.name[:60] if self.name else "(%s)" %self.id

    def get_absolute_url(self):
        return "/authors/%s" % self.id

    def total_cred(self):
        return 0 if not self.total_credibility else self.total_credibility // 1000

    def average_cred(self):
        return 0 if not self.average_credibility else self.average_credibility // 1000


class Collaboration(models.Model):
    partnership = models.ForeignKey(Author, on_delete = models.CASCADE, related_name='collaborators')
    individual = models.ForeignKey(Author, on_delete = models.CASCADE, related_name='collaborations')

    def __str__(self):
        return "%s (%s)" % (self.individual.name, self.partnership.name)


def default_publication_scores():
    return {
        'total':0, 'health':0, 'science':0, 'tech':0, 'business':0, 'media':0,
        'total_count':0, 'health_count':0, 'science_count':0, 'tech_count':0, 'business_count':0, 'media_count':0,
    }

# might need to break this down into separate publication and site tables
class Publication(models.Model):
    status = models.IntegerField(db_index=True)
    name = models.CharField(max_length=255)
    domain = models.CharField(db_index=True, max_length=255)
    url_policy = models.CharField(max_length=255, blank=True, default='')
    parser_rules = models.TextField(blank=True, default='')
    average_credibility = models.BigIntegerField(default=0)
    total_credibility = models.BigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    scores = JSONField(db_index=True, default=default_publication_scores)
    is_paywalled = models.BooleanField(default=False, db_index=True)

    def __str__(self):
        return self.name if self.name else self.domain

    def get_absolute_url(self):
        return "/publications/%s" % self.id

    def total_cred(self):
        return 0 if not self.total_credibility else self.total_credibility // 1000

    def average_cred(self):
        return 0 if not self.average_credibility else self.average_credibility // 1000


def default_scores():
    return {
        'total':0, 'health':0, 'science':0, 'tech':0, 'business':0, 'media':0
    }


class Article(models.Model):
    class Status(models.IntegerChoices):
        AUTHOR_ASSOCIATED = 3
        PUBLISHER_ASSOCIATED = 2
        METADATA_PARSED = 1
        CREATED = 0
        #errors
        PUBLICATION_PARSE_ERROR = -1
        METADATA_PARSE_ERROR = -2
        AUTHOR_NOT_FOUND = -3
        POTENTIAL_DUPLICATE = -4
    
    publication = models.ForeignKey(Publication, null=True, blank=True, on_delete = models.SET_NULL)
    author = models.ForeignKey(Author, null=True, blank=True, on_delete = models.SET_NULL)
    language = models.CharField(max_length = 5, db_index=True)
    status = models.IntegerField(choices=Status.choices, db_index=True)
    url = models.URLField(db_index=True, blank=True, max_length=1023)
    initial_url = models.URLField(null=True, blank=True, max_length=1023)
    title = models.CharField(blank=True, max_length=255)
    contents = models.TextField()
    metadata = models.TextField(blank=True, default='')
    published_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)
    total_credibility = models.BigIntegerField(default=0, db_index=True)
    scores = JSONField(db_index=True, default=default_scores)
    thumbnail_url = models.URLField(null=True, blank=True, max_length=1023)

    def __str__(self):
        return self.title[0:60] if self.title else "(%s)" %self.id

    def credibility(self):
        return round(self.total_credibility / 1000)

    def display_date(self):
        return self.published_at if self.published_at else self.created_at


class Share(models.Model):
    class Status(models.IntegerChoices):
        CREDIBILITY_FINALIZED = 4
        CREDIBILITY_ALLOCATED = 3
        SENTIMENT_CALCULATED = 2
        ARTICLE_ASSOCIATED = 1
        CREATED = 0
        #errors
        FETCH_ERROR = -1
        ARTICLE_ERROR = -2
        SENTIMENT_ERROR = -3
        SELF_SHARE = -4
        DUPLICATE_SHARE = -5

    sharer = models.ForeignKey(Sharer, on_delete=models.PROTECT)
    article = models.ForeignKey(Article, null=True, blank=True, on_delete = models.SET_NULL)
    status = models.IntegerField(choices=Status.choices, db_index=True)
    twitter_id = models.BigIntegerField(null=True, db_index=True)
    source = models.IntegerField(default=0, db_index=True)
    language = models.CharField(max_length = 5, db_index=True)
    text = models.CharField(max_length=4095)
    url = models.URLField(max_length=1023)
    sentiment = models.CharField(blank = True, max_length=1023)
    net_sentiment = models.DecimalField(null = True, blank = True, decimal_places = 2, max_digits = 4, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    category = models.IntegerField(db_index=True, default=0)
    
    def calculate_sentiment(self, score):
        # very very basic sentiment math
        self.sentiment = score
        self.net_sentiment = 100 * (score['Positive'] - score['Negative'])
        self.net_sentiment = 0.0 if score['Neutral'] > 0.75 else self.net_sentiment
        self.net_sentiment = -0.01 if score['Mixed'] > 0.75 else self.net_sentiment #flag for later

    def share_points(self):
        if self.net_sentiment is None:
            return 0
        if abs(self.net_sentiment) > 80:
            return 5
        if abs(self.net_sentiment) > 60:
            return 3
        if abs(self.net_sentiment) > 40:
            return 2
        if abs(self.net_sentiment) > 20:
            return 1
        return 1

    def __str__(self):
        return "%s (%s)" % (self.text[0:60], self.id)


class FeedShare(models.Model):
    user = models.ForeignKey(User, on_delete = models.CASCADE, related_name='feed_shares')
    share = models.ForeignKey(Share, on_delete = models.CASCADE, related_name='feed_shares')
    created_at = models.DateTimeField(auto_now_add=True)


class Tranche(models.Model):
    source = models.IntegerField()
    status = models.IntegerField()
    sender = models.BigIntegerField(db_index=True)
    receiver = models.BigIntegerField(db_index=True)
    quantity = models.IntegerField()
    category = models.IntegerField()
    type = models.IntegerField()
    tags = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)


class Job(models.Model):
    class Status(models.IntegerChoices):
        COMPLETED = 1
        LAUNCHED = 0
        # errors
        ERROR = -1
    status = models.IntegerField(choices=Status.choices, db_index=True)
    name = models.CharField(max_length=255, db_index=True)
    actions = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "%s %s" % (self.name, self.id)


class List(models.Model):
    status = models.IntegerField(db_index=True)
    twitter_id = models.BigIntegerField(db_index=True)
    metadata = JSONField(default=emptydict)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)


