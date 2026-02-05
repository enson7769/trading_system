import streamlit as st
import pandas as pd
from datetime import datetime
from typing import Dict, Any

class OrderStatusPage:
    def __init__(self, dashboard):
        """Initialize order status page"""
        self.dashboard = dashboard
    
    def render(self, page_size: int):
        """Render order status page"""
        st.header('订单状态')
        order_stats = self.dashboard.get_order_stats()
        
        # 使用列布局显示指标
        col1, col2, col3, col4 = st.columns(4)
        col1.metric('总订单数', order_stats['total_orders'])
        col2.metric('已成交', order_stats['filled_orders'])
        col3.metric('待处理', order_stats['pending_orders'])
        col4.metric('已拒绝', order_stats['rejected_orders'])
        
        st.metric('总订单规模', f"{order_stats['total_size']:.2f}")
        
        # 订单表格（带分页）
        st.subheader('订单')
        
        # 获取订单数据
        current_page = 1
        df_orders = self.dashboard._get_order_data(current_page, page_size)
        
        # 显示订单表格
        if not df_orders.empty:
            # 使用改进的选项显示数据框
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
            # 创建空的DataFrame以显示表头
            empty_df = pd.DataFrame(columns=[
                'Order ID', 'Instrument', 'Side', 'Type', 'Quantity', 
                'Price', 'Status', 'Filled Qty', 'Gateway ID', 'Timestamp'
            ])
            st.dataframe(
                empty_df,
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
            st.info('无订单数据可用。启动交易系统以查看订单。')
