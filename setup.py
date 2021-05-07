from setuptools import setup, find_packages
from os import path


this_directory = path.abspath(path.dirname(__file__))
with open(path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='prometheus-mysql-exporter',
    version='0.4.2',
    description='MySQL query Prometheus exporter',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/braedon/prometheus-mysql-exporter',
    author='Braedon Vickers',
    author_email='braedon.vickers@gmail.com',
    license='MIT',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'Topic :: System :: Monitoring',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
    ],
    keywords='monitoring prometheus exporter mysql',
    packages=find_packages(exclude=['tests']),
    python_requires='>=3.5',
    install_requires=[
        'click',
        'click-config-file',
        'croniter',
        'DBUtils ~= 1.3',
        'jog',
        'PyMySQL',
        'prometheus-client >= 0.6.0',
        'pytz',
    ],
    entry_points={
        'console_scripts': [
            'prometheus-mysql-exporter=prometheus_mysql_exporter:main',
        ],
    },
)
