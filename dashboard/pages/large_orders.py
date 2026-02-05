import streamlit as st
import pandas as pd
from datetime import datetime

class LargeOrdersPage:
    def __init__(self, dashboard):
        """Initialize large orders page"""
        self.dashboard = dashboard
    
    def render(self, page_size: int):
        """Render large orders page"""
        st.header('大额订单')
        
        # 获取大额订单数据
        current_large_order_page = 1
        df_large_orders = self.dashboard._get_large_order_data(current_large_order_page, page_size)
        
        if not df_large_orders.empty:
            # 使用改进的选项显示数据框
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
            # 创建空的DataFrame以显示表头
            empty_df = pd.DataFrame(columns=['Timestamp', 'Symbol', 'Side', 'Quantity', 'Price', 'Account'])
            st.dataframe(
                empty_df,
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
            st.info('无大额订单数据可用。启动交易系统以查看大额订单。')
