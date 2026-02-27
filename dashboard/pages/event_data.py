import streamlit as st
import pandas as pd
from datetime import datetime

class EventDataPage:
    def __init__(self, dashboard):
        """Initialize event data page"""
        self.dashboard = dashboard
    
    def render(self, page_size: int):
        """Render event data page"""
        st.header('事件数据')
        
        # 获取事件数据
        current_event_page = 1
        df_events = self.dashboard._get_event_data(current_event_page, page_size)
        
        if not df_events.empty:
            # 使用改进的选项显示数据框
            st.dataframe(
                df_events,
                width="100%",
                hide_index=True,
                column_config={
                    'Event Name': st.column_config.TextColumn('事件名称', width='small'),
                    'Timestamp': st.column_config.DatetimeColumn('时间戳'),
                    'Data': st.column_config.TextColumn('数据', width='large')
                }
            )
        else:
            # 创建空的DataFrame以显示表头
            empty_df = pd.DataFrame(columns=['Event Name', 'Timestamp', 'Data'])
            st.dataframe(
                empty_df,
                width="100%",
                hide_index=True,
                column_config={
                    'Event Name': st.column_config.TextColumn('事件名称', width='small'),
                    'Timestamp': st.column_config.DatetimeColumn('时间戳'),
                    'Data': st.column_config.TextColumn('数据', width='large')
                }
            )
            st.info('无事件数据可用。启动交易系统以查看事件。')
