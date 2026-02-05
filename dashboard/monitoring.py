import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
from datetime import datetime
from typing import Dict, Any
from dashboard.data_service import data_service
from dashboard.pages.order_status import OrderStatusPage
from dashboard.pages.market_liquidity import MarketLiquidityPage
from dashboard.pages.event_data import EventDataPage
from dashboard.pages.large_orders import LargeOrdersPage
from dashboard.pages.system_status import SystemStatusPage
from dashboard.pages.polymarket_data import PolymarketDataPage
from utils.logger import logger
from gateways.polymarket_gateway import PolymarketGateway
from security.credential_manager import CredentialManager
from config.config import config

class MonitoringDashboard:
    def __init__(self):
        """Initialize monitoring dashboard"""
        # Initialize Polymarket Gateway
        try:
            polymarket_config = config.get_gateway_config('polymarket')
            rpc_url = polymarket_config.get('rpc_url', 'https://polygon-rpc.com/')
            mock = polymarket_config.get('mock', True)
            
            self.credential_manager = CredentialManager()
            
            self.polymarket_gateway = PolymarketGateway(
                rpc_url=rpc_url,
                credential_manager=self.credential_manager,
                mock=mock
            )
            
            self.polymarket_gateway.connect()
            logger.info("Polymarket gateway initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Polymarket gateway: {e}")
            self.polymarket_gateway = None
        
        # Initialize page components
        self.order_status_page = OrderStatusPage(self)
        self.market_liquidity_page = MarketLiquidityPage(self)
        self.event_data_page = EventDataPage(self)
        self.large_orders_page = LargeOrdersPage(self)
        self.system_status_page = SystemStatusPage(self)
        self.polymarket_data_page = PolymarketDataPage(self)
    
    def _get_order_data(self, page: int = 1, page_size: int = 100) -> pd.DataFrame:
        """Get order data from backend with pagination"""
        if not data_service.is_initialized():
            return pd.DataFrame(columns=[
                'Order ID', 'Instrument', 'Side', 'Type', 'Quantity', 
                'Price', 'Status', 'Filled Qty', 'Gateway ID', 'Timestamp'
            ])
        
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
        if not data_service.is_initialized():
            return pd.DataFrame(columns=['Event Name', 'Timestamp', 'Data'])
        
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
        if not data_service.is_initialized():
            return pd.DataFrame(columns=['Timestamp', 'Symbol', 'Side', 'Quantity', 'Price', 'Account'])
        
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
    
    # Polymarket data methods
    def _get_polymarket_events(self) -> pd.DataFrame:
        """Get Polymarket events"""
        if not self.polymarket_gateway:
            return pd.DataFrame()
        
        def compute_events():
            events = self.polymarket_gateway.get_events()
            event_data = []
            for event in events:
                event_data.append({
                    'Event ID': event.get('id', ''),
                    'Title': event.get('title', ''),
                    'Description': event.get('description', ''),
                    'Categories': ', '.join(event.get('categories', []))
                })
            return pd.DataFrame(event_data)
        
        return compute_events()
    
    def _get_polymarket_markets(self, event_id: str = None) -> pd.DataFrame:
        """Get Polymarket markets"""
        if not self.polymarket_gateway:
            return pd.DataFrame()
        
        def compute_markets():
            markets = self.polymarket_gateway.get_markets(event_id)
            market_data = []
            for market in markets:
                market_id = market.get('id', '')
                # 处理结果选项，确保正确显示
                outcomes = market.get('outcomes', [])
                
                # 获取市场价格
                last_price = None
                try:
                    price_data = self.polymarket_gateway.get_market_price(market_id)
                    last_price_str = price_data.get('last_price', '0')
                    last_price = float(last_price_str)
                    logger.info(f"获取市场 {market_id} 价格成功: {last_price}")
                except Exception as e:
                    logger.error(f"获取市场 {market_id} 价格失败: {e}")
                
                if isinstance(outcomes, list):
                    if len(outcomes) == 2:
                        # 二元市场，计算每个结果的赢率
                        outcome1 = outcomes[0]
                        outcome2 = outcomes[1]
                        if last_price is not None:
                            # 即使价格为0，也显示赢率百分比
                            percentage1 = round(last_price * 100, 2)
                            percentage2 = round((1 - last_price) * 100, 2)
                            formatted_outcomes = f"{outcome1} ({percentage1}%), {outcome2} ({percentage2}%)"
                        else:
                            # 无法获取价格，仅显示结果选项
                            formatted_outcomes = ', '.join(outcomes)
                    else:
                        # 多元市场，仅显示结果选项
                        formatted_outcomes = ', '.join(outcomes)
                elif isinstance(outcomes, str):
                    # 如果是字符串，尝试解析为列表
                    try:
                        # 尝试去除可能的括号和引号，然后分割
                        cleaned_outcomes = outcomes.strip('[]')
                        # 处理带引号的情况
                        if '"' in cleaned_outcomes:
                            # 分割并去除引号和空格
                            items = [item.strip('" ')
                                   for item in cleaned_outcomes.split(',')
                                   if item.strip('" ')]
                        else:
                            # 直接分割
                            items = [item.strip() for item in cleaned_outcomes.split(',') if item.strip()]
                        
                        if len(items) == 2:
                            # 二元市场，计算每个结果的赢率
                            if last_price is not None:
                                # 即使价格为0，也显示赢率百分比
                                percentage1 = round(last_price * 100, 2)
                                percentage2 = round((1 - last_price) * 100, 2)
                                formatted_outcomes = f"{items[0]} ({percentage1}%), {items[1]} ({percentage2}%)"
                            else:
                                # 无法获取价格，仅显示结果选项
                                formatted_outcomes = ', '.join(items)
                        else:
                            # 多元市场，仅显示结果选项
                            formatted_outcomes = ', '.join(items)
                    except Exception:
                        # 如果解析失败，使用原始字符串
                        formatted_outcomes = outcomes
                else:
                    # 其他类型，转换为字符串
                    formatted_outcomes = str(outcomes)
                
                market_data.append({
                    'Market ID': market_id,
                    'Event ID': market.get('event_id', ''),
                    'Question': market.get('question', ''),
                    'Outcomes': formatted_outcomes,
                    'Status': market.get('status', '')
                })
            return pd.DataFrame(market_data)
        
        return compute_markets()
    
    def _get_polymarket_positions(self) -> pd.DataFrame:
        """Get Polymarket positions"""
        if not self.polymarket_gateway:
            return pd.DataFrame()
        
        def compute_positions():
            positions = self.polymarket_gateway.get_positions()
            position_data = []
            for position in positions:
                position_data.append({
                    'Market ID': position.get('market_id', ''),
                    'Outcome': position.get('outcome', ''),
                    'Size': float(position.get('size', '0')),
                    'Avg Price': float(position.get('avg_price', '0')),
                    'Current Price': float(position.get('current_price', '0')),
                    'PnL': float(position.get('pnl', '0'))
                })
            return pd.DataFrame(position_data)
        
        return compute_positions()
    
    def _get_polymarket_portfolio(self) -> Dict[str, Any]:
        """Get Polymarket portfolio"""
        if not self.polymarket_gateway:
            return {}
        
        def compute_portfolio():
            return self.polymarket_gateway.get_portfolio()
        
        return compute_portfolio()
    
    def run_dashboard(self):
        """运行仪表盘，使用页签聚合子页面内容"""
        st.title('交易系统监控仪表盘')
        
        # 初始化实时数据的会话状态
        if 'last_refresh' not in st.session_state:
            st.session_state.last_refresh = datetime.now()
        
        # 侧边栏控制
        with st.sidebar:
            st.header('仪表盘控制')
            page_size = st.selectbox('每页显示数量', [50, 100, 200], index=1, key='sidebar_page_size')
            
            # 数据服务状态
            st.header('数据服务状态')
            if data_service.is_initialized():
                st.success('数据服务已连接')
                system_status = data_service.get_system_status()
                components = system_status.get('components', {})
                for component, status in components.items():
                    if status:
                        st.success(f'{component.replace("_", " ").title()}')
                    else:
                        st.warning(f'{component.replace("_", " ").title()}')
            else:
                st.warning('数据服务未连接')
                st.info('请先运行主交易系统以初始化数据服务。')
        
        # 创建页签
        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
            '订单状态',
            '市场流动性',
            '事件数据',
            '大额订单',
            '系统状态',
            'Polymarket数据'
        ])
        
        # 订单状态页签
        with tab1:
            self.order_status_page.render(page_size)
        
        # 市场流动性页签
        with tab2:
            self.market_liquidity_page.render()
        
        # 事件数据页签
        with tab3:
            self.event_data_page.render(page_size)
        
        # 大额订单页签
        with tab4:
            self.large_orders_page.render(page_size)
        
        # 系统状态页签
        with tab5:
            self.system_status_page.render()
        
        # Polymarket数据页签
        with tab6:
            self.polymarket_data_page.render()
        
        # 显示最后刷新时间
        st.divider()
        col1, col2 = st.columns([3, 1])
        with col1:
            st.info(f'最后刷新: {st.session_state.last_refresh.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]}')
        with col2:
            if st.button('手动刷新数据', key='manual_refresh'):
                st.rerun()
        
        # 更新最后刷新时间
        st.session_state.last_refresh = datetime.now()

if __name__ == '__main__':
    dashboard = MonitoringDashboard()
    dashboard.run_dashboard()
