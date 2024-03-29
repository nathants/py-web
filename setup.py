import setuptools
import sys

requires = ['tornado']

try:
    _ = sys.pypy_version_info
    requires += ['typing',
                 'typing-extensions']
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
    package_data = {'web': ['py.typed']},
    install_requires=requires,
    description='a minimal, data centric web library'
)
