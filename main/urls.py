from django.urls import path

from . import views

urlpatterns = [
    path('', views.index_view, name='index'),
    path('authors/', views.authors_view, name='authors'),
    path('publications/', views.publications_view, name='publications'),
    path('author/<int:author_id>/', views.author_view, name='author'),
    path('publication/<int:publication_id>/', views.publication_view, name='publication'),
    path('article/<int:article_id>/', views.article_view, name='article'),
    path('category/<str:category>/', views.category_view, name='category'),
    path('buzz/', views.buzz_view, name='buzz'),
]