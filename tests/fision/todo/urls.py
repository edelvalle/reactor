from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("todo", views.todo, name="todo"),
    path("to-index", views.redirect_to_index, name="redirect_to_index"),
]
