import streamlit as st
from decimal import Decimal
from dashboard.data_service import data_service

class MarketLiquidityPage:
    def __init__(self, dashboard):
        """Initialize market liquidity page"""
        self.dashboard = dashboard
    
    def render(self):
        """Render market liquidity page"""
        st.header('市场流动性')
        
        # 添加流动性分析表单
        with st.expander('流动性分析'):
            symbol = st.text_input('交易对', '0x1234...abcd', key='market_liquidity_symbol')
            size = st.number_input('订单规模', min_value=1.0, max_value=1000.0, value=100.0, key='market_liquidity_size')
            
            if st.button('分析流动性', key='market_liquidity_analyze'):
                with st.spinner('正在分析流动性...'):
                    analysis = data_service.get_liquidity_analysis(symbol, Decimal(str(size)))
                    
                    # 显示分析结果
                    col1, col2, col3 = st.columns(3)
                    col1.metric('流动性评级', analysis['liquidity_rating'])
                    col2.metric('滑点估计', f"{analysis['slippage_estimate']:.4f}")
                    col3.metric('置信度', analysis['confidence'])
                    
                    st.info(analysis['message'])
