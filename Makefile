

all: install build

install:
	yarn install
	pip install --upgrade pip
	pip install -e .[dev]

watch-js:
	node esbuild.conf.js -w

build:
	node esbuild.conf.js
	python setup.py sdist

check:
	pyright
	flake8 --max-line-length=80 reactor
	djlint --check .

run:
	cd tests/; python manage.py runserver

shell:
	cd tests/; python manage.py shell


.PHONY: all install watch-js build check run shell
