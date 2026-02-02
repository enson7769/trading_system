from decimal import Decimal
from typing import Dict, Optional, Tuple, Any
from utils.logger import logger
from config.config import config

class ProbabilityStrategy:
    def __init__(self, 
                 min_total_probability: Decimal = None,
                 safe_total_probability: Decimal = None):
        """Initialize probability strategy with configurable thresholds"""
        # Load configuration
        strategy_config = config.get_strategy_config('probability')
        
        # Use provided value or config value or default
        if min_total_probability is None:
            min_total_probability = Decimal(str(strategy_config.get('min_total_probability', 90)))
        if safe_total_probability is None:
            safe_total_probability = Decimal(str(strategy_config.get('safe_total_probability', 97)))
        
        # Validate thresholds
        if min_total_probability < Decimal('0') or safe_total_probability > Decimal('100'):
            raise ValueError("Probability thresholds must be between 0 and 100")
        if min_total_probability > safe_total_probability:
            raise ValueError("Minimum probability threshold must be less than safe threshold")
        
        self.min_total_probability = min_total_probability
        self.safe_total_probability = safe_total_probability
    
    def check_probability(self, no_change_prob: Decimal, decrease_25bps_prob: Decimal) -> Tuple[bool, Optional[str]]:
        """Check if probability conditions are met for trading"""
        try:
            # Validate inputs
            if no_change_prob < Decimal('0') or decrease_25bps_prob < Decimal('0'):
                return False, "Negative probabilities are not allowed"
            if no_change_prob > Decimal('100') or decrease_25bps_prob > Decimal('100'):
                return False, "Probabilities cannot exceed 100"
            
            total_prob = no_change_prob + decrease_25bps_prob
            
            if total_prob >= self.safe_total_probability:
                return True, None
            elif total_prob >= self.min_total_probability:
                return True, f"Total probability {total_prob} below {self.safe_total_probability}, proceed with caution"
            else:
                return False, f"Total probability {total_prob} < {self.min_total_probability}, requires business judgment"
        except Exception as e:
            logger.error(f"Error checking probabilities: {e}")
            return False, f"Error in probability calculation: {str(e)}"
    
    def analyze_market_probabilities(self, market_data: Dict[str, Decimal]) -> Dict[str, Any]:
        """Analyze market probabilities and determine trading eligibility"""
        try:
            # Validate input
            if not isinstance(market_data, dict):
                return {
                    'no_change_prob': Decimal('0'),
                    'decrease_25bps_prob': Decimal('0'),
                    'total_prob': Decimal('0'),
                    'can_trade': False,
                    'message': 'Invalid market data format'
                }
            
            # Extract probabilities
            no_change_prob = market_data.get('no_change', Decimal('0'))
            decrease_25bps_prob = market_data.get('25bps_decrease', Decimal('0'))
            
            # Ensure values are Decimals
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
            logger.error(f"Error analyzing market probabilities: {e}")
            return {
                'no_change_prob': Decimal('0'),
                'decrease_25bps_prob': Decimal('0'),
                'total_prob': Decimal('0'),
                'can_trade': False,
                'message': f'Error in analysis: {str(e)}'
            }
    
    def get_trade_recommendation(self, market_data: Dict[str, Decimal]) -> Dict[str, Any]:
        """Get comprehensive trade recommendation based on probabilities"""
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
