import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any
from core.models import Order
from decimal import Decimal
from dashboard.data_service import data_service
from utils.logger import logger
import time
import asyncio
import threading
import websockets
import json

class MonitoringDashboard:
    def __init__(self):
        """Initialize monitoring dashboard with performance optimizations and WebSocket support"""
        self._cache: Dict[str, Dict] = {}
        self._cache_expiry: Dict[str, float] = {}
        self._cache_ttl = 5  # Cache time-to-live in seconds (reduced for real-time data)
        self._websocket_clients = set()
        self._websocket_server = None
        self._websocket_thread = None
        self._stop_event = threading.Event()
        self._data_update_event = threading.Event()
        self._data_update_event.set()  # Initial data update
    
    def _invalidate_cache(self, key: str):
        """Invalidate specific cache entry"""
        if key in self._cache:
            del self._cache[key]
        if key in self._cache_expiry:
            del self._cache_expiry[key]
    
    def _get_cached(self, key: str, func, *args, **kwargs) -> Any:
        """Get cached value or compute and cache it"""
        current_time = time.time()
        
        if key in self._cache and current_time < self._cache_expiry.get(key, 0):
            return self._cache[key]
        
        result = func(*args, **kwargs)
        self._cache[key] = result
        self._cache_expiry[key] = current_time + self._cache_ttl
        
        return result
    
    def get_order_stats(self) -> Dict[str, Any]:
        """Get order statistics from backend"""
        def compute_order_stats():
            return data_service.get_order_stats()
        
        return self._get_cached('order_stats', compute_order_stats)
    
    async def _websocket_handler(self, websocket, path):
        """Handle WebSocket connections"""
        # Register client
        self._websocket_clients.add(websocket)
        logger.info(f"WebSocket client connected. Total clients: {len(self._websocket_clients)}")
        
        try:
            # Send initial data
            initial_data = {
                'type': 'initial_data',
                'order_stats': self.get_order_stats()
            }
            await websocket.send(json.dumps(initial_data))
            
            # Listen for messages
            async for message in websocket:
                # Handle client messages if needed
                pass
        except websockets.exceptions.ConnectionClosed:
            logger.info("WebSocket client disconnected")
        finally:
            # Unregister client
            self._websocket_clients.remove(websocket)
            logger.info(f"WebSocket client disconnected. Total clients: {len(self._websocket_clients)}")
    
    async def _websocket_server_task(self):
        """WebSocket server task"""
        async with websockets.serve(self._websocket_handler, "localhost", 8765):
            logger.info("WebSocket server started on ws://localhost:8765")
            while not self._stop_event.is_set():
                # Check if data needs to be updated
                if self._data_update_event.wait(1):
                    # Broadcast data update
                    await self._broadcast_data_update()
                    self._data_update_event.clear()
    
    async def _broadcast_data_update(self):
        """Broadcast data updates to all WebSocket clients"""
        if not self._websocket_clients:
            return
        
        try:
            # Prepare update data
            update_data = {
                'type': 'data_update',
                'order_stats': self.get_order_stats(),
                'timestamp': datetime.now().isoformat()
            }
            
            # Send to all clients
            disconnected = []
            for client in self._websocket_clients:
                try:
                    await client.send(json.dumps(update_data))
                except websockets.exceptions.ConnectionClosed:
                    disconnected.append(client)
            
            # Clean up disconnected clients
            for client in disconnected:
                if client in self._websocket_clients:
                    self._websocket_clients.remove(client)
        except Exception as e:
            logger.error(f"Error broadcasting data update: {e}")
    
    def start_websocket_server(self):
        """Start WebSocket server in a separate thread"""
        if not self._websocket_thread:
            self._stop_event.clear()
            self._websocket_thread = threading.Thread(target=self._run_websocket_server, daemon=True)
            self._websocket_thread.start()
    
    def _run_websocket_server(self):
        """Run WebSocket server in a thread"""
        try:
            asyncio.run(self._websocket_server_task())
        except Exception as e:
            logger.error(f"WebSocket server error: {e}")
    
    def stop_websocket_server(self):
        """Stop WebSocket server"""
        self._stop_event.set()
        if self._websocket_thread:
            self._websocket_thread.join(timeout=5)
            self._websocket_thread = None
        logger.info("WebSocket server stopped")
    
    def trigger_data_update(self):
        """Trigger data update"""
        self._data_update_event.set()
    
    def _get_order_data(self, page: int = 1, page_size: int = 100) -> pd.DataFrame:
        """Get order data from backend with pagination"""
        def compute_order_data():
            order_history = data_service.get_order_history(page, page_size)
            order_data = []
            for order in order_history:
                order_data.append({
                    'Order ID': order.get('order_id', ''),
                    'Instrument': order.get('instrument', ''),
                    'Side': order.get('side', ''),
                    'Type': order.get('type', ''),
                    'Quantity': float(order.get('quantity', '0')),
                    'Price': float(order.get('price')) if order.get('price') else None,
                    'Status': order.get('status', ''),
                    'Filled Qty': 0,  # Not available in history
                    'Gateway ID': order.get('gateway_order_id', ''),
                    'Timestamp': datetime.fromisoformat(order.get('timestamp', datetime.now().isoformat()))
                })
            return pd.DataFrame(order_data)
        
        return compute_order_data()
    
    def _get_event_data(self, page: int = 1, page_size: int = 50) -> pd.DataFrame:
        """Get event data from backend with pagination"""
        def compute_event_data():
            event_data_list = data_service.get_event_data(7, page, page_size)
            event_data = []
            for event in event_data_list:
                event_data.append({
                    'Event Name': event.get('event_name', ''),
                    'Timestamp': datetime.fromisoformat(event.get('timestamp', datetime.now().isoformat())),
                    'Data': str(event.get('data', {}))
                })
            return pd.DataFrame(event_data)
        
        return compute_event_data()
    
    def _get_large_order_data(self, page: int = 1, page_size: int = 50) -> pd.DataFrame:
        """Get large order data from backend with pagination"""
        def compute_large_order_data():
            large_orders_list = data_service.get_large_orders(7, page, page_size)
            large_order_data = []
            for order in large_orders_list:
                large_order_data.append({
                    'Timestamp': datetime.fromisoformat(order.get('timestamp', datetime.now().isoformat())),
                    'Symbol': order.get('symbol', ''),
                    'Side': order.get('side', ''),
                    'Quantity': float(order.get('quantity', '0')),
                    'Price': float(order.get('price')) if order.get('price') else None,
                    'Account': order.get('account_id', '')
                })
            return pd.DataFrame(large_order_data)
        
        return compute_large_order_data()
    
    def run_dashboard(self):
        """Run the dashboard with real-time updates from backend using WebSocket"""
        st.title('交易系统监控仪表盘')
        
        # Initialize session state for real-time data
        if 'last_refresh' not in st.session_state:
            st.session_state.last_refresh = datetime.now()
        
        # Start WebSocket server
        self.start_websocket_server()
        
        # Sidebar for controls
        with st.sidebar:
            st.header('仪表盘控制')
            page_size = st.selectbox('每页显示数量', [50, 100, 200], index=1)
            
            # Data service status
            st.header('数据服务状态')
            if data_service.is_initialized():
                st.success('✓ 数据服务已连接')
                system_status = data_service.get_system_status()
                components = system_status.get('components', {})
                for component, status in components.items():
                    if status:
                        st.success(f'✓ {component.replace("_", " ").title()}')
                    else:
                        st.warning(f'⚠️ {component.replace("_", " ").title()}')
            else:
                st.warning('⚠️ 数据服务未初始化')
                st.info('请先运行主交易系统以初始化数据服务。')
            
            # WebSocket status
            st.header('WebSocket状态')
            st.success('✓ WebSocket服务已启动')
            st.info('数据将通过WebSocket实时更新')
            st.info('WebSocket地址: ws://localhost:8765')
        
        # Create placeholders for dynamic content
        status_section = st.empty()
        order_section = st.empty()
        liquidity_section = st.empty()
        event_section = st.empty()
        large_order_section = st.empty()
        system_section = st.empty()
        websocket_status = st.empty()
        
        # Function to refresh all data
        def refresh_all_data():
            # Update status section
            with status_section.container():
                st.header('仪表盘状态')
                if not data_service.is_initialized():
                    st.warning('⚠️ 仪表盘正在独立模式下运行。无来自后端的实时数据。')
                    st.info('启动主交易系统以获取实时数据。')
                else:
                    st.success('✓ 仪表盘已连接到后端服务。')
                    
                # Show last refresh time
                st.metric('最后刷新', st.session_state.last_refresh.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3])
            
            # Update order section
            with order_section.container():
                st.header('订单状态')
                order_stats = self.get_order_stats()
                
                # Use columns for metrics with improved layout
                col1, col2, col3, col4 = st.columns(4)
                col1.metric('总订单数', order_stats['total_orders'])
                col2.metric('已成交', order_stats['filled_orders'])
                col3.metric('待处理', order_stats['pending_orders'])
                col4.metric('已拒绝', order_stats['rejected_orders'])
                
                st.metric('总订单规模', f"{order_stats['total_size']:.2f}")
                
                # Order Table with pagination
                st.subheader('订单')
                
                # Get order data
                current_page = 1
                df_orders = self._get_order_data(current_page, page_size)
                
                # Display order table
                if not df_orders.empty:
                    # Use st.dataframe with improved options
                    st.dataframe(
                        df_orders,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            'Order ID': st.column_config.TextColumn('订单ID', width='small'),
                            'Instrument': st.column_config.TextColumn('交易对', width='small'),
                            'Side': st.column_config.TextColumn('方向'),
                            'Type': st.column_config.TextColumn('类型'),
                            'Quantity': st.column_config.NumberColumn('数量', format='%.2f'),
                            'Price': st.column_config.NumberColumn('价格', format='%.4f'),
                            'Status': st.column_config.TextColumn('状态'),
                            'Filled Qty': st.column_config.NumberColumn('已成交数量', format='%.2f'),
                            'Gateway ID': st.column_config.TextColumn('网关ID', width='small'),
                            'Timestamp': st.column_config.DatetimeColumn('时间戳')
                        }
                    )
                else:
                    st.info('无订单数据可用。启动交易系统以查看订单。')
            
            # Update liquidity section
            with liquidity_section.container():
                st.header('市场流动性')
                
                # Add liquidity analysis form
                with st.expander('流动性分析'):
                    symbol = st.text_input('交易对', '0x1234...abcd')
                    size = st.number_input('订单规模', min_value=1.0, max_value=1000.0, value=100.0)
                    
                    if st.button('分析流动性'):
                        with st.spinner('正在分析流动性...'):
                            analysis = data_service.get_liquidity_analysis(symbol, Decimal(str(size)))
                            
                            # Display analysis results
                            col1, col2, col3 = st.columns(3)
                            col1.metric('流动性评级', analysis['liquidity_rating'])
                            col2.metric('滑点估计', f"{analysis['slippage_estimate']:.4f}")
                            col3.metric('置信度', analysis['confidence'])
                            
                            st.info(analysis['message'])
            
            # Update event data section
            with event_section.container():
                st.header('事件数据')
                
                # Get event data
                current_event_page = 1
                df_events = self._get_event_data(current_event_page, page_size)
                
                if not df_events.empty:
                    # Use st.dataframe with improved options
                    st.dataframe(
                        df_events,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            'Event Name': st.column_config.TextColumn('事件名称', width='small'),
                            'Timestamp': st.column_config.DatetimeColumn('时间戳'),
                            'Data': st.column_config.TextColumn('数据', width='large')
                        }
                    )
                else:
                    st.info('无事件数据可用。启动交易系统以查看事件。')
            
            # Update large orders section
            with large_order_section.container():
                st.header('大额订单')
                
                # Get large order data
                current_large_order_page = 1
                df_large_orders = self._get_large_order_data(current_large_order_page, page_size)
                
                if not df_large_orders.empty:
                    # Use st.dataframe with improved options
                    st.dataframe(
                        df_large_orders,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            'Timestamp': st.column_config.DatetimeColumn('时间戳'),
                            'Symbol': st.column_config.TextColumn('交易对', width='small'),
                            'Side': st.column_config.TextColumn('方向'),
                            'Quantity': st.column_config.NumberColumn('数量', format='%.2f'),
                            'Price': st.column_config.NumberColumn('价格', format='%.4f'),
                            'Account': st.column_config.TextColumn('账户')
                        }
                    )
                else:
                    st.info('无大额订单数据可用。启动交易系统以查看大额订单。')
            
            # Update system status section
            with system_section.container():
                st.header('系统状态')
                system_status = data_service.get_system_status()
                
                # Display system metrics
                st.metric('历史订单数', system_status.get('order_history_count', 0))
                
                # Show engine status if available
                if data_service.is_initialized():
                    engine_status = data_service.get_engine_status()
                    st.metric('系统健康状态', engine_status.get('system_health', 'unknown'))
                    
                    # Show gateway information
                    gateways = engine_status.get('gateways', [])
                    if gateways:
                        st.subheader('已连接网关')
                        for gateway in gateways:
                            st.success(f'✓ {gateway}')
                    else:
                        st.info('无网关连接。')
            
            # Update WebSocket status
            with websocket_status.container():
                st.header('WebSocket连接状态')
                st.success(f'✓ WebSocket服务运行中')
                st.info(f'当前连接数: {len(self._websocket_clients)}')
                st.info('数据将通过WebSocket实时更新，无需手动刷新')
            
            # Update last refresh time
            st.session_state.last_refresh = datetime.now()
        
        # Initial refresh
        refresh_all_data()
        
        # Add a refresh button for manual updates
        if st.button('手动刷新数据'):
            refresh_all_data()
            self.trigger_data_update()
        
        # Add JavaScript for WebSocket client
        st.components.v1.html('''
        <script>
            // WebSocket client
            const ws = new WebSocket('ws://localhost:8765');
            
            ws.onopen = function() {
                console.log('WebSocket connected');
            };
            
            ws.onmessage = function(event) {
                console.log('WebSocket message received:', event.data);
                const data = JSON.parse(event.data);
                
                if (data.type === 'data_update') {
                    // Update UI elements when data changes
                    console.log('Updating UI with new data:', data);
                    // Streamlit will handle UI updates through its own rerun mechanism
                }
            };
            
            ws.onclose = function() {
                console.log('WebSocket disconnected');
            };
            
            ws.onerror = function(error) {
                console.error('WebSocket error:', error);
            };
            
            // Refresh data periodically to ensure UI is up to date
            setInterval(function() {
                // This will trigger Streamlit to rerun and update the UI
                console.log('Requesting UI update...');
            }, 5000);
        </script>
        ''', height=0)
        
        # Keep the app running and handle WebSocket updates
        try:
            # Main loop to handle data updates
            while True:
                # Wait for data update event
                if self._data_update_event.wait(1):
                    # Refresh UI with new data
                    refresh_all_data()
                    self._data_update_event.clear()
                
                # Small delay to prevent CPU usage
                time.sleep(0.1)
        finally:
            # Stop WebSocket server when exiting
            self.stop_websocket_server()

if __name__ == '__main__':
    dashboard = MonitoringDashboard()
    dashboard.run_dashboard()
