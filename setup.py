from setuptools import setup, find_packages


setup(
    name='phlorest',
    version='0.1.0',
    author='Simon Greenhill and Robert Forkel',
    author_email='dlce.rdm@eva.mpg.de',
    description='A cldfbench plugin to curate language phylogenies',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    keywords='',
    license='Apache 2.0',
    url='https://github.com/cldf/phlorest',
    packages=find_packages(where='src'),
    package_dir={'': 'src'},
    include_package_data=True,
    zip_safe=False,
    entry_points={
        'cldfbench.commands': [
            'phlorest=phlorest.commands',
        ],
    },
    platforms='any',
    python_requires='>=3.6',
    install_requires=[
        'clldutils',
        'cldfbench>=1.5.0',
        'attrs',
        'python-nexus',
    ],
    extras_require={
        'ete3': ['numpy', 'PyQt5', 'ete3'],
        'dev': ['flake8', 'wheel', 'twine'],
        'test': [
            'pyglottolog',
            'pytest>=5',
            'pytest-mock',
            'pytest-cov',
            'coverage>=4.2',
            'numpy',
            'PyQt5',
            'ete3',
        ],
    },
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy'
    ],
)
