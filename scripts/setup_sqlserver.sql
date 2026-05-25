-- ============================================================
-- ETL QA Demo Database Setup
-- Creates realistic source/target tables with intentional
-- data defects so you can see the QA tool catch them.
--
-- Run this in SQL Server Management Studio (SSMS)
-- against your local SQL Server instance.
--
-- Author : Satish Panchumarthy
-- GitHub : github.com/panchumarthy
-- ============================================================

-- Create and use demo database
IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = 'ETL_QA_Demo')
    CREATE DATABASE ETL_QA_Demo;
GO

USE ETL_QA_Demo;
GO

-- ── Drop tables if re-running ────────────────────────────────
IF OBJECT_ID('dbo.securities_target', 'U') IS NOT NULL DROP TABLE dbo.securities_target;
IF OBJECT_ID('dbo.securities_source', 'U') IS NOT NULL DROP TABLE dbo.securities_source;
IF OBJECT_ID('dbo.orders_target',     'U') IS NOT NULL DROP TABLE dbo.orders_target;
IF OBJECT_ID('dbo.orders_source',     'U') IS NOT NULL DROP TABLE dbo.orders_source;
IF OBJECT_ID('dbo.customers',         'U') IS NOT NULL DROP TABLE dbo.customers;
GO

-- ============================================================
-- TABLE 1: securities_source  (simulates Broadridge source feed)
-- ============================================================
CREATE TABLE dbo.securities_source (
    trade_id        INT             NOT NULL,
    cusip           VARCHAR(9)      NOT NULL,
    trade_date      DATE            NOT NULL,
    settlement_date DATE            NOT NULL,
    account_id      VARCHAR(20)     NOT NULL,
    security_desc   VARCHAR(100)    NULL,
    quantity        DECIMAL(18,4)   NOT NULL,
    price           DECIMAL(18,6)   NOT NULL,
    trade_amount    DECIMAL(18,2)   NOT NULL,
    currency        VARCHAR(3)      NOT NULL,
    trade_type      VARCHAR(10)     NOT NULL,
    broker_code     VARCHAR(10)     NULL,
    load_date       DATE            NOT NULL DEFAULT GETDATE()
);
GO

-- ============================================================
-- TABLE 2: securities_target  (simulates data warehouse target)
-- ============================================================
CREATE TABLE dbo.securities_target (
    trade_id        INT             NOT NULL,
    cusip           VARCHAR(9)      NOT NULL,
    trade_date      DATE            NOT NULL,
    settlement_date DATE            NOT NULL,
    account_id      VARCHAR(20)     NOT NULL,
    security_desc   VARCHAR(100)    NULL,
    quantity        DECIMAL(18,4)   NOT NULL,
    price           DECIMAL(18,6)   NOT NULL,
    trade_amount    DECIMAL(18,2)   NOT NULL,
    currency        VARCHAR(3)      NOT NULL,
    trade_type      VARCHAR(10)     NOT NULL,
    broker_code     VARCHAR(10)     NULL,
    load_date       DATE            NOT NULL DEFAULT GETDATE()
);
GO

-- ============================================================
-- TABLE 3: customers  (lookup / parent table)
-- ============================================================
CREATE TABLE dbo.customers (
    account_id      VARCHAR(20)     NOT NULL PRIMARY KEY,
    customer_name   VARCHAR(100)    NOT NULL,
    region          VARCHAR(50)     NOT NULL,
    account_type    VARCHAR(20)     NOT NULL
);
GO

-- ============================================================
-- TABLE 4: orders_source  (simulates order management source)
-- ============================================================
CREATE TABLE dbo.orders_source (
    order_id        INT             NOT NULL,
    account_id      VARCHAR(20)     NOT NULL,
    order_date      DATE            NOT NULL,
    product_code    VARCHAR(20)     NOT NULL,
    quantity        INT             NOT NULL,
    unit_price      DECIMAL(10,2)   NOT NULL,
    total_amount    DECIMAL(12,2)   NOT NULL,
    status          VARCHAR(20)     NOT NULL,
    load_date       DATE            NOT NULL DEFAULT GETDATE()
);
GO

