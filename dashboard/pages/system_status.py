import streamlit as st
from dashboard.data_service import data_service

class SystemStatusPage:
    def __init__(self, dashboard):
        """Initialize system status page"""
        self.dashboard = dashboard
    
    def render(self):
        """Render system status page"""
        st.header('系统状态')
        system_status = data_service.get_system_status()
        
        # 显示系统指标
        st.metric('历史订单数', system_status.get('order_history_count', 0))
        
        # 如果可用，显示引擎状态
        if data_service.is_initialized():
            engine_status = data_service.get_engine_status()
            st.metric('系统健康状态', engine_status.get('system_health', 'unknown'))
            
            # 显示网关信息
            gateways = engine_status.get('gateways', [])
            if gateways:
                st.subheader('已连接网关')
                for gateway in gateways:
                    st.success(f'{gateway}')
            else:
                st.info('无网关连接。')
