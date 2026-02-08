#!/usr/bin/env python3
"""
监控告警系统
用于及时发现和处理系统问题
"""

import time
import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum

class AlertLevel(Enum):
    """告警级别"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class AlertType(Enum):
    """告警类型"""
    SYSTEM = "system"
    NETWORK = "network"
    DATABASE = "database"
    ORDER = "order"
    RISK = "risk"
    API = "api"
    OTHER = "other"

class Alert:
    """告警对象"""
    
    def __init__(
        self,
        level: AlertLevel,
        alert_type: AlertType,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        alert_id: Optional[str] = None
    ):
        """初始化告警
        
        Args:
            level: 告警级别
            alert_type: 告警类型
            message: 告警消息
            details: 告警详情
            alert_id: 告警ID
        """
        self.alert_id = alert_id or f"alert_{int(time.time())}_{os.urandom(4).hex()}"
        self.level = level
        self.type = alert_type
        self.message = message
        self.details = details or {}
        self.timestamp = datetime.now().isoformat()
        self.status = "open"
        self.resolved_at = None
    
    def resolve(self):
        """解决告警"""
        self.status = "resolved"
        self.resolved_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典
        
        Returns:
            Dict[str, Any]: 告警字典
        """
        return {
            "alert_id": self.alert_id,
            "level": self.level.value,
            "type": self.type.value,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp,
            "status": self.status,
            "resolved_at": self.resolved_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Alert":
        """从字典创建告警
        
        Args:
            data: 告警字典
            
        Returns:
            Alert: 告警对象
        """
        alert = cls(
            level=AlertLevel(data["level"]),
            alert_type=AlertType(data["type"]),
            message=data["message"],
            details=data.get("details", {}),
            alert_id=data.get("alert_id")
        )
        alert.timestamp = data.get("timestamp", alert.timestamp)
        alert.status = data.get("status", "open")
        alert.resolved_at = data.get("resolved_at")
        return alert

class MonitoringManager:
    """监控告警管理器"""
    
    def __init__(self, alert_file: str = "data/alerts.json"):
        """初始化监控管理器
        
        Args:
            alert_file: 告警存储文件路径
        """
        self.alert_file = alert_file
        # 确保数据目录存在
        os.makedirs(os.path.dirname(self.alert_file), exist_ok=True)
        # 告警存储
        self.alerts: Dict[str, Alert] = {}
        # 加载历史告警
        self._load_alerts()
        # 告警计数器
        self.alert_counter = {
            "info": 0,
            "warning": 0,
            "error": 0,
            "critical": 0
        }
    
    def _load_alerts(self):
        """加载历史告警"""
        try:
            if os.path.exists(self.alert_file):
                with open(self.alert_file, 'r', encoding='utf-8') as f:
                    alert_data = json.load(f)
                for data in alert_data:
                    alert = Alert.from_dict(data)
                    self.alerts[alert.alert_id] = alert
                    # 更新告警计数器
                    if alert.status == "open":
                        self.alert_counter[alert.level.value] += 1
        except Exception as e:
            print(f"加载告警失败: {e}")
    
    def _save_alerts(self):
        """保存告警"""
        try:
            alert_data = [alert.to_dict() for alert in self.alerts.values()]
            with open(self.alert_file, 'w', encoding='utf-8') as f:
                json.dump(alert_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"保存告警失败: {e}")
    
    def create_alert(
        self,
        level: AlertLevel,
        alert_type: AlertType,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ) -> Alert:
        """创建告警
        
        Args:
            level: 告警级别
            alert_type: 告警类型
            message: 告警消息
            details: 告警详情
            
        Returns:
            Alert: 告警对象
        """
        alert = Alert(level, alert_type, message, details)
        self.alerts[alert.alert_id] = alert
        self.alert_counter[level.value] += 1
        
        # 保存告警
        self._save_alerts()
        
        # 触发告警通知
        self._notify_alert(alert)
        
        return alert
    
    def resolve_alert(self, alert_id: str) -> bool:
        """解决告警
        
        Args:
            alert_id: 告警ID
            
        Returns:
            bool: 是否成功解决
        """
        if alert_id in self.alerts:
            alert = self.alerts[alert_id]
            alert.resolve()
            self.alert_counter[alert.level.value] -= 1
            self._save_alerts()
            return True
        return False
    
    def resolve_all_alerts(self, level: Optional[AlertLevel] = None) -> int:
        """解决所有告警
        
        Args:
            level: 告警级别（可选）
            
        Returns:
            int: 解决的告警数量
        """
        resolved_count = 0
        for alert_id, alert in list(self.alerts.items()):
            if alert.status == "open":
                if level is None or alert.level == level:
                    self.resolve_alert(alert_id)
                    resolved_count += 1
        return resolved_count
    
    def get_open_alerts(self, level: Optional[AlertLevel] = None) -> List[Alert]:
        """获取未解决的告警
        
        Args:
            level: 告警级别（可选）
            
        Returns:
            List[Alert]: 未解决的告警列表
        """
        alerts = []
        for alert in self.alerts.values():
            if alert.status == "open":
                if level is None or alert.level == level:
                    alerts.append(alert)
        return alerts
    
    def get_alerts_by_time_range(
        self,
        start_time: datetime,
        end_time: datetime,
        level: Optional[AlertLevel] = None
    ) -> List[Alert]:
        """获取指定时间范围内的告警
        
        Args:
            start_time: 开始时间
            end_time: 结束时间
            level: 告警级别（可选）
            
        Returns:
            List[Alert]: 告警列表
        """
        alerts = []
        for alert in self.alerts.values():
            alert_time = datetime.fromisoformat(alert.timestamp)
            if start_time <= alert_time <= end_time:
                if level is None or alert.level == level:
                    alerts.append(alert)
        return alerts
    
    def get_alert_summary(self) -> Dict[str, Any]:
        """获取告警摘要
        
        Returns:
            Dict[str, Any]: 告警摘要
        """
        open_alerts = self.get_open_alerts()
        return {
            "total_alerts": len(self.alerts),
            "open_alerts": len(open_alerts),
            "alert_counts": self.alert_counter,
            "open_alert_details": {
                "critical": len([a for a in open_alerts if a.level == AlertLevel.CRITICAL]),
                "error": len([a for a in open_alerts if a.level == AlertLevel.ERROR]),
                "warning": len([a for a in open_alerts if a.level == AlertLevel.WARNING]),
                "info": len([a for a in open_alerts if a.level == AlertLevel.INFO])
            }
        }
    
    def _notify_alert(self, alert: Alert):
        """通知告警
        
        Args:
            alert: 告警对象
        """
        # 这里可以实现不同的通知方式
        # 例如：邮件、短信、Slack、微信等
        
        # 打印告警信息（默认通知方式）
        print(f"[{alert.level.value.upper()}] [{alert.type.value}] {alert.message}")
        if alert.details:
            print(f"  详情: {json.dumps(alert.details, indent=2, ensure_ascii=False)}")
        
        # 对于严重告警，可以添加更多通知方式
        if alert.level in [AlertLevel.ERROR, AlertLevel.CRITICAL]:
            # 这里可以添加邮件通知等
            pass
    
    def check_system_health(self) -> Dict[str, Any]:
        """检查系统健康状态
        
        Returns:
            Dict[str, Any]: 系统健康状态
        """
        health_status = {
            "timestamp": datetime.now().isoformat(),
            "status": "healthy",
            "components": {
                "system": "healthy",
                "disk": "healthy",
                "memory": "healthy"
            },
            "metrics": {
                "disk_usage": self._get_disk_usage(),
                "memory_usage": self._get_memory_usage(),
                "uptime": self._get_uptime()
            }
        }
        
        # 检查磁盘使用情况
        disk_usage = health_status["metrics"]["disk_usage"]
        if disk_usage > 90:
            health_status["components"]["disk"] = "unhealthy"
            health_status["status"] = "unhealthy"
            self.create_alert(
                AlertLevel.CRITICAL,
                AlertType.SYSTEM,
                f"磁盘使用率过高: {disk_usage:.1f}%",
                {"disk_usage": disk_usage}
            )
        elif disk_usage > 80:
            health_status["components"]["disk"] = "degraded"
            self.create_alert(
                AlertLevel.WARNING,
                AlertType.SYSTEM,
                f"磁盘使用率较高: {disk_usage:.1f}%",
                {"disk_usage": disk_usage}
            )
        
        # 检查内存使用情况
        memory_usage = health_status["metrics"]["memory_usage"]
        if memory_usage > 90:
            health_status["components"]["memory"] = "unhealthy"
            health_status["status"] = "unhealthy"
            self.create_alert(
                AlertLevel.CRITICAL,
                AlertType.SYSTEM,
                f"内存使用率过高: {memory_usage:.1f}%",
                {"memory_usage": memory_usage}
            )
        elif memory_usage > 80:
            health_status["components"]["memory"] = "degraded"
            self.create_alert(
                AlertLevel.WARNING,
                AlertType.SYSTEM,
                f"内存使用率较高: {memory_usage:.1f}%",
                {"memory_usage": memory_usage}
            )
        
        return health_status
    
    def _get_disk_usage(self) -> float:
        """获取磁盘使用率
        
        Returns:
            float: 磁盘使用率（百分比）
        """
        try:
            if os.name == 'nt':  # Windows
                import ctypes
                class DISKSPACE_INFORMATION(ctypes.Structure):
                    _fields_ = [
                        ('TotalNumberOfFreeBytes', ctypes.c_ulonglong),
                        ('TotalNumberOfBytes', ctypes.c_ulonglong)
                    ]
                
                diskspace = DISKSPACE_INFORMATION()
                drive = os.getcwd().split(':')[0] + ':\\'
                ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                    ctypes.c_wchar_p(drive),
                    ctypes.byref(diskspace),
                    ctypes.byref(diskspace),
                    None
                )
                total = diskspace.TotalNumberOfBytes
                free = diskspace.TotalNumberOfFreeBytes
                usage = (total - free) / total * 100
                return usage
            else:  # Unix-like
                statvfs = os.statvfs('/')
                total = statvfs.f_frsize * statvfs.f_blocks
                free = statvfs.f_frsize * statvfs.f_bavail
                usage = (total - free) / total * 100
                return usage
        except Exception as e:
            print(f"获取磁盘使用率失败: {e}")
            return 0.0
    
    def _get_memory_usage(self) -> float:
        """获取内存使用率
        
        Returns:
            float: 内存使用率（百分比）
        """
        try:
            if os.name == 'nt':  # Windows
                import psutil
                memory = psutil.virtual_memory()
                return memory.percent
            else:  # Unix-like
                with open('/proc/meminfo', 'r') as f:
                    meminfo = {}
                    for line in f:
                        parts = line.split(':')
                        if len(parts) == 2:
                            key = parts[0].strip()
                            value = int(parts[1].strip().split()[0])
                            meminfo[key] = value
                    total = meminfo.get('MemTotal', 0)
                    free = meminfo.get('MemFree', 0) + meminfo.get('Buffers', 0) + meminfo.get('Cached', 0)
                    usage = (total - free) / total * 100
                    return usage
        except Exception as e:
            print(f"获取内存使用率失败: {e}")
            return 0.0
    
    def _get_uptime(self) -> float:
        """获取系统运行时间
        
        Returns:
            float: 系统运行时间（秒）
        """
        try:
            if os.name == 'nt':  # Windows
                import psutil
                return time.time() - psutil.boot_time()
            else:  # Unix-like
                with open('/proc/uptime', 'r') as f:
                    uptime_seconds = float(f.readline().split()[0])
                    return uptime_seconds
        except Exception as e:
            print(f"获取系统运行时间失败: {e}")
            return 0.0

# 全局监控管理器实例
monitoring_manager = MonitoringManager()

if __name__ == "__main__":
    """测试监控告警系统"""
    # 创建测试告警
    alert1 = monitoring_manager.create_alert(
        AlertLevel.WARNING,
        AlertType.NETWORK,
        "网络连接不稳定",
        {"service": "polymarket_api", "status": "unstable"}
    )
    
    alert2 = monitoring_manager.create_alert(
        AlertLevel.ERROR,
        AlertType.ORDER,
        "订单执行失败",
        {"order_id": "12345", "error": "insufficient_liquidity"}
    )
    
    # 打印告警摘要
    print("\n告警摘要:")
    print(json.dumps(monitoring_manager.get_alert_summary(), indent=2, ensure_ascii=False))
    
    # 检查系统健康状态
    print("\n系统健康状态:")
    health_status = monitoring_manager.check_system_health()
    print(json.dumps(health_status, indent=2, ensure_ascii=False))
    
    # 解决告警
    print("\n解决告警:")
    monitoring_manager.resolve_alert(alert1.alert_id)
    
    # 打印更新后的告警摘要
    print("\n更新后的告警摘要:")
    print(json.dumps(monitoring_manager.get_alert_summary(), indent=2, ensure_ascii=False))
