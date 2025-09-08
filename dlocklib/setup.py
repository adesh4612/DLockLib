# -*- coding: utf-8 -
#
# This file is part of gunicorn released under the MIT license.
# See the NOTICE for more information.

from setuptools import setup, find_packages
exec(open("version.py").read())

# setup(
#     name="dlocklib",
#     version=__version__,
#     description="distributed lock lib",
#     long_description="API Interface to use to use distributed locks",
#     author="Adesh M",
#     author_email="adesh.matkar@druva.com",
#     license="Druva",
#     zip_safe=False,
#     packages=find_packages(),
#     include_package_data=True,
#     install_requires=[
#         'dblib@git+ssh://git@git.druva.org/druva.com/soabaselibs.git@v3.0.0#subdirectory=soabaselibs'
#     ]
# )
setup(
    name="dlocklib",
    version=__version__,
    description="distributed lock lib",
    long_description="API Interface to use to use distributed locks",
    author="Adesh M",
    author_email="adesh.matkar@druva.com",
    license="Druva",
    zip_safe=False,
    packages=find_packages(),
    include_package_data=True,
)
