origin = new Date()

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
    if not navigator?.onLine and @retry_interval?
      setTimeout (=> @open()), @retry_interval

    @websocket?.close()
    if window.location.protocol is 'https:'
      protocol = 'wss://'
    else
      protocol = 'ws://'

    @websocket = new WebSocket "#{protocol}#{window.location.host}#{@url}"
    @websocket.onopen = (e) =>
      @online = true
      @trigger 'open'

    @websocket.onclose = (e) =>
      @online = false
      @trigger 'close'
      if @retry_interval?
        setTimeout (=> @open()), @retry_interval

    @websocket.onmessage = (e) =>
      data = JSON.parse e.data
      @trigger 'message', data

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
    el.connect()


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
      html = []
      cursor = 0
      for diff in html_diff
        if typeof diff is 'string'
          html.push diff
        else if diff < 0
          cursor -= diff
        else
          html.push @_last_received_html[cursor..cursor + diff]
          cursor += diff
      console.log new Date() - origin
      @_last_received_html = html.join ''
      window.requestAnimationFrame =>
        morphdom this, @_last_received_html
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
      state ?= {id: @id}
      for {type, name, value, checked} in @querySelectorAll('[name]')
        state[name] = if type is 'checkbox' then checked else value
      state

  customElements.define(component, Component)


send = (element, name, args) ->
  while element
    if element.dispatch?
      return element.dispatch(name, args or {})
    element = element.parentElement

