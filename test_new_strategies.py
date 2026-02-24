#!/usr/bin/env python3
"""
测试新添加的策略：凯利公式、BS公式、最小二乘回归、向量自回归
"""

from decimal import Decimal
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from strategy.polymarket_strategy import PolymarketStrategy
from gateways.polymarket_gateway import PolymarketGateway
from security.credential_manager import CredentialManager

class TestNewStrategies:
    """测试新添加的策略"""
    
    def __init__(self):
        """初始化测试类"""
        # 创建模拟的Polymarket网关实例
        self.credential_manager = CredentialManager()
        self.polymarket_gateway = PolymarketGateway(
            rpc_url='https://polygon-rpc.com/',
            credential_manager=self.credential_manager,
            mock=True
        )
        
        # 创建Polymarket策略实例
        self.polymarket_strategy = PolymarketStrategy(
            gateway=self.polymarket_gateway
        )
    
    def test_kelly_criterion(self):
        """测试凯利公式"""
        print("\n=== 测试凯利公式 ===")
        
        # 测试用例1：高胜率，高赔率
        win_prob = 0.6
        win_loss_ratio = 2.0
        k = self.polymarket_strategy.kelly_criterion(win_prob, win_loss_ratio)
        print(f"测试用例1 - 胜率: {win_prob}, 赔率: {win_loss_ratio}, 最优仓位: {k:.4f}")
        
        # 测试用例2：低胜率，低赔率
        win_prob = 0.4
        win_loss_ratio = 1.0
        k = self.polymarket_strategy.kelly_criterion(win_prob, win_loss_ratio)
        print(f"测试用例2 - 胜率: {win_prob}, 赔率: {win_loss_ratio}, 最优仓位: {k:.4f}")
        
        # 测试用例3：边界情况 - 胜率为0
        win_prob = 0.0
        win_loss_ratio = 2.0
        k = self.polymarket_strategy.kelly_criterion(win_prob, win_loss_ratio)
        print(f"测试用例3 - 胜率: {win_prob}, 赔率: {win_loss_ratio}, 最优仓位: {k:.4f}")
        
        # 测试用例4：边界情况 - 赔率为0
        win_prob = 0.6
        win_loss_ratio = 0.0
        k = self.polymarket_strategy.kelly_criterion(win_prob, win_loss_ratio)
        print(f"测试用例4 - 胜率: {win_prob}, 赔率: {win_loss_ratio}, 最优仓位: {k:.4f}")
    
    def test_black_scholes(self):
        """测试BS公式"""
        print("\n=== 测试BS公式 ===")
        
        # 测试用例1：看涨期权
        s = 100.0  # 当前价格
        k = 100.0  # 行权价格
        t = 1.0    # 到期时间（年）
        r = 0.05   # 无风险利率
        sigma = 0.2  # 波动率
        option_type = 'call'
        price = self.polymarket_strategy.black_scholes(s, k, t, r, sigma, option_type)
        print(f"测试用例1 - 看涨期权价格: {price:.4f}")
        
        # 测试用例2：看跌期权
        option_type = 'put'
        price = self.polymarket_strategy.black_scholes(s, k, t, r, sigma, option_type)
        print(f"测试用例2 - 看跌期权价格: {price:.4f}")
        
        # 测试用例3：不同波动率
        sigma = 0.3
        option_type = 'call'
        price = self.polymarket_strategy.black_scholes(s, k, t, r, sigma, option_type)
        print(f"测试用例3 - 波动率=0.3的看涨期权价格: {price:.4f}")
    
    def test_linear_regression(self):
        """测试最小二乘回归"""
        print("\n=== 测试最小二乘回归 ===")
        
        # 测试用例1：线性关系
        x = [1, 2, 3, 4, 5]
        y = [2, 4, 6, 8, 10]  # y = 2x
        result = self.polymarket_strategy.linear_regression(x, y)
        print(f"测试用例1 - 斜率: {result['slope']:.4f}, 截距: {result['intercept']:.4f}, R²: {result['r_squared']:.4f}")
        
        # 测试用例2：非线性关系
        x = [1, 2, 3, 4, 5]
        y = [1, 3, 6, 10, 15]  # y = x(x+1)/2
        result = self.polymarket_strategy.linear_regression(x, y)
        print(f"测试用例2 - 斜率: {result['slope']:.4f}, 截距: {result['intercept']:.4f}, R²: {result['r_squared']:.4f}")
        
        # 测试用例3：边界情况 - 数据长度不足
        x = [1]
        y = [2]
        result = self.polymarket_strategy.linear_regression(x, y)
        print(f"测试用例3 - 斜率: {result['slope']:.4f}, 截距: {result['intercept']:.4f}, R²: {result['r_squared']:.4f}, 错误: {result['error']}")
    
    def test_vector_autoregression(self):
        """测试向量自回归"""
        print("\n=== 测试向量自回归 ===")
        
        # 测试用例1：简单的多变量时间序列
        data = [
            [1, 2],
            [2, 3],
            [3, 4],
            [4, 5],
            [5, 6]
        ]
        lag = 1
        result = self.polymarket_strategy.vector_autoregression(data, lag)
        print(f"测试用例1 - 滞后阶数: {lag}, 变量数量: {result['variable_count']}")
        for coeff in result['coefficients']:
            print(f"  变量 {coeff['variable']} - 斜率: {coeff['slope']:.4f}, 截距: {coeff['intercept']:.4f}, R²: {coeff['r_squared']:.4f}")
        
        # 测试用例2：边界情况 - 数据长度不足
        data = [[1, 2], [2, 3]]
        lag = 2
        result = self.polymarket_strategy.vector_autoregression(data, lag)
        print(f"测试用例2 - 滞后阶数: {lag}, 错误: {result['error']}")
    
    def run_all_tests(self):
        """运行所有测试"""
        print("开始测试新添加的策略...")
        
        self.test_kelly_criterion()
        self.test_black_scholes()
        self.test_linear_regression()
        self.test_vector_autoregression()
        
        print("\n所有测试完成！")

if __name__ == "__main__":
    test = TestNewStrategies()
    test.run_all_tests()
