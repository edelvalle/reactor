

all: build-deps build

build-deps:
	pip install rjsmin
	npm install coffeescript

build:
	./node_modules/.bin/coffee -cmb .
	python -m rjsmin <reactor/static/reactor.js >reactor/static/reactor.min.js
    mv reactor/static/reactor.min.js reactor/static/reactor.js
	python setup.py sdist

install:
	python setup.py develop
