from django.shortcuts import render


def index(request):
    return render(request, 'index.html')


def todo(request):
    return render(request, 'todo.html')
