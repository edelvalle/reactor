from django.urls import path
from . import views

urlpatterns = [
    path('', views.todo),
    path('counter', views.counter),
]
