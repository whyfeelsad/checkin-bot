"""数据库连接池管理"""

import asyncpg
from asyncpg import Pool
from typing import Optional

from checkin_bot.config.settings import get_settings

_pool: Optional[Pool] = None


async def _init_connection(conn):
    """初始化数据库连接（设置时区）"""
    settings = get_settings()
    # 设置数据库会话时区，使 NOW() 返回配置时区的时间
    await conn.execute(f"SET TIME ZONE '{settings.timezone}';")


async def get_pool() -> Pool:
    """获取数据库连接池（单例模式）"""
    global _pool
    if _pool is None:
        settings = get_settings()
        _pool = await asyncpg.create_pool(
            settings.database_url,
            min_size=5,
            max_size=20,
            command_timeout=60,
            init=_init_connection,
        )
    return _pool


async def close_pool():
    """关闭数据库连接池"""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


async def get_connection():
    """获取数据库连接（返回上下文管理器，需用 async with）"""
    pool = await get_pool()
    return pool.acquire()


class DatabaseConnection:
    """数据库连接上下文管理器"""

    def __init__(self):
        self._conn = None
        self._pool = None
        self._acquire_context = None

    async def __aenter__(self):
        self._pool = await get_pool()
        # acquire() 返回上下文管理器，需要通过 __aenter__ 获取实际连接
        self._acquire_context = self._pool.acquire()
        self._conn = await self._acquire_context.__aenter__()
        return self._conn

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._acquire_context:
            await self._acquire_context.__aexit__(exc_type, exc_val, exc_tb)
            self._acquire_context = None
            self._conn = None


# ==================== 数据库自动初始化 ====================

# SQL schema（分步执行，兼容旧版本 PostgreSQL）
_INIT_SQL_TYPES = """
-- ==================== 枚举类型 ====================

-- 站点类型枚举
DO $$ BEGIN
    CREATE TYPE account_site AS ENUM ('nodeseek', 'deepflood');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- 签到模式枚举
DO $$ BEGIN
    CREATE TYPE checkin_mode AS ENUM ('fixed', 'random');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- 账号状态枚举
DO $$ BEGIN
    CREATE TYPE account_status AS ENUM ('active', 'inactive', 'error');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- 签到状态枚举
DO $$ BEGIN
    CREATE TYPE checkin_status AS ENUM ('success', 'failed', 'partial');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- 更新状态枚举
DO $$ BEGIN
    CREATE TYPE update_status AS ENUM ('pending', 'processing', 'completed', 'failed');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- 会话状态枚举
DO $$ BEGIN
    CREATE TYPE session_state AS ENUM (
        'adding_account_site',
        'adding_account_credentials',
        'adding_account_checkin_mode',
        'setting_checkin_time',
        'setting_push_time',
        'confirming_delete',
        'selecting_fingerprint'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;
"""

