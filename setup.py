import setuptools
import sys

requires = ['tornado >6, <7']

try:
    _ = sys.pypy_version_info
    requires += ['typing >3, <4',
                 'typing-extensions >3, <4']
except AttributeError:
    pass

setuptools.setup(
    version="0.0.1",
    license='mit',
    name='py-web',
    author='nathan todd-stone',
    python_requires='>=3.6',
    author_email='me@nathants.com',
    url='http://github.com/nathants/py-web',
    packages=['web'],
    install_requires=requires,
    description='a minimal, data centric web library'
)
