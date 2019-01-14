import os

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()


config = {
    'description': 'Non-blocking multiprocessing pipe',
    'author': 'Maksim Afanasevsky',
    'url': 'https://github.com/maxtwen/pipe-nonblock',
    'download_url': 'https://github.com/maxtwen/pipe-nonblock',
    'author_email': 'maxtwen1@gmail.com',
    'version': '0.2',
    'install_requires': [''],
    'packages': ['pipe_nonblock'],
    'scripts': [],
    'name': 'pipe_nonblock',
    'long_description': read('README.md'),
    'long_description_content_type': 'text/markdown'
}

setup(**config)
