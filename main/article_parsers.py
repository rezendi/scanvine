import json, re
import dateparser
from .models import *

# Constructor methods

def get_author_for(metadata, publication):
    if not 'sv_author' in metadata:
        return None
    twitter_id = metadata['twitter:creator:id'] if 'twitter:creator:id' in metadata else None
    twitter_name = metadata['twitter:creator'] if 'twitter:creator' in metadata else ''
    if twitter_id and not twitter_id.isnumeric():
        twitter_name = twitter_id if not twitter_name else twitter_name
        twitter_id = None
    author_string = str(metadata['sv_author']) if 'sv_author' in metadata else ''

    names = clean_author_string(author_string, publication).split(",")
    pubname = publication.name.lower().strip()
    if pubname and len(pubname) > 2:
        names = [n for n in names if not n.lower().startswith(pubname) and not pubname.startswith(n.lower())]
    names = [n.strip() for n in names]
    names = [ii for n,ii in enumerate(names) if ii not in names[:n]] # remove duplicates
    names = [clean_author_name(n, publication) for n in names]
    names = [n for n in names if len(n)>3]


    if len(names) == 0:
        return None

    # if multiple names, we have a collaboration on our hands
    # if something is structurally wrong, bail
    if len(names) > 1:
        word_counts = [len(n.split(" ")) for n in names]
        max_words = max(word_counts)
        if max_words > 4: 
            print("Too many words in author names %s" % names)
            if len(names[0].split(" ")) < 4:
                names=[names[0]]
            else:
                return None
        if len(names)>2:
            if max_words <= 1:
                print("Not enough words in author names %s" % names)
                return None
            if len([c for c in word_counts if c==1]) > len(word_counts)/2:
                print("Too many single-word names in author names %s" % names)
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

    # OK, we think these names are good
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

    byline = ",".join([author.name for author in authors])
    if len(byline) > 255:
        byline = "%s%s" % (byline[0:252], "...")
    existing = Author.objects.filter(name__iexact=byline)
    if existing:
        return existing[0]
    new_byline = Author(status=Author.Status.CREATED, name=byline, is_collaboration=True, metadata='{}', current_credibility=0, total_credibility=0)
    new_byline.save()
    for author in authors:
        collaboration = Collaboration(partnership = new_byline, individual = author)
        collaboration.save()
    return new_byline

def clean_author_string(string, publication = None):
    exclusions = []
    if publication:
        exclusions+= [publication.domain]
        if publication.name:
            exclusions+= [publication.name, "%s%s" % (publication.domain, ".com"), "%s%s" % (publication.domain, ".org"), "%s%s" % (publication.domain, ".co")]
        exclusions+= [publication.domain.partition(".")[2]] if publication.domain.count(".") > 1 else []
    exclusions+= ["associated press", "health correspondent", "opinion columnist", "opinion contributor", "commissioning editor", "special correspondent"]
    exclusions+= ["correspondent", "contributor", "columnist", "editor," "editor-at-large", "opinion", "M.D.", "MD", "DPhil", "MA", "Inc."]
    exclusions+= ["business", "news", "with", "written," "|by", "by", "about", "contact", "byline", "author", "posted", "abstract", "on", "get"]
    exclusions+= ["authors", "et al"]
    exclusions+= ["reuters", "AP", "AFP", "|", "&", "and"]
    newstring = string.replace("&amp;","&") if string else ''
    for exclusion in exclusions:
        for variant in [exclusion, exclusion.title(), exclusion.lower(), exclusion.upper()]:
            newstring = newstring.replace(' %s ' % variant,', ')
            newstring = newstring.replace(' %s,' % variant,' ,')
            newstring = newstring.replace(',%s ' % variant,', ')
            newstring = newstring.replace('%s ' % variant, ' ') if newstring.startswith(variant) else newstring
            newstring = newstring.replace(' %s' % variant, ' ') if newstring.endswith(variant) else newstring
            newstring = newstring.replace('  ',' ')
    return newstring.replace('  ',' ').strip()

