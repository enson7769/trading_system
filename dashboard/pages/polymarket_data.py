import streamlit as st
import pandas as pd

class PolymarketDataPage:
    def __init__(self, dashboard):
        """Initialize Polymarket data page"""
        self.dashboard = dashboard
    
    def render(self):
        """Render Polymarket data page"""
        st.header('Polymarket数据')
        
        if not self.dashboard.polymarket_gateway:
            st.warning('Polymarket网关未初始化。无法显示Polymarket数据。')
        else:
            # Polymarket数据标签页
            tab1, tab2, tab3, tab4 = st.tabs(['事件', '市场', '持仓', '投资组合'])
            
            # 事件标签页
            with tab1:
                self._render_events_tab()
            
            # 市场标签页
            with tab2:
                self._render_markets_tab()
            
            # 持仓标签页
            with tab3:
                self._render_positions_tab()
            
            # 投资组合标签页
            with tab4:
                self._render_portfolio_tab()
    
    def _render_events_tab(self):
        """Render Polymarket events tab"""
        st.subheader('Polymarket事件')
        events_df = self.dashboard._get_polymarket_events()
        if not events_df.empty:
            st.dataframe(
                events_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    'Event ID': st.column_config.TextColumn('事件ID', width='small'),
                    'Title': st.column_config.TextColumn('标题', width='medium'),
                    'Description': st.column_config.TextColumn('描述', width='large'),
                    'Categories': st.column_config.TextColumn('类别', width='small')
                }
            )
        else:
            # 创建空的DataFrame以显示表头
            empty_df = pd.DataFrame(columns=['Event ID', 'Title', 'Description', 'Categories'])
            st.dataframe(
                empty_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    'Event ID': st.column_config.TextColumn('事件ID', width='small'),
                    'Title': st.column_config.TextColumn('标题', width='medium'),
                    'Description': st.column_config.TextColumn('描述', width='large'),
                    'Categories': st.column_config.TextColumn('类别', width='small')
                }
            )
            st.info('无事件数据可用。')
    
    def _render_markets_tab(self):
        """Render Polymarket markets tab"""
        st.subheader('Polymarket市场')
        # 添加市场数量输入框
        market_count = st.number_input(
            '显示市场数量',
            min_value=1,
            max_value=100,
            value=20,
            step=5,
            key='market_count'
        )
        markets_df = self.dashboard._get_polymarket_markets()
        if not markets_df.empty:
            # 根据输入的数量过滤市场数据
            filtered_markets_df = markets_df.head(market_count)
            st.dataframe(
                filtered_markets_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    'Market ID': st.column_config.TextColumn('市场ID', width='small'),
                    'Event ID': st.column_config.TextColumn('事件ID', width='small'),
                    'Question': st.column_config.TextColumn('问题', width='medium'),
                    'Outcomes': st.column_config.TextColumn('结果选项', width='medium'),
                    'Status': st.column_config.TextColumn('状态', width='small')
                }
            )
            # 显示过滤信息
            st.caption(f'显示前 {len(filtered_markets_df)} 个市场，共 {len(markets_df)} 个市场')
        else:
            # 创建空的DataFrame以显示表头
            empty_df = pd.DataFrame(columns=['Market ID', 'Event ID', 'Question', 'Outcomes', 'Status'])
            st.dataframe(
                empty_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    'Market ID': st.column_config.TextColumn('市场ID', width='small'),
                    'Event ID': st.column_config.TextColumn('事件ID', width='small'),
                    'Question': st.column_config.TextColumn('问题', width='medium'),
                    'Outcomes': st.column_config.TextColumn('结果选项', width='medium'),
                    'Status': st.column_config.TextColumn('状态', width='small')
                }
            )
            st.info('无市场数据可用。')
    
    def _render_positions_tab(self):
        """Render Polymarket positions tab"""
        st.subheader('Polymarket持仓')
        positions_df = self.dashboard._get_polymarket_positions()
        if not positions_df.empty:
            st.dataframe(
                positions_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    'Market ID': st.column_config.TextColumn('市场ID', width='small'),
                    'Outcome': st.column_config.TextColumn('结果', width='small'),
                    'Size': st.column_config.NumberColumn('数量', format='%.2f'),
                    'Avg Price': st.column_config.NumberColumn('平均价格', format='%.4f'),
                    'Current Price': st.column_config.NumberColumn('当前价格', format='%.4f'),
                    'PnL': st.column_config.NumberColumn('盈亏', format='%.2f')
                }
            )
        else:
            # 创建空的DataFrame以显示表头
            empty_df = pd.DataFrame(columns=['Market ID', 'Outcome', 'Size', 'Avg Price', 'Current Price', 'PnL'])
            st.dataframe(
                empty_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    'Market ID': st.column_config.TextColumn('市场ID', width='small'),
                    'Outcome': st.column_config.TextColumn('结果', width='small'),
                    'Size': st.column_config.NumberColumn('数量', format='%.2f'),
                    'Avg Price': st.column_config.NumberColumn('平均价格', format='%.4f'),
                    'Current Price': st.column_config.NumberColumn('当前价格', format='%.4f'),
                    'PnL': st.column_config.NumberColumn('盈亏', format='%.2f')
                }
            )
            st.info('无持仓数据可用。')
    
    def _render_portfolio_tab(self):
        """Render Polymarket portfolio tab"""
        st.subheader('Polymarket投资组合')
        portfolio = self.dashboard._get_polymarket_portfolio()
        if portfolio:
            col1, col2 = st.columns(2)
            col1.metric('总价值', f"${portfolio.get('total_value', '0')}")
            col2.metric('总盈亏', f"${portfolio.get('total_pnl', '0')}")
            
            # 投资组合持仓
            positions = portfolio.get('positions', [])
            if positions:
                st.subheader('持仓详情')
                positions_df = pd.DataFrame(positions)
                st.dataframe(
                    positions_df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        'market_id': st.column_config.TextColumn('市场ID', width='small'),
                        'outcome': st.column_config.TextColumn('结果', width='small'),
                        'value': st.column_config.NumberColumn('价值', format='%.2f'),
                        'pnl': st.column_config.NumberColumn('盈亏', format='%.2f')
                    }
                )
            else:
                # 创建空的DataFrame以显示表头
                empty_df = pd.DataFrame(columns=['market_id', 'outcome', 'value', 'pnl'])
                st.dataframe(
                    empty_df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        'market_id': st.column_config.TextColumn('市场ID', width='small'),
                        'outcome': st.column_config.TextColumn('结果', width='small'),
                        'value': st.column_config.NumberColumn('价值', format='%.2f'),
                        'pnl': st.column_config.NumberColumn('盈亏', format='%.2f')
                    }
                )
            
            # 投资组合统计
            stats = portfolio.get('stats', {})
            if stats:
                st.subheader('投资组合统计')
                col1, col2, col3, col4 = st.columns(4)
                col1.metric('总交易数', stats.get('total_trades', 0))
                col2.metric('胜率', f"{stats.get('win_rate', 0) * 100:.1f}%")
                col3.metric('平均盈利', f"${stats.get('avg_win', 0):.2f}")
                col4.metric('平均亏损', f"${stats.get('avg_loss', 0):.2f}")
        else:
            st.info('无投资组合数据可用。')
