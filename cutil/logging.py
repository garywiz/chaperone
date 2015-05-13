import logging
logger = logging.getLogger(__name__)

def set_log_level(lev):
    logger.setLevel(lev)

def warn(*args):
    logger.warning(*args)

def info(*args):
    logger.info(*args)
