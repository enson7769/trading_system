import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("Testing imports...")
try:
    from core.models import Order
    print("✓ Successfully imported Order from core.models")
except Exception as e:
    print(f"✗ Failed to import Order: {e}")

try:
    from engine.liquidity_analyzer import LiquidityAnalyzer
    print("✓ Successfully imported LiquidityAnalyzer from engine.liquidity_analyzer")
except Exception as e:
    print(f"✗ Failed to import LiquidityAnalyzer: {e}")

try:
    from engine.event_recorder import EventRecorder
    print("✓ Successfully imported EventRecorder from engine.event_recorder")
except Exception as e:
    print(f"✗ Failed to import EventRecorder: {e}")

try:
    from engine.large_order_monitor import LargeOrderMonitor
    print("✓ Successfully imported LargeOrderMonitor from engine.large_order_monitor")
except Exception as e:
    print(f"✗ Failed to import LargeOrderMonitor: {e}")

try:
    from utils.logger import logger
    print("✓ Successfully imported logger from utils.logger")
except Exception as e:
    print(f"✗ Failed to import logger: {e}")

print("Import test completed!")