_INIT_SQL_TABLES = """

-- ==================== 表结构 ====================

-- 用户表
CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    telegram_id BIGINT NOT NULL UNIQUE,
    telegram_username VARCHAR(255),
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    fingerprint VARCHAR(50),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- 账号表
CREATE TABLE IF NOT EXISTS accounts (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    site account_site NOT NULL,
    site_username VARCHAR(255) NOT NULL,
    encrypted_pass TEXT NOT NULL,
    cookie TEXT,
    checkin_mode checkin_mode NOT NULL,
    status account_status NOT NULL DEFAULT 'active',
    credits INTEGER NOT NULL DEFAULT 0,
    checkin_count INTEGER NOT NULL DEFAULT 0,
    checkin_hour SMALLINT,
    push_hour SMALLINT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, site, site_username)
);

-- 签到日志表
CREATE TABLE IF NOT EXISTS checkin_logs (
    id BIGSERIAL PRIMARY KEY,
    account_id BIGINT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    site account_site NOT NULL,
    status checkin_status NOT NULL,
    message TEXT,
    credits_delta INTEGER NOT NULL DEFAULT 0,
    credits_before INTEGER,
    credits_after INTEGER,
    error_code VARCHAR(50),
    executed_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- 会话表
CREATE TABLE IF NOT EXISTS sessions (
    id BIGSERIAL PRIMARY KEY,
    telegram_id BIGINT NOT NULL,
    state session_state NOT NULL,
    data JSONB NOT NULL DEFAULT '{}',
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- 账号更新追踪表
CREATE TABLE IF NOT EXISTS account_updates (
    id BIGSERIAL PRIMARY KEY,
    account_id BIGINT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    status update_status NOT NULL,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ==================== 索引 ====================

-- 用户表索引
CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id);

-- 账号表索引
CREATE INDEX IF NOT EXISTS idx_accounts_user_id ON accounts(user_id);
CREATE INDEX IF NOT EXISTS idx_accounts_site ON accounts(site);
CREATE INDEX IF NOT EXISTS idx_accounts_status ON accounts(status);
CREATE INDEX IF NOT EXISTS idx_accounts_checkin_hour ON accounts(checkin_hour) WHERE checkin_hour IS NOT NULL;

-- 签到日志表索引
CREATE INDEX IF NOT EXISTS idx_checkin_logs_account_id ON checkin_logs(account_id);
CREATE INDEX IF NOT EXISTS idx_checkin_logs_site ON checkin_logs(site);
CREATE INDEX IF NOT EXISTS idx_checkin_logs_status ON checkin_logs(status);
CREATE INDEX IF NOT EXISTS idx_checkin_logs_executed_at ON checkin_logs(executed_at DESC);

-- 会话表索引
CREATE INDEX IF NOT EXISTS idx_sessions_telegram_id ON sessions(telegram_id);
CREATE INDEX IF NOT EXISTS idx_sessions_state ON sessions(state);
CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions(expires_at);

-- 账号更新表索引
CREATE INDEX IF NOT EXISTS idx_account_updates_account_id ON account_updates(account_id);
CREATE INDEX IF NOT EXISTS idx_account_updates_status ON account_updates(status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_account_updates_active_constraint
    ON account_updates (account_id, status)
    WHERE status IN ('pending', 'processing');

-- ==================== 触发器 ====================

-- 更新时间戳触发器函数
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 为 users 表添加触发器
DROP TRIGGER IF EXISTS update_users_updated_at ON users;
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- 为 accounts 表添加触发器
DROP TRIGGER IF EXISTS update_accounts_updated_at ON accounts;
CREATE TRIGGER update_accounts_updated_at
    BEFORE UPDATE ON accounts
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- 为 sessions 表添加触发器
DROP TRIGGER IF EXISTS update_sessions_updated_at ON sessions;
CREATE TRIGGER update_sessions_updated_at
    BEFORE UPDATE ON sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
"""


async def init_database():
    """Initialize database tables if they don't exist"""
    import logging

    logger = logging.getLogger(__name__)
    settings = get_settings()

    try:
        conn = await asyncpg.connect(settings.database_url)

        try:
            # 设置时区
            await conn.execute(f"SET TIME ZONE '{settings.timezone}';")

            # 先创建枚举类型
            await conn.execute(_INIT_SQL_TYPES)
            logger.info("数据库类型初始化成功")

            # 再创建表结构
            await conn.execute(_INIT_SQL_TABLES)
            logger.info("数据库表初始化成功")
        finally:
            await conn.close()

    except Exception as e:
        logger.error(f"数据库初始化失败: {e}", exc_info=True)
        raise


async def check_and_init_database():
    """Check if tables exist, initialize if not"""
    import logging

    logger = logging.getLogger(__name__)
    settings = get_settings()

    try:
        conn = await asyncpg.connect(settings.database_url)

        try:
            # 设置时区
            await conn.execute(f"SET TIME ZONE '{settings.timezone}';")

            # Check if users table exists
            result = await conn.fetchval(
                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'users')"
            )

            if not result:
                logger.warning("数据库表不存在，正在初始化...")
                await init_database()
            else:
                logger.debug("数据库表已存在")
                # 检查 fingerprint 字段是否存在
                column_exists = await conn.fetchval(
                    """SELECT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'users' AND column_name = 'fingerprint'
                    )"""
                )
                if not column_exists:
                    await conn.execute(
                        "ALTER TABLE users ADD COLUMN fingerprint VARCHAR(50)"
                    )
                    logger.info("数据库迁移成功: 添加 users.fingerprint 字段")

        finally:
            await conn.close()

    except Exception as e:
        logger.error(f"检查数据库时出错: {e}", exc_info=True)
        # Try to initialize anyway
        try:
            await init_database()
        except Exception as init_error:
            logger.error(f"数据库初始化失败: {init_error}", exc_info=True)
            raise
