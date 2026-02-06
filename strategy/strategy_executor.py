from decimal import Decimal
from typing import Dict, List, Optional, Any
from datetime import datetime
from utils.logger import logger
from config.config import config
from strategy.polymarket_strategy import PolymarketStrategy
from engine.execution_engine import ExecutionEngine
from core.models import Order, Instrument
from gateways.polymarket_gateway import PolymarketGateway
from database.database_manager import db_manager
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
        
        # 事件订阅配置
        strategy_config = config.get_strategy_config('event_subscription') or {}
        self.event_subscription_enabled = strategy_config.get('enabled', True)  # 是否启用事件订阅
        self.subscribed_events = strategy_config.get('subscribed_events', [])  # 要订阅的事件列表
        self.event_min_confidence = strategy_config.get('min_confidence', 'MEDIUM')  # 事件触发的最小置信度
        self.max_orders_per_event = strategy_config.get('max_orders_per_event', 5)  # 每个事件的最大订单数
        self.order_size_multiplier = strategy_config.get('order_size_multiplier', 1.0)  # 事件触发的订单大小倍数
        self.cooldown_period = strategy_config.get('cooldown_period', 60)  # 事件触发后的冷却期（秒）
        
        # 事件冷却期跟踪
        self._event_cooldowns = {}
        
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
    
    def _get_selected_outcomes(self, market_id):
        """从数据库中读取选中的结果选项"""
        try:
            query = "SELECT outcome FROM selected_outcomes WHERE market_id = %s AND is_selected = TRUE"
            result = db_manager.execute_query(query, (market_id,))
            if result:
                return [row['outcome'] for row in result]
        except Exception as e:
            logger.error(f"读取选中的结果选项失败: {e}")
        return []
    
    def _execute_strategy(self):
        """执行策略"""
        logger.info(f"开始执行策略，监控市场数: {len(self.monitored_markets)}")
        
        try:
            # 运行策略获取交易建议
            start_time = time.time()
            
            # 为每个市场的选中结果选项获取交易建议
            all_recommendations = []
            for market_id in self.monitored_markets:
                try:
                    # 从数据库中读取选中的结果选项
                    selected_outcomes = self._get_selected_outcomes(market_id)
                    
                    if selected_outcomes:
                        logger.info(f"市场 {market_id} 有 {len(selected_outcomes)} 个选中的结果选项")
                        # 为每个选中的结果选项获取建议
                        for outcome in selected_outcomes:
                            try:
                                recommendation = self.polymarket_strategy.get_trade_recommendation(market_id, outcome)
                                all_recommendations.append(recommendation)
                            except Exception as e:
                                logger.error(f"获取市场 {market_id} 结果选项 {outcome} 的交易建议失败: {e}")
                    else:
                        logger.info(f"市场 {market_id} 没有选中的结果选项，跳过")
                except Exception as e:
                    logger.error(f"获取市场 {market_id} 的交易建议失败: {e}")
            
            execution_time = time.time() - start_time
            
            logger.info(f"策略运行完成，耗时: {execution_time:.2f}秒，获取交易建议数: {len(all_recommendations)}")
            
            # 处理交易建议
            self._process_recommendations(all_recommendations)
            
            logger.info("策略执行完成")
        except Exception as e:
            logger.error(f"策略执行失败: {e}")
            import traceback
            traceback.print_exc()
    
    def execute_m_choose_n_strategy(self, market_id: str, n: int) -> Dict[str, Any]:
        """执行M选N个结果交易策略
        
        Args:
            market_id: 市场ID
            n: 要选择的结果选项数量
            
        Returns:
            dict: 策略执行结果
        """
        logger.info(f"开始执行M选N个结果交易策略: 市场={market_id}, N={n}")
        
        try:
            # 获取市场的所有结果选项
            market_info = self.polymarket_gateway.get_market(market_id)
            if not market_info:
                logger.error(f"获取市场信息失败: {market_id}")
                return {
                    'status': 'error',
                    'message': f'获取市场信息失败: {market_id}'
                }
            
            outcomes = market_info.get('outcomes', [])
            m = len(outcomes)
            
            if n > m:
                logger.error(f"N={n} 大于结果选项总数 M={m}")
                return {
                    'status': 'error',
                    'message': f'N={n} 大于结果选项总数 M={m}'
                }
            
            if n <= 0:
                logger.error(f"N={n} 必须大于0")
                return {
                    'status': 'error',
                    'message': f'N={n} 必须大于0'
                }
            
            logger.info(f"市场 {market_id} 有 {m} 个结果选项，将选择 {n} 个进行交易")
            
            # 为市场的所有结果选项获取交易建议
            start_time = time.time()
            market_recommendations = self.polymarket_strategy.get_trade_recommendations_for_all_outcomes(market_id)
            execution_time = time.time() - start_time
            
            logger.info(f"获取交易建议完成，耗时: {execution_time:.2f}秒，获取交易建议数: {len(market_recommendations)}")
            
            # 过滤出有效的交易建议
            valid_recommendations = []
            for rec in market_recommendations:
                if self._is_valid_recommendation(rec):
                    valid_recommendations.append(rec)
            
            logger.info(f"有效交易建议数: {len(valid_recommendations)}")
            
            # 按置信度排序，选择前N个最佳的交易建议
            if len(valid_recommendations) > n:
                # 按置信度排序
                valid_recommendations.sort(key=lambda x: self.confidence_levels.get(x.get('confidence', 'LOW'), 0), reverse=True)
                # 选择前N个
                selected_recommendations = valid_recommendations[:n]
                logger.info(f"从 {len(valid_recommendations)} 个有效交易建议中选择了 {n} 个最佳的")
            else:
                selected_recommendations = valid_recommendations
                logger.info(f"有效交易建议数不足，仅选择了 {len(selected_recommendations)} 个")
            
            # 提交订单
            if selected_recommendations:
                orders = []
                for i, rec in enumerate(selected_recommendations):
                    try:
                        logger.debug(f"处理交易建议 {i+1}/{len(selected_recommendations)}: {rec.get('market_id')}, 信号: {rec.get('signal')}, 置信度: {rec.get('confidence')}, 结果选项: {rec.get('outcome')}")
                        order = self._create_order(rec)
                        if order:
                            orders.append((order, None))  # 暂时不提供市场概率数据
                            logger.info(f"已创建订单: {order.order_id}, 市场: {rec.get('market_id')}, 结果选项: {rec.get('outcome')}, 方向: {order.side}, 数量: {order.quantity}")
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
            else:
                logger.info("没有有效的交易建议")
            
            return {
                'status': 'success',
                'market_id': market_id,
                'm': m,
                'n': n,
                'selected_count': len(selected_recommendations),
                'selected_outcomes': [rec.get('outcome') for rec in selected_recommendations]
            }
        except Exception as e:
            logger.error(f"执行M选N个结果交易策略失败: {e}")
            import traceback
            traceback.print_exc()
            return {
                'status': 'error',
                'message': str(e)
            }
    
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
            outcome = recommendation.get('outcome')
            
            if not market_id:
                logger.error("创建订单失败: 缺少市场ID")
                return None
            
            logger.debug(f"开始创建订单: 市场ID={market_id}, 结果选项={outcome}, 信号={signal}, 订单大小={order_size}")
            
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
                    base_asset='OUTCOME',
                    quote_asset='USDC',
                    min_order_size=Decimal('1'),
                    tick_size=Decimal('0.01'),
                    gateway_name='polymarket'
                )
                logger.debug(f"创建交易品种成功: {instrument.symbol}")
            except Exception as e:
                logger.error(f"创建交易品种失败: {e}")
                return None
            
            # 创建订单
            try:
                # 为每个结果选项创建唯一的订单ID
                order_id = f"auto_{int(time.time())}_{market_id[:8]}_{outcome[:4] if outcome else 'none'}"
                order = Order(
                    order_id=order_id,
                    instrument=instrument,
                    side=side,
                    type='market',  # 使用市价单
                    quantity=order_size,
                    price=None,  # 市价单不需要价格
                    account_id='main_account',
                    outcome=outcome,
                    timestamp=datetime.now().isoformat()
                )
                
                logger.info(f"创建订单成功: {order.order_id}, 市场: {market_id}, 结果选项: {outcome}, 方向: {side}, 数量: {order_size}")
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
    
    def handle_event(self, event_name: str, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """处理外部事件触发的下单
        
        Args:
            event_name: 事件名称
            event_data: 事件数据
            
        Returns:
            dict: 事件处理结果
        """
        try:
            logger.info(f"收到事件触发: {event_name}")
            
            # 检查事件订阅是否启用
            if not self.event_subscription_enabled:
                logger.warning("事件订阅已禁用")
                return {
                    'event_name': event_name,
                    'status': 'disabled',
                    'reason': '事件订阅已禁用'
                }
            
            # 检查事件是否在订阅列表中
            if event_name not in self.subscribed_events:
                logger.warning(f"事件 {event_name} 不在订阅列表中")
                return {
                    'event_name': event_name,
                    'status': 'not_subscribed',
                    'reason': '事件不在订阅列表中'
                }
            
            # 检查事件冷却期
            if self._is_in_cooldown(event_name):
                logger.warning(f"事件 {event_name} 仍在冷却期中")
                return {
                    'event_name': event_name,
                    'status': 'cooldown',
                    'reason': '事件仍在冷却期中'
                }
            
            # 调用策略的事件处理方法
            event_result = self.polymarket_strategy.handle_event_trigger(event_name, event_data)
            
            # 检查事件处理结果
            if event_result.get('status') != 'processed':
                logger.warning(f"事件处理未完成: {event_result.get('reason', '未知原因')}")
                return event_result
            
            # 处理相关市场的交易信号
            results = event_result.get('results', [])
            if not results:
                return {
                    **event_result,
                    'order_status': 'no_orders'
                }
            
            # 准备订单
            orders = []
            for result in results:
                try:
                    # 检查是否有错误
                    if 'error' in result:
                        logger.error(f"市场 {result.get('market_id')} 分析失败: {result.get('error')}")
                        continue
                    
                    # 获取交易信号
                    signal = result.get('signal', {})
                    market_id = result.get('market_id')
                    order_size = result.get('order_size', Decimal('0'))
                    
                    # 应用订单大小倍数
                    order_size = order_size * Decimal(str(self.order_size_multiplier))
                    
                    # 检查信号是否有效
                    if not self._is_valid_event_signal(signal, order_size):
                        logger.debug(f"信号无效，跳过: {market_id}, 信号: {signal.get('signal')}, 置信度: {signal.get('confidence')}")
                        continue
                    
                    # 检查每事件订单数限制
                    if len(orders) >= self.max_orders_per_event:
                        logger.warning(f"已达到每事件最大订单数: {self.max_orders_per_event}")
                        break
                    
                    # 创建订单
                    order = self._create_order_from_event(signal, market_id, order_size)
                    if order:
                        orders.append((order, None))  # 暂时不提供市场概率数据
                        logger.info(f"已为事件创建订单: {order.order_id}, 市场: {market_id}, 方向: {order.side}, 数量: {order.quantity}")
                    else:
                        logger.warning(f"为事件创建订单失败: {market_id}")
                        
                except Exception as e:
                    logger.error(f"处理事件结果失败: {e}")
                    import traceback
                    traceback.print_exc()
            
            # 批量提交订单
            order_result = None
            if orders:
                logger.info(f"准备为事件提交 {len(orders)} 个订单")
                start_time = time.time()
                order_result = self.execution_engine.submit_orders_batch(orders)
                execution_time = time.time() - start_time
                logger.info(f"事件订单提交完成，耗时: {execution_time:.2f}秒，结果: {order_result}")
                
                # 设置事件冷却期
                self._set_cooldown(event_name)
            else:
                logger.info("没有有效的事件订单需要提交")
            
            return {
                **event_result,
                'order_status': 'submitted' if orders else 'no_orders',
                'order_count': len(orders),
                'order_result': order_result
            }
            
        except Exception as e:
            logger.error(f"处理事件失败: {e}")
            import traceback
            traceback.print_exc()
            return {
                'event_name': event_name,
                'status': 'error',
                'error': str(e)
            }
    
    def _is_in_cooldown(self, event_name: str) -> bool:
        """检查事件是否在冷却期中
        
        Args:
            event_name: 事件名称
            
        Returns:
            bool: 是否在冷却期中
        """
        try:
            cooldown_time = self._event_cooldowns.get(event_name, 0)
            current_time = time.time()
            return current_time < cooldown_time
        except Exception as e:
            logger.error(f"检查事件冷却期失败: {e}")
            return False
    
    def _set_cooldown(self, event_name: str):
        """设置事件冷却期
        
        Args:
            event_name: 事件名称
        """
        try:
            current_time = time.time()
            cooldown_time = current_time + self.cooldown_period
            self._event_cooldowns[event_name] = cooldown_time
            logger.info(f"为事件 {event_name} 设置冷却期，持续 {self.cooldown_period} 秒")
        except Exception as e:
            logger.error(f"设置事件冷却期失败: {e}")
    
    def _is_valid_event_signal(self, signal: Dict[str, Any], order_size: Decimal) -> bool:
        """检查事件触发的信号是否有效
        
        Args:
            signal: 交易信号
            order_size: 订单大小
            
        Returns:
            bool: 信号是否有效
        """
        try:
            # 检查信号类型
            signal_type = signal.get('signal', 'HOLD')
            if signal_type == 'HOLD':
                return False
            
            # 检查置信度
            confidence = signal.get('confidence', 'LOW')
            if self.confidence_levels.get(confidence, 0) < self.confidence_levels.get(self.event_min_confidence, 2):
                return False
            
            # 检查订单大小
            if order_size <= Decimal('0'):
                return False
            
            return True
        except Exception as e:
            logger.error(f"检查事件信号有效性失败: {e}")
            return False
    
    def _create_order_from_event(self, signal: Dict[str, Any], market_id: str, order_size: Decimal) -> Optional[Order]:
        """根据事件触发的信号创建订单
        
        Args:
            signal: 交易信号
            market_id: 市场ID
            order_size: 订单大小
            
        Returns:
            Optional[Order]: 创建的订单对象
        """
        try:
            signal_type = signal.get('signal')
            outcome = signal.get('outcome')
            
            if not market_id:
                logger.error("创建订单失败: 缺少市场ID")
                return None
            
            logger.debug(f"开始为事件创建订单: 市场ID={market_id}, 结果选项={outcome}, 信号={signal_type}, 订单大小={order_size}")
            
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
            side = 'buy' if signal_type == 'BUY' else 'sell'
            if signal_type == 'ARBITRAGE':
                # 对于套利信号，需要根据市场情况确定方向
                best_bid = signal.get('best_bid', Decimal('0'))
                best_ask = signal.get('best_ask', Decimal('0'))
                if best_bid > best_ask:
                    side = 'buy'
                    logger.debug(f"套利信号 - 选择买入方向: 最佳买入价={best_bid}, 最佳卖出价={best_ask}")
                else:
                    side = 'sell'
                    logger.debug(f"套利信号 - 选择卖出方向: 最佳买入价={best_bid}, 最佳卖出价={best_ask}")
            else:
                logger.debug(f"确定订单方向: {side} (信号: {signal_type})")
            
            # 创建交易品种
            try:
                instrument = Instrument(
                    symbol=market_id,
                    base_asset='OUTCOME',
                    quote_asset='USDC',
                    min_order_size=Decimal('1'),
                    tick_size=Decimal('0.01'),
                    gateway_name='polymarket'
                )
                logger.debug(f"创建交易品种成功: {instrument.symbol}")
            except Exception as e:
                logger.error(f"创建交易品种失败: {e}")
                return None
            
            # 创建订单
            try:
                # 为每个结果选项创建唯一的订单ID
                order_id = f"event_{int(time.time())}_{market_id[:8]}_{outcome[:4] if outcome else 'none'}"
                order = Order(
                    order_id=order_id,
                    instrument=instrument,
                    side=side,
                    type='market',  # 使用市价单
                    quantity=order_size,
                    price=None,  # 市价单不需要价格
                    account_id='main_account',
                    outcome=outcome,
                    timestamp=datetime.now().isoformat()
                )
                
                logger.info(f"为事件创建订单成功: {order.order_id}, 市场: {market_id}, 结果选项: {outcome}, 方向: {side}, 数量: {order_size}")
                return order
            except Exception as e:
                logger.error(f"创建订单对象失败: {e}")
                return None
        except Exception as e:
            logger.error(f"为事件创建订单失败: {e}")
            import traceback
            traceback.print_exc()
            return None
