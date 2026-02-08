#!/usr/bin/env python3
"""
错误重试工具
提供自动重试机制，提高系统稳定性
"""

import time
import random
from functools import wraps
from typing import Callable, Any, Tuple, Optional

class RetryError(Exception):
    """重试失败异常"""
    pass

def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    jitter: float = 0.1,
    exceptions: Tuple[Exception, ...] = (Exception,),
    log_func: Optional[Callable] = None
) -> Callable:
    """重试装饰器
    
    Args:
        max_attempts: 最大尝试次数
        delay: 初始延迟（秒）
        backoff: 延迟倍数
        jitter: 随机抖动因子
        exceptions: 需要重试的异常类型
        log_func: 日志函数
        
    Returns:
        Callable: 装饰后的函数
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            attempts = 0
            current_delay = delay
            
            while attempts < max_attempts:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    attempts += 1
                    if attempts >= max_attempts:
                        if log_func:
                            log_func(f"重试失败，最大尝试次数已达: {e}")
                        raise RetryError(f"重试失败，最大尝试次数已达: {e}") from e
                    
                    # 添加随机抖动
                    jitter_amount = current_delay * jitter
                    sleep_time = current_delay + random.uniform(-jitter_amount, jitter_amount)
                    sleep_time = max(0.1, sleep_time)  # 确保延迟至少为0.1秒
                    
                    if log_func:
                        log_func(f"尝试 {attempts}/{max_attempts} 失败: {e}，将在 {sleep_time:.2f} 秒后重试")
                    
                    time.sleep(sleep_time)
                    # 指数退避
                    current_delay *= backoff
            
            # 理论上不会执行到这里，但为了类型提示安全
            raise RetryError("重试失败")
        
        return wrapper
    
    return decorator

def retry_with_timeout(
    timeout: float,
    interval: float = 0.1,
    exceptions: Tuple[Exception, ...] = (Exception,),
    log_func: Optional[Callable] = None
) -> Callable:
    """带超时的重试装饰器
    
    Args:
        timeout: 超时时间（秒）
        interval: 重试间隔（秒）
        exceptions: 需要重试的异常类型
        log_func: 日志函数
        
    Returns:
        Callable: 装饰后的函数
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            start_time = time.time()
            attempts = 0
            
            while time.time() - start_time < timeout:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    attempts += 1
                    elapsed = time.time() - start_time
                    remaining = timeout - elapsed
                    
                    if remaining <= 0:
                        if log_func:
                            log_func(f"超时失败，尝试次数: {attempts}, 错误: {e}")
                        raise RetryError(f"超时失败: {e}") from e
                    
                    if log_func:
                        log_func(f"尝试 {attempts} 失败: {e}，将在 {interval:.2f} 秒后重试")
                    
                    time.sleep(interval)
            
            raise RetryError("超时失败")
        
        return wrapper
    
    return decorator

# 示例用法
if __name__ == "__main__":
    import logging
    
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    @retry(
        max_attempts=3,
        delay=1.0,
        backoff=2.0,
        exceptions=(ValueError,),
        log_func=logger.info
    )
    def test_func():
        """测试函数"""
        import random
        if random.random() < 0.7:
            raise ValueError("随机错误")
        return "成功"
    
    try:
        result = test_func()
        print(f"测试结果: {result}")
    except RetryError as e:
        print(f"测试失败: {e}")
