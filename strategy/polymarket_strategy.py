from decimal import Decimal
from typing import Dict, Optional, Tuple, List, Any
from utils.logger import logger
from config.config import config
from gateways.polymarket_gateway import PolymarketGateway

class PolymarketStrategy:
    """Polymarket交易策略类"""
    
    def __init__(self, 
                 gateway: PolymarketGateway,
                 min_price_difference: Decimal = None,
                 max_position_size: Decimal = None,
                 max_order_size: Decimal = None):
        """初始化Polymarket策略
        
        Args:
            gateway: Polymarket网关实例
            min_price_difference: 最小价格差异阈值
            max_position_size: 最大持仓大小
            max_order_size: 最大订单大小
        """
        # 加载配置
        strategy_config = config.get_strategy_config('polymarket')
        
        # 使用提供的值或配置值或默认值
        if min_price_difference is None:
            min_price_difference = Decimal(str(strategy_config.get('min_price_difference', 0.01)))
        if max_position_size is None:
            max_position_size = Decimal(str(strategy_config.get('max_position_size', 1000)))
        if max_order_size is None:
            max_order_size = Decimal(str(strategy_config.get('max_order_size', 100)))
        
        # 验证参数
        if min_price_difference < Decimal('0'):
            raise ValueError("最小价格差异不能为负")
        if max_position_size < Decimal('0'):
            raise ValueError("最大持仓大小不能为负")
        if max_order_size < Decimal('0'):
            raise ValueError("最大订单大小不能为负")
        
        self.gateway = gateway
        self.min_price_difference = min_price_difference
        self.max_position_size = max_position_size
        self.max_order_size = max_order_size
    
    def analyze_market(self, market_id: str) -> Dict[str, Any]:
        """分析市场数据
        
        Args:
            market_id: 市场ID
            
        Returns:
            dict: 市场分析结果
        """
        try:
            # 获取市场详情
            market_info = self.gateway.get_market(market_id)
            
            # 获取市场价格
            price_data = self.gateway.get_market_price(market_id)
            
            # 获取订单簿
            order_book = self.gateway.get_order_book(market_id)
            
            # 分析订单簿深度
            order_book_analysis = self._analyze_order_book(order_book)
            
            # 分析市场流动性
            liquidity_analysis = self._analyze_liquidity(order_book)
            
            # 综合分析
            analysis = {
                'market_id': market_id,
                'market_info': market_info,
                'price_data': price_data,
                'order_book': order_book,
                'order_book_analysis': order_book_analysis,
                'liquidity_analysis': liquidity_analysis,
                'timestamp': self._get_current_timestamp()
            }
            
            return analysis
        except Exception as e:
            logger.error(f"分析市场失败: {e}")
            return {
                'market_id': market_id,
                'error': str(e),
                'timestamp': self._get_current_timestamp()
            }
    
    def _analyze_order_book(self, order_book: dict) -> Dict[str, Any]:
        """分析订单簿
        
        Args:
            order_book: 订单簿数据
            
        Returns:
            dict: 订单簿分析结果
        """
        try:
            asks = order_book.get('asks', [])
            bids = order_book.get('bids', [])
            
            # 计算买卖价差
            if asks and bids:
                best_ask = Decimal(asks[0].get('price', '0'))
                best_bid = Decimal(bids[0].get('price', '0'))
                spread = best_ask - best_bid
                spread_percentage = (spread / best_bid) * Decimal('100') if best_bid > 0 else Decimal('0')
            else:
                best_ask = Decimal('0')
                best_bid = Decimal('0')
                spread = Decimal('0')
                spread_percentage = Decimal('0')
            
            # 计算订单簿深度
            ask_depth = sum(Decimal(ask.get('size', '0')) for ask in asks)
            bid_depth = sum(Decimal(bid.get('size', '0')) for bid in bids)
            total_depth = ask_depth + bid_depth
            
            return {
                'best_ask': best_ask,
                'best_bid': best_bid,
                'spread': spread,
                'spread_percentage': spread_percentage,
                'ask_depth': ask_depth,
                'bid_depth': bid_depth,
                'total_depth': total_depth,
                'ask_count': len(asks),
                'bid_count': len(bids)
            }
        except Exception as e:
            logger.error(f"分析订单簿失败: {e}")
            return {
                'error': str(e)
            }
    
    def _analyze_liquidity(self, order_book: dict) -> Dict[str, Any]:
        """分析市场流动性
        
        Args:
            order_book: 订单簿数据
            
        Returns:
            dict: 流动性分析结果
        """
        try:
            order_book_analysis = self._analyze_order_book(order_book)
            
            # 基于订单簿深度和价差评估流动性
            spread_percentage = order_book_analysis.get('spread_percentage', Decimal('0'))
            total_depth = order_book_analysis.get('total_depth', Decimal('0'))
            
            if spread_percentage < Decimal('0.1') and total_depth > Decimal('1000'):
                liquidity_score = 'HIGH'
            elif spread_percentage < Decimal('0.5') and total_depth > Decimal('500'):
                liquidity_score = 'MEDIUM'
            else:
                liquidity_score = 'LOW'
            
            return {
                'liquidity_score': liquidity_score,
                'spread_percentage': spread_percentage,
                'total_depth': total_depth
            }
        except Exception as e:
            logger.error(f"分析流动性失败: {e}")
            return {
                'error': str(e)
            }
    
    def generate_trade_signal(self, market_id: str) -> Dict[str, Any]:
        """生成交易信号
        
        Args:
            market_id: 市场ID
            
        Returns:
            dict: 交易信号
        """
        try:
            # 分析市场
            market_analysis = self.analyze_market(market_id)
            
            # 检查是否有错误
            if 'error' in market_analysis:
                return {
                    'market_id': market_id,
                    'signal': 'HOLD',
                    'confidence': 'LOW',
                    'reason': f"市场分析失败: {market_analysis['error']}",
                    'analysis': market_analysis
                }
            
            # 获取订单簿分析
            order_book_analysis = market_analysis.get('order_book_analysis', {})
            spread = order_book_analysis.get('spread', Decimal('0'))
            best_bid = order_book_analysis.get('best_bid', Decimal('0'))
            best_ask = order_book_analysis.get('best_ask', Decimal('0'))
            
            # 获取流动性分析
            liquidity_analysis = market_analysis.get('liquidity_analysis', {})
            liquidity_score = liquidity_analysis.get('liquidity_score', 'LOW')
            
            # 生成交易信号
            if liquidity_score == 'LOW':
                return {
                    'market_id': market_id,
                    'signal': 'HOLD',
                    'confidence': 'LOW',
                    'reason': '市场流动性不足',
                    'analysis': market_analysis
                }
            
            # 基于价差生成信号
            if spread > self.min_price_difference:
                # 存在套利机会
                return {
                    'market_id': market_id,
                    'signal': 'ARBITRAGE',
                    'confidence': 'HIGH',
                    'reason': f'价差过大: {spread}',
                    'analysis': market_analysis,
                    'best_bid': best_bid,
                    'best_ask': best_ask
                }
            else:
                # 无明显套利机会
                return {
                    'market_id': market_id,
                    'signal': 'HOLD',
                    'confidence': 'MEDIUM',
                    'reason': '价差在合理范围内',
                    'analysis': market_analysis
                }
        except Exception as e:
            logger.error(f"生成交易信号失败: {e}")
            return {
                'market_id': market_id,
                'signal': 'HOLD',
                'confidence': 'LOW',
                'reason': f"生成信号失败: {str(e)}"
            }
    
    def get_trade_recommendation(self, market_id: str) -> Dict[str, Any]:
        """获取交易建议
        
        Args:
            market_id: 市场ID
            
        Returns:
            dict: 交易建议
        """
        try:
            # 生成交易信号
            signal = self.generate_trade_signal(market_id)
            
            # 获取持仓信息
            positions = self.gateway.get_positions()
            market_position = next((p for p in positions if p.get('market_id') == market_id), None)
            
            # 计算建议订单大小
            order_size = self._calculate_order_size(market_position)
            
            # 生成建议
            recommendation = {
                **signal,
                'position': market_position,
                'order_size': order_size,
                'timestamp': self._get_current_timestamp()
            }
            
            return recommendation
        except Exception as e:
            logger.error(f"获取交易建议失败: {e}")
            return {
                'market_id': market_id,
                'signal': 'HOLD',
                'confidence': 'LOW',
                'reason': f"获取建议失败: {str(e)}"
            }
    
    def _calculate_order_size(self, position: Optional[Dict[str, Any]]) -> Decimal:
        """计算订单大小
        
        Args:
            position: 持仓信息
            
        Returns:
            Decimal: 订单大小
        """
        try:
            if not position:
                # 无持仓，使用最大订单大小
                return min(self.max_order_size, self.max_position_size)
            
            # 有持仓，计算剩余可用空间
            current_size = Decimal(position.get('size', '0'))
            remaining_size = self.max_position_size - current_size
            
            if remaining_size <= Decimal('0'):
                return Decimal('0')
            
            # 返回最小的可用空间和最大订单大小
            return min(remaining_size, self.max_order_size)
        except Exception as e:
            logger.error(f"计算订单大小失败: {e}")
            return Decimal('0')
    
    def _get_current_timestamp(self) -> float:
        """获取当前时间戳
        
        Returns:
            float: 当前时间戳
        """
        import time
        return time.time()
    
    def run_strategy(self, market_ids: List[str]) -> List[Dict[str, Any]]:
        """运行策略
        
        Args:
            market_ids: 市场ID列表
            
        Returns:
            list: 策略运行结果
        """
        results = []
        
        for market_id in market_ids:
            try:
                recommendation = self.get_trade_recommendation(market_id)
                results.append(recommendation)
            except Exception as e:
                logger.error(f"运行策略失败 for market {market_id}: {e}")
                results.append({
                    'market_id': market_id,
                    'signal': 'HOLD',
                    'confidence': 'LOW',
                    'reason': f"策略运行失败: {str(e)}"
                })
        
        return results
