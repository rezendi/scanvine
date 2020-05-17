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
        
    def test_sd_parser(self):
        url = "http://test.com"
        html = '<html><a class="author size-m workspace-trigger" name="bau2" href="#!"><span class="content"><span class="text given-name">L.A.</span><span class="text surname">McDermott</span><span class="author-ref" id="baff1"><sup>a</sup></span></span></a></html>'
        publication = Publication(status=0, name='', domain='test.com', average_credibility=0, total_credibility=0, parser_rules='[{"method":"sciencedirect_parser"}]')
        publication.save()
        article = Article(status=Article.Status.CREATED, language='en', url = url, initial_url=url, contents=html, title='', metadata='', publication_id=publication.id)
        article.save()
        tasks.parse_article_metadata(article.id)
        article.refresh_from_db()
        self.assertEqual(article.author.name, 'L.A. Mcdermott')


class ScoringTest(TestCase):
    def test_scoring(self):
        urls = ["http://test.com/one", "http://test.com/two", "http://test2.com/three", "http://test2.com/four"]
        htmls = ['<html><title>Testarticle One</title><meta name="author" content="Testauthor One"></html>',
                 '<html><title>Testarticle Two</title><meta name="author" content="Testauthor Two"></html>',
                 '<html><title>Testarticle Three</title><meta name="author" content="Testauthor Three"></html>',
                 '<html><title>Testarticle Four</title><meta name="author" content="Testauthor Three"></html>']
        article_ids = {}
        sharer_ids = {}
        share_ids = {}
        for idx, url in enumerate(urls):
            article = Article(status=Article.Status.CREATED, language='en', url = url, initial_url=url, contents=htmls[idx], title='', metadata='')
            article.save()
            article_ids[idx] = article.id
            tasks.parse_article_metadata(article.id)
            sharer = Sharer(twitter_id=int("54321%s" % article.id), status=Sharer.Status.CREATED, name="Name %s" % article.id,
                 twitter_screen_name = "twitter_%s" % article.id, profile="description %s" % article.title, category=idx%3, verified=False)
            sharer.save()
            sharer_ids[idx] = sharer.id
            share = Share(source=0, language='en', status=Share.Status.SENTIMENT_CALCULATED, twitter_id = int("12345%s" % article.id),
                  sharer_id = sharer.id, article_id = article.id, net_sentiment=16*idx)
            expected = 1 if idx< 2 else 2 if idx==2 else 3
            self.assertEqual(expected, share.share_points())
            share.save()
            share_ids[idx] = share.id
        share = Share(source=0, language='en', status=Share.Status.SENTIMENT_CALCULATED, twitter_id = 12345678, sharer_id = sharer_ids[0], article_id = article_ids[3], net_sentiment=16)
        share.save()
        share_ids[4]=share.id

        # last share shouldn't have a tranche, because that sharer already shared that article
        share = Share(source=0, language='en', status=Share.Status.SENTIMENT_CALCULATED, twitter_id = 12345678, sharer_id = sharer_ids[0], article_id = article_ids[3], net_sentiment=99)
        share.save()
        tasks.allocate_credibility()
        tasks.set_scores()
        tranches = Tranche.objects.filter(receiver=share.id)
        self.assertEqual(0, len(tranches))

        # OK, check tranches
        for idx, id in share_ids.items():
            expected = 1 if idx< 2 else 2 if idx==2 else 3 if idx==3 else 1
            tranche = Tranche.objects.get(receiver=id)
            self.assertIsNotNone(tranche)
            self.assertEqual(1008*expected, tranche.quantity)
        for idx, id in article_ids.items():
            article = Article.objects.get(id=id)
            expected = 1 if idx< 2 else 2 if idx==2 else 4
            self.assertEqual(1008*expected, article.total_credibility)
        authors = Author.objects.all()
        self.assertEqual(3, len(authors))
        for author in authors:
            if author.name == "Testauthor Three":
                self.assertEqual(6048, author.total_credibility)
            else:
                self.assertEqual(1008, author.total_credibility)
    
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