-- ============================================================
-- TABLE 5: orders_target
-- ============================================================
CREATE TABLE dbo.orders_target (
    order_id        INT             NOT NULL,
    account_id      VARCHAR(20)     NOT NULL,
    order_date      DATE            NOT NULL,
    product_code    VARCHAR(20)     NOT NULL,
    quantity        INT             NOT NULL,
    unit_price      DECIMAL(10,2)   NOT NULL,
    total_amount    DECIMAL(12,2)   NOT NULL,
    status          VARCHAR(20)     NOT NULL,
    load_date       DATE            NOT NULL DEFAULT GETDATE()
);
GO

-- ============================================================
-- SEED: customers
-- ============================================================
INSERT INTO dbo.customers VALUES
('ACC001', 'Goldman Sachs Asset Mgmt',  'Northeast', 'Institutional'),
('ACC002', 'BlackRock Fund Advisors',   'Northeast', 'Institutional'),
('ACC003', 'Vanguard Group',            'Mid-Atlantic', 'Institutional'),
('ACC004', 'Fidelity Investments',      'Northeast', 'Institutional'),
('ACC005', 'JP Morgan Securities',      'Northeast', 'Prime Broker'),
('ACC006', 'Morgan Stanley Wealth',     'Northeast', 'Wealth Mgmt'),
('ACC007', 'Charles Schwab Corp',       'West',      'Retail Broker'),
('ACC008', 'T. Rowe Price Group',       'Mid-Atlantic', 'Institutional'),
('ACC009', 'Wellington Management',     'Northeast', 'Institutional'),
('ACC010', 'State Street Global',       'Northeast', 'Custody');
GO

-- ============================================================
-- SEED: securities_source (100 trades — clean data)
-- ============================================================
INSERT INTO dbo.securities_source
    (trade_id, cusip, trade_date, settlement_date, account_id,
     security_desc, quantity, price, trade_amount, currency, trade_type, broker_code, load_date)
