from os.path import dirname, abspath

from setuptools import find_packages, setup


HERE = abspath(dirname(__file__))
README = open('README.md', encoding='utf-8').read()

setup(
    name='django-reactor',
    version='1.8.3b0',
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
        'channels>=2.2.0,<2.5',
    ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Framework :: Django',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Topic :: Internet :: WWW/HTTP',
    ],
)
