import json

def npr_parser(html, soup):
    npr = "".join(soup.find("script", {"id":"npr-vars"}).contents)
    metadata = npr.partition("NPR.serverVars = ")[2][:-2]
    metadata['author'] = metadata['byline']
    return metadata

def json_ld_parser(soup):
    metastring = "".join(soup.find("script", {"type":"application/ld+json"}).contents)
    try:
        metadata = json.loads(metastring)
        if type(metadata) is list:
            metadata = metadata[0]
    except Exception as ex:
        print("Could not parse LD-JSON %s" % metastring)
        return {}

    if 'headline' in metadata and not 'title' in metadata:
        metadata['title'] = metadata['headline']

    author_name = None
    if 'author' in metadata:
        inner = metadata['author']
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
        metadata['author_field'] = metadata['author']
    if not author_name and 'name' in metadata:
        author_name = metadata['name']
    if author_name:
        metadata['author'] = author_name
    return metadata

def meta_parser(soup):
    metadata = {}
    for meta in soup.find_all("meta"):
        attrs = meta.attrs
        keys = list(attrs)
        if 'name' in keys and 'content' in keys:
            metadata[attrs['name']] = attrs['content']
        if len(keys)==2 and 'content' in keys:
            idx = 1 if keys[0]=='content' else 0
            metadata[attrs[keys[idx]]] = attrs['content']

    if not 'author' in metadata:
        author = soup.find("meta", {"name":"author"})
        if not author:
            author = soup.find("meta", {"property":"author"})
        if not author:
            author = soup.find("meta", {"property":"article:author"})
        if not author:
            author = soup.find("meta", {"itemprop":"author"})
        if not author:
            author = soup.find("meta", {"property":"og:author"})
        if not author:
            author = soup.find("meta", {"property":"twitter:author"})
        if not author:
            author = soup.find("meta", {"property":"sailthru:author"})
        if author:
            author_name = author['content']
            if author_name:
                metadata['author'] = author_name

    if not 'title' in metadata:
        title = soup.find("meta", {"name":"title"})
        if not title:
            title = soup.find("meta", {"property":"title"})
        if not title:
            title = soup.find("meta", {"itemprop":"title"})
        if not title:
            title = soup.find("meta", {"property":"og:title"})
        if not title:
            title = soup.find("meta", {"property":"twitter:title"})
        if not title:
            title = soup.find("meta", {"property":"sailthru:title"})
        if title:
            title_text = title['content']
            if title_text:
                metadata['title'] = title_text

    return metadata
