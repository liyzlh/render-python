#!/usr/bin/env python
from setuptools import setup
import sys
from setuptools.command.test import test as TestCommand


class PyTest(TestCommand):
    user_options = [('pytest-args=', 'a', "Arguments to pass to pytest")]

    def initialize_options(self):
        TestCommand.initialize_options(self)
        self.pytest_args = ""

    def run_tests(self):
        # import here, cause outside the eggs aren't loaded
        import shlex
        import pytest
        self.pytest_args += " --cov=renderapi --cov-report html "\
                            "--junitxml=test-reports/test.xml"

        errno = pytest.main(shlex.split(self.pytest_args))
        sys.exit(errno)


with open('test/requirements.txt', 'r') as f:
    test_required = f.read().splitlines()

with open('requirements.txt', 'r') as f:
    required = f.read().splitlines()

setup(name='render-python',
      version='1.0',
      description=' a python API to interact via python with render '
                  'databases see https://github.com/saalfeldlab/render',
      author='Forrest Collman, Russel Torres, Eric Perlman, Sharmi Seshamani',
      author_email='forrest.collman@gmail.com',
      url='https://github.com/fcollman/render-python',
      packages=['renderapi'],
      install_requires=required,
      setup_requires=['flake8'],
      tests_require=test_required,
      cmdclass={'test': PyTest},)