def clean_author_name(name, publication = None):
    exclusions = []
    if publication:
        exclusions+= [publication.domain]
        exclusions+= [publication.name] if publication.name else []
        exclusions+= [publication.domain.partition(".")[2]] if publication.domain.count(".") > 1 else []
    exclusions+= ["associated press", "health correspondent", "opinion columnist", "opinion contributor", "commissioning editor", "special correspondent"]
    exclusions+= ["correspondent", "contributor", "columnist", "editor," "editor-at-large", "opinion", "M.D.", "MD", "DPhil", "MA", "Inc."]
    exclusions+= ["business", "news", "with", "written," "|by", "by", "about", "the", "author", "byline", "contact", "posted", "abstract", "on", "get"]
    exclusions+= ["authors", "et al"]
    exclusions+= ["reuters", "AP", "AFP", "|"]
    newname = name.replace("&amp;","&") if name else ''
    newname = re.sub(r'<[^>]*>', "", newname)
    for exclusion in exclusions:
        for variant in [exclusion, exclusion.title(), exclusion.lower(), exclusion.upper()]:
            newname = newname.replace(' %s ' % variant, ' ')
            newname = newname.replace('%s ' % variant, ' ') if newname.startswith(variant) else newname
            newname = newname.replace(' %s' % variant, ' ') if newname.endswith(variant) else newname
            newname = newname.replace('  ',' ')
    newname = newname.replace('  ',' ').strip()
    if newname.startswith("http"):
        split = newname.rpartition("/")
        newname = split[0].rpartition("/")[2] if split[2].isnumeric() else split[2]
        tentative = newname.split("-")
        if len(tentative)>1 and len (tentative) <5:
            newname = " ".join(tentative)

    words = newname.split(" ")
    if len(words) > 1:
        newname = newname.title() if newname.islower() or newname.isupper() else newname
        newname = newname.replace("'S ","'s ")

    if newname and newname.lower() != name.lower():
        existing = Author.objects.filter(name=name)
        if existing:
            existing[0].name = newname
            existing[0].save()

    return newname
    
def get_author_from(existing, metadata):
    oldval = existing['sv_author'] if 'sv_author' in existing else None
    newval = metadata['sv_author'] if 'sv_author' in metadata else None
    return better_name(oldval, newval)

def better_name(oldval, newval):
    # print("comparing %s to %s" % (oldval, newval))
    if not newval:
        return oldval
    if type(newval) is list:
        names = [x['name'] if type(x) is dict and 'name' in x else x for x in newval]
        return names[0] if len(names)==1 else ','.join(names)
    if type(newval) is dict:
        newval = newval['name'] if 'name' in newval else None
    if not oldval:
        return newval
    if not newval:
        return oldval
    if newval and (newval.startswith("[") or newval.startswith("{")):
        return oldval
    new_words = len(newval.split(" ")) if newval and type(newval) == str else 0
    old_words = len(oldval.split(" ")) if oldval and type(oldval) == str else 0
    if new_words == 1 and old_words > 1:
        return oldval
    if new_words < 4 and old_words > 8:
        return newval
    if old_words < 4 and new_words > 8:
        return oldval
    if new_words - old_words > 8:
        return oldval
    if new_words - old_words > 2 and newval.find(",")==-1:
        return oldval
    return newval


# Parser methods

