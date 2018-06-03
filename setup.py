import setuptools


setuptools.setup(
    version="0.0.1",
    license='mit',
    name='py-web',
    author='nathan todd-stone',
    python_requires='>=3.6',
    author_email='me@nathants.com',
    url='http://github.com/nathants/py-web',
    packages=['web'],
    install_requires=['tornado==5.0.2',
                      'py-util',
                      'py-schema',
                      'py-pool'],
    dependency_links=['https://github.com/nathants/py-util/tarball/4d1fe20ecfc0b6982933a8c9b622b1b86da2be5e#egg=py-util-0.0.1',
                      'https://github.com/nathants/py-pool/tarball/f1e9aee71bc7d8302f0df8d9111e49e008a16351#egg=py-pool-0.0.1',
                      'https://github.com/nathants/py-schema/tarball/826ee02cf2040a66ce7d9c9ec498fe6cc467f5a8#egg=py-schema-0.0.1'],
    description='a minimal, data centric web library'
)
