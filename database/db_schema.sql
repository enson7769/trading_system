-- MySQL Database Schema for Trading System
-- Version: 1.0
-- Date: 2026-02-02

-- Create database if not exists
CREATE DATABASE IF NOT EXISTS trading_system CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE trading_system;

-- Drop tables if they exist (for development only)
DROP TABLE IF EXISTS liquidity_data;
DROP TABLE IF EXISTS large_orders;
DROP TABLE IF EXISTS events;
DROP TABLE IF EXISTS order_history;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS accounts;
DROP TABLE IF EXISTS instruments;

-- Instruments table (交易对表)
CREATE TABLE instruments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    symbol VARCHAR(100) NOT NULL UNIQUE,
    base_asset VARCHAR(50) NOT NULL,
    quote_asset VARCHAR(50) NOT NULL,
    min_order_size DECIMAL(20, 8) NOT NULL,
    tick_size DECIMAL(20, 8) NOT NULL,
    gateway_name VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_symbol (symbol),
    INDEX idx_gateway (gateway_name)
);

-- Accounts table (账户表)
CREATE TABLE accounts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    account_id VARCHAR(100) NOT NULL UNIQUE,
    gateway_name VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_account_id (account_id),
    INDEX idx_gateway (gateway_name)
);

-- Account balances table (账户余额表)
CREATE TABLE account_balances (
    id INT AUTO_INCREMENT PRIMARY KEY,
    account_id VARCHAR(100) NOT NULL,
    asset VARCHAR(50) NOT NULL,
    balance DECIMAL(20, 8) NOT NULL DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES accounts(account_id) ON DELETE CASCADE,
    UNIQUE KEY idx_account_asset (account_id, asset),
    INDEX idx_account (account_id)
);

-- Orders table (订单表)
CREATE TABLE orders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_id VARCHAR(100) NOT NULL UNIQUE,
    account_id VARCHAR(100) NOT NULL,
    instrument_id INT NOT NULL,
    side VARCHAR(10) NOT NULL,  -- BUY or SELL
    type VARCHAR(10) NOT NULL,  -- MARKET or LIMIT
    quantity DECIMAL(20, 8) NOT NULL,
    price DECIMAL(20, 8) NULL,  -- NULL for market orders
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',  -- PENDING, FILLED, REJECTED, CANCELLED
    filled_qty DECIMAL(20, 8) NOT NULL DEFAULT 0,
    gateway_order_id VARCHAR(100) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES accounts(account_id) ON DELETE CASCADE,
    FOREIGN KEY (instrument_id) REFERENCES instruments(id) ON DELETE CASCADE,
    INDEX idx_order_id (order_id),
    INDEX idx_account (account_id),
    INDEX idx_instrument (instrument_id),
    INDEX idx_status (status),
    INDEX idx_created_at (created_at)
);

-- Order history table (订单历史表)
CREATE TABLE order_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_id VARCHAR(100) NOT NULL,
    account_id VARCHAR(100) NOT NULL,
    instrument_id INT NOT NULL,
    side VARCHAR(10) NOT NULL,
    type VARCHAR(10) NOT NULL,
    quantity DECIMAL(20, 8) NOT NULL,
    price DECIMAL(20, 8) NULL,
    status VARCHAR(20) NOT NULL,
    filled_qty DECIMAL(20, 8) NOT NULL,
    gateway_order_id VARCHAR(100) NULL,
    execution_result JSON NULL,  -- Store execution details as JSON
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE,
    FOREIGN KEY (account_id) REFERENCES accounts(account_id) ON DELETE CASCADE,
    FOREIGN KEY (instrument_id) REFERENCES instruments(id) ON DELETE CASCADE,
    INDEX idx_order_id (order_id),
    INDEX idx_account (account_id),
    INDEX idx_recorded_at (recorded_at)
);

