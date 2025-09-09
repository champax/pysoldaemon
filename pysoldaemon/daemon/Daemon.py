"""
# -*- coding: utf-8 -*-
# ===============================================================================
#
# Copyright (C) 2013/2025 Laurent Labatut / Laurent Champagnac
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

import argparse
import atexit
import logging
from signal import SIGUSR1, SIGUSR2, SIGTERM

import sys
from logging.handlers import SysLogHandler

# noinspection PyProtectedMember
from gevent.signal import signal
from pysolbase.SolBase import SolBase

try:
    import resource
except Exception as e:
    print("Possible windows, ex=" + str(e))
try:
    import pwd
except Exception as e:
    print("Possible windows, ex=" + str(e))
try:
    import grp
except Exception as e:
    print("Possible windows, ex=" + str(e))
import errno
import os
import gevent

SolBase.voodoo_init()
logger = logging.getLogger(__name__)


class Daemon(object):
    """
    Daemon helper.
    """

    def __init__(self):
        """
        Constructor
        """
        self.vars = None

    def _internal_init(self,
                       pidfile,
                       stdin, stdout, stderr,
                       logfile, loglevel,
                       on_start_exit_zero,
                       max_open_files,
                       change_dir,
                       timeout_ms,
                       logtosyslog=True,
                       logtosyslog_facility=SysLogHandler.LOG_LOCAL0,
                       logtoconsole=False,
                       app_name=None
                       ):
        """
        Internal init.
        :param pidfile: Pid file.
        :type pidfile: str
        :param change_dir: Enable directory change
        :type change_dir: bool
        :param max_open_files: Max open files.
        :type max_open_files: int
        :param stdin: stdin. What else?
        :type stdin: str
        :param stdout: stdout. What else?
        :type stdout: str
        :param stderr: stderr. What else?
        :type stderr: str
        :param logfile: logfile. If none or empty, log to files will be disabled. What else?
        :type logfile: str
        :param loglevel: loglevel. What else?
        :type loglevel: str
        :param on_start_exit_zero: perform an exit(0) on start.
        :type on_start_exit_zero: bool
        :param timeout_ms: Timeout in ms
        :type timeout_ms: int
        :param logtosyslog: bool,None (default True)
        :type logtosyslog: bool,None
        :param logtosyslog_facility: int,None default SysLogHandler.LOG_LOCAL0
        :type logtosyslog_facility: int,None
        :param logtoconsole: bool,None (default False)
        :type logtoconsole: bool,None
        :param app_name: Application name (syslog), default None
        :type app_name: str,None
        """

        # File handle
        self._stderr_file = None
        self._stdin_file = None
        self._stdout_file = None

        # Store
        self._pidfile = pidfile
        self._maxOpenFiles = max_open_files
        self._timeout_ms = timeout_ms

        self._stdin = stdin
        self._stdout = stdout
        self._stderr = stderr
        self._loglevel = loglevel

        self._changeDir = change_dir
        self._onStartExitZero = on_start_exit_zero

        # Engage logfile asap if specified
        logger.debug("_loglevel=%s", self._loglevel)

        # App name
        self.v_app_name = app_name
        if self.v_app_name:
            SolBase.set_compo_name(self.v_app_name)

        # Init : log to console
        self.v_log_to_console = False
        if logtoconsole is not None:
            self.v_log_to_console = logtoconsole

        # Init : log to file
        self.v_log_to_file = None
        if logfile and len(logfile) > 0:
            self.v_log_to_file = logfile

        # Init : log to syslog
        self.v_log_to_syslog = True
        self.v_log_to_syslog_facility = SysLogHandler.LOG_LOCAL0
        if logtosyslog is not None:
            self.v_log_to_syslog = logtosyslog
        if logtosyslog_facility is not None:
            self.v_log_to_syslog_facility = logtosyslog_facility

        # Log
        logger.info("Starting, action=%s, app_name=%s, v_log_to_file=%s, v_log_to_syslog=%s, v_log_to_syslog_facility=%s, v_log_to_console=%s",
                    self.vars.get("action", None) if self.vars else None,
                    self.v_app_name,
                    self.v_log_to_file, self.v_log_to_syslog, self.v_log_to_syslog_facility, self.v_log_to_console)

        self._logging_reset()

        # Go
        logger.debug("_pidfile=%s", self._pidfile)
        logger.debug("_maxOpenFiles=%s", self._maxOpenFiles)
        logger.debug("_timeout_ms=%s", self._timeout_ms)

        logger.debug("_stdin=%s", self._stdin)
        logger.debug("_stdout=%s", self._stdout)
        logger.debug("_stderr=%s", self._stderr)
        logger.debug("_loglevel=%s", self._loglevel)

        logger.debug("_onStartExitZero=%s", self._onStartExitZero)
        logger.debug("_changeDir=%s", self._changeDir)

        logger.info("vars=%s", self.vars)

        # Check
        if not pidfile:
            raise Exception("pidfile is required")

        # Internal
        self._pidFileHandle = None
        self._softLimit = None
        self._hardLimit = None

    def _logging_reset(self):
        """
        Logging reset
        """

        # Go
        # Ouch, this hack disable console logs (zzzz), status invocation now flush nothing...
        if self.vars and "action" in self.vars and self.vars["action"] in ["status", "reload", "stop"]:
            logger.debug("Bypassing switch to logfile due to 'status|reload|stop' action")
        else:
            logger.debug("Switching to logfile, you will lost console logs now")

            for h in logging.root.handlers:
                h.close()

            SolBase.logging_init(
                log_level=self._loglevel,
                force_reset=True,
                log_to_file=self.v_log_to_file,
                log_to_syslog=self.v_log_to_syslog,
                log_to_syslog_facility=self.v_log_to_syslog_facility,
                log_to_console=self.v_log_to_console,
            )

    # ===============================================
    # UTILITIES
    # ===============================================

    def _close_files(self):
        """
        Close files
        """

        if self._stdin_file:
            self._stdin_file.flush()
            self._stdin_file.close()
            self._stdin_file = None

        if self._stdout_file:
            self._stdout_file.flush()
            self._stdout_file.close()
            self._stdout_file = None

        if self._stderr_file:
            self._stderr_file.flush()
            self._stderr_file.close()
            self._stderr_file = None

    def _redirect_all_std(self):
        """
        Redirect std
        """

        # Flush
        logger.debug("flushing")
        sys.stdout.flush()
        sys.stderr.flush()

        # Open new std
        try:
            # Trying
            sys.stdin.fileno()
            sys.stdout.fileno()
            sys.stderr.fileno()

            # Go
            logger.debug("opening new ones")
            self._stdin_file = open(self._stdin, "r")
            self._stdout_file = open(self._stdout, "a+")
            self._stderr_file = open(self._stderr, "a+")

            # Dup std
            logger.debug("dup2 (expecting log loss now)")

            os.dup2(self._stdin_file.fileno(), sys.stdin.fileno())
            os.dup2(self._stdout_file.fileno(), sys.stdout.fileno())
            os.dup2(self._stderr_file.fileno(), sys.stderr.fileno())
            logger.debug("dup2 done")
        except Exception:
            self._close_files()
            raise

    def _set_limits(self):
        """
        Set limits
        """

        logger.debug("Setting max open file=%s", self._maxOpenFiles)
        try:
            # Get
            self._softLimit, self._hardLimit = resource.getrlimit(resource.RLIMIT_NOFILE)
            logger.info("rlimit before : soft=%s, hard=%s", self._softLimit, self._hardLimit)

            # Update
            resource.setrlimit(resource.RLIMIT_NOFILE, (self._maxOpenFiles, self._maxOpenFiles))

            # Get
            self._softLimit, self._hardLimit = resource.getrlimit(resource.RLIMIT_NOFILE)
            logger.info("rlimit after, soft=%s, hard=%s", self._softLimit, self._hardLimit)

        except Exception as ex:
            # Get
            self._softLimit, self._hardLimit = resource.getrlimit(resource.RLIMIT_NOFILE)

            # Log it
            logger.error("setrlimit failed, soft=%s, hard=%s, required=%s, ex=%s", self._softLimit, self._hardLimit,
                         self._maxOpenFiles, SolBase.extostr(ex))

            # This is fatal
            logger.error("failed to apply _maxOpenFiles, exit(-3) now")
            sys.exit(-3)

    def _godaemon(self):
        """
        daemonize us
        """

        logger.debug("Entering, pid=%s", os.getpid())

        # Limit
        self._set_limits()

        # Fork1
        logger.debug("fork1, %s", SolBase.get_current_pid_as_string())
        try:
            pid = gevent.fork()
            if pid > 0:
                # Exit first parent
                logger.debug("exit(0) first parent")
                sys.exit(0)
        except OSError as ex:
            logger.error("fork1 failed, exit(1) now : errno=%s, err=%s, ex=%s", ex.errno, ex.strerror,
                         SolBase.extostr(ex))
            sys.exit(1)
        logger.debug("fork1 done, %s", SolBase.get_current_pid_as_string())

        # Diverge from parent
        if self._changeDir:
            logger.debug("chdir now")
            os.chdir("/")

        # Set stuff
        logger.debug("setsid and umask")
        # noinspection PyArgumentList
        os.setsid()
        os.umask(0)

        # Fork2
        logger.debug("fork2, %s", SolBase.get_current_pid_as_string())
        try:
            pid = gevent.fork()
            if pid > 0:
                # exit from second parent
                logger.debug("exit(0) second parent")
                sys.exit(0)
        except OSError as ex:
            logger.error("fork2 failed, exit(2) now : errno=%s, err=%s, ex=%s", ex.errno, ex.strerror,
                         SolBase.extostr(ex))
            sys.exit(2)
        logger.debug("fork2 done, %s", SolBase.get_current_pid_as_string())

        # Redirect std
        self._redirect_all_std()

        # Go
        logger.debug("initializing _pidfile=%s", self._pidfile)

        # Register the method called at exit
        atexit.register(self._remove_pid_file)

        # Write pidfile
        pid = str(os.getpid())
        try:
            f = open(self._pidfile, "w")
            f.write("%s" % pid)
            f.close()

        except IOError as ex:
            logger.error("pid file initialization failed, going exit(3), ex=%s", SolBase.extostr(ex))
            sys.exit(3)

            # Ok
        logger.debug("pid file set")

        # Finish
        logger.debug("registering gevent signal handler : SIGUSR1")
        signal(SIGUSR1, self._on_reload)
        logger.debug("registering gevent signal handler : SIGUSR2")
        signal(SIGUSR2, self._on_status)
        logger.debug("registering gevent signal handler : SIGTERM")
        signal(SIGTERM, self._exit_handler)

        logger.debug("registering gevent signal handler : done")

        # Fatality
        SolBase.voodoo_init()
        logger.debug("process started, pid=%s, pidfile=%s", os.getpid(), self._pidfile)

    def _remove_pid_file(self):
        """
        Remove the pid file
        """
        if os.path.exists(self._pidfile):
            os.remove(self._pidfile)

    # noinspection PyMethodMayBeStatic
    def _set_user_and_group(self, user, group):
        """
        Set user and group
        :param user: User
        :type user: str
        :param group: Group
        :type group: str
        """
        if group:
            os.setgid(grp.getgrnam(group).gr_gid)
            logger.debug("group set=%s", group)
        if user:
            os.setuid(pwd.getpwnam(user).pw_uid)
            logger.debug("user set=%s", user)

    def _get_running_pid(self):
        """
        Get running pid
        :return: int
        """

        pf = None
        try:
            pf = open(self._pidfile, "r")
            return int(pf.read().strip())
        except IOError:
            return None
        finally:
            if pf:
                pf.close()

    # ===============================================
    # HANDLERS
    # ===============================================

    def _on_start(self):
        """
        On start
        """
        logger.info("Base implementation (pass)")

    def _on_stop(self):
        """
        On stop
        """
        logger.info("Base implementation (pass)")

    # noinspection PyUnusedLocal
    def _on_reload(self, *argv, **kwargs):
        """
        On reload
        """
        logger.info("Base implementation (pass)")

    # noinspection PyUnusedLocal
    def _on_status(self, *argv, **kwargs):
        """
        On status
        """
        logger.info("Base implementation (pass)")

    # noinspection PyUnusedLocal
    def _exit_handler(self, *argv, **kwargs):
        """
        Exit handler
        """

        try:
            # Call
            self._on_stop()
        finally:
            pass

        logger.debug("exiting Daemon with exit(0)")
        self._close_files()
        sys.exit(0)

    # ===============================================
    # DAEMON METHODS
    # ===============================================

    def _daemon_start(self, user, group):
        """
        Start the Daemon
        :param user: User
        :type user: str
        :param group: Group
        :type group: str

        """
        """
        # Status : OK, implemented
        # - Running : exit 0 => OK
        # - Not running and pid file exist : exit 1 => OK
        # - Not running : exit 3 => OK
        # - Other : 4 => NOT TESTED
        """
        # Check for a pidfile to see if the Daemon already runs
        logger.debug("entering")
        pid = self._get_running_pid()

        # Pid ?
        if pid:
            # Check with SIGUSR2
            try:
                os.kill(pid, SIGUSR2)

                # Check success, asked to start, but already running
                logger.info("Already running, exit(1) now, pid=%s", pid)
                sys.exit(1)
            except OSError as err:
                if err.errno == errno.ESRCH:
                    logger.info("Found pidfile but SIGUSR2 failed, rm on file, pid=%s, pidfile=%s", pid, self._pidfile)
                    if os.path.exists(self._pidfile):
                        logger.debug("Removing pidfile")
                        self._remove_pid_file()

        # Ok start now
        self._godaemon()
        self._set_user_and_group(user, group)
        self._on_start()

        # =====================
        # CAUTION : With same Daemon, this should not happen (custom start will exit the main
        # due to unlock by customStop)
        # So, the exit(0) is USELESS and may be DISABLED
        # =====================

        # Exit
        if self._onStartExitZero:
            logger.debug("exiting WITH exit(0) due to _onStartExitZero==True")
            sys.exit(0)
        else:
            logger.debug("exiting WITHOUT exit(0)")

    def _daemon_stop(self):
        """
        Stop the Daemon
        # Status : OK, implemented
        # - Running : exit 0 => OK
        # - Not running and pid file exist : exit 1 => OK
        # - Not running : exit 3 => OK
        # - Other : 4 => NOT TESTED
        """

        logger.debug("entering")

        # Get the pid from the pidfile
        pid = self._get_running_pid()
        if not pid:
            logger.info("Daemon is not running, pidFile=%s", self._pidfile)
            return

        # Stop it
        logger.debug("sending SIGTERM, pid=%s, pidFile=%s", pid, self._pidfile)
        try:
            os.kill(pid, SIGTERM)
        except OSError as ex:
            if ex.errno == errno.ESRCH:
                logger.info("SIGTERM failed, ESRCH, ex=%s", SolBase.extostr(ex))
            else:
                logger.info("SIGTERM failed, not an ESRCH, ex=%s", SolBase.extostr(ex))
        except Exception as ex:
            logger.info("SIGTERM failed, not an OSError, going exit(1), ex=%s", SolBase.extostr(ex))
            sys.exit(1)
        finally:
            if os.path.exists(self._pidfile):
                logger.debug("Removing pidFile=%s", self._pidfile)
                self._remove_pid_file()

        # Ok
        logger.debug("SIGTERM sent")
        ms_start = SolBase.mscurrent()

        # Validate
        proc_target = "/proc/%d" % pid
        while SolBase.msdiff(ms_start) < self._timeout_ms:
            if os.path.exists(proc_target):
                SolBase.sleep(10)
                continue

            # Over
            logger.info("SIGTERM success, pid=%s", pid)
            self._remove_pid_file()
            return

        # Not cool
        logger.warning("SIGTERM timeout=%s ms, pid=%s", self._timeout_ms, pid)

    def _daemon_status(self):
        """
        Check status.
        May send a SIGUSR2 to process.
        
        # Status : 
        # - Running : exit 0 
        # - Not running and pid file exist : exit 1 
        # - Not running : exit 3 
        # - Other : 4 => NOT TESTED

        """
        # Get the pid from the pidfile
        pid = self._get_running_pid()
        if not pid:
            logger.info("Daemon is not running (no pidfile), pidfile=%s", self._pidfile)
            sys.exit(3)

        # Validate
        try:
            os.kill(pid, SIGUSR2)
        except OSError as err:
            if err.errno == errno.ESRCH:
                # Process not found
                logger.info("Daemon is not running (SIGUSR2 failed), pid=%s, pidfile=%s", pid, self._pidfile)
                sys.exit(1)

        # Ok
        logger.info("Daemon is running, pid=%s, pidfile=%s", pid, self._pidfile)
        sys.exit(0)

    def _daemon_reload(self):
        """
        Reload.
        May send a SIGUSR1 to process.
        """

        # Get
        pid = self._get_running_pid()
        if not pid:
            logger.warning("Daemon not running, (no pidfile), pidfile=%s", self._pidfile)
            return

        # Signal it
        try:
            os.kill(pid, SIGUSR1)
        except OSError as err:
            if err.errno == errno.ESRCH:
                # Process not found
                logger.info("Daemon is not running (SIGUSR1 failed), pid=%s, pidfile=%s", pid, self._pidfile)
                sys.exit(2)

        logger.info("Reload requested through SIGUSR1, pid=%s, pidfile=%s", pid, self._pidfile)

    # ===============================================
    # COMMAND LINE PARSER
    # ===============================================

    @classmethod
    def initialize_arguments_parser(cls):
        """
        Initialize the parser
        :param cls: class
        :return ArgumentParser
        :rtype ArgumentParser
        """
        logger.debug("Entering")

        # Create an argument parser
        arg_parser = argparse.ArgumentParser(description='SolBase.Daemon', add_help=True)

        # Set it
        arg_parser.add_argument(
            "programname",
            metavar="programname",
            type=str,
            action="store",
            help="Program name (argv[0]) [required]"
        )
        arg_parser.add_argument(
            "-pidfile",
            metavar="pidfile",
            type=str,
            default=None,
            action="store",
            help="pid filename [required]"
        )
        arg_parser.add_argument(
            "-user",
            metavar="user",
            type=str,
            default=None,
            action="store",
            help="Daemon user [optional]"
        )
        arg_parser.add_argument(
            "-group",
            metavar="group",
            type=str,
            default=None,
            action="store",
            help="Daemon group [optional]"
        )

        arg_parser.add_argument(
            "-stdin",
            metavar="stdin",
            type=str,
            default="/dev/null",
            action="store",
            help="std redirect [optional]"
        )
        arg_parser.add_argument(
            "-stdout",
            metavar="stdout",
            type=str,
            default="/dev/null",
            action="store",
            help="std redirect [optional]"
        )
        arg_parser.add_argument(
            "-stderr",
            metavar="stderr",
            type=str,
            default="/dev/null",
            action="store",
            help="std redirect [optional]"
        )
        arg_parser.add_argument(
            "-logfile",
            metavar="logfile",
            type=str,
            default="",
            action="store",
            help="logfile (full path) (if specified, all logs goes to this file, console/rsyslog and so on are disabled) [optional]"
        )
        arg_parser.add_argument(
            "-logconsole",
            metavar="logconsole",
            type=bool,
            default=False,
            action="store",
            help="Log to console (boolean) (default False) [optional]"
        )
        arg_parser.add_argument(
            "-logsyslog",
            metavar="logsyslog",
            type=bool,
            default=True,
            action="store",
            help="Log to syslog (boolean) (default True) [optional]"
        )
        arg_parser.add_argument(
            "-logsyslog_facility",
            metavar="logsyslog_facility",
            type=int,
            default=16,
            action="store",
            help="Log to syslog facility (int) (default local0, 16) [optional]"
        )
        arg_parser.add_argument(
            "-appname",
            metavar="appname",
            type=str,
            default="KnockDaemon",
            action="store",
            help="Syslog appname (str) (default KnockDaemon) [optional]"
        )
        arg_parser.add_argument(
            "-loglevel",
            metavar="loglevel",
            type=str,
            default="INFO",
            action="store",
            help="loglevel (DEBUG, INFO, WARN, ERROR) (applies only if logfile is specified) [optional]"
        )
        arg_parser.add_argument(
            "-name",
            metavar="name",
            help="Optional name"
        )
        arg_parser.add_argument(
            "-maxopenfiles",
            metavar="maxopenfiles",
            type=int,
            default=1048576,
            action="store",
            help="max open files [optional]"
        )
        arg_parser.add_argument(
            "-timeoutms",
            metavar="timeoutms",
            type=int,
            default=15000,
            action="store",
            help="timeout when checking process [optional]"
        )
        arg_parser.add_argument(
            "-changedir",
            metavar="changedir",
            type=bool,
            default=False,
            action="store",
            help="if set, dir is changed after fork [optional]"
        )
        arg_parser.add_argument(
            "-onstartexitzero",
            metavar="onstartexitzero",
            type=bool,
            default=True,
            action="store",
            help="if set, Daemon will exit zero after start [optional]"
        )
        arg_parser.add_argument(
            "action",
            metavar="action",
            type=str,
            choices=["start", "stop", "status", "reload"],
            action="store",
            help="Daemon action to perform (start|stop|status|reload) [required]"
        )
        logger.debug("Done")
        return arg_parser

    @classmethod
    def parse_arguments(cls, argv):
        """
        Parse command line argument (initParser required before call)
        :param cls: Our class.
        :param argv: Command line argv
        :type argv: list, tuple
        :return dict
        :rtype dict
        """

        logger.debug("Entering")

        # Check argv
        if not isinstance(argv, (tuple, list)):
            raise Exception("parse_arguments : argv not a list, class=%s" + SolBase.get_classname(argv))

        # Parse
        local_args = cls.initialize_arguments_parser().parse_args(argv)

        # Flush
        d = vars(local_args)
        logger.debug("Having vars=%s", d)

        return d

    # ===============================================
    # ALLOCATE (pseudo factory)
    # ===============================================

    @classmethod
    def get_daemon_instance(cls):
        """
        Get a new Daemon instance
        :return Daemon
        :rtype Daemon
        """
        return Daemon()

    # ===============================================
    # MAIN
    # ===============================================

    @classmethod
    def main_helper(cls, argv, kwargs):
        """
        Main helper
        :param argv: Command line argv
        :type argv: list, tuple
        :param kwargs: Command line argv
        :type kwargs: dict
        :return Daemon
        :rtype Daemon
        """

        logger.debug("Entering, argv=%s, kwargs=%s", argv, kwargs)

        try:
            # Parse
            vars_hsh = cls.parse_arguments(argv)

            # Get stuff
            action = vars_hsh["action"]
            user = vars_hsh["user"]
            group = vars_hsh["group"]
            pidfile = vars_hsh["pidfile"]
            stdin = vars_hsh["stdin"]
            stdout = vars_hsh["stdout"]
            stderr = vars_hsh["stderr"]
            logfile = vars_hsh["logfile"]
            loglevel = vars_hsh["loglevel"]
            on_start_exit_zero = vars_hsh["onstartexitzero"]
            max_open_files = vars_hsh["maxopenfiles"]
            change_dir = vars_hsh["changedir"]
            timeout_ms = vars_hsh["timeoutms"]

            # New
            logconsole = vars_hsh["logconsole"]
            logsyslog = vars_hsh["logsyslog"]
            logsyslog_facility = vars_hsh["logsyslog_facility"]
            appname = vars_hsh["appname"]

            # Allocate now
            logger.debug("Allocating Daemon")
            di = cls.get_daemon_instance()

            # Store vars
            di.vars = vars_hsh

            logger.debug("Internal initialization, class=%s", SolBase.get_classname(di))
            di._internal_init(
                pidfile=pidfile,
                stdin=stdin, stdout=stdout, stderr=stderr, logfile=logfile, loglevel=loglevel,
                on_start_exit_zero=on_start_exit_zero,
                max_open_files=max_open_files,
                change_dir=change_dir,
                timeout_ms=timeout_ms,
                logtosyslog=logsyslog,
                logtosyslog_facility=logsyslog_facility,
                logtoconsole=logconsole,
                app_name=appname,
            )

            logger.info("action=%s, user=%s, group=%s", action, user, group)

            if action == "start":
                di._daemon_start(user, group)
            elif action == "stop":
                di._daemon_stop()
            elif action == "status":
                di._daemon_status()
            elif action == "reload":
                di._daemon_reload()
            else:
                logger.info("Invalid action=%s", action)
                print(
                    "usage: %s -pidfile filename [_maxopenfiles int] [-timeoutms int] "
                    "[-stdin string] [-stdout string] [-stderr string] [-logfile string] [-loglevel string] [-changedir bool] "
                    "[-onstartexitzero bool] [-user string] [-group string] start|stop|status|reload" %
                    argv[0])
                sys.exit(2)

            # Done
            logger.debug("Done")
            return di
        except Exception as ex:
            logger.error("Exception, ex=%s", SolBase.extostr(ex))
            raise


# ==========================
# MAIN / COMMAND LINE INTERCEPTION
# ==========================

if __name__ == "__main__":
    """
    Main
    """

    try:
        # Go
        cur_path = sys.path
        for s in cur_path:
            logger.debug("__main__ : Starting, path=%s", s)

        # Run
        Daemon.main_helper(sys.argv, {})
    except Exception as e:
        # Failed
        logger.error("__main__ : Exception, exiting -1, ex=%s", SolBase.extostr(e))
        sys.exit(-1)
    finally:
        logger.debug("__main__ : Exiting now")
