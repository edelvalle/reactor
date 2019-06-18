origin = new Date()
FOCUSABLE_INPUTS = [
  'text'
  'textarea'
  'number'
  'email'
  'password'
  'search'
  'tel'
  'url'
]

class ReactorChannel
  constructor: (@url='/reactor', @retry_interval=100) ->
    @online = false
    @callbacks = {}
    @original_retry_interval = @retry_interval

  on: (event_name, callback) =>
    @callbacks[event_name] = callback

  trigger: (event_name, args  ...) ->
    @callbacks[event_name]?(args...)

  open: ->
    if @retry_interval < 10000
      @retry_interval += 1000

    if navigator.onLine
      @websocket?.close()

      if window.location.protocol is 'https:'
        protocol = 'wss://'
      else
        protocol = 'ws://'
      @websocket = new WebSocket "#{protocol}#{window.location.host}#{@url}"
      @websocket.onopen = (event) =>
        @online = true
        @trigger 'open', event
        @retry_interval = @original_retry_interval

      @websocket.onclose = (event) =>
        @online = false
        @trigger 'close', event
        setTimeout (=> @open()), @retry_interval or 0

      @websocket.onmessage = (e) =>
        data = JSON.parse e.data
        @trigger 'message', data
    else
      setTimeout (=> @open()), @retry_interval

  send: (command, payload) ->
    data =
      command: command
      payload: payload
    if @online
      try
        @websocket.send JSON.stringify data
      catch
        console.log 'Failed sending'

  reconnect: ->
    @retry_interval = 0
    @websocket?.close()



reactor_channel = new ReactorChannel()

all_reactor_components = (
  "#{name},[is='#{name}']" for name in Object.keys(reactor_components)
).join(',')

reactor_channel.on 'open', ->
  console.log 'ON-LINE'
  for el in document.querySelectorAll(all_reactor_components)
    el.classList.remove('reactor-disconnected')
    el.connect()

reactor_channel.on 'close', ->
  console.log 'OFF-LINE'
  for el in document.querySelectorAll(all_reactor_components)
    el.classList.add('reactor-disconnected')


reactor_channel.on 'message', ({type, id, html_diff, url}) ->
  console.log '<<<', type.toUpperCase(), id or url
  if type is 'redirect'
    location.assign url
  else
    el = document.getElementById(id)
    if el?
      if type is 'render'
        el.apply_diff(html_diff)
      else if type is 'remove'
        window.requestAnimationFrame ->
          el.remove()

for component_name, base_html_element of reactor_components
  base_element = document.createElement base_html_element
  class Component extends base_element.constructor
    constructor: (...args) ->
      super(...args)
      @tag_name = @getAttribute('is') or @tagName.toLowerCase()
      @_last_received_html = ''

    connectedCallback: ->
      @connect()

    disconnectedCallback: ->
      reactor_channel.send 'leave', id: @id

    is_root: -> not @parent_component()

    parent_component: ->
      component = @parentElement
      while component
        if component.dispatch?
          return component
        component = component.parentElement

    connect: ->
      if @is_root()
        console.log '>>> JOIN', @tag_name
        state = JSON.parse @getAttribute 'state'
        reactor_channel.send 'join',
          tag_name: @tag_name
          state: state

    apply_diff: (html_diff) ->
      console.log new Date() - origin
      html = []
      cursor = 0
      console.log html_diff
      for diff in html_diff
        if typeof diff is 'string'
          html.push diff
        else if diff < 0
          cursor -= diff
        else
          html.push @_last_received_html[cursor...cursor + diff]
          cursor += diff
      html = html.join ''
      if @_last_received_html isnt html
        @_last_received_html = html
        window.requestAnimationFrame =>
          morphdom this, html,
            onBeforeElUpdated: (from_el, to_el) ->
              # Prevent object from being updated
              if from_el.hasAttribute('reactor-once')
                return false

              # Prevent updating the input that has the focus
              if (from_el.type in FOCUSABLE_INPUTS and
                    from_el is document.activeElement and
                    'reactor-override-value' not in to_el.getAttributeNames())
                to_el.getAttributeNames().forEach (name) ->
                  from_el.setAttribute(name, to_el.getAttribute(name))
                from_el.readOnly = to_el.readOnly
                return false
              return true
          @querySelector('[reactor-focus]')?.focus()

    dispatch: (name, form, args) ->
      state = @serialize form or this
      for k, v of args
        state[k] = v

      console.log '>>> USER_EVENT', @tag_name, name, state
      origin = new Date()
      reactor_channel.send 'user_event',
        name: name
        state: state

    serialize: (form) ->
      # Serialize the fields with name attribute and creates a dictionary
      # with them. It support nested name spaces.
      #
      # Ex1:
      #   <input name="a" value="q">
      #   <input name="b" value="x">
      # Result: {a: "q", b: "x"}
      #
      # Ex2:
      #   <input name="query" value="q">
      #   <input name="person.name" value="John">
      #   <input name="person.age" value="99">
      # Result: {query: "q", person: {name: "John", value: "99"}}
      #
      # Ex3:
      #   <input name="query" value="q">
      #   <input name="persons[].name" value="a">
      #   <input name="persons[].name" value="b">
      # Result: {query: "q", persons: [{name: "a"}, {name: "b"}]}

      state = {id: @id}
      for {type, name, value, checked} in form.querySelectorAll('[name]')
        value = if type is 'checkbox' then checked else value
        for part in name.split('.').reverse()
          obj = {}
          if part.endsWith('[]')
            obj[part[...-2]] = [value]
          else
            obj[part] = value
          value = obj
        satte = merge_objects state, value
      state

  customElements.define(component_name, Component, extends: base_html_element)


merge_objects = (target, source) ->
  for k, v of source
    target_value = target[k]
    if Array.isArray target_value
      target_value.push v...
    else if typeof target_value is 'object'
      merge_objects target_value, v
    else
      target[k] = v
  target


send = (element, name, args) ->
  first_form_found = null
  while element

    if first_form_found is null and element.tagName is 'FORM'
      first_form_found = element

    if element.dispatch?
      return element.dispatch(name, first_form_found, args or {})

    element = element.parentElement


_timeouts = {}

debounce = (delay_name, delay) -> (...args) ->
  clearTimeout _timeouts[delay_name]
  _timeouts[delay_name] = setTimeout (=> send(...args)), delay

reactor_channel.open()
