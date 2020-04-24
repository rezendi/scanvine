from celery import shared_task
from .models import *

# crude initial algorithm:
# for each sharer, get list of shares
# shares with +ve or -ve get 2 points, mixed/neutral get 1 point, total N points
# 5040 credibility/day for maximum divisibility, N points means 5040/N cred for that share, truncate

@shared_task
def allocate_credibility():
    for sharer in Sharer.objects.all():
        shares = Share.objects.filter(sharer_id=sharer.id)
        if not shares.exists():
            continue
        total_points = 0
        for s in shares:
            total_points += 2 if abs(s.net_sentiment) > 50 else 1
        if total_points==0:
            continue
        cred_per_point = 5040 // total_points
        for share in shares:
            points = 2 if abs(share.net_sentiment) > 50 else 1
            share_cred = cred_per_point * points
            article = share.article
            if not article:
                continue
            author = article.author
            if not author:
                continue
            t = Tranche(status=0, tags='', sender=sharer.id, receiver=author.id, quantity = share_cred, category=sharer.category, type=author.status)
            t.save()
            
