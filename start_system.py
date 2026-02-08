#!/usr/bin/env python3
"""
启动脚本：启动交易系统
"""

import subprocess
import time
import sys

def main():
    print("=== 启动交易系统 ===")
    print("1. 启动交易系统...")
    print("2. 启动仪表盘...")
    print("")
    print("交易系统将在这个终端运行")
    print("仪表盘将在浏览器中打开: http://localhost:8501")
    print("")
    print("按 Ctrl+C 停止整个系统")
    print("")
    
    # 启动交易系统
    try:
        # 直接运行main.py，它会同时启动交易系统和仪表盘
        subprocess.run([sys.executable, "main.py", "--no-input"])
    except KeyboardInterrupt:
        print("\n系统已停止")

if __name__ == "__main__":
    main()
