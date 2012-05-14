#!/usr/bin/env python

import re
import os
import sys
import shutil
import tempfile
import argparse
import xmlrpclib
from pip.vcs import VcsSupport

VERSION = '0.4.0'
PYPI_ENDPOINT = "http://pypi.python.org/pypi"
HOMEBREW_CELLAR = os.environ.get("HOMEBREW_CELLAR")
CACHE_LOCATION = os.environ.get("PIP_DOWNLOAD_CACHE") or os.environ.get("HOMEBREW_CACHE")
VERSION_REGEXP = r'(?P<name>[\w-]+)-(?P<version>[0-9.-_]+)\.'
ENABLED_PIP_VCS_BACKENDS = tuple(["%s+" % scheme for scheme in VcsSupport.schemes])

class NoPackageInfo(Exception): pass

def get_package_info(package):
    """
    Return (package_name, version) for a given package.

    If the version isn't specified in package, query PyPI for the
    latest.
    """
    name, version = None, None

    if package.startswith(ENABLED_PIP_VCS_BACKENDS):
        assert "#egg=" in package, "VCS package missing an '#egg=' identifier"
        result = re.search('#egg=(?P<name>.+)$', package)
        name = result.group('name')

        result = re.search('@(?P<version>[^#]+)#', package)
        if result:
            version = "rev-" + result.group('version')
        else:
            version = 'HEAD'
    elif re.search(VERSION_REGEXP, os.path.basename(package)):
        result = re.search(VERSION_REGEXP, os.path.basename(package))
        name = result.group('name')
        version = result.group('version')
    elif '==' in package:
        name, version = package.split('==')
    else:
        client = xmlrpclib.ServerProxy(PYPI_ENDPOINT)
        if '>=' in package:
            (package, _) = package.split('>=')
        releases = client.package_releases(package)
        if not releases:
            # PyPI searching is case-sensitive, so try a capitalized
            # version of the package name if the above didn't find
            # anything.
            releases = client.package_releases(package.capitalize())
            assert releases, "Couldn't find any package named '%s'" % package
        name = package
        version = releases[0]

    if name and version:
        return (name.lower(), version)
    else:
        raise NoPackageInfo("Couldn't determine either name (%r) or version (%r) "
                            "for the requested package (%r).  Aborting." % (name, version, package))

def main(args):
    for package in args.package:
        (package_name, version) = get_package_info(package)

        if args.upgrade:
            os.system("brew rm %s" % package_name)

        prefix = os.path.join(HOMEBREW_CELLAR, package_name, version)
        build_dir = tempfile.mkdtemp(prefix='brew-pip-')

        cmd = ["pip", "install",
               "-v" if args.verbose else "",
               package,
               "--build=%s" % build_dir,
               "--install-option=--prefix=%s" % prefix,
               "--install-option=--install-scripts=%s" % os.path.join(prefix, "share", "python")]

        if CACHE_LOCATION:
            cmd.append("--download-cache=%s" % CACHE_LOCATION)

        if args.verbose:
            print " ".join(cmd)

        os.system(" ".join(cmd))

        if not args.keg_only:
            os.system("brew link %s" % package_name)

        shutil.rmtree(build_dir)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog='brew pip')
    parser.add_argument("--version", action="version", version="%(prog)s v" + VERSION)
    parser.add_argument("-v", "--verbose", action="store_true", default=False, help="be verbose")
    parser.add_argument("-k", "--keg-only", action="store_true", default=False, help="don't link files into prefix")
    parser.add_argument("-u", "--upgrade", action="store_true", default=False, help="upgrade the package")
    parser.add_argument("package", nargs='+', help="name of the package(s) to install")
    main(parser.parse_args())
