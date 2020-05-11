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

    if 'author' in metadata:
        auth = metadata['author']
        if type(auth) is str or type(auth) is list or (type(auth) is dict and 'name' in auth):
            metadata['sv_author'] = metadata['author']
    elif '@graph' in metadata:
        graph = metadata['@graph']
        graph = graph[0] if type(graph) is list and len(graph)>0 else graph
        if 'author' in graph:
            metadata['sv_author'] = graph['author']

    pub = None
    if 'publisher' in metadata:
        pub = metadata['publisher']
        pub = pub['name'] if type(pub) is dict and 'name' in pub else None
    if 'isPartOf' in metadata and not pub:
        pub = metadata['isPartOf']
        pub = pub['name'] if type(pub) is dict and 'name' in pub else None
    if pub and type(pub) is str:
        metadata['sv_publication'] = str(pub).replace("The ","")

    # print("0 author %s" % metadata['sv_author']) if 'sv_author' in metadata else 'No 0'
    return metadata

def meta_parser(soup):
    metadata = {}
    for meta in soup.find_all("meta"):
        attrs = meta.attrs
        keys = list(attrs)
        for nameval in ['name', 'property', 'itemprop']:
            if nameval in keys and 'content' in keys:
                metadata[attrs[nameval]] = attrs['content']
        if len(keys)==2 and 'content' in keys:
            idx = 1 if keys[0]=='content' else 0
            metadata[attrs[keys[idx]]] = attrs['content']

    if 'author' in metadata:
        metadata['sv_author'] = metadata['author']
    else:
        author = None
        for nameval in ["article:author", "og:author", "twitter:author", "sailthru:author", "DCSext.author"]:
            if not author:
                author = soup.find("meta", {"property":nameval})
            if not author:
                author = soup.find("meta", {"name":nameval})
        if author:
            author_name = None
            if 'value' in author.attrs:
                author_name = author['value']
            if 'content' in author.attrs:
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
            if 'value' in title.attrs:
                title_text = title['value']
            if 'content' in title.attrs:
                title_text = title['content']
            if title_text:
                metadata['sv_title'] = title_text

    # if nothing, search for tag with 'byline' in its class?
    if not 'sv_author' in metadata:
        byline = ''
        for word in ['author', 'byline', 'contributor']:
            if not byline:
                candidates = soup.find_all(True, {"rel" : word})
                if not candidates:
                    candidates = soup.find_all(True, {"class" : lambda L: L and (L.startswith(word) or L.endswith(word))})
                for candidate in candidates:
                    possible_byline = clean_author_name(candidate.text,'')
                    if possible_byline:
                        byline = "%s, %s" % (byline, possible_byline) if byline else possible_byline
        if byline:
            print("byline %s" % byline)
            metadata['sv_author'] = byline

    if 'publisher' in metadata:
        metadata['sv_publication'] = metadata['publisher']
    else:
        pub = soup.find("meta", {"property":"og:site_name"})
        if pub and 'content' in pub:
            metadata['sv_publication'] = str(pub['content']).replace("The ","")

    # print("1 author %s" % metadata['sv_author']) if 'sv_author' in metadata else 'No 1'
    return metadata

def npr_parser(soup):
    npr = "".join(soup.find("script", {"id":"npr-vars"}).contents)
    metadata = json.loads(npr.partition("NPR.serverVars = ")[2][:-2])
    metadata['sv_author'] = metadata['byline']
    metadata['sv_publication'] = "NPR"
    return metadata

def get_author_from(existing, metadata):
    oldval = existing['sv_author'] if 'sv_author' in existing else None
    newval = metadata['sv_author'] if 'sv_author' in metadata else None
    if not newval:
        return oldval
    if type(newval) is list:
        names = [x['name'] if type(x) is dict and 'name' in x else x for x in newval]
        return names[0] if len(names)==1 else ','.join(names)
    if type(newval) is dict:
        newval = newval['name'] if 'name' in newval else None
    if not oldval:
        return newval
    if newval and (newval.startswith("[") or newval.startswith("{")):
        return oldval
    if len(newval.split(" "))==1 and len(oldval.split(" "))>1:
        return oldval
    return newval

