# Change Log 

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
