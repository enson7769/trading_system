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
from gateways.binance_gateway import BinanceGateway
from engine.execution_engine import ExecutionEngine
from security.credential_manager import CredentialManager
from dashboard.data_service import data_service
from config.config import config
from utils.logger import logger

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-input", action="store_true", help="Use only environment variables")
    parser.add_argument("--no-dashboard", action="store_true", help="Skip starting the monitoring dashboard")
    args = parser.parse_args()

    cred_mgr = CredentialManager()
    acc_mgr = AccountManager()
    
    # Load account configurations from config
    # Main account (Polymarket)
    account_config = config.get_account_config('main_account')
    acc_mgr.add_account(
        "main_account", 
        account_config.get('gateway', 'polymarket'), 
        account_config.get('initial_balances', {"USDC": 10000})
    )
    
    # Binance account
    binance_account_config = config.get_account_config('binance_account')
    acc_mgr.add_account(
        "binance_account", 
        binance_account_config.get('gateway', 'binance'), 
        binance_account_config.get('initial_balances', {"USDC": 10000, "BTC": 1.0, "ETH": 10.0})
    )

    # Load gateway configurations from config
    # Polymarket gateway
    gateway_config = config.get_gateway_config('polymarket')
    poly_gw = PolymarketGateway(
        gateway_config.get('rpc_url', 'https://polygon-rpc.com/'), 
        cred_mgr, 
        mock=gateway_config.get('mock', True)
    )
    poly_gw.no_input = args.no_input
    poly_gw.connect()
    
    # Binance gateway
    binance_config = config.get_gateway_config('binance')
    binance_gw = BinanceGateway(
        cred_mgr, 
        mock=binance_config.get('mock', True)
    )
    binance_gw.no_input = args.no_input
    binance_gw.connect()

    engine = ExecutionEngine(acc_mgr, {"polymarket": poly_gw, "binance": binance_gw})
    
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
    
    # Test 7: Binance gateway functionality
    logger.info("\n=== Test 7: Binance gateway functionality ===")
    try:
        # Test Binance account balance
        binance_balance = binance_gw.get_account_balance()
        logger.info(f"Binance account balance: {binance_balance}")
        
        # Test specific coin balance
        usdc_balance = binance_gw.get_account_balance('USDC')
        logger.info(f"Binance USDC balance: {usdc_balance}")
        
        # Test deposit history
        deposit_history = binance_gw.deposit_history('USDC')
        logger.info(f"Binance deposit history (USDC): {deposit_history}")
        
        # Test withdraw history
        withdraw_history = binance_gw.withdraw_history('USDC')
        logger.info(f"Binance withdraw history (USDC): {withdraw_history}")
        
        # Test withdrawal (simulated)
        withdraw_result = binance_gw.withdraw(
            coin='USDC',
            amount=100.0,
            address='0xWithdrawAddress12345678901234567890123456789012',
            network='BSC'
        )
        logger.info(f"Binance withdrawal result: {withdraw_result}")
        
    except Exception as e:
        logger.error(f"Error testing Binance gateway: {e}")
    
    logger.info("\n=== Test Results ===")
    logger.info("1. High probability trading: Should be accepted")
    logger.info("2. Medium probability trading: Should be rejected (below 90%)")
    logger.info("3. Large order monitoring: Should record the 150-unit order")
    logger.info("4. Event data recording: Should record CPI data")
    logger.info("5. Liquidity analysis: Should provide analysis results")
    logger.info("6. Large orders summary: Should show summary data")
    logger.info("7. Binance gateway: Should show balance and transaction history")
    
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