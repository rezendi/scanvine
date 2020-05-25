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
        self.assertEqual(article.author.name, 'L.A. McDermott')


class ScoringTest(TestCase):
    def test_scoring(self):
        urls = ["http://test.com/one", "http://test.com/two", "http://test2.com/three", "http://test2.com/four"]
        htmls = ['<html><title>Testarticle One</title><meta name="author" content="Testauthor One"></html>',
                 '<html><title>Testarticle Two</title><meta name="author" content="Testauthor One, Testauthor Two"></html>',
                 '<html><title>Testarticle Three</title><meta name="author" content="Testauthor Three"></html>',
                 '<html><title>Testarticle Four</title><meta name="author" content="Testauthor Three"></html>']
        for idx, url in enumerate(urls):
            article = Article(status=Article.Status.CREATED, language='en', url = url, initial_url=url, contents=htmls[idx], title='', metadata='')
            article.save()
            tasks.parse_article_metadata(article.id)
            sharer = Sharer(twitter_id=int("54321%s" % article.id), status=Sharer.Status.CREATED, name="Name %s" % article.id,
                 twitter_screen_name = "twitter_%s" % article.id, profile="description %s" % article.title, category=idx%3, verified=False)
            sharer.save()
            share = Share(source=0, language='en', status=Share.Status.SENTIMENT_CALCULATED, twitter_id = int("12345%s" % article.id),
                  sharer_id = sharer.id, article_id = article.id, category=idx%3, net_sentiment=16*idx)
            expected = 1 if idx<= 2 else 2
            self.assertEqual(expected, share.share_points())
            share.save()

        # first share shouldn't have a tranche, because we use share with highest net sentiment
        sharer = Share.objects.all()[:1][0]
        article = Article.objects.all()[:4][3]
        share = Share(source=0, language='en', status=Share.Status.SENTIMENT_CALCULATED, twitter_id = 12345678, category = 0, sharer_id = sharer.id, article_id = article.id, net_sentiment=15)
        share.save()
        no_tranche_id = share.id
        share = Share(source=0, language='en', status=Share.Status.SENTIMENT_CALCULATED, twitter_id = 12345678, category = 0, sharer_id = sharer.id, article_id = article.id, net_sentiment=16)
        share.save()

        # do the aallocation
        tasks.allocate_credibility()
        tasks.set_scores()
        tranches = Tranche.objects.filter(receiver=no_tranche_id)
        self.assertEqual(0, len(tranches))

        # OK, check tranches
        for idx,share in enumerate(Share.objects.all().order_by("id")[:4]):
            expected = 2 if idx==3 else 1
            tranche = Tranche.objects.get(receiver=share.id)
            self.assertIsNotNone(tranche)
            self.assertEqual(1008*expected, tranche.quantity)
        for idx,article in enumerate(Article.objects.all().order_by("id")):
            expected = 1 if idx<= 2 else 3 if idx==3 else 0
            self.assertEqual(1008*expected, article.total_credibility)
            expected_health_buzz = 1008 if idx==0 else 3024 if idx==3 else 0
            self.assertEqual(expected_health_buzz, article.scores['health'])
            expected_tech_buzz = 1008 if idx==2 else 0
            self.assertEqual(expected_tech_buzz, article.scores['tech'])
            self.assertEqual(0, article.scores['media'])
        self.assertEqual(4, Author.objects.all().count())
        self.assertEqual(2, Collaboration.objects.all().count())
        for author in Author.objects.all():
            if author.name == "Testauthor Three":
                self.assertEqual(4032, author.total_credibility)
            elif author.name == "Testauthor Two":
                self.assertEqual(504, author.total_credibility)
            elif author.name == "Testauthor One":
                self.assertEqual(1512, author.total_credibility)
            else:
                self.assertEqual(0, author.total_credibility)
        pub = Publication.objects.get(domain="test.com")
        self.assertEqual(2, pub.scores['total_count'])
        self.assertEqual(0, pub.scores['media_count'])
        self.assertEqual(1008, pub.scores['health'])
        self.assertEqual(2016, pub.total_credibility)
        self.assertEqual(1008, pub.average_credibility)
        pub = Publication.objects.get(domain="test2.com")
        self.assertEqual(2, pub.scores['total_count'])
        self.assertEqual(3024, pub.scores['health'])
        self.assertEqual(4032, pub.total_credibility)
        self.assertEqual(2016, pub.average_credibility)
    
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

