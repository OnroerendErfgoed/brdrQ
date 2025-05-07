# coding=utf-8
"""
Test Suite.

.. note:: This program is free software; you can redistribute it and/or modify
     it under the terms of the GNU General Public License as published by
     the Free Software Foundation; either version 2 of the License, or
     (at your option) any later version.

"""

import sys
import unittest
import qgis  # noqa: F401

import coverage
from osgeo import gdal

__author__ = ""
__revision__ = "$Format:%H$"
__date__ = ""
__copyright__ = ""


def _run_tests(test_suite, package_name):
    """Core function to test a test suite."""
    count = test_suite.countTestCases()
    print("########")
    print("%s test has been discovered in %s" % (count, package_name))
    print("Python GDAL : %s" % gdal.VersionInfo("VERSION_NUM"))
    print("########")

    cov = coverage.Coverage(
        source=["test/*"],
        omit=[
            "*/???.py",
            "*/???.py",
            "*/__init__.py",
            "*/test/*",
            "*/test_suite.py",
        ],
    )
    cov.start()

    unittest.TextTestRunner(verbosity=3, stream=sys.stdout).run(test_suite)

    cov.stop()
    cov.save()
    cov.report(file=sys.stdout)


def test_package(package="brdrq"):
    """Test package.
    This function is called by travis without arguments.

    :param package: The package to test.
    :type package: str
    """
    test_loader = unittest.defaultTestLoader
    try:
        test_suite = test_loader.discover(package)
    except ImportError:
        test_suite = unittest.TestSuite()
    _run_tests(test_suite, package)


if __name__ == "__main__":
    test_package()