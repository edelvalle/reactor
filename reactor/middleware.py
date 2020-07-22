from django.http.request import HttpRequest
from django.http.response import HttpResponse


def turbolinks_middleware(get_response):
    def middleware(request: HttpRequest):
        response: HttpResponse = get_response(request)
        response['Turbolinks-Location'] = request.get_full_path()
        return response
    return middleware
