# Change Log

## 1.10.0b0 - Granular control over auto broadcast

### Changed

- The settings `REACTOR_AUTO_BROADCAST` can be a `bool` or a `dict`, if it is a `bool` it will enable/disable completely the auto broadcast of model changes. When a `dict` can be like:

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

Each key controls an specific broadcast type, if a keys is missing `False` is assumed.

- Template directive `:override` is gone, use `:keep` to preserve the `value` of an `input`, `select` or `textarea` HTML element from render to render.


## 1.9.0b0 - Middleware for turbolinks

### Added

- Method `Component.send_parent` to send an event to the parent component.

### Removed

- Template filter `tojson_safe`, use piping of `tojson` into `safe` instead.

### Changed

- Template filter `tojson` now supports an integer argument corresponding to the `indent` parameter in `json.dumps`.
- In the front-end there is the assumption that components IDs are unique, so this was also implemented as this in the back-end.


## 1.8.4b0 - Middleware for turbolinks

### Added

- If you have turbolinks you need to add `reactor.middleware.turbolinks_middleware` to your `settings.MIDDLEWARE`, because of <https://github.com/turbolinks/turbolinks#following-redirects>

## 1.8.3b0 - Syntax sugar

### Added

- Instead of writing `<div is="x-component" id="{{ this.id }}" state="{{ this.serialize|tojson }}">`, now you can do `<div {{ this|safe }} >`.

## 1.8.2b0 - Hot fix

### Fixed

- Fix missing transpilation when a DOM node was added

## 1.8.1b0 - DOM hooks

### Added new reactor events

- `@reactor-added`, when an HTML element is added
- `@reactor-updated`, when an HTML element is updated

### Changed

- `@reactor-init`, is not triggered on any HTML element of a component when this one is initialized (appears for first time in the DOM).

## 1.8.0b0 - Bring back optional diffing using difflib

### Added

- New setting `REACTOR_USE_HTML_DIFF` (default: `False`), it will use `difflib` to send the HTML diff, is a line based diff not a character based one but is very fast, not like `diff_match_patch`


## 1.7.0b0 - Remove diffing, was very slow

### Removed

- Dependency on `diff_match_patch` had been removed, diffing was very very very slow.

## 1.6.1b0 - Numpy support

### Added

- Add capability to serializer `numpy.array` and `numpy.float` as the component state.

## 1.6.0b0 - Migration to Turbolinks

### Added

- `REACTOR_INCLUDE_TURBOLINKS` is a new setting, by default to `False`, when enabled will load Turbolinks as part of the reactor headers and the reactor redirects (`Component.send_redirect`) will use `Turbolinks.visit`. This also affects all the links in your application, check out the documentation of Turbolinks.

### Removed

- `:load` directive had been removed in favor of Tubolinks.


## 1.5.1b0 - Improve broadcasting with parameters

### Added

- `Component.update(origin, type, **kwargs)` is called when there is an update coming from `broadcast` and it receive  whatever kwargs where passed to `reactor.broadcast`. You could override this method to handle the update in the way you want, the default behavior is to call `Component.refresh`.

### Change

- `reactor.broadcast`, now can receive parameters.
