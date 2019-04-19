from setuptools import find_packages, setup
from reactor import __version__

setup(
    name='reactor',
    version=__version__,
    url='https://github.com/edelvalle/reactor',
    author='Eddy Ernesto del Valle Pino',
    author_email='eddy@edelvalle.me',
    description="Brings LiveView from Phoenix framework into Django",
    license='BSD',
    packages=find_packages(exclude=['tests']),
    include_package_data=True,
    python_requires='>=3.6',
    install_requires=[
        'channels>=2.2.0,<2.3',
    ],
    extras_require={
        'tests': [
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
