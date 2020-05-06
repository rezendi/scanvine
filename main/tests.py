from django.test import TestCase

from . import models, tasks

class MetadataParserTests(TestCase):
    def test_basic_parsing(self):
        html = '<html><head><title>TestTitle1</title><meta name="author" content="TestAuthor1"></html>'
        metadata = tasks.parse_article(html)
        self.assertEqual("TestTitle1", metadata['sv_title'])
        self.assertEqual("TestAuthor1", metadata['sv_author'])

    def test_share_fetch(self):
        html = '<html><head><title>TestTitle1</title><meta name="author" content="TestAuthor1"></html>'
        tasks.add_tweet(1258151068892094468)
        shares = models.Share.objects.filter(twitter_id=1258151068892094468)
        self.assertTrue(len(shares)>0)
        share = shares[0]
        self.assertIsNotNone(share.article_id)
        article = models.Article.objects.get(id=share.article_id)
        tasks.parse_article_metadata(article.id)
        article.refresh_from_db()
        self.assertIsNotNone(article.author_id)
