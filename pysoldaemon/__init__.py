"""
# -*- coding: utf-8 -*-
# ===============================================================================
#
# Copyright (C) 2013/2017 Laurent Labatut / Laurent Champagnac
#
#
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA
# ===============================================================================
"""
import logging
import sys

logger = logging.getLogger(__name__)

PY2 = sys.version_info[0] == 2
PY3 = sys.version_info[0] >= 3

# Switches:
# PY2        PY3
# str        bytes
# unicode    str

# Code :
# a) replace str by bytes
# b) replace unicode by str

# Then :
if PY3:
    string_types = str,
    integer_types = int,
    text_type = str
    binary_type = bytes,bytearray

    items = dict.items
    itervalues = dict.values
    # noinspection PyShadowingBuiltins
    xrange = range
    # noinspection PyShadowingBuiltins
    long = int

    max_int = sys.maxsize

    print("str={0}".format(str))
    print("bytes={0}".format(bytes))
else:
    # noinspection PyUnresolvedReferences,PyCompatibility
    string_types = basestring,
    # noinspection PyUnresolvedReferences,PyUnboundLocalVariable
    integer_types = (int, long)
    # noinspection PyUnresolvedReferences
    text_type = unicode, str
    binary_type = str

    # noinspection PyUnresolvedReferences
    items = dict.items
    # noinspection PyUnresolvedReferences
    itervalues = dict.itervalues
    # noinspection PyUnresolvedReferences
    import __builtin__

    # noinspection PyUnresolvedReferences,PyShadowingBuiltins
    xrange = __builtin__.xrange

    # noinspection PyShadowingBuiltins
    # noinspection PyUnresolvedReferences
    str = unicode

    # noinspection PyUnresolvedReferences
    max_int = sys.maxint

    # noinspection PyUnresolvedReferences
    print("unicode={0}".format(unicode))
    print("str={0}".format(str))
    print("bytes={0}".format(bytes))
