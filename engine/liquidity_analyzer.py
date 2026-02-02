from decimal import Decimal
from typing import Dict, List, Any
import pandas as pd
from datetime import datetime, timedelta
from utils.logger import logger

class LiquidityAnalyzer:
    def __init__(self, max_history_per_symbol: int = 10000):
        self.historical_data: Dict[str, List[Dict[str, Any]]] = {}
        self.max_history_per_symbol = max_history_per_symbol
        self._cache: Dict[str, Dict[str, Any]] = {}
    
    def add_historical_data(self, symbol: str, timestamp: datetime, api_price: Decimal, 
                           executed_price: Decimal, size: Decimal) -> None:
        """Add historical trade data for liquidity analysis"""
        try:
            if symbol not in self.historical_data:
                self.historical_data[symbol] = []
            
            # Add new data point
            self.historical_data[symbol].append({
                'timestamp': timestamp,
                'api_price': float(api_price),
                'executed_price': float(executed_price),
                'size': float(size),
                'slippage': float(executed_price) - float(api_price)
            })
            
            # Limit history size to prevent memory issues
            if len(self.historical_data[symbol]) > self.max_history_per_symbol:
                self.historical_data[symbol] = self.historical_data[symbol][-self.max_history_per_symbol:]
            
            # Clear cache for this symbol
            self._clear_cache(symbol)
            
        except Exception as e:
            logger.error(f"Error adding historical data: {e}")
    
    def _clear_cache(self, symbol: str) -> None:
        """Clear cache for a specific symbol"""
        cache_keys = [key for key in self._cache if key.startswith(symbol)]
        for key in cache_keys:
            del self._cache[key]
    
    def analyze_liquidity(self, symbol: str, target_size: Decimal) -> Dict[str, Any]:
        """Analyze liquidity for a given symbol and order size"""
        # Generate cache key
        cache_key = f"{symbol}_{target_size}"
        
        # Check cache
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        try:
            # Validate inputs
            if not symbol or target_size <= Decimal('0'):
                return {
                    'liquidity_rating': 'LOW',
                    'slippage_estimate': Decimal('0.01'),
                    'confidence': 'LOW',
                    'message': 'Invalid input parameters'
                }
            
            # Check if we have enough data
            if symbol not in self.historical_data or len(self.historical_data[symbol]) < 10:
                result = {
                    'liquidity_rating': 'LOW',
                    'slippage_estimate': Decimal('0.01'),
                    'confidence': 'LOW',
                    'message': 'Insufficient historical data'
                }
                self._cache[cache_key] = result
                return result
            
            # Convert to DataFrame for analysis
            df = pd.DataFrame(self.historical_data[symbol])
            
            # Filter recent data (last 7 days)
            cutoff_time = datetime.now() - timedelta(days=7)
            recent_data = df[df['timestamp'] > cutoff_time]
            
            if len(recent_data) < 5:
                result = {
                    'liquidity_rating': 'LOW',
                    'slippage_estimate': Decimal('0.01'),
                    'confidence': 'LOW',
                    'message': 'Insufficient recent data'
                }
                self._cache[cache_key] = result
                return result
            
            # Determine size bucket
            target_size_float = float(target_size)
            target_bucket = self._get_size_bucket(target_size_float)
            
            # Get data for the target bucket
            bucket_data = self._filter_by_size_bucket(recent_data, target_bucket)
            
            if len(bucket_data) == 0:
                result = {
                    'liquidity_rating': 'LOW',
                    'slippage_estimate': Decimal('0.02'),
                    'confidence': 'LOW',
                    'message': f'No historical data for {target_bucket} size bucket'
                }
                self._cache[cache_key] = result
                return result
            
            # Calculate liquidity metrics
            liquidity_metrics = self._calculate_liquidity_metrics(bucket_data)
            
            # Determine liquidity rating
            liquidity_rating = self._calculate_liquidity_rating(liquidity_metrics)
            
            # Calculate confidence level
            confidence = 'HIGH' if len(bucket_data) >= 20 else 'MEDIUM'
            
            result = {
                'liquidity_rating': liquidity_rating,
                'slippage_estimate': Decimal(str(abs(liquidity_metrics['avg_slippage'] + 2 * liquidity_metrics['std_slippage']))),
                'confidence': confidence,
                'message': f'Analyzed {len(bucket_data)} historical trades for {target_bucket} size bucket',
                'avg_slippage': Decimal(str(liquidity_metrics['avg_slippage'])),
                'max_slippage': Decimal(str(liquidity_metrics['max_slippage'])),
                'std_slippage': Decimal(str(liquidity_metrics['std_slippage']))
            }
            
            # Cache result
            self._cache[cache_key] = result
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing liquidity: {e}")
            return {
                'liquidity_rating': 'LOW',
                'slippage_estimate': Decimal('0.01'),
                'confidence': 'LOW',
                'message': f'Error during analysis: {str(e)}'
            }
    
    def _get_size_bucket(self, size: float) -> str:
        """Determine size bucket based on order size"""
        if size >= 100:
            return 'large'
        elif size >= 10:
            return 'medium'
        else:
            return 'small'
    
    def _filter_by_size_bucket(self, data: pd.DataFrame, bucket: str) -> pd.DataFrame:
        """Filter data by size bucket"""
        if bucket == 'large':
            return data[data['size'] >= 100]
        elif bucket == 'medium':
            return data[(data['size'] >= 10) & (data['size'] < 100)]
        else:  # small
            return data[data['size'] < 10]
    
    def _calculate_liquidity_metrics(self, data: pd.DataFrame) -> Dict[str, float]:
        """Calculate liquidity metrics from data"""
        return {
            'avg_slippage': data['slippage'].mean(),
            'max_slippage': data['slippage'].max(),
            'std_slippage': data['slippage'].std()
        }
    
    def _calculate_liquidity_rating(self, metrics: Dict[str, float]) -> str:
        """Calculate liquidity rating based on metrics"""
        avg_slippage = abs(metrics['avg_slippage'])
        std_slippage = metrics['std_slippage']
        
        if avg_slippage < 0.001 and std_slippage < 0.002:
            return 'HIGH'
        elif avg_slippage < 0.005 and std_slippage < 0.005:
            return 'MEDIUM'
        else:
            return 'LOW'
    
    def check_execution_feasibility(self, symbol: str, api_price: Decimal, size: Decimal) -> Dict[str, Any]:
        """Check if execution is feasible based on liquidity"""
        try:
            liquidity_analysis = self.analyze_liquidity(symbol, size)
            
            if liquidity_analysis['liquidity_rating'] == 'LOW':
                return {
                    'feasible': False,
                    'estimated_execution_price': api_price + liquidity_analysis['slippage_estimate'],
                    'risk_level': 'HIGH',
                    'message': 'Low liquidity, high slippage risk'
                }
            
            return {
                'feasible': True,
                'estimated_execution_price': api_price + liquidity_analysis['slippage_estimate'],
                'risk_level': 'LOW' if liquidity_analysis['liquidity_rating'] == 'HIGH' else 'MEDIUM',
                'message': f'Liquidity sufficient for execution, estimated slippage: {liquidity_analysis["slippage_estimate"]}'
            }
        except Exception as e:
            logger.error(f"Error checking execution feasibility: {e}")
            return {
                'feasible': False,
                'estimated_execution_price': api_price,
                'risk_level': 'HIGH',
                'message': f'Error during feasibility check: {str(e)}'
            }

