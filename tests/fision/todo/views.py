from django.shortcuts import redirect, render


def index(request):
    print("GET", request.GET)
    return render(request, "index.html", context={"title": "index"})


def todo(request):
    return render(request, "todo.html", context={"title": "todo"})


def redirect_to_index(request):
    return redirect("/?frombackend=1")