VALUES
(1001,'037833100','2026-05-21','2026-05-23','ACC001','Apple Inc Common Stock',         500.0000,  189.250000,  94625.00,'USD','BUY', 'GS01','2026-05-21'),
(1002,'594918104','2026-05-21','2026-05-23','ACC001','Microsoft Corp Common Stock',    200.0000,  415.300000,  83060.00,'USD','BUY', 'GS01','2026-05-21'),
(1003,'023135106','2026-05-21','2026-05-23','ACC002','Amazon.com Inc',                  150.0000,  185.750000,  27862.50,'USD','BUY', 'ML02','2026-05-21'),
(1004,'02079K305','2026-05-21','2026-05-23','ACC002','Alphabet Inc Class C',            100.0000,  175.900000,  17590.00,'USD','SELL','ML02','2026-05-21'),
(1005,'67066G104','2026-05-21','2026-05-23','ACC003','NVIDIA Corporation',              300.0000,  875.500000, 262650.00,'USD','BUY', 'CS03','2026-05-21'),
(1006,'70450Y103','2026-05-21','2026-05-23','ACC003','PayPal Holdings Inc',             400.0000,   62.300000,  24920.00,'USD','SELL','CS03','2026-05-21'),
(1007,'46625H100','2026-05-21','2026-05-23','ACC004','JPMorgan Chase & Co',             250.0000,  198.600000,  49650.00,'USD','BUY', 'MS04','2026-05-21'),
(1008,'172967424','2026-05-21','2026-05-23','ACC004','Citigroup Inc',                   600.0000,   64.150000,  38490.00,'USD','BUY', 'MS04','2026-05-21'),
(1009,'191216100','2026-05-21','2026-05-23','ACC005','Coca-Cola Company',               1000.0000,  62.800000,  62800.00,'USD','BUY', 'DB05','2026-05-21'),
(1010,'808513105','2026-05-21','2026-05-23','ACC005','Charles Schwab Corp',             350.0000,   76.400000,  26740.00,'USD','SELL','DB05','2026-05-21'),
(1011,'037833100','2026-05-21','2026-05-23','ACC006','Apple Inc Common Stock',          800.0000,  189.250000, 151400.00,'USD','SELL','UB06','2026-05-21'),
(1012,'594918104','2026-05-21','2026-05-23','ACC006','Microsoft Corp Common Stock',     450.0000,  415.300000, 186885.00,'USD','BUY', 'UB06','2026-05-21'),
(1013,'023135106','2026-05-21','2026-05-23','ACC007','Amazon.com Inc',                   75.0000,  185.750000,  13931.25,'USD','BUY', 'TD07','2026-05-21'),
(1014,'67066G104','2026-05-21','2026-05-23','ACC008','NVIDIA Corporation',              125.0000,  875.500000, 109437.50,'USD','BUY', 'RJ08','2026-05-21'),
(1015,'46625H100','2026-05-21','2026-05-23','ACC009','JPMorgan Chase & Co',             500.0000,  198.600000,  99300.00,'USD','SELL','EV09','2026-05-21'),
(1016,'172967424','2026-05-21','2026-05-23','ACC009','Citigroup Inc',                   750.0000,   64.150000,  48112.50,'USD','BUY', 'EV09','2026-05-21'),
(1017,'191216100','2026-05-21','2026-05-23','ACC010','Coca-Cola Company',               2000.0000,  62.800000, 125600.00,'USD','BUY', 'NT10','2026-05-21'),
(1018,'808513105','2026-05-21','2026-05-23','ACC010','Charles Schwab Corp',              900.0000,  76.400000,  68760.00,'USD','SELL','NT10','2026-05-21'),
(1019,'02079K305','2026-05-21','2026-05-23','ACC001','Alphabet Inc Class C',             225.0000, 175.900000,  39577.50,'USD','BUY', 'GS01','2026-05-21'),
(1020,'70450Y103','2026-05-21','2026-05-23','ACC002','PayPal Holdings Inc',              300.0000,  62.300000,  18690.00,'USD','BUY', 'ML02','2026-05-21');
GO

-- Add 30 more source trades for volume
DECLARE @i INT = 1021;
WHILE @i <= 1050
BEGIN
    INSERT INTO dbo.securities_source
        (trade_id, cusip, trade_date, settlement_date, account_id,
         security_desc, quantity, price, trade_amount, currency, trade_type, broker_code, load_date)
    VALUES (
        @i,
        CASE (@i % 5)
            WHEN 0 THEN '037833100' WHEN 1 THEN '594918104'
            WHEN 2 THEN '023135106' WHEN 3 THEN '67066G104'
            ELSE '46625H100'
        END,
        '2026-05-21', '2026-05-23',
        'ACC0' + RIGHT('0' + CAST((@i % 10) + 1 AS VARCHAR), 2),
        'Security ' + CAST(@i AS VARCHAR),
        CAST((@i % 500 + 100) AS DECIMAL(18,4)),
        CAST((@i % 200 + 50)  AS DECIMAL(18,6)),
        CAST((@i % 500 + 100) * (@i % 200 + 50) AS DECIMAL(18,2)),
        'USD',
        CASE WHEN @i % 2 = 0 THEN 'BUY' ELSE 'SELL' END,
        'BR' + CAST(@i % 5 AS VARCHAR),
        '2026-05-21'
    );
    SET @i = @i + 1;
END
GO

-- ============================================================
-- SEED: securities_target
-- !! INTENTIONAL DEFECTS INTRODUCED !!
--    1. Trade IDs 1005, 1010, 1015 are MISSING (dropped records)
--    2. Trade 1003 has a NULL broker_code (data corruption)
--    3. Trade 1007 has wrong trade_amount (transformation error)
--    4. Trade ID 1001 is DUPLICATED (duplicate load bug)
-- ============================================================
INSERT INTO dbo.securities_target
    (trade_id, cusip, trade_date, settlement_date, account_id,
     security_desc, quantity, price, trade_amount, currency, trade_type, broker_code, load_date)
