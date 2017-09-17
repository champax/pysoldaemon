import logging
import sys

from pysol_base.SolBase import SolBase

SolBase.logging_init("INFO")
logger = logging.getLogger(__name__)

sys.stdout = open('/tmp/log.txt', 'a')
print('hey')
logger.info("hey2")
print("hey3")

SolBase.logging_init("INFO", True)
print('pd1')
logger.info("pd2")
print("pd2")
