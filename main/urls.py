from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('authors/', views.authors, name='authors'),
    path('publications/', views.publications, name='publications'),
    path('author/<int:author_id>/', views.author, name='author'),
    path('publication/<int:publication_id>/', views.publication, name='publication'),
    path('article/<int:article_id>/', views.article, name='article'),
    path('category/<str:category>/', views.category, name='category'),
]