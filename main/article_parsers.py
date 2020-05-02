import json

def npr_parser(soup):
    npr = "".join(soup.find("script", {"id":"npr-vars"}).contents)
    metadata = json.loads(npr.partition("NPR.serverVars = ")[2][:-2])
    print("metadata %s" % metadata)
    author = metadata['byline']
    if type(author) is list:
        author = str(author) if len(author) != 1 else author[0]
    metadata['sv_author'] = author
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
        metadata['sv_author'] = metadata['author']
    return metadata

def meta_parser(soup):
    metadata = {}
    for meta in soup.find_all("meta"):
        attrs = meta.attrs
        keys = list(attrs)
        if 'name' in keys and 'content' in keys:
            metadata[attrs['name']] = attrs['content']
        if 'property' in keys and 'content' in keys:
            metadata[attrs['property']] = attrs['content']
        if 'itemprop' in keys and 'content' in keys:
            metadata[attrs['itemprop']] = attrs['content']
        if len(keys)==2 and 'content' in keys:
            idx = 1 if keys[0]=='content' else 0
            metadata[attrs[keys[idx]]] = attrs['content']

    if 'author' in metadata:
        metadata['sv_author'] = metadata['author']
    else:
        author = soup.find("meta", {"property":"article:author"})
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

    if 'title' in metadata:
        metadata['sv_author'] = metadata['title']
    else:
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
