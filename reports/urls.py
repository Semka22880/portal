# reports/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.build_list, name='build_list'),
    path('build/<int:build_id>/', views.build_detail, name='build_detail'),
    path('test/<str:test_name>/<str:architecture>/', views.test_history, name='test_history'),
]