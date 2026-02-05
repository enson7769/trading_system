# 交易系统 (Trading System)

交易系统是一个功能强大的交易平台，支持多个交易所的集成，包括Polymarket和币安。系统默认使用真实API连接，提供实时交易功能。

## 项目概述

- **多交易所集成**：支持Polymarket和币安交易所的实时连接
- **实时数据更新**：使用WebSocket实现实时数据推送和页面刷新
- **智能交易策略**：内置概率策略和Polymarket专用策略
- **市场监控**：实时监控市场流动性和大额订单
- **事件驱动**：基于市场事件的交易决策
- **直观的仪表盘**：提供实时交易数据和系统状态监控

## 核心功能

### 1. 交易所集成

#### Polymarket集成
- **完整API支持**：集成Gamma API、CLOB API、Data API和WebSocket API
- **实时市场数据**：获取事件、市场、订单簿和价格数据
- **账户管理**：查询持仓、交易历史和投资组合
- **订单执行**：发送、取消和管理订单

#### 币安集成
- **账户余额查询**：实时获取账户余额
- **充值历史**：查询充值记录
- **提现历史**：查询提现记录
- **提现操作**：支持数字货币提现

### 2. 交易引擎

- **订单管理**：处理订单提交、执行和状态更新
- **风险管理**：基于概率的交易风险评估
- **流动性分析**：评估市场流动性和滑点风险
- **大额订单监控**：跟踪和分析大额订单
- **事件记录**：记录和分析市场事件数据

### 3. 仪表盘

- **实时数据**：通过WebSocket实现数据实时更新
- **多维度监控**：订单状态、市场流动性、事件数据等
- **Polymarket数据**：事件、市场、持仓和投资组合
- **系统状态**：网关连接状态和系统健康度
- **响应式设计**：适配不同屏幕尺寸

## 系统架构

```
trading_system/
├── account/          # 账户管理
├── config/           # 配置文件
├── core/             # 核心模型和枚举
├── dashboard/        # 仪表盘
├── database/         # 数据库管理
├── engine/           # 执行引擎
├── gateways/         # 交易所网关
│   ├── base.py       # 网关抽象基类
│   ├── polymarket_gateway.py  # Polymarket网关
│   └── binance_gateway.py     # 币安网关
├── security/         # 安全相关
├── strategy/         # 交易策略
│   ├── probability_strategy.py  # 概率策略
│   └── polymarket_strategy.py   # Polymarket策略
├── utils/            # 工具函数
├── main.py           # 主程序
├── requirements.txt  # 依赖项
├── start_system.sh   # 系统启动脚本
├── README.md         # 项目文档
└── ...               # 其他文件
```

## 配置说明

### 配置文件

系统使用 `config/config.yaml` 文件进行配置，主要配置项包括：

#### 网关配置

```yaml
# 网关配置
gateways:
  polymarket:
    rpc_url: https://polygon-rpc.com/  # RPC节点URL
    mock: false  # 默认不启用模拟模式
    exchange_address: "0x435AB6645531D3f5391E8B8DA9c0F7b64e6C7e11"  # 交易所合约地址
    usdc_address: "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"  # USDC代币合约地址
    # 账户配置
    address: "0xd5d4b186871b3f33c4dc36a0714975b30fed60e6"  # Polymarket账户地址
    api_key: "019bf930-1295-7dcf-8260-78915aac9bc1"  # Polymarket API Key
    # API端点配置
    gamma_api_url: https://gamma-api.polymarket.com  # Gamma API端点
    clob_api_url: https://clob.polymarket.com  # CLOB API端点
    data_api_url: https://data-api.polymarket.com  # Data API端点
    websocket_url: wss://ws-subscriptions-clob.polymarket.com  # WebSocket API端点
  binance:
    mock: false  # 默认不启用模拟模式
    testnet: false  # 是否使用测试网络
    base_url: https://api.binance.com  # API基础URL
```

#### 账户配置

```yaml
# 账户配置
accounts:
  main_account:
    gateway: polymarket  # 所属网关
    initial_balances:  # 初始余额
      USDC: 10000
  binance_account:
    gateway: binance  # 所属网关
    initial_balances:  # 初始余额
      USDC: 10000
      BTC: 1.0
      ETH: 10.0
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置系统

编辑 `config/config.yaml` 文件，设置您的账户信息和API密钥：

- **Polymarket**：设置 `address` 和 `api_key`
- **币安**：通过环境变量或安全方式设置API密钥

### 3. 启动系统

使用提供的启动脚本同时启动交易系统和仪表盘：

```bash
./start_system.sh
```

系统启动后，您可以：

- 在终端查看交易系统的运行状态
- 在浏览器中访问仪表盘：http://localhost:8501

### 4. 单独启动组件

#### 单独启动交易系统

```bash
python main.py --no-dashboard
```

#### 单独启动仪表盘

```bash
python -m streamlit run dashboard/monitoring.py
```

## 仪表盘使用

1. **访问仪表盘**：在浏览器中打开 http://localhost:8501

2. **主要功能**：
   - **订单状态**：查看订单执行情况和统计数据
   - **市场流动性**：分析市场流动性和滑点风险
   - **事件数据**：查看和分析市场事件
   - **大额订单**：监控大额订单活动
   - **Polymarket数据**：查看事件、市场、持仓和投资组合

3. **实时更新**：
   - 数据通过WebSocket实时更新，无需手动刷新页面
   - 支持手动刷新数据按钮

## 交易策略

### 1. 概率策略

基于市场概率的交易策略，支持配置最小总概率阈值和安全总概率阈值。当市场概率达到安全阈值时，系统会自动执行交易。

### 2. Polymarket策略

专为Polymarket设计的交易策略，包括：
- **市场分析**：分析市场状态和趋势
- **订单簿分析**：评估买卖价差和流动性
- **交易信号生成**：基于市场数据生成交易信号
- **持仓管理**：优化投资组合配置

## 安全注意事项

1. **API密钥管理**：请通过环境变量或安全方式提供API密钥，不要直接硬编码在配置文件中

2. **私钥安全**：私钥等敏感信息请妥善保管，避免泄露

3. **网络安全**：确保网络连接安全，特别是在使用WebSocket时

4. **交易风险**：系统默认使用真实API，请注意交易风险，建议先在小金额下测试

5. **API限制**：使用时请注意各交易所的API调用限制，避免触发限流

## 系统要求

- **Python**：3.8+  
- **网络连接**：稳定的互联网连接
- **硬件要求**：至少2GB RAM，推荐4GB+ RAM
- **操作系统**：支持Windows、macOS和Linux

## 依赖项

请查看 `requirements.txt` 文件获取项目依赖项。

## 故障排除

### 常见问题

1. **API连接失败**：
   - 检查网络连接
   - 验证API密钥是否正确
   - 确认API端点URL是否正确

2. **WebSocket连接断开**：
   - 检查网络稳定性
   - 确认防火墙设置
   - 查看系统日志获取详细错误信息

3. **仪表盘无法访问**：
   - 确认Streamlit是否正常启动
   - 检查端口8501是否被占用
   - 查看终端输出的错误信息

4. **订单执行失败**：
   - 检查账户余额是否充足
   - 验证订单参数是否符合交易所要求
   - 查看系统日志获取详细错误信息

### 日志查看

系统日志会输出到终端和日志文件，您可以通过查看日志获取详细的错误信息和系统状态。

## 许可证

本项目采用MIT许可证。

## 免责声明

本交易系统仅供学习和研究使用，不构成任何投资建议。使用本系统进行实际交易时，风险自担。请在使用前充分了解相关交易所的规则和风险。