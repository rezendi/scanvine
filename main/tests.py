from django.test import TestCase

from . import models, tasks

class MetadataParserTests(TestCase):
    def test_basic_parsing(self):
        html = '<html><head><title>TestTitle1</title><meta name="author" content="TestAuthor1"></html>'
        metadata = tasks.parse_article(html)
        self.assertEqual("TestTitle1", metadata['sv_title'])
        self.assertEqual("TestAuthor1", metadata['sv_author'])

