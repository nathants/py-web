import setuptools

setuptools.setup(
    version="0.0.1",
    license='mit',
    name='py-web',
    author='nathan todd-stone',
    python_requires='>=3.7',
    author_email='me@nathants.com',
    url='http://github.com/nathants/py-web',
    packages=['web'],
    install_requires=['tornado >6, <7'],
    description='a minimal, data centric web library'
)
