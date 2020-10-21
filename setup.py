import json
from configparser import ConfigParser
from distutils.core import setup


def project_info():
    config = ConfigParser()
    config.read('pyproject.toml')
    project = config['tool.poetry']
    return {
        'name': json.loads(project['name']),
        'version': json.loads(project['version']),
    }


setup(packages=['reactor'], **project_info())
