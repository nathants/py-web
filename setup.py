import setuptools


setuptools.setup(
    version="0.0.1",
    license='mit',
    name="web",
    author='nathan todd-stone',
    author_email='me@nathants.com',
    url='http://github.com/nathants/web',
    packages=setuptools.find_packages(),
    install_requires=open('requirements.txt').readlines(),
)
