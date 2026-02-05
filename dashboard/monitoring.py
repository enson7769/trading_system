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
import asyncio
import threading
import websockets
import json
from gateways.polymarket_gateway import PolymarketGateway
from security.credential_manager import CredentialManager
from config.config import config

class MonitoringDashboard:
    def __init__(self):
        """Initialize monitoring dashboard with performance optimizations and WebSocket support"""
        self._websocket_clients = set()
        self._websocket_thread = None
        self._stop_event = threading.Event()
        self._data_update_event = threading.Event()
        self._data_update_event.set()
        
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
    

    
    def get_order_stats(self) -> Dict[str, Any]:
        """Get order statistics from backend"""
        if data_service.is_initialized():
            return data_service.get_order_stats()
        else:
            return {
                'total_orders': 0,
                'filled_orders': 0,
                'pending_orders': 0,
                'rejected_orders': 0,
                'total_size': 0
            }
    
    async def _websocket_handler(self, websocket, path):
        """Handle WebSocket connections according to Polymarket API spec"""
        self._websocket_clients.add(websocket)
        logger.info(f"WebSocket client connected. Total clients: {len(self._websocket_clients)}")
        
        client_subscriptions = {
            'user': [],
            'market': []
        }
        
        try:
            initial_message = await websocket.recv()
            logger.info(f"Received initial WebSocket message: {initial_message}")
            
            try:
                subscription_data = json.loads(initial_message)
                
                if 'type' not in subscription_data:
                    await websocket.send(json.dumps({
                        'error': 'Missing required field: type'
                    }))
                    return
                
                if 'auth' in subscription_data:
                    logger.info("Authentication provided")
                
                channel_type = subscription_data['type'].upper()
                
                if channel_type == 'USER':
                    markets = subscription_data.get('markets', [])
                    client_subscriptions['user'] = markets
                    logger.info(f"User channel subscribed to markets: {markets}")
                    
                elif channel_type == 'MARKET':
                    assets_ids = subscription_data.get('assets_ids', [])
                    client_subscriptions['market'] = assets_ids
                    logger.info(f"Market channel subscribed to assets: {assets_ids}")
                
                initial_data = {
                    'type': 'initial_data',
                    'channel': channel_type,
                    'order_stats': self.get_order_stats(),
                    'subscriptions': client_subscriptions
                }
                await websocket.send(json.dumps(initial_data))
                
            except json.JSONDecodeError:
                await websocket.send(json.dumps({
                    'error': 'Invalid JSON format'
                }))
                return
            except Exception as e:
                await websocket.send(json.dumps({
                    'error': f'Invalid subscription message: {str(e)}'
                }))
                return
            
            async for message in websocket:
                try:
                    msg_data = json.loads(message)
                    operation = msg_data.get('operation', '').lower()
                    
                    if operation in ['subscribe', 'unsubscribe']:
                        if 'markets' in msg_data:
                            if operation == 'subscribe':
                                client_subscriptions['user'].extend(msg_data['markets'])
                                client_subscriptions['user'] = list(set(client_subscriptions['user']))
                            else:
                                client_subscriptions['user'] = [
                                    market for market in client_subscriptions['user'] 
                                    if market not in msg_data['markets']
                                ]
                            logger.info(f"User channel {operation}d to markets: {msg_data['markets']}")
                            
                        elif 'assets_ids' in msg_data:
                            if operation == 'subscribe':
                                client_subscriptions['market'].extend(msg_data['assets_ids'])
                                client_subscriptions['market'] = list(set(client_subscriptions['market']))
                            else:
                                client_subscriptions['market'] = [
                                    asset_id for asset_id in client_subscriptions['market'] 
                                    if asset_id not in msg_data['assets_ids']
                                ]
                            logger.info(f"Market channel {operation}d to assets: {msg_data['assets_ids']}")
                        
                        await websocket.send(json.dumps({
                            'type': 'subscription_updated',
                            'subscriptions': client_subscriptions
                        }))
                    
                except json.JSONDecodeError:
                    await websocket.send(json.dumps({
                        'error': 'Invalid JSON format'
                    }))
                except Exception as e:
                    await websocket.send(json.dumps({
                        'error': f'Error processing message: {str(e)}'
                    }))
        
        except websockets.exceptions.ConnectionClosed:
            logger.info("WebSocket client disconnected")
        finally:
            self._websocket_clients.remove(websocket)
            logger.info(f"WebSocket client disconnected. Total clients: {len(self._websocket_clients)}")
    
    async def _websocket_server_task(self):
        """WebSocket server task"""
        async with websockets.serve(self._websocket_handler, "localhost", 8765):
            logger.info("WebSocket server started on ws://localhost:8765")
            while not self._stop_event.is_set():
                if self._data_update_event.wait(1):
                    await self._broadcast_data_update()
                    self._data_update_event.clear()
    
    async def _broadcast_data_update(self):
        """Broadcast data updates to all WebSocket clients based on their subscriptions"""
        if not self._websocket_clients:
            return
        
        try:
            order_stats = self.get_order_stats()
            timestamp = datetime.now().isoformat()
            
            disconnected = []
            for client in self._websocket_clients:
                try:
                    update_data = {
                        'type': 'data_update',
                        'order_stats': order_stats,
                        'timestamp': timestamp
                    }
                    await client.send(json.dumps(update_data))
                except websockets.exceptions.ConnectionClosed:
                    disconnected.append(client)
            
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
                market_data.append({
                    'Market ID': market.get('id', ''),
                    'Event ID': market.get('event_id', ''),
                    'Question': market.get('question', ''),
                    'Outcomes': ', '.join(market.get('outcomes', [])),
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
        
        # 启动WebSocket服务器
        self.start_websocket_server()
        
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
            
            # WebSocket状态
            st.header('WebSocket状态')
            st.success('WebSocket服务已启动')
            st.info('数据将通过WebSocket实时更新')
            st.info('WebSocket地址: ws://localhost:8765')
        
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
                self.trigger_data_update()
                st.rerun()
        
        # 添加WebSocket客户端JavaScript代码（兼容Polymarket API）
        st.components.v1.html('''
        <script>
            // WebSocket客户端（兼容Polymarket API）
            const ws = new WebSocket('ws://localhost:8765');
            
            ws.onopen = function() {
                console.log('WebSocket已连接');
                
                const subscriptionMessage = {
                    type: 'USER',
                    markets: []
                };
                
                console.log('发送订阅消息:', subscriptionMessage);
                ws.send(JSON.stringify(subscriptionMessage));
            };
            
            ws.onmessage = function(event) {
                console.log('收到WebSocket消息:', event.data);
                const data = JSON.parse(event.data);
                
                if (data.type === 'initial_data') {
                    console.log('收到初始数据:', data);
                } else if (data.type === 'data_update') {
                    console.log('使用新数据更新UI:', data);
                } else if (data.type === 'subscription_updated') {
                    console.log('订阅已更新:', data.subscriptions);
                } else if (data.error) {
                    console.error('WebSocket错误:', data.error);
                }
            };
            
            ws.onclose = function() {
                console.log('WebSocket已断开连接');
            };
            
            ws.onerror = function(error) {
                console.error('WebSocket错误:', error);
            };
            
            function subscribeToMarkets(markets) {
                if (ws.readyState === WebSocket.OPEN) {
                    const subscribeMessage = {
                        operation: 'subscribe',
                        markets: markets
                    };
                    ws.send(JSON.stringify(subscribeMessage));
                }
            }
            
            function unsubscribeFromMarkets(markets) {
                if (ws.readyState === WebSocket.OPEN) {
                    const unsubscribeMessage = {
                        operation: 'unsubscribe',
                        markets: markets
                    };
                    ws.send(JSON.stringify(unsubscribeMessage));
                }
            }
        </script>
        ''', height=0)
        
        # 更新最后刷新时间
        st.session_state.last_refresh = datetime.now()

if __name__ == '__main__':
    dashboard = MonitoringDashboard()
    dashboard.run_dashboard()
