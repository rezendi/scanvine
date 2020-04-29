import json

def npr_parser(html, soup):
    if html.find("npr-vars") > 0:
        npr = "".join(soup.find("script", {"id":"npr-vars"}).contents)
        metadata = npr.partition("NPR.serverVars = ")[2][:-2]
        return (metadata, metadata['title'], metadata['byline'])

def json_ld_parser(soup):
    metadata = "".join(soup.find("script", {"type":"application/ld+json"}).contents)
    meta = json.loads(metadata)
    title = meta['headline'] if 'headline' in meta else ''
    title = meta['title'] if 'title' in meta else title
    author_name = ''
    if 'author' in meta:
        inner = meta['author']
        if type(inner) is list:
            subinner = inner[0]
            if type(subinner) is dict:
                author_name = subinner['name']
            else:
                author_name = subinner
        if type(inner) is dict:
            author_name=inner['name']
        else:
            author_name=inner
    if not author_name and 'name' in meta:
        author_name = meta['name']
    return (metadata, title, author_name)