

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
	python setup.py develop
	pip install flake8 pytest-django pytest-asyncio pytest-cov pyquery rjsmin

test:
	flake8 --max-line-length=80 reactor
	py.test --cov reactor
