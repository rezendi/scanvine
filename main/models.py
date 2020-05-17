from django.db import models
from django.contrib.postgres.fields import JSONField

# Create your models here.

class Sharer(models.Model):
    class Status(models.IntegerChoices):
        LISTED = 2
        SELECTED = 1
        CREATED = 0
        DESELECTED = -1
        DISABLED = -2
    
    class Category(models.IntegerChoices):
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

    def __str__(self):
        return "%s (%s)" % (self.twitter_screen_name, self.id)


class Author(models.Model):
    class Status(models.IntegerChoices):
        CREATED = 0

    status = models.IntegerField(db_index=True, choices=Status.choices)
    name = models.CharField(max_length=255)
    is_collaboration = models.BooleanField()
    twitter_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    twitter_screen_name = models.CharField(max_length=63, blank=True, default='')
    metadata = models.TextField(blank=True, default='')
    current_credibility = models.BigIntegerField()
    total_credibility = models.BigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name[:60] if self.name else "(%s)" %self.id

    def get_absolute_url(self):
        return "/authors/%s" % self.id

    def credibility(self):
        return round(self.total_credibility / 1000)


class Collaboration(models.Model):
    partnership = models.ForeignKey(Author, on_delete = models.CASCADE, related_name='collaborators')
    individual = models.ForeignKey(Author, on_delete = models.CASCADE, related_name='collaborations')

    def __str__(self):
        return "%s (%s)" % (self.individual.name, self.partnership.name)


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

    def __str__(self):
        return self.name if self.name else self.domain

    def get_absolute_url(self):
        return "/publications/%s" % self.id

    def total_cred(self):
        return round(self.total_credibility / 1000)

    def average_cred(self):
        return round(self.average_credibility / 1000)


def default_scores():
    return {
        'total':0, 'publisher_average':0, 'health':0, 'science':0, 'tech':0, 'business':0, 'media':0
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
    
    publication = models.ForeignKey(Publication, null=True, blank=True, on_delete = models.SET_NULL)
    author = models.ForeignKey(Author, null=True, blank=True, on_delete = models.SET_NULL)
    language = models.CharField(max_length = 5, db_index=True)
    status = models.IntegerField(choices=Status.choices, db_index=True)
    url = models.URLField(db_index=True, blank=True)
    initial_url = models.URLField(null=True, blank=True)
    title = models.CharField(blank=True, max_length=255)
    contents = models.TextField()
    metadata = models.TextField(blank=True, default='')
    published_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)
    total_credibility = models.BigIntegerField(default=0, db_index=True)
    scores = JSONField(db_index=True, default=default_scores)

    def __str__(self):
        return self.title[0:60] if self.title else "(%s)" %self.id

    def credibility(self):
        return round(self.total_credibility / 1000)

    def relative_cred(self):
        return round(int(self.scores['publisher_average']) / 1000)


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

    sharer = models.ForeignKey(Sharer, on_delete=models.PROTECT)
    article = models.ForeignKey(Article, null=True, blank=True, on_delete = models.SET_NULL)
    status = models.IntegerField(choices=Status.choices, db_index=True)
    twitter_id = models.BigIntegerField(null=True, db_index=True)
    source = models.IntegerField(default=0, db_index=True)
    language = models.CharField(max_length = 5, db_index=True)
    text = models.CharField(max_length=4095)
    url = models.URLField()
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
            return 8
        if abs(self.net_sentiment) > 60:
            return 5
        if abs(self.net_sentiment) > 40:
            return 3
        if abs(self.net_sentiment) > 20:
            return 2
        return 1

    def __str__(self):
        return "%s (%s)" % (self.text[0:60], self.id)


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
