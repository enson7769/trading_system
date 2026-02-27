import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dashboard.monitoring import MonitoringDashboard

class PolymarketDataPage:
    """Polymarket数据页面"""
    
    def __init__(self, dashboard: 'MonitoringDashboard'):
        self.dashboard = dashboard
    
    def render(self):
        """运行页面"""
        st.set_page_config(
            page_title="Polymarket数据",
            page_icon="📊",
            layout="wide"
        )
        
        # 页面标题
        st.title('📊 Polymarket数据')
        st.markdown("---")
        
        # 标签页
        tab1, tab2, tab3, tab4 = st.tabs(['🏪 市场', '💼 持仓', '💰 投资组合', '⚙️ 交易设置'])
        
        with tab1:
            self._render_markets_tab()
        with tab2:
            self._render_positions_tab()
        with tab3:
            self._render_portfolio_tab()
        with tab4:
            self._render_trading_settings_tab()
    
    def _render_markets_tab(self):
        """Render Polymarket markets tab"""
        st.subheader('🏪 Polymarket市场')
        
        # 查询方式选择
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            query_method = st.radio(
                '查询方式',
                ['全部市场', '按Slug查询', '按标签查询', '通过事件接口'],
                label_visibility='collapsed'
            )
        
        # 根据查询方式显示不同的输入框
        if query_method == '全部市场':
            # 显示全部市场
            markets = self._get_all_markets()
            self._display_markets(markets)
        
        elif query_method == '按Slug查询':
            # 按Slug查询
            with col2:
                slug = st.text_input('输入市场Slug', placeholder='例如: will-bitcoin-price-exceed-100000')
            if slug:
                markets = self._get_markets_by_slug(slug)
                self._display_markets(markets)
        
        elif query_method == '按标签查询':
            # 按标签查询
            with col3:
                tag = st.text_input('输入标签', placeholder='例如: crypto, politics, sports')
            if tag:
                markets = self._get_markets_by_tag(tag)
                self._display_markets(markets)
        
        elif query_method == '通过事件接口':
            # 通过事件接口获取市场
            events = self.dashboard._get_polymarket_events()
            if not events.empty:
                with col4:
                    event_options = events['Title'].tolist()
                    selected_event = st.selectbox('选择事件', event_options)
                
                if selected_event:
                    # 获取选中事件的ID
                    event_row = events[events['Title'] == selected_event]
                    if not event_row.empty:
                        event_id = event_row.iloc[0]['Event ID']
                        markets = self._get_markets_by_event(event_id)
                        self._display_markets(markets)
    
    def _get_all_markets(self) -> pd.DataFrame:
        """获取全部市场数据"""
        if not self.dashboard.polymarket_gateway:
            return pd.DataFrame()
        
        try:
            markets = self.dashboard.polymarket_gateway.get_markets(active=True, closed=False, limit=100)
            market_data = []
            for market in markets:
                # 处理结果选项，确保正确显示
                outcomes = market.get('outcomes', [])
                clob_token_ids = market.get('clobTokenIds', [])
                
                # 获取市场价格
                last_price = None
                try:
                    price_data = self.dashboard.polymarket_gateway.get_market_price(market.get('id', ''))
                    last_price_str = price_data.get('last_price', '0')
                    last_price = float(last_price_str)
                except Exception as e:
                    pass
                
                if isinstance(outcomes, list) and len(outcomes) == 2:
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
                    if isinstance(outcomes, list):
                        formatted_outcomes = ', '.join(outcomes)
                    else:
                        formatted_outcomes = str(outcomes)
                
                market_data.append({
                    'Market ID': market.get('id', ''),
                    'Question': market.get('question', ''),
                    'Outcomes': formatted_outcomes,
                    'Status': market.get('status', ''),
                    'Slug': market.get('slug', ''),
                    'Yes Token ID': clob_token_ids[0] if len(clob_token_ids) > 0 else '',
                    'No Token ID': clob_token_ids[1] if len(clob_token_ids) > 1 else ''
                })
            return pd.DataFrame(market_data)
        except Exception as e:
            st.error(f'获取市场数据失败: {e}')
            return pd.DataFrame()
    
    def _get_markets_by_slug(self, slug: str) -> pd.DataFrame:
        """按Slug查询市场"""
        if not self.dashboard.polymarket_gateway:
            return pd.DataFrame()
        
        try:
            markets = self.dashboard.polymarket_gateway.get_markets_by_slug(slug, active=True, closed=False, limit=100)
            market_data = []
            for market in markets:
                # 处理结果选项，确保正确显示
                outcomes = market.get('outcomes', [])
                clob_token_ids = market.get('clobTokenIds', [])
                
                # 获取市场价格
                last_price = None
                try:
                    price_data = self.dashboard.polymarket_gateway.get_market_price(market.get('id', ''))
                    last_price_str = price_data.get('last_price', '0')
                    last_price = float(last_price_str)
                except Exception as e:
                    pass
                
                if isinstance(outcomes, list) and len(outcomes) == 2:
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
                    if isinstance(outcomes, list):
                        formatted_outcomes = ', '.join(outcomes)
                    else:
                        formatted_outcomes = str(outcomes)
                
                market_data.append({
                    'Market ID': market.get('id', ''),
                    'Question': market.get('question', ''),
                    'Outcomes': formatted_outcomes,
                    'Status': market.get('status', ''),
                    'Slug': market.get('slug', ''),
                    'Yes Token ID': clob_token_ids[0] if len(clob_token_ids) > 0 else '',
                    'No Token ID': clob_token_ids[1] if len(clob_token_ids) > 1 else ''
                })
            return pd.DataFrame(market_data)
        except Exception as e:
            st.error(f'获取市场数据失败: {e}')
            return pd.DataFrame()
    
    def _get_markets_by_tag(self, tag: str) -> pd.DataFrame:
        """按标签查询市场"""
        if not self.dashboard.polymarket_gateway:
            return pd.DataFrame()
        
        try:
            markets = self.dashboard.polymarket_gateway.get_markets_by_tag(tag, active=True, closed=False, limit=100)
            market_data = []
            for market in markets:
                # 处理结果选项，确保正确显示
                outcomes = market.get('outcomes', [])
                clob_token_ids = market.get('clobTokenIds', [])
                
                # 获取市场价格
                last_price = None
                try:
                    price_data = self.dashboard.polymarket_gateway.get_market_price(market.get('id', ''))
                    last_price_str = price_data.get('last_price', '0')
                    last_price = float(last_price_str)
                except Exception as e:
                    pass
                
                if isinstance(outcomes, list) and len(outcomes) == 2:
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
                    if isinstance(outcomes, list):
                        formatted_outcomes = ', '.join(outcomes)
                    else:
                        formatted_outcomes = str(outcomes)
                
                market_data.append({
                    'Market ID': market.get('id', ''),
                    'Question': market.get('question', ''),
                    'Outcomes': formatted_outcomes,
                    'Status': market.get('status', ''),
                    'Slug': market.get('slug', ''),
                    'Yes Token ID': clob_token_ids[0] if len(clob_token_ids) > 0 else '',
                    'No Token ID': clob_token_ids[1] if len(clob_token_ids) > 1 else ''
                })
            return pd.DataFrame(market_data)
        except Exception as e:
            st.error(f'获取市场数据失败: {e}')
            return pd.DataFrame()
    
    def _get_markets_by_event(self, event_id: str) -> pd.DataFrame:
        """通过事件接口获取市场数据"""
        if not self.dashboard.polymarket_gateway:
            return pd.DataFrame()
        
        try:
            markets = self.dashboard.polymarket_gateway.get_markets_by_event(event_id, active=True, closed=False, limit=100)
            market_data = []
            for market in markets:
                # 处理结果选项，确保正确显示
                outcomes = market.get('outcomes', [])
                clob_token_ids = market.get('clobTokenIds', [])
                
                # 获取市场价格
                last_price = None
                try:
                    price_data = self.dashboard.polymarket_gateway.get_market_price(market.get('id', ''))
                    last_price_str = price_data.get('last_price', '0')
                    last_price = float(last_price_str)
                except Exception as e:
                    pass
                
                if isinstance(outcomes, list) and len(outcomes) == 2:
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
                    if isinstance(outcomes, list):
                        formatted_outcomes = ', '.join(outcomes)
                    else:
                        formatted_outcomes = str(outcomes)
                
                market_data.append({
                    'Market ID': market.get('id', ''),
                    'Question': market.get('question', ''),
                    'Outcomes': formatted_outcomes,
                    'Status': market.get('status', ''),
                    'Slug': market.get('slug', ''),
                    'Yes Token ID': clob_token_ids[0] if len(clob_token_ids) > 0 else '',
                    'No Token ID': clob_token_ids[1] if len(clob_token_ids) > 1 else ''
                })
            return pd.DataFrame(market_data)
        except Exception as e:
            st.error(f'获取市场数据失败: {e}')
            return pd.DataFrame()
    
    def _display_markets(self, markets: pd.DataFrame):
        """显示市场数据"""
        if markets.empty:
            st.info('📭 无市场数据可用。')
            return
        
        # 显示市场数量
        st.info(f'📊 共找到 {len(markets)} 个市场')
        
        # 显示市场表格
        st.dataframe(
            markets,
            width="100%",
            hide_index=True,
            column_config={
                'Market ID': st.column_config.TextColumn('市场ID', width='small'),
                'Question': st.column_config.TextColumn('问题', width='large'),
                'Outcomes': st.column_config.TextColumn('结果', width='medium'),
                'Status': st.column_config.TextColumn('状态', width='small'),
                'Slug': st.column_config.TextColumn('Slug', width='medium'),
                'Yes Token ID': st.column_config.TextColumn('Yes Token ID', width='medium'),
                'No Token ID': st.column_config.TextColumn('No Token ID', width='medium')
            }
        )
    
    def _render_positions_tab(self):
        """Render Polymarket positions tab"""
        st.subheader('💼 Polymarket持仓')
        
        # 获取持仓数据
        positions = self.dashboard._get_polymarket_positions()
        if not positions.empty:
            # 显示持仓数量
            st.info(f'📊 共找到 {len(positions)} 个持仓')
            
            st.dataframe(
                positions,
                width="100%",
                hide_index=True
            )
        else:
            st.info('📭 无持仓数据可用。')
    
    def _render_portfolio_tab(self):
        """Render Polymarket portfolio tab"""
        st.subheader('💰 资产组合')
        
        # 获取投资组合数据
        portfolio = self.dashboard._get_polymarket_portfolio()
        if portfolio:
            # 资产组合概览
            total_value = portfolio.get('total_value', '26.85')
            total_pnl = "-1.00"
            available_for_trading = total_value
            
            # 计算过去一天的盈亏（模拟数据）
            daily_change = "0.19"
            daily_change_percent = "0.71%"
            
            # 显示资产组合概览
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                st.metric(
                    label="总价值",
                    value=f"${total_value}",
                    delta=f"-${daily_change} ({daily_change_percent})",
                    delta_color="inverse"
                )
            with col2:
                st.metric(
                    label="可用于交易",
                    value=f"${available_for_trading}"
                )
            with col3:
                st.metric(
                    label="盈亏",
                    value=f"${total_pnl}",
                    delta_color="inverse"
                )
            
            # 充值和提现按钮
            col1, col2 = st.columns(2)
            with col1:
                if st.button('💳 充值', width="100%"):
                    st.info('充值功能开发中...')
            with col2:
                if st.button('💸 提现', width="100%"):
                    # 提现表单
                    with st.expander('💸 提现', expanded=True):
                        amount = st.number_input('提现金额', min_value=0.01, step=0.01, placeholder='输入提现金额')
                        destination = st.text_input('目标地址', placeholder='输入接收地址')
                        asset = st.selectbox('资产类型', ['USDC'])
                        
                        if st.button('确认提现', type='primary'):
                            if not amount or not destination:
                                st.error('请输入提现金额和目标地址')
                            else:
                                # 调用提现方法
                                if self.dashboard.polymarket_gateway:
                                    try:
                                        result = self.dashboard.polymarket_gateway.withdraw(amount, destination, asset)
                                        if 'error' in result:
                                            st.error(f'提现失败: {result["error"]}')
                                        else:
                                            st.success(f'提现成功！交易ID: {result.get("id", "-")}')
                                            st.info(f'金额: {amount} {asset}')
                                            st.info(f'目标地址: {destination}')
                                            st.info(f'状态: {result.get("status", "处理中")}')
                                    except Exception as e:
                                        st.error(f'提现失败: {e}')
                                else:
                                    st.error('Polymarket网关未初始化')
            
            # 时间范围选择
            st.write(" ")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                if st.button('1D', width="100%"):
                    st.info('显示过去一天的数据')
            with col2:
                if st.button('1W', width="100%"):
                    st.info('显示过去一周的数据')
            with col3:
                if st.button('1M', width="100%"):
                    st.info('显示过去一个月的数据')
            with col4:
                if st.button('ALL', width="100%"):
                    st.info('显示所有数据')
            
            # 盈亏趋势图（模拟数据）
            import pandas as pd
            
            # 生成模拟数据
            dates = pd.date_range(start='2026-01-26', end='2026-02-26')
            values = [27.0, 27.2, 27.5, 27.3, 27.1, 26.9, 26.8, 26.7, 26.6, 26.5, 26.4, 26.3, 26.2, 26.1, 26.0, 25.9, 25.8, 25.7, 25.6, 25.5, 25.4, 25.3, 25.2, 25.1, 25.0, 24.9, 24.8, 24.7, 24.6, 24.5, 24.4, 24.3]
            df = pd.DataFrame({'日期': dates, '价值': values})
            
            # 创建图表
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=df['日期'],
                y=df['价值'],
                mode='lines',
                name='资产价值',
                line=dict(color='#1f77b4', width=2)
            ))
            fig.update_layout(
                title='资产价值趋势',
                xaxis_title='日期',
                yaxis_title='价值 ($)',
                height=300,
                margin=dict(l=0, r=0, t=30, b=0),
                showlegend=False
            )
            st.plotly_chart(fig, width="100%")
            
            # 标签页
            tab1, tab2, tab3 = st.tabs(['📦 持仓', '📋 未成交订单', '📜 历史记录'])
            
            with tab1:
                # 搜索框和排序选项
                col1, col2 = st.columns([3, 1])
                with col1:
                    search_term = st.text_input('🔍 搜索', placeholder='输入关键词搜索...')
                with col2:
                    sort_by = st.selectbox('📊 排序', ['当前价值'], key='sort_by')
                
                # 投资组合持仓
                positions = portfolio.get('positions', [])
                if positions:
                    # 显示真实持仓数据
                    for i, position in enumerate(positions):
                        # 获取市场信息以显示更详细的盘口信息
                        market_id = position.get('market_id', '')
                        market_info = ""
                        try:
                            # 尝试获取市场信息
                            markets = self.dashboard._get_polymarket_markets()
                            if not markets.empty:
                                market_row = markets[markets['Market ID'] == market_id]
                                if not market_row.empty:
                                    market_info = market_row.iloc[0].get('Question', market_id)
                        except Exception as e:
                            pass
                        
                        # 计算投入金额和可赢金额（简化处理）
                        value = float(position.get('value', '0'))
                        pnl = float(position.get('pnl', '0'))
                        invested_amount = value - pnl
                        potential_win = value * 2
                        
                        # 计算均价和当前价（简化处理）
                        avg_price = "0¢"
                        current_price = "0¢"
                        
                        # 显示持仓卡片
                        with st.container():
                            st.markdown("---")
                            col1, col2, col3, col4, col5, col6, col7 = st.columns([2, 1, 1, 1, 1, 1, 1])
                            with col1:
                                st.markdown(f"**{market_info or market_id}**")
                                st.markdown(f"📌 结果: {position.get('outcome', '')}")
                            with col2:
                                st.markdown(f"**均价**")
                                st.markdown(avg_price)
                            with col3:
                                st.markdown(f"**当前价**")
                                st.markdown(current_price)
                            with col4:
                                st.markdown(f"**投入金额**")
                                st.markdown(f"${invested_amount:.2f}")
                            with col5:
                                st.markdown(f"**可赢金额**")
                                st.markdown(f"${potential_win:.2f}")
                            with col6:
                                st.markdown(f"**当前价值**")
                                st.markdown(f"<span style='color: {'red' if pnl < 0 else 'green'}'>${value:.2f}</span>", unsafe_allow_html=True)
                            with col7:
                                if st.button('🔴 卖出', key=f"sell_{i}", width="100%"):
                                    st.info('卖出功能开发中...')
                else:
                    # 显示空持仓提示
                    st.info('📭 无持仓数据可用。')
            
            with tab2:
                st.info('📭 无未成交订单数据可用。')
            
            with tab3:
                st.info('📭 无历史记录数据可用。')
        else:
            st.info('📭 无法获取投资组合数据。')
    
    def _render_trading_settings_tab(self):
        """Render trading settings tab"""
        st.subheader('⚙️ 交易设置')
        
        # 获取市场数据
        markets = self._get_all_markets()
        if markets.empty:
            st.info('📭 无市场数据可用。')
            return
        
        # 选择市场
        col1, col2 = st.columns([2, 1])
        with col1:
            market_options = markets['Question'].tolist()
            selected_market = st.selectbox('🏪 选择市场', market_options)
        
        with col2:
            if st.button('🔄 刷新市场', width="100%"):
                st.rerun()
        
        if selected_market:
            # 获取选中市场的信息
            market_row = markets[markets['Question'] == selected_market]
            if not market_row.empty:
                market_id = market_row.iloc[0]['Market ID']
                yes_token_id = market_row.iloc[0]['Yes Token ID']
                no_token_id = market_row.iloc[0]['No Token ID']
                
                # 分割线
                st.markdown("---")
                
                # 选择结果选项
                col1, col2 = st.columns(2)
                with col1:
                    outcome = st.radio('📌 选择结果选项', ['Yes', 'No'], horizontal=True)
                with col2:
                    st.markdown(f"**Yes Token ID**: `{yes_token_id}`")
                    st.markdown(f"**No Token ID**: `{no_token_id}`")
                
                # 分割线
                st.markdown("---")
                
                # 设置触发购买值
                col1, col2 = st.columns([1, 1])
                with col1:
                    trigger_price = st.number_input('🎯 触发购买值', min_value=0.0, max_value=1.0, value=0.5, step=0.01, format="%.2f")
                with col2:
                    st.info('当市场价格低于此值时，将自动触发购买')
                
                # 分割线
                st.markdown("---")
                
                # 设置凯利公式参数
                st.subheader('📊 凯利公式参数')
                col1, col2, col3 = st.columns(3)
                with col1:
                    win_rate = st.number_input('🎲 胜率', min_value=0.0, max_value=1.0, value=0.5, step=0.01, format="%.2f")
                with col2:
                    avg_win = st.number_input('📈 平均盈利', min_value=0.0, value=1.0, step=0.01, format="%.2f")
                with col3:
                    avg_loss = st.number_input('📉 平均亏损', min_value=0.0, value=1.0, step=0.01, format="%.2f")
                
                # 计算凯利公式
                kelly_fraction = (win_rate * avg_win - (1 - win_rate) * avg_loss) / avg_win
                st.info(f'📊 凯利公式结果: **{kelly_fraction:.4f}**')
                
                # 分割线
                st.markdown("---")
                
                # 设置下单数量
                col1, col2 = st.columns([1, 1])
                with col1:
                    order_size = st.number_input('💰 下单数量', min_value=0.0, value=10.0, step=0.01, format="%.2f")
                with col2:
                    st.info('下单数量 = 账户余额 × 凯利公式结果')
                
                # 分割线
                st.markdown("---")
                
                # 操作按钮
                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button('💾 保存设置', width="100%", type='primary'):
                        # 保存到MySQL
                        try:
                            from database.database_manager import db_manager
                            db_manager.connect()
                            
                            # 创建交易设置表
                            create_table_sql = """
                            CREATE TABLE IF NOT EXISTS trading_settings (
                                id INT AUTO_INCREMENT PRIMARY KEY,
                                market_id VARCHAR(255) NOT NULL,
                                outcome VARCHAR(50) NOT NULL,
                                trigger_price DECIMAL(10, 4) NOT NULL,
                                win_rate DECIMAL(10, 4) NOT NULL,
                                avg_win DECIMAL(10, 4) NOT NULL,
                                avg_loss DECIMAL(10, 4) NOT NULL,
                                kelly_fraction DECIMAL(10, 4) NOT NULL,
                                order_size DECIMAL(10, 4) NOT NULL,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                            )
                            """
                            db_manager.execute(create_table_sql)
                            
                            # 插入交易设置
                            insert_sql = """
                            INSERT INTO trading_settings (
                                market_id, outcome, trigger_price, win_rate, avg_win, avg_loss, kelly_fraction, order_size
                            ) VALUES (
                                %s, %s, %s, %s, %s, %s, %s, %s
                            )
                            """
                            db_manager.execute(insert_sql, (
                                market_id, outcome, trigger_price, win_rate, avg_win, avg_loss, kelly_fraction, order_size
                            ))
                            
                            st.success('✅ 设置保存成功！')
                        except Exception as e:
                            st.error(f'❌ 保存设置失败: {e}')
                
                with col2:
                    if st.button('🔔 订阅市场数据', width="100%"):
                        # 订阅市场数据
                        if self.dashboard.polymarket_gateway:
                            self.dashboard.polymarket_gateway.subscribe_to_market(market_id)
                            st.success(f'✅ 已订阅市场: {selected_market}')
                            st.info(f'🎯 当价格达到 {trigger_price} 时，将触发购买 {outcome} 选项')
                        else:
                            st.error('❌ Polymarket网关未初始化')
                
                with col3:
                    if st.button('🔍 检查触发条件', width="100%"):
                        # 获取账户余额
                        balance = 0.0
                        try:
                            balance_data = self.dashboard._get_polymarket_balance()
                            usdc_balance = float(balance_data.get('usdc', '0'))
                            balance = usdc_balance
                        except Exception as e:
                            st.error(f'❌ 获取账户余额失败: {e}')
                        
                        # 检查触发条件并执行交易
                        if self.dashboard.polymarket_gateway:
                            result = self.dashboard.polymarket_gateway.check_trigger_and_execute(
                                market_id, outcome, trigger_price, win_rate, avg_win, avg_loss, balance
                            )
                            
                            if 'error' in result:
                                st.error(f'❌ 检查触发条件失败: {result["error"]}')
                            elif result.get('triggered'):
                                st.success('✅ 触发条件满足，已执行交易!')
                                st.json(result)
                            else:
                                st.info(f'📊 触发条件未满足。当前价格: {result.get("current_price")}, 触发价格: {result.get("trigger_price")}')
                        else:
                            st.error('❌ Polymarket网关未初始化')
                
                # 分割线
                st.markdown("---")
                
                # 手动下单
                col1, col2 = st.columns([1, 1])
                with col1:
                    if st.button('🛒 手动下单', width="100%", type='primary'):
                        # 创建订单
                        if self.dashboard.polymarket_gateway:
                            order_result = self.dashboard.polymarket_gateway.create_order(
                                market_id, outcome, trigger_price, order_size, 'buy'
                            )
                            
                            if 'error' in order_result:
                                st.error(f'❌ 下单失败: {order_result["error"]}')
                            else:
                                st.success('✅ 下单成功!')
                                st.json(order_result)
                        else:
                            st.error('❌ Polymarket网关未初始化')
                with col2:
                    st.info('💡 提示：手动下单将立即执行，不会等待触发条件')
