from decimal import Decimal
from typing import Dict, List, Optional, Any
from datetime import datetime
from utils.logger import logger
from config.config import config
from strategy.polymarket_strategy import PolymarketStrategy
from engine.execution_engine import ExecutionEngine
from core.models import Order, Instrument
from gateways.polymarket_gateway import PolymarketGateway
import threading
import time
import asyncio

class StrategyExecutor:
    """策略执行器，负责连接策略生成的信号和实际的订单提交"""
    
    def __init__(self, 
                 execution_engine: ExecutionEngine, 
                 polymarket_strategy: PolymarketStrategy,
                 polymarket_gateway: PolymarketGateway):
        """初始化策略执行器
        
        Args:
            execution_engine: 执行引擎实例
            polymarket_strategy: Polymarket策略实例
            polymarket_gateway: Polymarket网关实例
        """
        # 加载配置
        executor_config = config.get_strategy_config('executor')
        
        # 配置参数
        self.check_interval = executor_config.get('check_interval', 30)  # 策略检查间隔（秒）
        self.min_confidence = executor_config.get('min_confidence', 'MEDIUM')  # 最小置信度
        self.max_orders_per_batch = executor_config.get('max_orders_per_batch', 10)  # 每批最大订单数
        self.enabled = executor_config.get('enabled', True)  # 是否启用策略执行器
        self.auto_start = executor_config.get('auto_start', True)  # 是否自动启动策略执行器
        
        # 核心组件
        self.execution_engine = execution_engine
        self.polymarket_strategy = polymarket_strategy
        self.polymarket_gateway = polymarket_gateway
        
        # 运行状态
        self._running = False
        self._thread = None
        self._stop_event = threading.Event()
        
        # 监控的市场
        self.monitored_markets = executor_config.get('monitored_markets', [])
        
        # 置信度映射（用于比较）
        self.confidence_levels = {
            'LOW': 1,
            'MEDIUM': 2,
            'HIGH': 3
        }
        
        logger.info("策略执行器初始化完成")
    
    def start(self):
        """启动策略执行器"""
        if not self.enabled:
            logger.info("策略执行器已禁用")
            return
        
        if self._running:
            logger.warning("策略执行器已经在运行中")
            return
        
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("策略执行器已启动")
    
    def stop(self):
        """停止策略执行器"""
        if not self._running:
            logger.warning("策略执行器未在运行中")
            return
        
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10)
        self._running = False
        logger.info("策略执行器已停止")
    
    def add_market(self, market_id: str):
        """添加要监控的市场
        
        Args:
            market_id: 市场ID
        """
        if market_id not in self.monitored_markets:
            self.monitored_markets.append(market_id)
            logger.info(f"已添加市场到监控列表: {market_id}")
    
    def remove_market(self, market_id: str):
        """从监控列表中移除市场
        
        Args:
            market_id: 市场ID
        """
        if market_id in self.monitored_markets:
            self.monitored_markets.remove(market_id)
            logger.info(f"已从监控列表中移除市场: {market_id}")
    
    def set_markets(self, market_ids: List[str]):
        """设置要监控的市场列表
        
        Args:
            market_ids: 市场ID列表
        """
        self.monitored_markets = market_ids
        logger.info(f"已设置监控市场列表: {market_ids}")
    
    def _run_loop(self):
        """策略执行器主循环"""
        while not self._stop_event.is_set():
            try:
                if self.monitored_markets:
                    self._execute_strategy()
                else:
                    logger.debug("监控市场列表为空，跳过策略执行")
            except Exception as e:
                logger.error(f"策略执行器主循环错误: {e}")
            
            # 等待下一次检查
            for _ in range(self.check_interval):
                if self._stop_event.is_set():
                    break
                time.sleep(1)
    
    def _execute_strategy(self):
        """执行策略"""
        logger.info(f"开始执行策略，监控市场数: {len(self.monitored_markets)}")
        
        try:
            # 运行策略获取交易建议
            start_time = time.time()
            recommendations = self.polymarket_strategy.run_strategy(self.monitored_markets)
            execution_time = time.time() - start_time
            
            logger.info(f"策略运行完成，耗时: {execution_time:.2f}秒，获取交易建议数: {len(recommendations)}")
            
            # 处理交易建议
            self._process_recommendations(recommendations)
            
            logger.info("策略执行完成")
        except Exception as e:
            logger.error(f"策略执行失败: {e}")
            import traceback
            traceback.print_exc()
    
    def _process_recommendations(self, recommendations: List[Dict[str, Any]]):
        """处理交易建议
        
        Args:
            recommendations: 交易建议列表
        """
        try:
            # 过滤出有效的交易建议
            valid_recommendations = []
            for rec in recommendations:
                if self._is_valid_recommendation(rec):
                    valid_recommendations.append(rec)
            
            logger.info(f"有效交易建议数: {len(valid_recommendations)}")
            
            # 批量处理订单
            if valid_recommendations:
                self._submit_orders(valid_recommendations)
            else:
                logger.info("没有有效的订单需要提交")
        except Exception as e:
            logger.error(f"处理交易建议失败: {e}")
            import traceback
            traceback.print_exc()
    
    def _is_valid_recommendation(self, recommendation: Dict[str, Any]) -> bool:
        """检查交易建议是否有效
        
        Args:
            recommendation: 交易建议
            
        Returns:
            bool: 交易建议是否有效
        """
        try:
            # 检查信号类型
            signal = recommendation.get('signal', 'HOLD')
            if signal == 'HOLD':
                logger.debug(f"交易建议无效 (信号为HOLD): {recommendation.get('market_id')}")
                return False
            
            # 检查置信度
            confidence = recommendation.get('confidence', 'LOW')
            if self.confidence_levels.get(confidence, 0) < self.confidence_levels.get(self.min_confidence, 2):
                logger.debug(f"交易建议无效 (置信度不足): {recommendation.get('market_id')}, 置信度: {confidence}, 最小要求: {self.min_confidence}")
                return False
            
            # 检查订单大小
            order_size = recommendation.get('order_size', Decimal('0'))
            if order_size <= Decimal('0'):
                logger.debug(f"交易建议无效 (订单大小为0): {recommendation.get('market_id')}, 订单大小: {order_size}")
                return False
            
            # 检查市场ID
            market_id = recommendation.get('market_id')
            if not market_id:
                logger.debug("交易建议无效 (缺少市场ID)")
                return False
            
            logger.debug(f"交易建议有效: {market_id}, 信号: {signal}, 置信度: {confidence}, 订单大小: {order_size}")
            return True
        except Exception as e:
            logger.error(f"检查交易建议有效性失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _submit_orders(self, recommendations: List[Dict[str, Any]]):
        """提交订单
        
        Args:
            recommendations: 交易建议列表
        """
        try:
            # 限制每批订单数量
            recommendations = recommendations[:self.max_orders_per_batch]
            
            logger.info(f"处理 {len(recommendations)} 个交易建议，每批最多 {self.max_orders_per_batch} 个订单")
            
            # 准备订单列表
            orders = []
            for i, rec in enumerate(recommendations):
                try:
                    logger.debug(f"处理交易建议 {i+1}/{len(recommendations)}: {rec.get('market_id')}, 信号: {rec.get('signal')}, 置信度: {rec.get('confidence')}")
                    order = self._create_order(rec)
                    if order:
                        orders.append((order, None))  # 暂时不提供市场概率数据
                        logger.info(f"已创建订单: {order.order_id}, 市场: {rec.get('market_id')}, 方向: {order.side}, 数量: {order.quantity}")
                    else:
                        logger.warning(f"创建订单失败，交易建议无效: {rec.get('market_id')}")
                except Exception as e:
                    logger.error(f"创建订单失败 (市场: {rec.get('market_id')}): {e}")
                    import traceback
                    traceback.print_exc()
            
            # 批量提交订单
            if orders:
                logger.info(f"准备提交 {len(orders)} 个订单")
                start_time = time.time()
                result = self.execution_engine.submit_orders_batch(orders)
                execution_time = time.time() - start_time
                logger.info(f"订单提交完成，耗时: {execution_time:.2f}秒，结果: {result}")
            else:
                logger.info("没有有效的订单需要提交")
        except Exception as e:
            logger.error(f"提交订单失败: {e}")
            import traceback
            traceback.print_exc()
    
    def _create_order(self, recommendation: Dict[str, Any]) -> Optional[Order]:
        """根据交易建议创建订单
        
        Args:
            recommendation: 交易建议
            
        Returns:
            Optional[Order]: 创建的订单对象
        """
        try:
            market_id = recommendation.get('market_id')
            signal = recommendation.get('signal')
            order_size = recommendation.get('order_size', Decimal('0'))
            
            if not market_id:
                logger.error("创建订单失败: 缺少市场ID")
                return None
            
            logger.debug(f"开始创建订单: 市场ID={market_id}, 信号={signal}, 订单大小={order_size}")
            
            # 获取市场信息
            try:
                market_info = self.polymarket_gateway.get_market(market_id)
                if not market_info:
                    logger.error(f"获取市场信息失败: {market_id}")
                    return None
                logger.debug(f"获取市场信息成功: {market_info.get('question', market_id)}")
            except Exception as e:
                logger.error(f"获取市场信息失败 (市场ID: {market_id}): {e}")
                return None
            
            # 确定订单方向
            side = 'buy' if signal == 'BUY' else 'sell'
            if signal == 'ARBITRAGE':
                # 对于套利信号，需要根据市场情况确定方向
                best_bid = recommendation.get('best_bid', Decimal('0'))
                best_ask = recommendation.get('best_ask', Decimal('0'))
                if best_bid > best_ask:
                    side = 'buy'
                    logger.debug(f"套利信号 - 选择买入方向: 最佳买入价={best_bid}, 最佳卖出价={best_ask}")
                else:
                    side = 'sell'
                    logger.debug(f"套利信号 - 选择卖出方向: 最佳买入价={best_bid}, 最佳卖出价={best_ask}")
            else:
                logger.debug(f"确定订单方向: {side} (信号: {signal})")
            
            # 创建交易品种
            try:
                instrument = Instrument(
                    symbol=market_id,
                    name=market_info.get('question', market_id),
                    gateway_name='polymarket',
                    precision=2
                )
                logger.debug(f"创建交易品种成功: {instrument.name}")
            except Exception as e:
                logger.error(f"创建交易品种失败: {e}")
                return None
            
            # 创建订单
            try:
                order_id = f"auto_{int(time.time())}_{market_id[:8]}"
                order = Order(
                    order_id=order_id,
                    instrument=instrument,
                    side=side,
                    type='market',  # 使用市价单
                    quantity=order_size,
                    price=None,  # 市价单不需要价格
                    account_id='main_account',
                    timestamp=datetime.now().isoformat()
                )
                
                logger.info(f"创建订单成功: {order.order_id}, 市场: {market_id}, 方向: {side}, 数量: {order_size}")
                return order
            except Exception as e:
                logger.error(f"创建订单对象失败: {e}")
                return None
        except Exception as e:
            logger.error(f"创建订单失败: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def get_status(self) -> Dict[str, Any]:
        """获取策略执行器状态
        
        Returns:
            dict: 策略执行器状态
        """
        return {
            'running': self._running,
            'enabled': self.enabled,
            'auto_start': self.auto_start,
            'check_interval': self.check_interval,
            'min_confidence': self.min_confidence,
            'max_orders_per_batch': self.max_orders_per_batch,
            'monitored_markets': self.monitored_markets,
            'market_count': len(self.monitored_markets)
        }
