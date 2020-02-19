# Reactor, a LiveView library for Django

Reactor enables you to do something similar to Phoenix framework LiveView using Django Channels.

## What's in the box?

This is no replacement for VueJS or ReactJS, or any JavaScript but it will allow you use all the potential of Django to create interactive front-ends. This method has its drawbacks because if connection is lost to the server the components in the front-end go busted until connection is re-established. But also has some advantages, as everything is server side rendered the interface comes already with meaningful information in the first request response, you can use all the power of Django template without limitations, if connection is lost or a component crashes, the front-end will have enough information to rebuild their state in the last good known state.

## Installation and setup

Reactor requires Python >=3.6. 

[Setup up your django-channels](https://channels.readthedocs.io/en/latest/installation.html) project beforehand.
You will need to set up [Channel Layers](https://channels.readthedocs.io/en/latest/topics/channel_layers.html) as part of your configuration - Reactor won't work without Channel Layers enabled.

Install reactor:

```bash
pip install django-reactor
```

Add `reactor` to your `INSTALLED_APPS`. Register the URL patterns of reactor in your your file where is the ASGI application, usually `<youproject>/asgi.py`, something like this:

```python
# flake8: noqa

import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tourproject.settings')

import django
django.setup()


from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from reactor.urls import websocket_urlpatterns  # <- for Django Reactor

import yourproject.urls  # Pre load all components

application = ProtocolTypeRouter({
    'websocket': AuthMiddlewareStack(URLRouter(
        websocket_urlpatterns, # <- For Django Reactor
    ))
})
```

Reactor does not search your code base for components so you have to pre-load them. So this will be the file to import them from where ever they are so they are available to be rendered.

My personal philosophy is to have the components in the same files of the views where they are, this views are imported by urls.py. 

In the templates where you want to use reactive components you have to load the reactor static files. So do something like this so the right JavaScript gets loaded:

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

Don't worry if you put this as early as possible, the scripts are loaded using `<script defer>` so they will be downloaded in parallel with the html, and then all is loaded they are executed.

## APIs

### Template tags and filters of `react` library

- `{% reactor_headers %}`: that includes the necessary JavaScript to make this library work. ~5Kb of minified JS, compressed with gz or brotli.
- `{% component 'x-component-name' param1=1 param2=2 %}`: Renders a component by its name and passing whatever parameters you put there to the `Component.mount` method.
- `tojson`: Takes something and renders it in JSON, the `ReactorJSONEncoder` extends the `DjangoJSONEncoder` it serializes a `Model` instance to its `id` and a `QuerySet` as a list of `ids`.
- `tojson_safe`: Same as `tojson` but does not "HTML escapes" the output.
- `then`: Use as a shorthand for if, `{% if expression %}print-this{% endif %}` is equivalent to `{{ expresssion|then:'print-this' }}`.
- `ifnot`: Use a shorthand for if not, `{% if not expression %}print-this{% endif %}` is equivalent to `{{ expresssion|ifnot:'print-this' }}, and can be concatenated with then, like in: `{{ expression|then:'positive'|ifnot:'negative' }}`

### `reactor.component` module

- `Component`: This is the base component you should extend.
- `AuthComponent`: Extends `Component` and ensures the user is logged in.
- `boarcast(*names)`: Broadcasts the given names too all the system.
- `on_commit(function)(*args, **kwargs)`: Calls `function` with the given arguments after database commit. 

#### Component API

- `template_name`: Set the name of the template of the component.
- `extends`: Tag name HTML element the component extends.
- `serialize`: Should returns a dictionary with the persistent state of the component (stored in the front-end) so when the components is connects to the back-end (or reconnects) that state can be recreated, By default serializes just the `id` of the component, and the `id` should always be serialized.
- `mount(**kwargs)`: Loads the initial state of the component when is rendered from the back-end or it reconnects from the front-end (using the information created by `serialize`), it is also called in case a subscription of the component is triggered.
- subscribe(*names): Subscribes the current component to the given signal names, when one of those signals is broadcasted the component is refreshed, meaning that `mount` is called passing the result `serialize` and the component is re-rendered.
- `send_redirect(url, *args, **kwargs )`: Resolves the `url`, and instructs the front-end to redirect to that `url`, if push_state=False, the redirect is done in hard HTML5 `pushState` is not used.
- `send(_name, id=None, **kwargs)`: Sends a message with the name `_name` to the component with `id`, if `id` is `None` the message is sent to the current component.


#### AuthComponent API

This component ensures the user is logged in or redirects the user to the login screen; when using this component and overriding `mount` make sure to call the support mount first.

- `mount(**kwargs)`: Same as before, but returns `True` if the user is logged in.
- `user`: the current logged-in user.

## Simple counter example

In your app create a template `x-counter.html`:

```html
{% load reactor %}
<div is="x-counter" id="{{ this.id }}" state="{{ this.serialize|tojson }}">
  {{ this.amount }}
  <button @click="inc">+</button>
  <button @click="dec">-</button>
  <button @click="set_to {amount: 0}">reset</button>
</div>
```

Anatomy of a template: each component should be a [custom web component](https://developer.mozilla.org/en-US/docs/Web/Web_Components/Using_custom_elements) that inherits from [HTMLElement](https://developer.mozilla.org/en-US/docs/Web/API/HTMLElement). They should have an `id` so the backend knows which instance is this one and a `state` attribute with the necessary information to recreate the full state of the component on first render and in case of reconnection to the back-end.

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
