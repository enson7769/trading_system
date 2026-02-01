import re
from loguru import logger as _logger

class SensitiveFilter:
    def __call__(self, record):
        record["message"] = re.sub(r'0x[0-9a-fA-F]{64}', '0x[REDACTED]', record["message"])
        record["message"] = re.sub(r'\b[0-9a-fA-F]{64}\b', '[REDACTED]', record["message"])
        return True

logger = _logger
logger.remove()
logger.add(lambda msg: print(msg, end=""), filter=SensitiveFilter(), level="INFO")