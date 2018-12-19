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
    install_requires=['tornado==5.1.1',
                      'py-util==0.0.1',
                      'py-schema==0.0.1',
                      'py-pool==0.0.1'],
    dependency_links=['https://github.com/nathants/py-util/tarball/0e2f7c7637bb2907a817b343712289d64119377b#egg=py-util-0.0.1',
                      'https://github.com/nathants/py-pool/tarball/784c70058fe7bb835fe05e38c49b6632b09f242d#egg=py-pool-0.0.1',
                      'https://github.com/nathants/py-schema/tarball/4ca9827e06c5422e0988ba2be1e4478f6901b69e#egg=py-schema-0.0.1'],
    description='a minimal, data centric web library'
)