def json_ld_parser(soup):
    ld_jsons = soup.find_all("script", {"type":"application/ld+json"})
    metadata ={}
    for ld_json in ld_jsons:
        metastring = "".join(ld_json.contents)
        metastring = metastring.replace("//<![CDATA[","").replace("//]]>","").strip()
        try:
            vals = json.loads(metastring)
            if type(vals) is list:
                vals = vals[0]
            if vals is not None:
                metadata.update(vals)
        except Exception as ex:
            print("Could not parse LD-JSON %s" % metastring)
            return {}
    
    if 'headline' in metadata:
        metadata['sv_title'] = metadata['headline']
    if 'title' in metadata:
        metadata['sv_title'] = metadata['title']

    auth = ''
    for word in ['creator','author','authors', 'Creator', 'Author', 'Authors', 'CREATOR', 'AUTHOR', 'AUTHORS']:
        if word in metadata and not 'sv_author' in metadata:
            auth = metadata[word]
            auth = auth[0] if type(auth)==list and len(auth)==1 else auth
            auth = auth['name'] if type(auth) is dict and 'name' in auth else auth
            auth = auth['alternateName'] if type(auth) is dict and 'alternateName' in auth else auth
            auth = [d['name'] if type(d) is dict and 'name' in d else d for d in auth] if type(auth) is list else auth
            auth = auth[0] if type(auth) is list and len(auth)==1 else auth
            auth = ",".join(auth) if type(auth) is list else auth
        if auth:
            metadata['sv_author'] = auth

    if 'sv_author' not in metadata and '@graph' in metadata:
        graph = metadata['@graph']
        graph = graph[0] if type(graph)==list and len(graph)==1 else graph
        if type(graph)==list:
            for g in graph:
                if type(g) is dict and '@type' in g and (g['@type']=="Person" or g['@type']==["Person"]):
                        graph = g
                        break
        if 'author' in graph:
            auth = graph['author']
            auth = auth['name'] if type(auth) is dict and 'name' in auth else auth
            auth = [d['name'] for d in auth if type(d) is dict and 'name' in d] if type(auth) is list else auth
            auth = auth[0] if type(auth) is list and len(auth)==1 else auth
            auth = ",".join(auth) if type(auth) is list else auth
        elif 'name' in graph:
            auth = graph['name']
            auth = auth[0] if type(auth) is list and len(auth)==1 else auth
            auth = ",".join(auth) if type(auth) is list else auth
        if auth:
            metadata['sv_author'] = auth

    pub = None
    if 'publisher' in metadata:
        pub = metadata['publisher']
        pub = pub['name'] if type(pub) is dict and 'name' in pub else None
    if 'isPartOf' in metadata and not pub:
        pub = metadata['isPartOf']
        pub = pub['name'] if type(pub) is dict and 'name' in pub else None
    if pub and type(pub) is str:
        metadata['sv_publication'] = str(pub).replace("The ","")

    if 'datePublished' in metadata and metadata['datePublished']:
        date = dateparser.parse(metadata['datePublished'])
        if date:
            metadata['sv_pub_date'] = date.isoformat()
        
    if 'thumbnailUrl' in metadata and metadata['thumbnailUrl']:
        thumbnail = metadata['thumbnailUrl']
        thumbnail = thumbnail[0] if type(thumbnail) is list else thumbnail
        metadata['sv_image'] = thumbnail
    elif 'image' in metadata and metadata['image'] and 'url' in metadata['image']:
        metadata['sv_image'] = metadata['image']['url']
        
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
        metanames = ["article:author", "OG:author", "twitter:author", "sailthru:author", "DCSext.author", "DC.Contributor", "DC.Creator", "DCterms.creator"]
        metanames+= ["news_authors", "citation_author"]
        authors = [] 
        for nameval in metanames:
            variants = [nameval, nameval.lower()] if nameval != nameval.lower() else [nameval]
            for variant in variants:
                if not authors:
                    authors = soup.find_all("meta", {"property":variant})
                if not authors:
                    authors = soup.find_all("meta", {"name":variant})
        if authors:
            author_name = None
            for author in authors:
                if 'value' in author.attrs:
                    author_name = author['value'] if not author_name else "%s, %s" % (author_name, author['value'])
                if 'content' in author.attrs:
                    author_name = author['content'] if not author_name else "%s, %s" % (author_name, author['content'])
            if author_name:
                metadata['sv_author'] = author_name

    # if nothing else, search for tags by class...
    if not 'sv_author' in metadata or metadata['sv_author'].startswith('http'):
        byline = ''
        for sup in soup.findAll('sup'):
            sup.replaceWith(",")
        wordline = ''
        for word in ['author', 'author-name', 'byline', 'contributor', 'authors', 'Author', 'Byline', 'Contributor', 'Authors']:
            candidate_tags = soup.find_all(True, {"rel" : word})
            if not candidate_tags:
                candidate_tags = soup.find_all(True, {"class" : word})
            if not candidate_tags:
                candidate_tags = soup.find_all(True, {"class" : lambda L: L and L.startswith(word) and L.find("comment")<0})
            if not candidate_tags:
                candidate_tags = soup.find_all(True, {"class" : lambda L: L and L.endswith(word) and L.find("comment")<0})
            for candidate_tag in candidate_tags:
                if candidate_tag.name=='body':
                    continue
                if candidate_tag.find('a') and 'data-name' in candidate_tag.find('a').attrs:
                    candidate=candidate_tag.find('a')['data-name']
                    wordline = "%s, %s" % (wordline, candidate) if wordline else candidate
                    continue
                words = candidate_tag.text.split(" ")
                if len(words) > 32:
                    continue
                for candidate in candidate_tag.stripped_strings:
                    candidate = candidate.partition("\n")[0].strip()
                    candidate = '' if any(char.isdigit() for char in candidate) else candidate
                    words = candidate.split(" ")
                    candidate = '' if len(words) > 32 else candidate
                    candidate = '' if len(words) > 3 and candidate.title() != candidate else candidate
                    candidate = clean_author_name(candidate)
                    if candidate:
                        wordline = "%s, %s" % (wordline, candidate) if wordline else candidate
            byline = better_name(byline, wordline)
            if byline:
                break
        if byline:
            print("Found byline tags")
            metadata['sv_author'] = byline

    if not 'sv_author' in metadata:
        byline = ''
        vcards = soup.find_all(True, {"class" : "vcard"})
        for vcard in vcards:
            if str(vcard).find("comment") > 0:
                continue
            text = vcard.find().text if vcard.find() else vcard.text
            if text:
                byline = "%s, %s" % (byline, text) if byline else text
        if byline:
            print("Found vcards")
            metadata['sv_author'] = byline

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

    if 'publisher' in metadata:
        metadata['sv_publication'] = metadata['publisher']
    else:
        pub = soup.find("meta", {"property":"og:site_name"})
        if pub and 'content' in pub:
            metadata['sv_publication'] = str(pub['content']).replace("The ","")

    if 'article:published' in metadata and metadata['article:published']:
        date = dateparser.parse(metadata['article:published'])
        if date:
            metadata['sv_pub_date'] = date.isoformat()
    else:
        time = soup.find("time")
        if time and 'datetime' in time.attrs:
            date = dateparser.parse(time.attrs['datetime'])
            if date:
                metadata['sv_pub_date'] = date.isoformat()

    if 'og:image' in metadata:
        metadata['sv_image'] = metadata['og:image']
    elif 'twitter:image' in metadata:
        metadata['sv_image'] = metadata['twitter:image']
        

    # print("1 author %s" % metadata['sv_author']) if 'sv_author' in metadata else 'No 1'
    return metadata

