

all: build-deps build

build-deps:
	npm install coffeescript uglify-es

build:
	./node_modules/.bin/coffee -c reactor/static/reactor/reactor.coffee
	./node_modules/.bin/uglifyjs reactor/static/reactor/reactor.js >reactor/static/reactor/reactor.min.js
	mv reactor/static/reactor/reactor.min.js reactor/static/reactor/reactor.js
	poetry build

install:
	pip install --upgrade pip
	pip install poetry
	poetry install

test:
	flake8 --max-line-length=80 reactor
	py.test
