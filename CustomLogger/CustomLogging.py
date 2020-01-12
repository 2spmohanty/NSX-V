__author__ = 'smrutim'

import logging

"""
For Any Code changes.
Please update the READ.md file and here also for quick reference.

"""


def generate_logger(log_file=None):
    log_level = logging.DEBUG
    fh = None
    FORMAT = "%(asctime)s %(levelname)s %(message)s"
    logger = logging.getLogger(__name__)
    logger.setLevel(log_level)
    # Reset the logger.handlers if it already exists.
    if logger.handlers:
        logger.handlers = []
    formatter = logging.Formatter(FORMAT)
    if log_file:
        fh = logging.FileHandler(log_file)
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    return logger