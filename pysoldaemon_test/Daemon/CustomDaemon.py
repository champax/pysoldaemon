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
from logging.handlers import SysLogHandler

import os
from pysolbase.SolBase import SolBase

from pysoldaemon.daemon.Daemon import Daemon

logger = logging.getLogger(__name__)


class CustomDaemon(Daemon):
    """
    Custom daemon for test
    """

    DAEMON_LAST_ACTION_FILE = "/tmp/daemon_last_action.txt"

    def _internal_init(self,
                       pidfile,
                       stdin, stdout, stderr, logfile, loglevel,
                       on_start_exit_zero,
                       max_open_files,
                       change_dir,
                       timeout_ms,
                       logtosyslog=True,
                       logtosyslog_facility=SysLogHandler.LOG_LOCAL0,
                       logtoconsole=True,
                       app_name="Test"
                       ):

        # Us
        self.is_running = True
        self.start_count = 0
        self.stop_count = 0
        self.reload_count = 0
        self.status_count = 0
        self.start_loop_exited = False
        self.last_action = "noaction"

        # Base
        Daemon._internal_init(self, pidfile, stdin, stdout, stderr, logfile, loglevel, on_start_exit_zero, max_open_files, change_dir, timeout_ms,
                              logtosyslog, logtosyslog_facility, logtoconsole, app_name)

        # Log
        logger.debug("Done, self.class=%s", SolBase.get_classname(self))

    @classmethod
    def get_daemon_instance(cls):
        """
        Get a new Daemon instance
        :return CustomDaemon
        :rtype CustomDaemon
        """
        return CustomDaemon()

    def _write_state(self):
        """
        Write state
        """
        f = open(CustomDaemon.DAEMON_LAST_ACTION_FILE, "w")
        buf = "" \
              "pid={0}\nppid={1}\nis_running={2}\nstart_count={3}\nstop_count={4}\n" \
              "reload_count={5}\nstatus_count={6}\nlast_action={7}\nstart_loop_exited={8}\n" \
            .format(os.getpid(),
                    os.getppid(),
                    self.is_running,
                    self.start_count, self.stop_count, self.reload_count, self.status_count,
                    self.last_action,
                    self.start_loop_exited
                    )
        f.write(buf)
        f.close()

    def _on_stop(self):
        """
        Test
        """
        logger.info("Called")
        self.is_running = False
        self.stop_count += 1
        self.last_action = "stop"
        self._write_state()

        # Signal
        self.is_running = False

        # Wait for completion
        while not self.start_loop_exited:
            SolBase.sleep(10)

    def _on_reload(self, *args, **kwargs):
        """
        Test
        """
        logger.info("Called")
        self.reload_count += 1
        self.last_action = "reload"
        self._write_state()

    def _on_start(self):
        """
        Test
        """
        logger.info("Called")
        self.start_count += 1
        self.last_action = "start"
        self._write_state()

        logger.info("Engaging running loop")
        while self.is_running:
            SolBase.sleep(10)
        logger.info("Exited running loop")

        self.start_loop_exited = True
        self._write_state()
        logger.debug("Exited")

    def _on_status(self):
        """
        Test
        """
        logger.info("Called")
        self.status_count += 1
        self.last_action = "status"
        self._write_state()
