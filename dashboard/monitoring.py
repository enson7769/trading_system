import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from core.models import Order
from engine.liquidity_analyzer import LiquidityAnalyzer
from engine.event_recorder import EventRecorder
from engine.large_order_monitor import LargeOrderMonitor
from utils.logger import logger
import time

class MonitoringDashboard:
    def __init__(self):
        """Initialize monitoring dashboard with performance optimizations"""
        self.orders: List[Order] = []
        self.liquidity_analyzer = LiquidityAnalyzer()
        self.event_recorder = EventRecorder()
        self.large_order_monitor = LargeOrderMonitor()
        self.event_data: List[Dict] = []
        self.large_orders: List[Dict] = []
        self._cache: Dict[str, Dict] = {}
        self._cache_expiry: Dict[str, float] = {}
        self._cache_ttl = 60  # Cache time-to-live in seconds
    
    def add_order(self, order: Order):
        """Add order with cache invalidation"""
        self.orders.append(order)
        self._invalidate_cache('order_stats')
        self._invalidate_cache('order_table')
    
    def add_event_data(self, event_name: str, timestamp: datetime, data: Dict):
        """Add event data with cache invalidation"""
        self.event_data.append({
            'event_name': event_name,
            'timestamp': timestamp,
            'data': data
        })
        self._invalidate_cache('event_table')
    
    def add_large_order(self, order_info: Dict):
        """Add large order with cache invalidation"""
        self.large_orders.append(order_info)
        self._invalidate_cache('large_order_table')
    
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
        """Get order statistics with caching"""
        def compute_order_stats():
            total_orders = len(self.orders)
            filled_orders = len([o for o in self.orders if o.status == 'filled'])
            pending_orders = len([o for o in self.orders if o.status == 'pending'])
            rejected_orders = len([o for o in self.orders if o.status == 'rejected'])
            
            total_size = sum([float(o.quantity) for o in self.orders])
            
            return {
                'total_orders': total_orders,
                'filled_orders': filled_orders,
                'pending_orders': pending_orders,
                'rejected_orders': rejected_orders,
                'total_size': total_size
            }
        
        return self._get_cached('order_stats', compute_order_stats)
    
    def _get_order_data(self, page: int = 1, page_size: int = 100) -> pd.DataFrame:
        """Get order data with pagination"""
        def compute_order_data():
            order_data = []
            for order in self.orders:
                order_data.append({
                    'Order ID': order.order_id,
                    'Instrument': order.instrument.symbol,
                    'Side': order.side.value,
                    'Type': order.type.value,
                    'Quantity': float(order.quantity),
                    'Price': float(order.price) if order.price else None,
                    'Status': order.status.value,
                    'Filled Qty': float(order.filled_qty),
                    'Gateway ID': order.gateway_order_id,
                    'Timestamp': datetime.now()  # Placeholder for actual timestamp
                })
            return pd.DataFrame(order_data)
        
        df_orders = self._get_cached('order_table', compute_order_data)
        
        # Apply pagination
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        return df_orders.iloc[start_idx:end_idx]
    
    def _get_event_data(self, page: int = 1, page_size: int = 50) -> pd.DataFrame:
        """Get event data with pagination"""
        def compute_event_data():
            event_data = []
            for event in self.event_data:
                event_data.append({
                    'Event Name': event['event_name'],
                    'Timestamp': event['timestamp'],
                    'Data': str(event['data'])
                })
            return pd.DataFrame(event_data)
        
        df_events = self._get_cached('event_table', compute_event_data)
        
        # Apply pagination
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        return df_events.iloc[start_idx:end_idx]
    
    def _get_large_order_data(self, page: int = 1, page_size: int = 50) -> pd.DataFrame:
        """Get large order data with pagination"""
        def compute_large_order_data():
            large_order_data = []
            for order in self.large_orders:
                large_order_data.append({
                    'Timestamp': order.get('timestamp'),
                    'Symbol': order.get('symbol'),
                    'Side': order.get('side'),
                    'Quantity': order.get('quantity'),
                    'Price': order.get('price'),
                    'Account': order.get('account_id')
                })
            return pd.DataFrame(large_order_data)
        
        df_large_orders = self._get_cached('large_order_table', compute_large_order_data)
        
        # Apply pagination
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        return df_large_orders.iloc[start_idx:end_idx]
    
    def run_dashboard(self):
        """Run the dashboard with performance optimizations"""
        st.title('Trading System Monitoring Dashboard')
        
        # Sidebar for controls
        with st.sidebar:
            st.header('Dashboard Controls')
            refresh_interval = st.slider('Refresh Interval (seconds)', 5, 60, 15)
            page_size = st.selectbox('Items per page', [50, 100, 200], index=1)
            
            # Auto-refresh setup
            st.info(f'Dashboard will refresh every {refresh_interval} seconds')
        
        # Order Status Section
        st.header('Order Status')
        order_stats = self.get_order_stats()
        
        # Use columns for metrics with improved layout
        col1, col2, col3, col4 = st.columns(4)
        col1.metric('Total Orders', order_stats['total_orders'])
        col2.metric('Filled', order_stats['filled_orders'])
        col3.metric('Pending', order_stats['pending_orders'])
        col4.metric('Rejected', order_stats['rejected_orders'])
        
        st.metric('Total Order Size', f"{order_stats['total_size']:.2f}")
        
        # Order Table with pagination
        if self.orders:
            st.subheader('Orders')
            
            # Pagination controls
            total_pages = (len(self.orders) + page_size - 1) // page_size
            current_page = st.number_input('Page', min_value=1, max_value=total_pages, value=1)
            
            # Get paginated data
            df_orders = self._get_order_data(current_page, page_size)
            
            # Use st.dataframe with improved options
            st.dataframe(
                df_orders,
                use_container_width=True,
                hide_index=True,
                column_config={
                    'Order ID': st.column_config.TextColumn(width='small'),
                    'Instrument': st.column_config.TextColumn(width='small'),
                    'Quantity': st.column_config.NumberColumn(format='%.2f'),
                    'Price': st.column_config.NumberColumn(format='%.4f'),
                    'Filled Qty': st.column_config.NumberColumn(format='%.2f')
                }
            )
            
            # Pagination info
            st.caption(f'Page {current_page} of {total_pages}')
        
        # Liquidity Section with caching
        st.header('Market Liquidity')
        
        # Add liquidity analysis form
        with st.expander('Liquidity Analysis'):
            symbol = st.text_input('Symbol', '0x1234...abcd')
            size = st.number_input('Order Size', min_value=1.0, max_value=1000.0, value=100.0)
            
            if st.button('Analyze Liquidity'):
                with st.spinner('Analyzing liquidity...'):
                    analysis = self.liquidity_analyzer.analyze_liquidity(
                        symbol, 
                        order.size if 'order' in locals() else float(size)
                    )
                    
                    # Display analysis results
                    col1, col2, col3 = st.columns(3)
                    col1.metric('Liquidity Rating', analysis['liquidity_rating'])
                    col2.metric('Slippage Estimate', f"{analysis['slippage_estimate']:.4f}")
                    col3.metric('Confidence', analysis['confidence'])
                    
                    st.info(analysis['message'])
        
        # Event Data Section with pagination
        st.header('Event Data')
        if self.event_data:
            # Pagination controls
            total_event_pages = (len(self.event_data) + page_size - 1) // page_size
            current_event_page = st.number_input('Event Page', min_value=1, max_value=total_event_pages, value=1)
            
            # Get paginated data
            df_events = self._get_event_data(current_event_page, page_size)
            
            # Use st.dataframe with improved options
            st.dataframe(
                df_events,
                use_container_width=True,
                hide_index=True,
                column_config={
                    'Event Name': st.column_config.TextColumn(width='small'),
                    'Timestamp': st.column_config.DatetimeColumn(),
                    'Data': st.column_config.TextColumn(width='large')
                }
            )
            
            # Pagination info
            st.caption(f'Page {current_event_page} of {total_event_pages}')
        
        # Large Orders Section with pagination
        st.header('Large Orders')
        if self.large_orders:
            # Pagination controls
            total_large_order_pages = (len(self.large_orders) + page_size - 1) // page_size
            current_large_order_page = st.number_input('Large Order Page', min_value=1, max_value=total_large_order_pages, value=1)
            
            # Get paginated data
            df_large_orders = self._get_large_order_data(current_large_order_page, page_size)
            
            # Use st.dataframe with improved options
            st.dataframe(
                df_large_orders,
                use_container_width=True,
                hide_index=True,
                column_config={
                    'Timestamp': st.column_config.DatetimeColumn(),
                    'Symbol': st.column_config.TextColumn(width='small'),
                    'Quantity': st.column_config.NumberColumn(format='%.2f'),
                    'Price': st.column_config.NumberColumn(format='%.4f')
                }
            )
            
            # Pagination info
            st.caption(f'Page {current_large_order_page} of {total_large_order_pages}')
        
        # System Status Section
        st.header('System Status')
        system_status = {
            'Orders in Memory': len(self.orders),
            'Events Recorded': len(self.event_data),
            'Large Orders Detected': len(self.large_orders),
            'Last Updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        for key, value in system_status.items():
            st.metric(key, value)
        
        # Add auto-refresh
        st.empty()  # Placeholder for auto-refresh indicator
        time.sleep(refresh_interval)
        st.rerun()

if __name__ == '__main__':
    dashboard = MonitoringDashboard()
    dashboard.run_dashboard()