def npr_parser(soup):
    npr = "".join(soup.find("script", {"id":"npr-vars"}).contents)
    metadata = json.loads(npr.partition("NPR.serverVars = ")[2][:-2])
    if 'byline' in metadata:
        metadata['sv_author'] = metadata['byline'] 
    metadata['sv_publication'] = "NPR"
    return metadata

def reddit_parser(soup):
    author_tags = [item for item in soup.find_all() if "data-author" in item.attrs]
    if author_tags:
        return {'sv_author': author_tags[0]["data-author"]}
    return {}

def instagram_parser(soup):
    parts = []
    title = soup.title
    if title:
        title = title.text
    if title and title.find("on Instagram:")>0:
        parts = title.partition("on Instagram:")
    if title and title.find("’s Instagram profile post:")>0:
        parts = title.partition("’s Instagram profile post:")
    if parts:
        return {'sv_author': parts[0], 'sv_title' : parts[2]}
    return {}

def linkedin_parser(soup):
    title = soup.title
    if title:
        author_name = soup.title.string.partition(" on LinkedIn")[0]
        return {'sv_author': author_name}
    return {}

def sciencedirect_parser(soup):
    names = []
    author_tags = soup.find_all(True, {"class" : "author"})
    for tag in author_tags:
        first = tag.find("span", {"class" : "given-name"})
        last = tag.find("span", {"class" : "surname"})
        name = '%s %s' % ((first.text if first else ''), (last.text if last else ''))
        names.append(name.strip())
    names = [n for n in names if len(n)>0]
    author = names[0] if len(names)==1 else ','.join(names)
    return {'sv_author': author}

def youtube_parser(soup):
    text = ''
    for script in soup.find_all("script"):
        if ("%s" % script).startswith("<script>var ytplayer"):
            text = ("%s" % script).partition(";(function")[0]
            text = text.partition("author")[2]
            text = text.partition(",")[0]
            text = text.replace('\\"','').replace(":",'')
    return {'sv_author': text}


