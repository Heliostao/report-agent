"""
长期记忆 — PostgreSQL 持久化存储

跨会话持久化报告摘要和文件索引，支持历史回溯和去重。

表结构：
  - report_summaries: 存储每次分析的最终报告摘要
  - processed_files:   已分析文件的索引（防重复处理）

使用方式：
  save_report(result)     — graph 完成后调用
  get_file_history(path)  — 查询某文件的历史分析记录
"""

from datetime import  timezone, timedelta

from src.config.util_config import postgres_url


# 中国时区 UTC+8
TZ = timezone(timedelta(hours=8))

# 表结构 DDL
DDL = """
CREATE TABLE IF NOT EXISTS report_summaries (
    id              SERIAL PRIMARY KEY,
    file_path       TEXT NOT NULL,
    company_name    TEXT,
    stock_code      TEXT,
    rating          TEXT,
    target_price    FLOAT,
    one_liner       TEXT,
    key_data_table  TEXT,
    confidence_note TEXT,
    risk_highlight  TEXT,
    draft_report    TEXT,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS processed_files (
    id          SERIAL PRIMARY KEY,
    file_path   TEXT UNIQUE NOT NULL,
    hash_md5    TEXT,
    first_seen  TIMESTAMP DEFAULT NOW(),
    last_seen   TIMESTAMP DEFAULT NOW()
);
"""


def _get_conn():
    """获取 psycopg2 连接"""
    import psycopg2
    return psycopg2.connect(postgres_url)


def init_db():
    """初始化数据库表（幂等）"""
    conn = None
    cur = None
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute(DDL)
        conn.commit()
    except Exception:
        pass
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def save_report(state: dict) -> bool:
    conn = None
    cur = None
    try:
        final = state.get("final_report") or {}
        data = state.get("extracted_data") or {}
        file_path = state.get("file_path", "")

        conn = _get_conn()
        cur = conn.cursor()

        cur.execute(
            """INSERT INTO report_summaries
               (file_path, company_name, stock_code, rating, target_price,
                one_liner, key_data_table, confidence_note, risk_highlight, draft_report)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                file_path,
                data.get("company_name"),
                data.get("stock_code"),
                data.get("rating"),
                data.get("target_price"),
                final.get("one_liner"),
                final.get("key_data_table"),
                final.get("confidence_note"),
                final.get("risk_highlight"),
                state.get("draft_report", ""),
            ),
        )

        cur.execute(
            """INSERT INTO processed_files (file_path)
               VALUES (%s)
               ON CONFLICT (file_path) DO UPDATE SET last_seen = NOW()""",
            (file_path,),
        )

        conn.commit()
        return True
    except Exception:
        return False
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def get_file_history(file_path: str, limit: int = 5) -> list[dict]:
    conn = None
    cur = None
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute(
            """SELECT company_name, rating, one_liner, key_data_table, created_at
               FROM report_summaries
               WHERE file_path = %s
               ORDER BY created_at DESC LIMIT %s""",
            (file_path, limit),
        )
        rows = cur.fetchall()
        return [
            {
                "company_name": r[0],
                "rating": r[1],
                "one_liner": r[2],
                "key_data_table": r[3],
                "created_at": r[4].isoformat() if r[4] else None,
            }
            for r in rows
        ]
    except Exception:
        return []
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def get_recent_reports(limit: int = 3) -> list[dict]:
    conn = None
    cur = None
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute(
            """SELECT id, company_name, stock_code, rating, target_price,
                      one_liner, key_data_table, confidence_note, risk_highlight,
                      created_at
               FROM report_summaries
               ORDER BY created_at DESC LIMIT %s""",
            (limit,),
        )
        rows = cur.fetchall()
        return [
            {
                "id": r[0],
                "company_name": r[1] or "未知",
                "stock_code": r[2] or "",
                "rating": r[3] or "",
                "target_price": r[4],
                "one_liner": r[5] or "",
                "key_data_table": r[6] or "",
                "confidence_note": r[7] or "",
                "risk_highlight": r[8] or "",
                "created_at": r[9].isoformat() if r[9] else None,
            }
            for r in rows
        ]
    except Exception:
        return []
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def search_reports_by_company(keyword: str, limit: int = 3) -> list[dict]:
    conn = None
    cur = None
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute(
            """SELECT id, company_name, stock_code, rating, target_price,
                      one_liner, key_data_table, confidence_note, risk_highlight,
                      created_at
               FROM report_summaries
               WHERE company_name ILIKE %s
               ORDER BY created_at DESC LIMIT %s""",
            (f"%{keyword}%", limit),
        )
        rows = cur.fetchall()
        return [
            {
                "id": r[0],
                "company_name": r[1] or "未知",
                "stock_code": r[2] or "",
                "rating": r[3] or "",
                "target_price": r[4],
                "one_liner": r[5] or "",
                "key_data_table": r[6] or "",
                "confidence_note": r[7] or "",
                "risk_highlight": r[8] or "",
                "created_at": r[9].isoformat() if r[9] else None,
            }
            for r in rows
        ]
    except Exception:
        return []
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
