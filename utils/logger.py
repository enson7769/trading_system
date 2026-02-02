import re
from loguru import logger as _logger

class SensitiveFilter:
    """敏感信息过滤器"""
    
    def __call__(self, record):
        """过滤记录中的敏感信息
        
        Args:
            record: 日志记录对象
            
        Returns:
            bool: 是否保留该记录
        """
        # 过滤私钥等敏感信息
        record["message"] = re.sub(r'0x[0-9a-fA-F]{64}', '0x[已隐藏]', record["message"])
        record["message"] = re.sub(r'\b[0-9a-fA-F]{64}\b', '[已隐藏]', record["message"])
        return True

# 配置日志记录器
logger = _logger
# 移除默认处理器
logger.remove()
# 添加自定义处理器，使用敏感信息过滤器
logger.add(lambda msg: print(msg, end=""), filter=SensitiveFilter(), level="INFO")