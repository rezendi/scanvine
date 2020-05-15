from django.test import TestCase

from .models import *
from . import tasks, admin

TEST_TWEET_ID = 1258151068892094468

class MetadataParserTest(TestCase):
    def test_basic_parsing(self):
        html = '<html><title>Test Title 1</title><meta name="author" content="Test Author 1"><meta name="publisher" content="Test Pub 1"></html>'
        metadata = tasks.parse_article(html)
        self.assertEqual("Test Title 1", metadata['sv_title'])
        self.assertEqual("Test Author 1", metadata['sv_author'])
        self.assertEqual("Test Pub 1", metadata['sv_publication'])

class AuthorTests(TestCase):
    def test_complex_name(self):
        url = "http://test.com"
        html = '<html><title>TestTitle1</title><meta name="author" content="Test Writer | Associated Press, opinion contributor"></html>'
        article = Article(status=Article.Status.CREATED, language='en', url = url, initial_url=url, contents=html, title='', metadata='')
        article.save()
        tasks.parse_article_metadata(article.id)
        article.refresh_from_db()
        author_id = article.author_id
        self.assertIsNotNone(author_id)
        self.assertEqual("Test Writer", article.author.name)
        article2 = Article(status=Article.Status.CREATED, language='en', url = url, initial_url=url, contents=html, title='', metadata='')
        article2.save()
        tasks.parse_article_metadata(article2.id)
        article2.refresh_from_db()
        self.assertEqual(author_id, article2.author_id)

    def test_complex_collaboration(self):
        url = "http://test.com"
        html = '<html><title>TestTitle1</title><meta name="author" content="Writer 1, Writer 2 | Associated Press, Writer 3, contributor"></html>'
        article = Article(status=Article.Status.CREATED, language='en', url = url, initial_url=url, contents=html, title='', metadata='')
        article.save()
        tasks.parse_article_metadata(article.id)
        article.refresh_from_db()
        author_id = article.author_id
        self.assertIsNotNone(author_id)
        author = article.author
        self.assertEqual("Writer 1,Writer 2,Writer 3", author.name)
        self.assertTrue(author.is_collaboration)
        collabs = Collaboration.objects.filter(partnership_id=author.id)
        self.assertEqual(3, len(collabs))
        article2 = Article(status=Article.Status.CREATED, language='en', url = url, initial_url=url, contents=html, title='', metadata='')
        article2.save()
        tasks.parse_article_metadata(article2.id)
        article2.refresh_from_db()
        self.assertEqual(author_id, article2.author_id)

    def test_word_counts(self):
        url = "http://test.com"
        html = '<html><title>TestTitle1</title><meta name="author" content="Author1,Author2,Author3"></html>'
        article = Article(status=Article.Status.CREATED, language='en', url = url, initial_url=url, contents=html, title='', metadata='')
        article.save()
        tasks.parse_article_metadata(article.id)
        article.refresh_from_db()
        self.assertIsNone(article.author, 'Only one-word names')
        article.html = '<html><title>TestTitle1</title><meta name="author" content="Author1,This is a lot of words"></html>'
        article.save()
        tasks.parse_article_metadata(article.id)
        article.refresh_from_db()
        self.assertIsNone(article.author, 'Too many words')
        article.html =  '<html><title>TestTitle1</title><meta name="author" content="Author1,Writer Two, Author3, Writer Four, Author5"></html>'
        article.save()
        tasks.parse_article_metadata(article.id)
        article.refresh_from_db()
        self.assertIsNone(article.author, 'Too many single-word names')

    def test_word_counts_2(self):
        url = "http://test.com"
        html = '<html><title>TestTitle1</title><meta name="author" content="Writer1,Writer Two, Writer Four"></html>'
        article = Article(status=Article.Status.CREATED, language='en', url = url, initial_url=url, contents=html, title='', metadata='')
        article.save()
        tasks.parse_article_metadata(article.id)
        article.refresh_from_db()
        self.assertIsNotNone(article.author, 'Half and half is OK')
        
    def test_ld_json(self):
        url = "http://test.com"
        html = '<html><script type="application/ld+json">{"@graph":[{"name":"Hospital staff carrying COVID-19","author":{"name":"Chris Smith"}}]}</script>'
        article = Article(status=Article.Status.CREATED, language='en', url = url, initial_url=url, contents=html, title='', metadata='')
        article.save()
        tasks.parse_article_metadata(article.id)
        article.refresh_from_db()
        self.assertEqual(article.author.name, 'Chris Smith')

    def test_ld_json_2(self):
        url = "http://test.com"
        html = '<html><script type="application/ld+json">{"@graph":{"name":"Jessica Jones"}}</script>'
        article = Article(status=Article.Status.CREATED, language='en', url = url, initial_url=url, contents=html, title='', metadata='')
        article.save()
        tasks.parse_article_metadata(article.id)
        article.refresh_from_db()
        self.assertEqual(article.author.name, 'Jessica Jones')

    def test_ld_json_3(self):
        url = "http://test.com"
        html = '<html><script type="application/ld+json">{"author":[{"name":"Jessica Jones"},{"name":"Chris Smith"}]}</script>'
        article = Article(status=Article.Status.CREATED, language='en', url = url, initial_url=url, contents=html, title='', metadata='')
        article.save()
        tasks.parse_article_metadata(article.id)
        article.refresh_from_db()
        self.assertEqual(article.author.name, 'Jessica Jones,Chris Smith')

    def test_ld_json_4(self):
        url = "http://test.com"
        html = '<html><script type="application/ld+json">{"creator":[{"name":"Jessica Smith"}]}</script>'
        article = Article(status=Article.Status.CREATED, language='en', url = url, initial_url=url, contents=html, title='', metadata='')
        article.save()
        tasks.parse_article_metadata(article.id)
        article.refresh_from_db()
        self.assertEqual(article.author.name, 'Jessica Smith')


class EndToEndTest(TestCase):
    def test_share_fetch_parse(self):
        admin.add_tweet(TEST_TWEET_ID)
        shares = Share.objects.filter(twitter_id=TEST_TWEET_ID)
        self.assertTrue(len(shares)>0)
        share = shares[0]
        self.assertIsNotNone(share.article_id)
        article = Article.objects.get(id=share.article_id)
        tasks.parse_article_metadata(article.id)
        article.refresh_from_db()
        self.assertIsNotNone(article.author_id)
        tasks.analyze_sentiment()
        share.refresh_from_db()
        self.assertEqual(Share.Status.SENTIMENT_CALCULATED, share.status)
        tasks.allocate_credibility()
        self.assertTrue(len(Tranche.objects.all())>0)

