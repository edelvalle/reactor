# Reactor, a LiveView library for Django

Reactor enables you to do something similar to Phoenix framework LiveView using Django Channels.

## Installation and setup

Reactor requires Python >=3.6. 

[Setup up your django-channels](https://channels.readthedocs.io/en/latest/installation.html) project beforehand.
You will need to set up [Channel Layers](https://channels.readthedocs.io/en/latest/topics/channel_layers.html) as part of your configuration - Reactor won't work without Channel Layers enabled.

Install reactor:

```bash
pip install django-reactor
```

Add `reactor` to your `INSALLED_APPS`. Register the URL patterns of reactor in your your file where is the ASGI application, usually `<youproject>/routing.py`, something like this:

```python
from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from reactor.urls import websocket_urlpatterns  # <- for Django Reactor

application = ProtocolTypeRouter({
    'websocket': AuthMiddlewareStack(URLRouter(
        websocket_urlpatterns, # <- For Django Reactor
        ...
    ))
})
```

In the templates where you want to use reactive components you have to load the reactor static files. So do something like:

```html
{% load reactor %}
<!doctype html>
<html>
  <head>
     ....
     {% reactor_header %}
  </head>
  ...
</html>
```

Put them as early as possible, they use `<script defer>` so they will be downloaded in parallel with the page load and when the page is loaded will be executed.

## Simple counter example

In your app create a template `x-counter.html`:

```html
{% load reactor %}
<x-counter id="{{ this.id }}" state="{{ this.serialize|tojson }}">
  {{ this.amount }}
  <button onclick="send(this, 'inc')">+</button>
  <button onclick="send(this, 'dec')">-</button>
  <button onclick="send(this, 'set_to', {amount: 0})">reset</button>
</x-counter>
```

Anatomy of a template: each component should is a [custom web component](https://developer.mozilla.org/en-US/docs/Web/Web_Components/Using_custom_elements) that inherits from [HTMLElement](https://developer.mozilla.org/en-US/docs/Web/API/HTMLElement). They should have an `id` so the backend knows which instance is this one and a `state` attribute with the necessary information to recreate the full state of the component on first render and in case of reconnection to the back-end.

Render things as usually, so you can use full Django template language, `trans`, `if`, `for` and so on. Just keep in mind that the instance of the component is referred as `this`.

Forwarding events to the back-end: Notice that for event binding in-line JavaScript is used on the event handler of the HTML elements. How this works? When the increment button receives a click event `send(this, 'inc')` is called, `send` is a reactor function that will look for the parent custom component and will dispatch to it the `inc` message, or the `set_to` message and its parameters `{amount: 0}`. The custom element then will send this message to the back-end, where the state of the component will change and then will be re-rendered back to the front-end. In the front-end `morphdom` (just like in Phoenix LiveView) is used to apply the new HTML.

Now let's write the behavior part of the component in `views.py`:

```python
from reactor import Component

class XCounter(Component):

    amount = None

    # reference the template from above
    template_name = 'x-counter.html' 

    # A component is instantiated during normal rendering and when the component
    # connects from the front-end. Then  __init__ is called passing `context` of
    # creation (in case of HTML  rendering is the context of the template, in
    # case of a WebSocket connection is the scope of django channels) Also the
    # `id` is passed if any is provided, otherwise a `uuid4` is  generated on
    # the fly.

    # This method is called after __init__ passing the initial state of the 
    # Component, this method is responsible taking the state of the component
    # and construct or reconstruct the component. Sometimes loading things from
    # the database like tests of this project.
    def mount(self, amount=0, **kwargs):
        self.amount = amount

    # This method is used to capture the essence of the state of a component
    # state, so it can be reconstructed at any given time on the future.
    # By passing what ever is returned by this method to `mount`.
    def serialize(self):
        return dict(id=self.id, amount=self.amount)

    # This are the event handlers they always start with `receive_`

    def receive_inc(self, **kwargs):
        self.amount += 1

    def receive_dec(self, **kwargs):
        self.amount -= 1

    def receive_set_to(self, amount, **kwargs):
        self.amount = amount
```

Let's now render this counter, expose a normal view that renders HTML, like:


```python
def index(request):
    return render(request, 'index.html')
```

And the index template being:

```html
{% load reactor %}
<!doctype html>
<html>
  <head>
     ....
     {% reactor_header %}
  </head>
  <body>
    {% component 'x-counter' %}

    <!-- or passing an initial state -->
    {% component 'x-counter' amount=100 %}    

  </body>
</html>
```

Don't forget to update your `urls.py` to call the index view.

## More complex components

I made a TODO list app using models that signals from the model to the respective channels to update the interface when something gets created, modified or deleted.

This example contains nested components and some more complex interactions than a simple counter, the app is in the `/tests/` directory.


## Development & Contribution

Clone the repo and create a virtualenv or any other contained environment, get inside the repo directory, build the development environment and the run tests.

```bash
git clone git@github.com:edelvalle/reactor.git
cd reactor
make install
make test
```

If you wanna run the inside Django project that is used for testing do:

```bash
make
cd tests
python manage.py runserver
```

Enjoy!
