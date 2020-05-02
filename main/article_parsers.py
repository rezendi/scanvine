import json, re
from .models import *

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
        metadata['sv_title'] = metadata['title']
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

def npr_parser(soup):
    npr = "".join(soup.find("script", {"id":"npr-vars"}).contents)
    metadata = json.loads(npr.partition("NPR.serverVars = ")[2][:-2])
    metadata['sv_author'] = metadata['byline']
    return metadata

def get_author_for(metadata):
    if not 'sv_author' in metadata:
        return None
    twitter_id = metadata['twitter:creator:id'] if 'twitter:creator:id' in metadata else None
    twitter_name = metadata['twitter:creator'] if 'twitter:creator' in metadata else ''
    author_string = str(metadata['sv_author']).strip()
    author_string = author_string.replace(" and",",").replace(" And",",").replace(" AND",",").replace("&",",")
    if author_string.find(",") == -1:
        name = author_string
        existing = Author.objects.filter(name=name)
        existing = existing.filter(twitter_screen_name=twitter_name) if twitter_name else existing
        if existing:
            return existing[0] # TODO handle multiple matches
        else:
            author=Author(status=Author.Status.CREATED, name=name, twitter_id=twitter_id, twitter_screen_name=twitter_name,
                          is_collaboration=False, metadata='{}', current_credibility=0, total_credibility=0)
            author.save()
            return author

    # if we're here, we have a collaboration on our hands
    names = author_string.split(",")
    names = [n.strip() for n in names]
    names = [n for n in names if len(n)>3]
    print("names %s" % names)
    authors = []
    for name in names:
        existing = Author.objects.filter(name=name)
        existing = existing.filter(twitter_screen_name=twitter_name) if twitter_name else existing
        if existing:
            authors.append(existing[0]) # TODO handle multiple matches
        else:
            author=Author(status=Author.Status.CREATED, name=name, is_collaboration=False, metadata='{}', current_credibility=0, total_credibility=0)
            author.save()
            authors.append(author)
    
    byline = Author(status=Author.Status.CREATED, name=author_string, is_collaboration=True, metadata='{}', current_credibility=0, total_credibility=0)
    byline.save()
    for author in authors:
        collaboration = Collaboration(partnership = byline, individual = author)
        collaboration.save()
    return byline