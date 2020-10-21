

all: build-deps build

build-deps:
	pip install rjsmin
	npm install coffeescript

build:
	./node_modules/.bin/coffee -c reactor/static/reactor/reactor.coffee
	python -m rjsmin <reactor/static/reactor/reactor.js >reactor/static/reactor/reactor.min.js
	mv reactor/static/reactor/reactor.min.js reactor/static/reactor/reactor.js
	python setup.py sdist

install:
	pip install --upgrade pip
	pip install poetry
	poetry install

test:
	flake8 --max-line-length=80 reactor
	py.test
