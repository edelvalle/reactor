from os.path import dirname, abspath
from setuptools import find_packages, setup

from reactor import __version__

HERE = abspath(dirname(__file__))
README = open('README.md', encoding='utf-8').read()

# if sys.argv[-1] == 'publish':
#     if os.system("pip freeze | grep twine"):
#         print("twine not installed.\nUse `pip install twine`.\nExiting.")
#         sys.exit()
#     os.system("python setup.py sdist bdist_wheel")
#     os.system("twine upload dist/*")
#     print("You probably want to also tag the version now:")
#     print("  git tag -a %s -m 'version %s'" % (version, version))
#     print("  git push --tags")
#     shutil.rmtree('dist')
#     shutil.rmtree('build')
#     shutil.rmtree('djangorestframework.egg-info')
#     sys.exit()

setup(
    name='django-reactor',
    version=__version__,
    url='https://github.com/edelvalle/reactor',
    author='Eddy Ernesto del Valle Pino',
    author_email='eddy@edelvalle.me',
    long_description=README,
    long_description_content_type='text/markdown',
    description="Brings LiveView from Phoenix framework into Django",
    license='BSD',
    packages=find_packages(exclude=['tests']),
    include_package_data=True,
    zip_safe=False,
    python_requires='>=3.6',
    install_requires=[
        'channels>=2.2.0,<2.3',
    ],
    extras_require={
        'development': [
            'rjsmin',
        ],
    },
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Web Environment',
        'Framework :: Django',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Topic :: Internet :: WWW/HTTP',
    ],
)
