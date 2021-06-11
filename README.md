# Reactor, a LiveView library for Django

Reactor enables you to do something similar to Phoenix framework LiveView using Django Channels.

![TODO MVC demo app](demo.gif)

## What's in the box?

This is no replacement for VueJS or ReactJS, or any JavaScript but it will allow you use all the potential of Django to create interactive front-ends. This method has its drawbacks because if connection is lost to the server the components in the front-end go busted until connection is re-established. But also has some advantages, as everything is server side rendered the interface comes already with meaningful information in the first request response, you can use all the power of Django template without limitations, if connection is lost or a component crashes, the front-end will have enough information to rebuild their state in the last good known state.

## Installation and setup

Reactor requires Python >=3.6.

Install reactor:

```bash
pip install django-reactor
```

Reactor makes use of `django-channels`, by default this one uses an InMemory channel layer which is not capable of a real broadcasting, so you might wanna use the Redis one, take a look here: [Channel Layers](https://channels.readthedocs.io/en/latest/topics/channel_layers.html)

Add `reactor` and `channels` to your `INSTALLED_APPS` before the Django applications so channels can override the `runserver` command.

```python
INSTALLED_APPS = [
    'reactor',
    'channels',
    ...
]

...

ASGI_APPLICATION = 'project_name.asgi.application'
```

and modify your `project_name/asgi.py` file like:

```python
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project_name.settings')

import django
django.setup()

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
from project_name.urls import websocket_urlpatterns

application = ProtocolTypeRouter({
    'http': get_asgi_application(),
    'websocket': AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
})
```

In your `project_name/urls.py`, add the following lines:

```python
from reactor.channels import ReactorConsumer

# ...

websocket_urlpatterns = [
    path('__reactor__', ReactorConsumer),
]
```

Note: Reactor since version 2, autoloads any `live.py` file in your applications with the hope to find there Reactor Components so they get registered and can be instantiated.

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

## Settings:

- `REACTOR_AUTO_BROADCAST` (default: `False`), when enabled will activate listeners for every time a model is created, modified or deleted, and will broadcast a message related to that modification that you can subscribe to and use to refresh your components in real-time, you can fine tune what kind of notification you want to get by turning this in a dictionary, for example:

```python
AUTO_BROADCAST = {
    # model_a
    # model_a.del
    # model_a.new
    'MODEL': True,

    # model_a.1234
    'MODEL_PK': True,

    # model_b.1234.model_a_set
    # model_b.1234.model_a_set.new
    # model_b.1234.model_a_set.del
    'RELATED': True,

    # model_b.1234.model_a_set
    # model_a.1234.model_b_set
    'M2M': True,
}
```

- `REACTOR_USE_HTML_DIFF` (default: `True`), when enabled uses `difflib` to create diffs to patch the front-end, reducing bandwidth.
- `REACTOR_USE_HMIN` (default: `False`), when enabled and django-hmin is installed will use it to minified the HTML of the components and save bandwidth.

## Back-end APIs

### Template tags and filters of `reactor` library

- `{% reactor_header %}`: that includes the necessary JavaScript to make this library work. ~5Kb of minified JS, compressed with gz or brotli.
- `{% component 'x-component-name' param1=1 param2=2 %}`: Renders a component by its name and passing whatever parameters you put there to the `Component.mount` method.
- `tojson`: Takes something and renders it in JSON, the `ReactorJSONEncoder` extends the `DjangoJSONEncoder` it serializes a `Model` instance to its `id` and a `QuerySet` as a list of `ids`.
- `tojson_safe`: Same as `tojson` but does not "HTML escapes" the output.
- `then`: Use as a shorthand for if, `{% if expression %}print-this{% endif %}` is equivalent to `{{ expresssion|then:'print-this' }}`.
- `ifnot`: Use a shorthand for if not, `{% if not expression %}print-this{% endif %}` is equivalent to `{{ expresssion|ifnot:'print-this' }}, and can be concatenated with then, like in: `{{ expression|then:'positive'|ifnot:'negative' }}`
- `eq`: Compares its arguments and returns `"yes"` or empty string, `{{ this_thing|eq:other_thing|then:'print-this' }}`.
- `cond`: Allows simple conditional presence of a string: `{% cond {'hidden': is_hidden } %}`.
- `class`: Use it to handle conditional classes: `<div {% class {'nav_bar': True, 'hidden': is_hidden} %}></div>`.

### `reactor.component` module

- `Component`: This is the base component you should extend.
- `AuthComponent`: Extends `Component` and ensures the user is logged in.
- `broadcast(*names)`: Broadcasts the given names too all the system.
- `on_commit(function)(*args, **kwargs)`: Calls `function` with the given arguments after database commit.

#### Component API

- `__init__`: Is responsable for the component initialization, pass what ever you need to bootstrap the component state.
- `template_name`: Set the name of the template of the component.
- `extends`: Tag name HTML element the component extends.
- `_subscribe(*names)`: Subscribes the current component to the given signal names, when one of those signals is broadcasted the component is refreshed, meaning that `mount` is called passing the result `serialize` and the component is re-rendered.
- `visit(url, action='advance', **kwargs )`: Resolves the `url` using `**kwargs`, and depending on `action` the navigation will be `advance` (pushState) or `replace` (repalceState).
- `destroy()`: Removes the component from the interface.
- `_send(_name, id=None, **kwargs)`: Sends a message with the name `_name` to the component with `id`, if `id` is `None` the message is sent to the current component.
- `_send_parent(_name, kwargs)`: Sends a message with the name `_name` to the parent component.

## Front-end APIs

- `reactor.visit(url, {action='advance'})`: if `action` is `advance`, calls `window.history.replaceState`, else tries to talk to [Turbo](https://turbo.hotwire.dev/handbook/drive#application-visits) or falls back to `window.history.pushState` or just `window.location.assign`.
- `reactor.send(element, event_name, args)`: send the event `event_name` with the `args` parameters to the HTML `element`. It what is used to forward user event to the back-end.

### Special HTMLElement attributes

- `:keep`: Prevent the value of an input from being changed across renders.
- `:override`: When an input is being updated and the user has the focus there reactor by default will not update the input field value (has if it had `:keep`), use `:override` to do otherwise.
- `:once`: Reactor will render this element and children once, and never update it again.
- `:focus`: Sets the focus on this element after an HTML update.

### Event binding in the front-end

Look at this:

```html
  <button @click.prevent="submit">Submit</button?>
```

The format is `@<event>[.modifier][.modifier]="event_name[ {arg1: 1, arg2: '2'}]"`:

- `event`: is the name of the HTMLElement event: `click`, `blur`, `change`, `keypress`, `keyup`, `keydown`...
- `modifier`: can be concatenated after the event name and represent actions or conditions to be met before the event execution. This is very similar as [how VueJS does event binding](https://vuejs.org/v2/guide/events.html):
  - `prevent`: calls `event.preventDefault();`
  - `stop`: calls (`event.stopPropagation();`),
  - `enter`, `ctrl`, `alt`, `space`, expects any of those keys to be press.
  - `inlinejs`: allows you to write your custom JavaScript in the event handler.
  - `debounce`: debounces the event, it needs a name and a delay in milliseconds. Example: `@keypress.100.search.debounce='message'`.
- `event_name`: is the name of the message to be send to this component
- The arguments can be completely omitted, or specified as a dictionary.

When the arguments are omitted, reactor serializes the form where the current element is or the current component if no form is found, and sends that as the arguments. The arguments will be always sent with the `id` of the current component as a parameter.

### JS Hooks

These are custom events triggered by reactor in different instants of the life cycle of the component.

- `onreactor-init`: Triggered on any HTML element when the component is initialized.
- `onreactor-added`: Triggered on any HTML element that is added to the DOM of the component.
- `onreactor-updated`: Triggered on any HTML element that is updated, after the update happens.
- `onreactor-leave`: Triggered on the root element when the element had been removed from the DOM.

### Event handlers in the back-end

Given:

```html
<button @click="inc {amount: 2}">Increment</button?>
```

You will need an event handler in that component in the back-end:

```python
def inc(self, amount: int):
    pass
```

## Simple example of a counter

In your app create a template `x-counter.html`:

```html
{% load reactor %}
<div {% tag_header %}>
  {{ amount }}
  <button @click="inc">+</button>
  <button @click="dec">-</button>
  <button @click="set_to {amount: 0}">reset</button>
</div>
```

Anatomy of a template: each component should be a [custom web component](https://developer.mozilla.org/en-US/docs/Web/Web_Components/Using_custom_elements) that inherits from [HTMLElement](https://developer.mozilla.org/en-US/docs/Web/API/HTMLElement). They should have an `id` so the backend knows which instance is this one and a `state` attribute with the necessary information to recreate the full state of the component on first render and in case of re-connection to the back-end.

Render things as usually, so you can use full Django template language, `trans`, `if`, `for` and so on. Just keep in mind that the instance of the component is referred as `this`.

Forwarding events to the back-end: Notice that for event binding in-line JavaScript is used on the event handler of the HTML elements. How does this work? When the increment button receives a click event `send(this, 'inc')` is called, `send` is a reactor function that will look for the parent custom component and will dispatch to it the `inc` message, or the `set_to` message and its parameters `{amount: 0}`. The custom element then will send this message to the back-end, where the state of the component will change and then will be re-rendered back to the front-end. In the front-end `morphdom` (just like in Phoenix LiveView) is used to apply the new HTML.

Now let's write the behavior part of the component in `live.py`:

```python
from reactor import Component


class XCounter(Component):
    template_name = 'x-counter.html'

    def __init__(self, amount: int = 0, **kwargs):
        super().__init__(**kwargs)
        self.amount = amount

    def inc(self):
        self.amount += 1

    def dec(self):
        self.amount -= 1

    def set_to(self, amount: int):
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


## Development & Contributing

Clone the repo and create a virtualenv or any other contained environment, get inside the repo directory, build the development environment and the run tests.

```bash
git clone git@github.com:edelvalle/reactor.git
cd reactor
make install
make test
```

If you want to run the included Django project used for testing do:

```bash
make
cd tests
python manage.py runserver
```

Enjoy!
