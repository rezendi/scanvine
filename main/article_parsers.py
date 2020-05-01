import json

def npr_parser(html, soup):
    npr = "".join(soup.find("script", {"id":"npr-vars"}).contents)
    metadata = npr.partition("NPR.serverVars = ")[2][:-2]
    metadata['scanvine_author'] = metadata['byline']
    return metadata

def json_ld_parser(soup):
    ld_jsons = soup.find_all("script", {"type":"application/ld+json"})
    metadata ={}
    for ld_json in ld_jsons:
        metastring = "".join(ld_json.contents)
        try:
            vals = json.loads(metastring)
            if type(vals) is list:
                vals = vals[0]
        except Exception as ex:
            print("Could not parse LD-JSON %s" % metastring)
            return {}
        metadata.update(vals)
    
    if 'headline' in metadata:
        metadata['sv_title'] = metadata['headline']
    if 'title' in metadata:
        metadata['sv_title'] = metadata['title']

    author_name = None
    if 'author' in metadata:
        print("got author %s" % metadata['author'])
        inner = metadata['author']
        if type(inner) is list:
            subinner = inner[0]
            metadata['sv_author'] = subinner['name'] if type(subinner) is dict else subinner
        metadata['sv_author'] = inner['name'] if type(inner) is dict else inner
    if 'sv_author' not in metadata and 'name' in metadata:
        metadata['sv_author'] = metadata['name']
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
            author_name = None
            if 'value' in author:
                author_name = author['value']
            if 'content' in author:
                author_name = author['content']
            if author_name:
                metadata['sv_author'] = author_name

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
            title_text = None
            if 'value' in title:
                title_text = title['value']
            if 'content' in title:
                title_text = title['content']
            if title_text:
                metadata['sv_title'] = title_text

    return metadata