-- Events table (事件数据表)
CREATE TABLE events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    event_name VARCHAR(100) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    data JSON NOT NULL,  -- Store event data as JSON
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_event_name (event_name),
    INDEX idx_timestamp (timestamp),
    INDEX idx_recorded_at (recorded_at)
);

-- Large orders table (大额订单表)
CREATE TABLE large_orders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_id VARCHAR(100) NOT NULL,
    instrument_id INT NOT NULL,
    account_id VARCHAR(100) NOT NULL,
    side VARCHAR(10) NOT NULL,
    quantity DECIMAL(20, 8) NOT NULL,
    price DECIMAL(20, 8) NULL,
    gateway_name VARCHAR(50) NOT NULL,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE,
    FOREIGN KEY (instrument_id) REFERENCES instruments(id) ON DELETE CASCADE,
    FOREIGN KEY (account_id) REFERENCES accounts(account_id) ON DELETE CASCADE,
    INDEX idx_order_id (order_id),
    INDEX idx_instrument (instrument_id),
    INDEX idx_account (account_id),
    INDEX idx_recorded_at (recorded_at)
);

-- Liquidity data table (流动性数据表)
CREATE TABLE liquidity_data (
    id INT AUTO_INCREMENT PRIMARY KEY,
    instrument_id INT NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    order_size DECIMAL(20, 8) NOT NULL,
    liquidity_rating VARCHAR(10) NOT NULL,  -- LOW, MEDIUM, HIGH
    slippage_estimate DECIMAL(10, 6) NOT NULL,
    confidence VARCHAR(10) NOT NULL,  -- LOW, MEDIUM, HIGH
    message VARCHAR(255) NULL,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (instrument_id) REFERENCES instruments(id) ON DELETE CASCADE,
    INDEX idx_instrument (instrument_id),
    INDEX idx_timestamp (timestamp),
    INDEX idx_recorded_at (recorded_at)
);

-- Insert sample data
-- Sample instrument
INSERT INTO instruments (symbol, base_asset, quote_asset, min_order_size, tick_size, gateway_name)
VALUES ('0x1234...abcd', 'USDC', 'USDC', 1, 0.01, 'polymarket');

-- Sample account
INSERT INTO accounts (account_id, gateway_name)
VALUES ('main_account', 'polymarket');

-- Sample account balance
INSERT INTO account_balances (account_id, asset, balance)
VALUES ('main_account', 'USDC', 10000);

-- Create stored procedures and functions if needed
-- Example: Stored procedure to get order statistics
DELIMITER //
CREATE PROCEDURE GetOrderStats()
BEGIN
    SELECT 
        COUNT(*) AS total_orders,
        SUM(CASE WHEN status = 'FILLED' THEN 1 ELSE 0 END) AS filled_orders,
        SUM(CASE WHEN status = 'PENDING' THEN 1 ELSE 0 END) AS pending_orders,
        SUM(CASE WHEN status = 'REJECTED' THEN 1 ELSE 0 END) AS rejected_orders,
        SUM(quantity) AS total_size
    FROM orders;
END //
DELIMITER ;

-- Example: Stored procedure to get large orders summary
DELIMITER //
CREATE PROCEDURE GetLargeOrdersSummary(IN days INT)
BEGIN
    SELECT 
        COUNT(*) AS total_large_orders,
        SUM(quantity) AS total_quantity,
        AVG(quantity) AS average_quantity
    FROM large_orders
    WHERE recorded_at >= NOW() - INTERVAL days DAY;
END //
DELIMITER ;

-- Example: Stored procedure to get recent events
DELIMITER //
CREATE PROCEDURE GetRecentEvents(IN days INT, IN limit_count INT)
BEGIN
    SELECT 
        event_name,
        timestamp,
        data
    FROM events
    WHERE timestamp >= NOW() - INTERVAL days DAY
    ORDER BY timestamp DESC
    LIMIT limit_count;
END //
DELIMITER ;
