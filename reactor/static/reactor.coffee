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

class Channel
  constructor: (@url, options={}) ->
    @retry_interval = options.retry_interval or 1000
    @online = false
    @callbacks = {}

  on: (event_name, callback) =>
    @callbacks[event_name] = callback

  trigger: (event_name, args...) ->
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
      @websocket.onopen = (e) =>
        @online = true
        @trigger 'open'
        @retry_interval = 1000

      @websocket.onclose = (e) =>
        @online = false
        @trigger 'close'
        setTimeout (=> @open()), @retry_interval

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


channel = new Channel('/reactor')
channel.open()

channel.on 'open', ->
  console.log 'ON-LINE'
  for el in document.querySelectorAll(reactor_components.join(','))
    el.classList.remove('reactor-disconnected')
    el.connect()

reactor_channel.on 'close', ->
  for el in document.querySelectorAll(reactor_components.join(','))
    el.classList.add('reactor-disconnected')


channel.on 'message', ({type, id, html_diff}) ->
  console.log '<<<', type.toUpperCase(), id
  el = document.getElementById(id)
  if el?
    if type is 'render'
      el.apply_diff(html_diff)
    else if type is 'remove'
      window.requestAnimationFrame ->
        el.remove()

for component in reactor_components
  class Component extends HTMLElement
    constructor: ->
      super()
      @tag_name = @tagName.toLowerCase()
      @_last_received_html = ''

    connectedCallback: ->
      @connect()

    disconnectedCallback: ->
      channel.send 'leave', id: @id

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
        channel.send 'join',
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
              # Prevent updating the input that has the focus
              if (from_el.type in FOCUSABLE_INPUTS and
                    from_el is document.activeElement and
                    'reactor-orverride-value' not in to_el.getAttributeNames())
                to_el.getAttributeNames().forEach (name) ->
                  from_el.setAttribute(name, to_el.getAttribute(name))
                from_el.readOnly = to_el.readOnly
                return false
              return true
          @querySelector('[focus]')?.focus()

    dispatch: (name, args) ->
      state = @serialize()
      for k, v of args
        state[k] = v

      console.log '>>> USER_EVENT', @tag_name, name, state
      origin = new Date()
      channel.send 'user_event',
        name: name
        state: state

    serialize: (state) ->
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

      state ?= {id: @id}
      for {type, name, value, checked} in @querySelectorAll('[name]')
        value = if type is 'checkbox' then checked else value
        for part in name.split('.').reverse()
          obj = {}
          obj[part] = value
          value = obj
        satte = merge_objects state, value
      state

  customElements.define(component, Component)


merge_objects = (target, source) ->
  for k, v of source
    if typeof target[k] is 'object'
      merge_objects target[k], v
    else
      target[k] = v
  target

send = (element, name, args) ->
  while element
    if element.dispatch?
      return element.dispatch(name, args or {})
    element = element.parentElement

