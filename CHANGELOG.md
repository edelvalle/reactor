# Change Log

## 1.8.0b0 - Bring back optional diffing using difflib

## Added

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
