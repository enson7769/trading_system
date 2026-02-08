import os
import getpass
import json
import hashlib
import hmac
from typing import Optional, Dict, Any

class CredentialManager:
    """凭证管理器"""
    
    def __init__(self, secure_file: str = "data/secure_secrets.json"):
        """初始化凭证管理器
        
        Args:
            secure_file: 安全存储文件路径
        """
        # 存储凭证的字典
        self._secrets: Dict[str, str] = {}
        self.secure_file = secure_file
        # 确保数据目录存在
        os.makedirs(os.path.dirname(self.secure_file), exist_ok=True)
        # 加载安全存储的凭证
        self._load_secure_secrets()

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
                # 验证私钥格式（如果是私钥）
                if 'private_key' in key.lower():
                    if not self._validate_private_key(from_env):
                        raise ValueError("无效的私钥格式")
                self._secrets[key] = from_env
                return from_env

        # 交互式输入
        if not no_input:
            secret = getpass.getpass(prompt)
            if secret.strip():
                # 验证私钥格式（如果是私钥）
                if 'private_key' in key.lower():
                    if not self._validate_private_key(secret.strip()):
                        raise ValueError("无效的私钥格式")
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
    
    def _validate_private_key(self, private_key: str) -> bool:
        """验证私钥格式
        
        Args:
            private_key: 私钥字符串
            
        Returns:
            bool: 是否为有效的私钥格式
        """
        # 移除开头的0x前缀（如果有）
        if private_key.startswith('0x'):
            private_key = private_key[2:]
        
        # 检查长度（64个十六进制字符 = 32字节）
        if len(private_key) != 64:
            return False
        
        # 检查是否为有效的十六进制字符串
        try:
            int(private_key, 16)
            return True
        except ValueError:
            return False
    
    def _load_secure_secrets(self):
        """加载安全存储的凭证"""
        try:
            if os.path.exists(self.secure_file):
                with open(self.secure_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                # 这里应该有解密逻辑，现在简化处理
                # 实际生产环境中应该使用加密存储
                pass
        except Exception as e:
            print(f"加载安全存储失败: {e}")
    
    def secure_store(self, key: str, value: str, encrypt: bool = True):
        """安全存储凭证
        
        Args:
            key: 凭证键名
            value: 凭证值
            encrypt: 是否加密存储
            
        Returns:
            bool: 是否存储成功
        """
        try:
            # 验证私钥格式（如果是私钥）
            if 'private_key' in key.lower():
                if not self._validate_private_key(value):
                    return False
            
            # 这里应该有加密逻辑，现在简化处理
            # 实际生产环境中应该使用加密存储
            data = {}
            if os.path.exists(self.secure_file):
                with open(self.secure_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            
            data[key] = value
            
            with open(self.secure_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            return True
        except Exception as e:
            print(f"安全存储失败: {e}")
            return False
    
    def secure_retrieve(self, key: str, decrypt: bool = True) -> Optional[str]:
        """安全获取存储的凭证
        
        Args:
            key: 凭证键名
            decrypt: 是否解密
            
        Returns:
            Optional[str]: 凭证值
        """
        try:
            if os.path.exists(self.secure_file):
                with open(self.secure_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                # 这里应该有解密逻辑，现在简化处理
                # 实际生产环境中应该使用加密存储
                return data.get(key)
            return None
        except Exception as e:
            print(f"安全获取失败: {e}")
            return None
    
    def generate_api_key(self, prefix: str = "api") -> str:
        """生成安全的API密钥
        
        Args:
            prefix: 密钥前缀
            
        Returns:
            str: 生成的API密钥
        """
        import secrets
        import time
        
        # 生成随机密钥
        random_part = secrets.token_hex(16)
        timestamp = str(int(time.time()))
        
        # 组合密钥
        api_key = f"{prefix}_{timestamp}_{random_part}"
        
        return api_key
    
    def get_hmac_signature(self, data: str, secret: str) -> str:
        """生成HMAC签名
        
        Args:
            data: 要签名的数据
            secret: 密钥
            
        Returns:
            str: HMAC签名
        """
        signature = hmac.new(
            secret.encode('utf-8'),
            data.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature