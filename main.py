import sys
import os
import threading
import time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import argparse
from decimal import Decimal
from core.models import Instrument
from account.account_manager import AccountManager
from gateways.polymarket_gateway import PolymarketGateway
from engine.execution_engine import ExecutionEngine
from security.credential_manager import CredentialManager
from dashboard.data_service import data_service
from utils.logger import logger

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-input", action="store_true", help="Use only environment variables")
    parser.add_argument("--no-dashboard", action="store_true", help="Skip starting the monitoring dashboard")
    args = parser.parse_args()

    cred_mgr = CredentialManager()
    acc_mgr = AccountManager()
    acc_mgr.add_account("main_account", "polymarket", {"USDC": 10000})

    poly_gw = PolymarketGateway("https://polygon-rpc.com/", cred_mgr, mock=True)
    poly_gw.no_input = args.no_input
    poly_gw.connect()

    engine = ExecutionEngine(acc_mgr, {"polymarket": poly_gw})
    
    # Initialize data service for dashboard
    data_service.initialize(engine)
    logger.info("Data service initialized for dashboard")
    
    # Start dashboard in a separate thread if not disabled
    if not args.no_dashboard:
        logger.info("Starting monitoring dashboard...")
        dashboard_thread = threading.Thread(target=start_dashboard, daemon=True)
        dashboard_thread.start()
        # Give dashboard time to start
        time.sleep(2)

    inst = Instrument(
        symbol="0x1234...abcd",
        base_asset="USDC",
        quote_asset="USDC",
        min_order_size=Decimal('1'),
        tick_size=Decimal('0.01'),
        gateway_name="polymarket"
    )

    from core.models import Order
    from core.enums import OrderSide, OrderType
    
    # Test 1: Probability-based trading (high probability case)
    logger.info("=== Test 1: High probability trading ===")
    market_probabilities_high = {
        'no_change': Decimal('60'),
        '25bps_decrease': Decimal('38')  # Total: 98 >= 97
    }
    
    order1 = Order(
        order_id="test_order_1",
        instrument=inst,
        side=OrderSide.BUY,
        type=OrderType.MARKET,
        quantity=Decimal('5'),
        account_id="main_account"
    )
    
    engine.submit_order(order1, market_probabilities_high)
    
    # Test 2: Probability-based trading (medium probability case)
    logger.info("\n=== Test 2: Medium probability trading ===")
    market_probabilities_medium = {
        'no_change': Decimal('50'),
        '25bps_decrease': Decimal('35')  # Total: 85 < 90
    }
    
    order2 = Order(
        order_id="test_order_2",
        instrument=inst,
        side=OrderSide.BUY,
        type=OrderType.MARKET,
        quantity=Decimal('5'),
        account_id="main_account"
    )
    
    engine.submit_order(order2, market_probabilities_medium)
    
    # Test 3: Large order monitoring
    logger.info("\n=== Test 3: Large order monitoring ===")
    order3 = Order(
        order_id="test_order_3",
        instrument=inst,
        side=OrderSide.BUY,
        type=OrderType.MARKET,
        quantity=Decimal('150'),  # Large order
        account_id="main_account"
    )
    
    engine.submit_order(order3)
    
    # Test 4: Event data recording
    logger.info("\n=== Test 4: Event data recording ===")
    cpi_data = {
        'actual': 3.2,
        'expected': 3.3,
        'previous': 3.4,
        'market_reaction': 'positive'
    }
    engine.record_event_data('cpi', cpi_data)
    
    # Test 5: Liquidity analysis
    logger.info("\n=== Test 5: Liquidity analysis ===")
    liquidity_analysis = engine.get_liquidity_analysis(inst.symbol, Decimal('100'))
    logger.info(f"Liquidity analysis: {liquidity_analysis}")
    
    # Test 6: Large orders summary
    logger.info("\n=== Test 6: Large orders summary ===")
    large_orders_summary = engine.get_large_orders_summary()
    logger.info(f"Large orders summary: {large_orders_summary}")
    
    logger.info("\n=== Test Results ===")
    logger.info("1. High probability trading: Should be accepted")
    logger.info("2. Medium probability trading: Should be rejected (below 90%)")
    logger.info("3. Large order monitoring: Should record the 150-unit order")
    logger.info("4. Event data recording: Should record CPI data")
    logger.info("5. Liquidity analysis: Should provide analysis results")
    logger.info("6. Large orders summary: Should show summary data")
    
    logger.info("\nDemo completed. Check the dashboard for monitoring.")
    
    # Print test completion message to console
    print("\nTest completed successfully! Check logs for details.")
    print("\nMonitoring dashboard is starting...")
    print("Dashboard will be available at: http://localhost:8501")

# Function to start Streamlit dashboard
def start_dashboard():
    """Start Streamlit dashboard in a separate thread"""
    import subprocess
    import sys
    
    try:
        # Start Streamlit dashboard
        streamlit_cmd = [
            sys.executable,
            "-m", "streamlit",
            "run", "dashboard/monitoring.py",
            "--server.headless", "true",
            "--server.port", "8501"
        ]
        
        logger.info(f"Starting dashboard with command: {' '.join(streamlit_cmd)}")
        
        # Run Streamlit in the background
        process = subprocess.Popen(
            streamlit_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        
        # Monitor the process output
        for line in iter(process.stdout.readline, ''):
            if "You can now view your Streamlit app in your browser" in line:
                logger.info("Dashboard started successfully!")
                print("\nDashboard started successfully!")
                print("   Local URL: http://localhost:8501")
            elif "Error" in line or "Exception" in line:
                logger.error(f"Dashboard error: {line.strip()}")
            
    except Exception as e:
        logger.error(f"Failed to start dashboard: {e}")
        print(f"\nFailed to start dashboard: {e}")

if __name__ == "__main__":
    main()