SELECT
    trade_id, cusip, trade_date, settlement_date, account_id,
    security_desc, quantity, price, trade_amount, currency, trade_type, broker_code, load_date
FROM dbo.securities_source
WHERE trade_id NOT IN (1005, 1010, 1015);   -- ← 3 records intentionally DROPPED
GO

-- Defect 2: NULL out broker_code for trade 1003
UPDATE dbo.securities_target SET broker_code = NULL WHERE trade_id = 1003;
GO

-- Defect 3: Wrong trade_amount for trade 1007 (off by $10,000)
UPDATE dbo.securities_target SET trade_amount = 39650.00 WHERE trade_id = 1007;
GO

-- Defect 4: Duplicate — insert trade 1001 again
INSERT INTO dbo.securities_target
    (trade_id, cusip, trade_date, settlement_date, account_id,
     security_desc, quantity, price, trade_amount, currency, trade_type, broker_code, load_date)
SELECT trade_id, cusip, trade_date, settlement_date, account_id,
       security_desc, quantity, price, trade_amount, currency, trade_type, broker_code, load_date
FROM dbo.securities_source WHERE trade_id = 1001;
GO

-- ============================================================
-- SEED: orders_source and orders_target (second pipeline)
-- ============================================================
INSERT INTO dbo.orders_source VALUES
(5001,'ACC001','2026-05-21','AAPL-OPT',  10, 1250.00,  12500.00,'FILLED', '2026-05-21'),
(5002,'ACC002','2026-05-21','MSFT-OPT',   5, 2100.00,  10500.00,'FILLED', '2026-05-21'),
(5003,'ACC003','2026-05-21','NVDA-OPT',  20,  875.00,  17500.00,'FILLED', '2026-05-21'),
(5004,'ACC004','2026-05-21','JPM-OPT',    8,  990.00,   7920.00,'FILLED', '2026-05-21'),
(5005,'ACC005','2026-05-21','AMZN-OPT',  15,  925.00,  13875.00,'FILLED', '2026-05-21'),
(5006,'ACC006','2026-05-21','GOOG-OPT',   3, 1750.00,   5250.00,'PENDING','2026-05-21'),
(5007,'ACC007','2026-05-21','TSLA-OPT',  25,  245.00,   6125.00,'FILLED', '2026-05-21'),
(5008,'ACC008','2026-05-21','META-OPT',  12,  510.00,   6120.00,'FILLED', '2026-05-21'),
(5009,'ACC999','2026-05-21','BRK-OPT',    2, 5600.00,  11200.00,'FILLED', '2026-05-21'), -- ACC999 not in customers!
(5010,'ACC010','2026-05-21','V-OPT',      7,  275.00,   1925.00,'FILLED', '2026-05-21');
GO

INSERT INTO dbo.orders_target
SELECT * FROM dbo.orders_source WHERE order_id NOT IN (5006, 5009);  -- 2 records dropped
GO

-- ============================================================
-- Verification counts
-- ============================================================
SELECT 'securities_source' AS tbl, COUNT(*) AS rows FROM dbo.securities_source
UNION ALL
SELECT 'securities_target',         COUNT(*)         FROM dbo.securities_target
UNION ALL
SELECT 'orders_source',             COUNT(*)         FROM dbo.orders_source
UNION ALL
SELECT 'orders_target',             COUNT(*)         FROM dbo.orders_target
UNION ALL
SELECT 'customers',                 COUNT(*)         FROM dbo.customers;
GO

PRINT '✅ ETL_QA_Demo database setup complete!';
PRINT '';
PRINT 'Intentional defects introduced for QA tool demonstration:';
PRINT '  securities pipeline: 3 dropped records, 1 duplicate, 1 null, 1 wrong amount';
PRINT '  orders pipeline    : 2 dropped records, 1 orphaned account_id (ACC999)';
GO
