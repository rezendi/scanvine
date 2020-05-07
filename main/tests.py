from django.test import TestCase

from .models import *
from . import tasks

TEST_TWEET_ID = 1258151068892094468

class MetadataParserTests(TestCase):
    def test_basic_parsing(self):
        html = '<html><head><title>TestTitle1</title><meta name="author" content="TestAuthor1"></html>'
        metadata = tasks.parse_article(html)
        self.assertEqual("TestTitle1", metadata['sv_title'])
        self.assertEqual("TestAuthor1", metadata['sv_author'])

    def test_share_fetch_parse(self):
        tasks.add_tweet(TEST_TWEET_ID)
        shares = Share.objects.filter(twitter_id=TEST_TWEET_ID)
        self.assertTrue(len(shares)>0)
        share = shares[0]
        self.assertIsNotNone(share.article_id)
        article = Article.objects.get(id=share.article_id)
        tasks.parse_article_metadata(article.id)
        article.refresh_from_db()
        self.assertIsNotNone(article.author_id)

class AuthorTests(TestCase):
    def test_complex_name(self):
        url = "http://test.com"
        html = '<html><head><title>TestTitle1</title><meta name="author" content="Test Author | Associated Press, opinion contributor"></html>'
        article = Article(status=Article.Status.CREATED, language='en', url = url, initial_url=url, contents=html, title='', metadata='')
        article.save()
        tasks.parse_article_metadata(article.id)
        article.refresh_from_db()
        self.assertIsNotNone(article.author_id)
        self.assertEqual("Test Author", article.author.name)

    def test_complex_collaboration(self):
        url = "http://test.com"
        html = '<html><head><title>TestTitle1</title><meta name="author" content="Author1, Author2 | Associated Press, Author3, contributor"></html>'
        article = Article(status=Article.Status.CREATED, language='en', url = url, initial_url=url, contents=html, title='', metadata='')
        article.save()
        tasks.parse_article_metadata(article.id)
        article.refresh_from_db()
        self.assertIsNotNone(article.author_id)
        author = article.author
        self.assertEqual("Author1,Author2,Author3", author.name)
        self.assertTrue(author.is_collaboration)
        collabs = Collaboration.objects.filter(partnership_id=author.id)
        self.assertEqual(3, len(collabs))
