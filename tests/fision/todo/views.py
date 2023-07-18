from django.shortcuts import redirect, render
from fision.todo.models import Item


def index(request):
    return render(request, "index.html", context={"title": "index"})


def todo(request):
    return render(
        request,
        "todo.html",
        context={
            "title": "todo",
            "showing": request.GET.get("showing", "all"),
        },
    )


def redirect_to_index(request):
    return redirect("/?frombackend=1")