def get_author_for(metadata, publication):
    if not 'sv_author' in metadata:
        return None
    twitter_id = metadata['twitter:creator:id'] if 'twitter:creator:id' in metadata else None
    twitter_name = metadata['twitter:creator'] if 'twitter:creator' in metadata else ''
    author_string = str(metadata['sv_author']) if 'sv_author' in metadata else ''
    names = clean_author_string(author_string, publication.name).split(",")
    names = [clean_author_name(n, publication.name) for n in names]
    names = [n for n in names if len(n)>3]

    if len(names) == 0:
        return None

    if len(names) == 1:
        name = names[0]
        existing = Author.objects.filter(name__iexact=name)
        if len(existing) > 1 and twitter_name:
            print("Filtering by twitter_name %s" % twitter_name)
            existing = existing.filter(twitter_screen_name__iexact=twitter_name)
        if existing:
            return existing[0] # TODO handle multiple matches
        else:
            author=Author(status=Author.Status.CREATED, name=name, twitter_id=twitter_id, twitter_screen_name=twitter_name,
                          is_collaboration=False, metadata='{}', current_credibility=0, total_credibility=0)
            author.save()
            return author

    # if we're here, we have a collaboration on our hands
    authors = []
    for name in names:
        existing = Author.objects.filter(name__iexact=name)
        if len(existing) > 1 and twitter_name:
            print("Filtering by twitter_name %s" % twitter_name)
            existing = existing.filter(twitter_screen_name__iexact=twitter_name)
        if existing:
            authors.append(existing[0]) # TODO handle multiple matches
        else:
            author=Author(status=Author.Status.CREATED, name=name, is_collaboration=False, metadata='{}', current_credibility=0, total_credibility=0)
            author.save()
            authors.append(author)

    byline = ",".join(names)    
    existing = Author.objects.filter(name__iexact=byline)
    if existing:
        return existing[0]
    new_byline = Author(status=Author.Status.CREATED, name=byline, is_collaboration=True, metadata='{}', current_credibility=0, total_credibility=0)
    new_byline.save()
    for author in authors:
        collaboration = Collaboration(partnership = new_byline, individual = author)
        collaboration.save()
    return new_byline

def clean_author_string(string, publication_name):
    newstring = string if string else ''
    print("cleaning %s from %s" % (string, publication_name))
    exclusions = [publication_name] if publication_name else []
    exclusions+= ["associated press", "health correspondent", "opinion columnist", "opinion contributor"]
    exclusions+= ["correspondent", "contributor", "columnist", "with", "by"]
    exclusions+= ["reuters", "AP", "AFP"]
    for exclusion in exclusions:
        print("excluding %s" % exclusion)
        newstring = newstring.replace(', %s' % exclusion,', ')
        newstring = newstring.replace(',%s' % exclusion,',')
        newstring = newstring.replace(', %s' % exclusion.title(),', ')
        newstring = newstring.replace(',%s' % exclusion.title(),',')
    newstring = newstring.replace(" and",",").replace(" And",",").replace(" AND",",").replace("&",",")
    print("cleaned %s" % newstring)
    return newstring.strip()

def clean_author_name(name, publication_name):
    exclusions = [publication_name] if publication_name else []
    exclusions+= ["associated press", "health correspondent", "opinion columnist", "opinion contributor"]
    exclusions+= ["correspondent", "contributor", "columnist", "with", "by"]
    exclusions+= ["reuters", "AP", "AFP"]
    exclusions+= ["|"]
    newname = name if name else ''
    newname = re.sub(r'<[^>]*>', "", newname)
    for exclusion in exclusions:
        newname = newname.replace(exclusion,'')
        newname = newname.replace('  ',' ')
        newname = newname.replace(exclusion.title(),'')
        newname = newname.replace('  ',' ')
    newname = newname.replace('  ',' ').strip()
    newname = newname.title() if newname.find(" ") > 0 else newname

    if newname != name:        
        existing = Author.objects.filter(name=name)
        if existing:
            existing[0].name = newname
            existing[0].save()

    return newname
    
