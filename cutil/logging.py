from asyncio.log import logger

def warn(*args):
    logger.warning(*args)

def info(*args):
    logger.info(*args)
