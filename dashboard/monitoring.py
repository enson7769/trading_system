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

class MonitoringDashboard:
    def __init__(self):
        """Initialize monitoring dashboard with performance optimizations"""
        self._cache: Dict[str, Dict] = {}
        self._cache_expiry: Dict[str, float] = {}
        self._cache_ttl = 5  # Cache time-to-live in seconds (reduced for real-time data)
    
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
        """Run the dashboard with real-time updates from backend"""
        st.title('交易系统监控仪表盘')
        
        # Initialize session state for real-time data
        if 'last_refresh' not in st.session_state:
            st.session_state.last_refresh = datetime.now()
        
        # Sidebar for controls
        with st.sidebar:
            st.header('仪表盘控制')
            refresh_interval = st.slider('刷新间隔 (秒)', 1, 60, 5)
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
            
            # Auto-refresh setup
            st.info(f'仪表盘将每 {refresh_interval} 秒刷新一次')
        
        # Create placeholders for dynamic content
        status_section = st.empty()
        order_section = st.empty()
        liquidity_section = st.empty()
        event_section = st.empty()
        large_order_section = st.empty()
        system_section = st.empty()
        
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
            
            # Update last refresh time
            st.session_state.last_refresh = datetime.now()
        
        # Initial refresh
        refresh_all_data()
        
        # Add a refresh button for manual updates
        if st.button('刷新数据'):
            refresh_all_data()
        
        # Auto-refresh using Streamlit's rerun with timeout
        import time
        st.empty()  # Placeholder for refresh indicator
        time.sleep(refresh_interval)
        st.rerun()

if __name__ == '__main__':
    dashboard = MonitoringDashboard()
    dashboard.run_dashboard()
