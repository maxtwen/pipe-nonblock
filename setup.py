try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

config = {
    'description': 'non-blocking pipe',
    'author': 'Maksim Afanasevsky',
    'url': 'https://github.com/maxtwen/Non-Blocking-Pipe',
    'download_url': 'https://github.com/maxtwen/Non-Blocking-Pipe',
    'author_email': 'maxtwen1@gmail.com',
    'version': '0.3',
    'install_requires': [''],
    'packages': ['non_blocking_pipe'],
    'scripts': [],
    'name': 'non_blocking_pipe'
}

setup(**config)
