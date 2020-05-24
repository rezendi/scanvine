from django.urls import path

from . import views

urlpatterns = [
    path('', views.index_view, name='index'),
    path('authors/publication/<int:publication_id>/', views.authors_view, name='publication_authors'),
    path('authors/<str:category>/', views.authors_view, name='category_authors'),
    path('authors/', views.authors_view, name='authors'),
    path('author/<int:author_id>/', views.author_view, name='author'),
    path('publications/', views.publications_view, name='publications'),
    path('publications/<str:category>/', views.publications_view, name='publications'),
    path('publication/<int:publication_id>/', views.publication_view, name='publication'),
    path('article/<int:article_id>/', views.article_view, name='article'),
    path('shares/<str:category>/', views.shares_view, name='shares'),
    path('<str:category>/<str:scoring>/<int:days>/', views.index_view, name='category_score_days'),
    path('<str:category>/<str:scoring>/', views.index_view, name='category_score'),
    path('<str:category>/<int:days>/', views.index_view, name='category_days'),
    path('<str:scoring>/', views.index_view, name='scored'),
]