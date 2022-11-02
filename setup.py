from setuptools import setup, find_packages


setup(
    name='phlorest',
    version='0.1.1.dev0',
    author='Simon Greenhill and Robert Forkel',
    author_email='dlce.rdm@eva.mpg.de',
    description='A cldfbench plugin to curate language phylogenies',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    keywords='',
    license='Apache 2.0',
    url='https://github.com/phlorest/phlorest',
    packages=find_packages(where='src'),
    package_dir={'': 'src'},
    include_package_data=True,
    zip_safe=False,
    entry_points={
        'cldfbench.commands': [
            'phlorest=phlorest.commands',
        ],
         'cldfbench.scaffold': [
            'phlorest=phlorest.scaffold:PhlorestTemplate',
        ],
        'console_scripts': [
            'phlorest=phlorest.__main__:main'
        ],
    },
    platforms='any',
    python_requires='>=3.7',
    install_requires=[
        'clldutils',
        'cldfbench>=1.10.0',
        'cldfcatalog',
        'attrs',
        'python-nexus>=2.8.0',
        'pyglottolog>=-3.9.0',
        'toytree>=toytree-2.0.1',
        'termcolor',
    ],
    extras_require={
        'dev': ['flake8', 'wheel', 'twine'],
        'test': [
            'pyglottolog',
            'pytest>=5',
            'pytest-mock',
            'pytest-cov',
            'coverage>=4.2',
            'newick',
            'numpy',
            'toytree',
            'pyglottolog',
            'termcolor',
        ],
    },
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy'
    ],
)
