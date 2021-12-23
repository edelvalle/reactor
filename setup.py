from pathlib import Path

from setuptools import find_packages, setup

HERE = Path(__file__).absolute().parent
README = open(HERE / "README.md", encoding="utf8").read()

setup(
    name="djangoreactor",
    version="3.0.0b0",
    url="https://github.com/edelvalle/reactor",
    author="Eddy Ernesto del Valle Pino",
    author_email="eddy@edelvalle.me",
    long_description=README,
    long_description_content_type="text/markdown",
    description="Brings LiveView from Phoenix framework into Django",
    license="BSD",
    packages=find_packages(exclude=["tests"]),
    include_package_data=True,
    zip_safe=False,
    python_requires=">=3.6",
    install_requires=[
        "channels>=3.0.4,<4",
        "pydantic>=1.8.0,<2",
        "lru-dict>=1.1.7,<1.2",
    ],
    extras_require={
        "dev": [
            "black",
            "flake8",
            "ipython",
            "whitenoise",
            "channels-redis",
        ]
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Web Environment",
        "Framework :: Django",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Topic :: Internet :: WWW/HTTP",
    ],
)
