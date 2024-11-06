from setuptools import setup, find_packages


def readme():
    with open('README.md', 'r') as f:
        return f.read()


setup(
    name='pybalt',
    version='2024.11.5',
    author='nichind',
    author_email='nichinddev@gmail.com',
    description='',
    long_description=readme(),
    long_description_content_type='text/markdown',
    url='https://github.com/nichind/pybalt',
    packages=find_packages(),
    install_requires=[
        'aiohttp',
        'aiofiles',
        'pytube',
    ],
    classifiers=[
        'Programming Language :: Python :: 3.11',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent'
    ],
    python_requires='>=3.8',
    entry_points={
        'console_scripts': [
            'pybalt=pybalt.__main__:main',
            'cobalt=pybalt.__main__:main',
        ],
    },
)
