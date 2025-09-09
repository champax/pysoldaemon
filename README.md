pysoldaemon
============

Welcome to pysol

Copyright (C) 2013/2025 Laurent Labatut / Laurent Champagnac

pysoldaemon is a generic linux daemon in Python.

It supports :
- Double forking
- std redirect to files
- log to file
- working directory change after Fork 1
- start/stop/status/reload commands

It is gevent (co-routines) based.

Usage
===============

An implementation is available in :
- pysoldaemon_test.Daemon.CustomDaemon.CustomDaemon
