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

      @websocket.onmessage = (event) =>
        data = JSON.parse event.data
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

  close: ->
    console.log 'CLOSE'
    @websocket?.close()



reactor_channel = new ReactorChannel()


reactor_channel.on 'open', ->
  console.log 'ON-LINE'
  for el in document.querySelectorAll '[is]'
    el.classList.remove('reactor-disconnected')
    el.connect?()

reactor_channel.on 'close', ->
  console.log 'OFF-LINE'
  for el in document.querySelectorAll '[is]'
    el.classList.add('reactor-disconnected')


reactor_channel.on 'message', ({type, id, html_diff, url, component_types}) ->
  console.log '<<<', type.toUpperCase(), id or url or component_types
  if type is 'components'
    declare_components(component_types)
  else if type is 'redirect'
    window.location.assign url
  else if type is 'push_state'
    reactor.push_state url
  else
    el = document.getElementById(id)
    if el?
      if type is 'render'
        el.apply_diff(html_diff)
      else if type is 'remove'
        window.requestAnimationFrame ->
          el.remove()


TRANSPILER_CACHE = {}

transpile = (el) ->
  if el.attributes is undefined
    return

  replacements = []
  for attr in el.attributes
    if attr.name is ':load'
      replacements.push {
        name: 'onclick'
        code: 'event.preventDefault(); reactor.push_state(this.href);'
      }

    else if attr.name.startsWith('@')
      [name, ...modifiers] = attr.name.split('.')
      start = attr.value.indexOf(' ')
      if start isnt -1
        method_name = attr.value[...start]
        method_args = attr.value[start + 1...]
      else
        method_name = attr.value
        method_args = 'null'

      cache_key = "#{modifiers}.#{method_name}.#{method_args}"
      code = TRANSPILER_CACHE[cache_key]
      if not code
        if method_name is ''
          code = ''
        else
          code = "reactor.send(this, '#{method_name}', #{method_args});"

        while modifiers.length
          modifier = modifiers.pop()
          modifier = if modifier is 'space' then ' ' else modifier
          switch modifier
            when 'inlinejs'
              code = attr.value
            when 'debounce'
              _name = modifiers.pop()
              _delay = modifiers.pop()
              code = "reactor.debounce('#{_name}', #{_delay})(function(){ #{code} })()"
            when 'prevent'
              code = "event.preventDefault(); " + code
            when 'stop'
              code = "event.stopPropagation(); " + code
            when 'ctrl'
              code = "if (event.ctrlKey) { #{code} }"
            when 'alt'
              code = "if (event.altKey) { #{code} }"
            else
              code = "if (event.key.toLowerCase() == '#{modifier}') { #{code} }; "
        TRANSPILER_CACHE[cache_key] = code

      replacements.push {
        old_name: attr.name
        name: 'on' + name[1...]
        code: code
      }

  for {old_name, name, code} in replacements
      if old_name
        el.attributes.removeNamedItem old_name
      nu_attr = document.createAttribute name
      nu_attr.value = code
      el.attributes.setNamedItem nu_attr


declare_components = (component_types) ->
  for component_name, base_html_element of component_types
    if customElements.get(component_name)
      continue

    base_element = document.createElement base_html_element
    class Component extends base_element.constructor
      constructor: (...args) ->
        super(...args)
        @tag_name = @getAttribute 'is'
        @_last_received_html = ''

      connectedCallback: ->
        @deep_transpile()
        eval @getAttribute 'onreactor-init'
        @connect()

      disconnectedCallback: ->
        eval @getAttribute 'onreactor-leave'
        console.log '>>> LEAVE', @id
        reactor_channel.send 'leave', id: @id

      deep_transpile: (element=null) ->
        if not element?
          transpile this
          element = this
        for child in element.children
          transpile child
          @deep_transpile(child)

      is_root: -> not @parent_component()

      parent_component: ->
        component = @parentElement
        while component
          if component.getAttribute 'is'
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
        console.log "#{new Date() - origin}ms"
        html = []
        cursor = 0
        for diff in html_diff
          if typeof diff is 'string'
            html.push diff
          else if diff < 0
            cursor -= diff
          else
            html.push @_last_received_html[cursor...cursor + diff]
            cursor += diff
        html = html.join ''
        @_last_received_html = html
        window.requestAnimationFrame =>
          morphdom this, html,
            onNodeAdded: transpile
            onBeforeElUpdated: (from_el, to_el) =>
              # Prevent object from being updated

              if from_el.hasAttribute(':once') or from_el.isEqualNode(to_el)
                return false

              # Prevent updating the inputs that has the focus
              should_patch = (
                from_el is document.activeElement and
                not to_el.hasAttribute(':override')
                (
                  from_el.type in FOCUSABLE_INPUTS or
                  from_el.hasAttribute(':contenteditable')
                )
              )
              if should_patch
                transpile(to_el)
                to_el.getAttributeNames().forEach (name) ->
                  from_el.setAttribute(name, to_el.getAttribute(name))
                from_el.readOnly = to_el.readOnly
                transpile(from_el)
                return false

              transpile(to_el)
              return true
          @querySelector('[\\:focus]:not([disabled])')?.focus()

      dispatch: (name, form, args) ->
        if args
          state = args
        else
          state = @serialize form or this

        state['id'] = @id
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
        for el in form.querySelectorAll('[name]')
          value = (
            if el.type is 'checkbox'
              el.checked
            else if el.hasAttribute 'contenteditable'
              if el.hasAttribute ':as-text'
                el.innerText
              else
                el.innerHTML.trim()
            else
              el.value
          )
          for part in el.getAttribute('name').split('.').reverse()
            obj = {}
            if part.endsWith('[]')
              obj[part[...-2]] = [value]
            else
              obj[part] = value
            value = obj
          state = merge_objects state, value
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

window.reactor = reactor = {}

reactor.send = (element, name, args) ->
  first_form_found = null
  while element

    if first_form_found is null and element.tagName is 'FORM'
      first_form_found = element

    if element.dispatch?
      return element.dispatch(name, first_form_found, args)

    element = element.parentElement


_timeouts = {}

reactor.debounce = (delay_name, delay) -> (f) -> (...args) ->
  clearTimeout _timeouts[delay_name]
  _timeouts[delay_name] = setTimeout (=> f(...args)), delay

reactor.push_state = (url) ->
  if history.pushState?
    load_page url, true
  else
    window.location.assign url

window.addEventListener 'popstate',  ->
  load_page window.location.href

load_page = (url, push=true) ->
  console.log 'GOTO', url
  utf8_decoder = new TextDecoder("utf-8")
  fetch(url).then (response) ->
    if response.redirected
      load_page response.url
    else
      history.pushState {}, '', url
      reader = await response.body.getReader()
      done = false
      result = []
      until done
        {done, value} = await reader.read()
        value = if value then utf8_decoder.decode(value) else ''
        result.push value
      html = result.join('').trim()
      window.requestAnimationFrame ->
        morphdom document.documentElement, html,
          onNodeAdded: transpile
          onBeforeElUpdated: (from_el, to_el) ->
            if (from_el.isEqualNode(to_el) or
                from_el.hasAttribute(':persistent') and from_el.id is to_el.id)
              return false

            transpile(to_el)
            true

        document.querySelector('[autofocus]:not([disabled])')?.focus()


reactor_channel.open()

