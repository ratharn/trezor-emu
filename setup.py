from setuptools import setup, find_packages
from os.path import dirname, join

here = dirname(__file__)
setup(
    name = 'trezor-emu',
    version = '0.2.0',
    author = 'Bitcoin TREZOR',
    author_email = 'info@bitcointrezor.com',
    description = 'Python implementation of TREZOR compatible hardware bitcoin wallet',
    long_description = open(join(here, 'README.rst')).read(),
    packages = find_packages(),
    test_suite = 'tests',
    dependency_links=['https://github.com/trezor/python-mnemonic/archive/master.zip#egg=mnemonic-0.8'],
    install_requires=['ecdsa>=0.11', 'RPi.GPIO', 'spidev', 'pyserial', 'protobuf==2.6.1', 'mnemonic>=0.8', 'pyaes'],
    entry_points = {'console_scripts': ['trezor-emu  =  trezor:run', ], },
    include_package_data = True,
    package_data = {'protobuf': ['*.proto'], },
    zip_safe = False,
    classifiers  =  [
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Operating System :: POSIX :: Linux',
    ],
)
