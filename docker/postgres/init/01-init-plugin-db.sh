#!/bin/sh
# 为 AntiHub Plugin 服务创建独立的数据库和用户
# 此脚本由 PostgreSQL 官方镜像在首次初始化时自动执行

set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- 创建 plugin 用户
    CREATE USER ${PLUGIN_DB_USER} WITH PASSWORD '${PLUGIN_DB_PASSWORD}';

    -- 创建 plugin 数据库并指定所有者
    CREATE DATABASE ${PLUGIN_DB_NAME} OWNER ${PLUGIN_DB_USER};

    -- 给用户授予连接权限
    GRANT ALL PRIVILEGES ON DATABASE ${PLUGIN_DB_NAME} TO ${PLUGIN_DB_USER};

    -- 切换到 plugin 数据库
    \c ${PLUGIN_DB_NAME}

    -- 在 plugin 数据库中授予 schema 权限
    GRANT ALL ON SCHEMA public TO ${PLUGIN_DB_USER};
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO ${PLUGIN_DB_USER};
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO ${PLUGIN_DB_USER};

    -- 创建扩展（如果需要）
    -- CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
EOSQL
