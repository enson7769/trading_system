import os
import getpass
from typing import Optional, Dict

class CredentialManager:
    """凭证管理器"""
    
    def __init__(self):
        """初始化凭证管理器"""
        # 存储凭证的字典
        self._secrets: Dict[str, str] = {}

    def get_secret(
        self,
        key: str,
        prompt: str,
        env_var: Optional[str] = None,
        no_input: bool = False
    ) -> str:
        """获取凭证
        
        Args:
            key: 凭证键名
            prompt: 输入提示信息
            env_var: 环境变量名
            no_input: 是否禁止交互式输入
            
        Returns:
            str: 凭证值
            
        Raises:
            ValueError: 缺少凭证时抛出异常
        """
        # 首先检查是否已缓存
        if key in self._secrets:
            return self._secrets[key]

        # 检查环境变量
        if env_var:
            from_env = os.getenv(env_var)
            if from_env:
                self._secrets[key] = from_env
                return from_env

        # 交互式输入
        if not no_input:
            secret = getpass.getpass(prompt)
            if secret.strip():
                self._secrets[key] = secret.strip()
                return self._secrets[key]

        # 无法获取凭证
        raise ValueError(f"缺少凭证: {key}。请设置环境变量 '{env_var}' 或不使用 --no-input 运行。")

    def clear_secret(self, key: str):
        """清除指定凭证
        
        Args:
            key: 凭证键名
        """
        self._secrets.pop(key, None)

    def clear_all(self):
        """清除所有凭证"""
        self._secrets.clear()