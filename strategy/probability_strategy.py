from decimal import Decimal
from typing import Dict, Optional, Tuple, Any
from utils.logger import logger
from config.config import config

class ProbabilityStrategy:
    """概率策略类"""
    
    def __init__(self, 
                 min_total_probability: Decimal = None,
                 safe_total_probability: Decimal = None):
        """使用可配置的阈值初始化概率策略
        
        Args:
            min_total_probability: 最小总概率阈值
            safe_total_probability: 安全总概率阈值
        """
        # 加载配置
        strategy_config = config.get_strategy_config('probability')
        
        # 使用提供的值或配置值或默认值
        if min_total_probability is None:
            min_total_probability = Decimal(str(strategy_config.get('min_total_probability', 90)))
        if safe_total_probability is None:
            safe_total_probability = Decimal(str(strategy_config.get('safe_total_probability', 97)))
        
        # 验证阈值
        if min_total_probability < Decimal('0') or safe_total_probability > Decimal('100'):
            raise ValueError("概率阈值必须在0到100之间")
        if min_total_probability > safe_total_probability:
            raise ValueError("最小概率阈值必须小于安全阈值")
        
        self.min_total_probability = min_total_probability
        self.safe_total_probability = safe_total_probability
    
    def check_probability(self, no_change_prob: Decimal, decrease_25bps_prob: Decimal) -> Tuple[bool, Optional[str]]:
        """检查概率条件是否满足交易要求
        
        Args:
            no_change_prob: 无变化概率
            decrease_25bps_prob: 下降25个基点的概率
            
        Returns:
            (是否可以交易, 消息)
        """
        try:
            # 验证输入
            if no_change_prob < Decimal('0') or decrease_25bps_prob < Decimal('0'):
                return False, "不允许负概率"
            if no_change_prob > Decimal('100') or decrease_25bps_prob > Decimal('100'):
                return False, "概率不能超过100"
            
            total_prob = no_change_prob + decrease_25bps_prob
            
            if total_prob >= self.safe_total_probability:
                return True, None
            elif total_prob >= self.min_total_probability:
                return True, f"总概率 {total_prob} 低于 {self.safe_total_probability}，请谨慎操作"
            else:
                return False, f"总概率 {total_prob} < {self.min_total_probability}，需要业务判断"
        except Exception as e:
            logger.error(f"检查概率时出错: {e}")
            return False, f"概率计算错误: {str(e)}"
    
    def analyze_market_probabilities(self, market_data: Dict[str, Decimal]) -> Dict[str, Any]:
        """分析市场概率并确定交易资格
        
        Args:
            market_data: 市场数据，包含概率信息
            
        Returns:
            分析结果，包含概率、是否可以交易等信息
        """
        try:
            # 验证输入
            if not isinstance(market_data, dict):
                return {
                    'no_change_prob': Decimal('0'),
                    'decrease_25bps_prob': Decimal('0'),
                    'total_prob': Decimal('0'),
                    'can_trade': False,
                    'message': '无效的市场数据格式'
                }
            
            # 提取概率
            no_change_prob = market_data.get('no_change', Decimal('0'))
            decrease_25bps_prob = market_data.get('25bps_decrease', Decimal('0'))
            
            # 确保值是Decimal类型
            if not isinstance(no_change_prob, Decimal):
                no_change_prob = Decimal(str(no_change_prob))
            if not isinstance(decrease_25bps_prob, Decimal):
                decrease_25bps_prob = Decimal(str(decrease_25bps_prob))
            
            can_trade, message = self.check_probability(no_change_prob, decrease_25bps_prob)
            total_prob = no_change_prob + decrease_25bps_prob
            
            return {
                'no_change_prob': no_change_prob,
                'decrease_25bps_prob': decrease_25bps_prob,
                'total_prob': total_prob,
                'can_trade': can_trade,
                'message': message,
                'thresholds': {
                    'min_total_probability': self.min_total_probability,
                    'safe_total_probability': self.safe_total_probability
                }
            }
        except Exception as e:
            logger.error(f"分析市场概率时出错: {e}")
            return {
                'no_change_prob': Decimal('0'),
                'decrease_25bps_prob': Decimal('0'),
                'total_prob': Decimal('0'),
                'can_trade': False,
                'message': f'分析错误: {str(e)}'
            }
    
    def get_trade_recommendation(self, market_data: Dict[str, Decimal]) -> Dict[str, Any]:
        """基于概率获取综合交易建议
        
        Args:
            market_data: 市场数据，包含概率信息
            
        Returns:
            交易建议，包含分析结果、推荐操作和置信度
        """
        analysis = self.analyze_market_probabilities(market_data)
        
        if analysis['can_trade']:
            if analysis['total_prob'] >= self.safe_total_probability:
                recommendation = 'STRONG_BUY'
                confidence = 'HIGH'
            else:
                recommendation = 'CAUTIOUS_BUY'
                confidence = 'MEDIUM'
        else:
            recommendation = 'HOLD'
            confidence = 'LOW'
        
        return {
            **analysis,
            'recommendation': recommendation,
            'confidence': confidence
        }
