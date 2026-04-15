from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path


DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "data.db"


def get_db_path(db_path: str | None = None) -> str:
    return db_path or os.getenv("ALERTS_DB_PATH") or str(DEFAULT_DB_PATH)


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    connection = sqlite3.connect(get_db_path(db_path), check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def transaction(db_path: str | None = None):
    connection = get_connection(db_path)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def now_timestamp(connection: sqlite3.Connection) -> str:
    return connection.execute(
        "SELECT datetime('now') AS value"
    ).fetchone()["value"]


def init_database(db_path: str | None = None, *, seed_demo_data: bool = True) -> None:
    path = Path(get_db_path(db_path))
    path.parent.mkdir(parents=True, exist_ok=True)
    with transaction(str(path)) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS repayment_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                borrower_name TEXT NOT NULL,
                vehicle_plate TEXT NOT NULL,
                amount_due REAL NOT NULL,
                installment_no INTEGER NOT NULL,
                due_date TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                sales_username TEXT NOT NULL DEFAULT 'jamesduan',
                paid_at TEXT,
                last_risk_triggered_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS alert_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                event_type TEXT NOT NULL,
                title_template TEXT NOT NULL,
                body_template TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS wechat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recipient_username TEXT NOT NULL,
                message_type TEXT NOT NULL,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_record_id INTEGER,
                read_status INTEGER NOT NULL DEFAULT 0,
                sent_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS reminder_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repayment_plan_id INTEGER NOT NULL,
                template_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                business_date TEXT NOT NULL,
                delivery_slot TEXT,
                trigger_reason TEXT NOT NULL,
                send_status TEXT NOT NULL,
                message_id INTEGER,
                rendered_title TEXT NOT NULL,
                rendered_body TEXT NOT NULL,
                recipient_username TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(repayment_plan_id) REFERENCES repayment_plans(id),
                FOREIGN KEY(template_id) REFERENCES alert_templates(id),
                FOREIGN KEY(message_id) REFERENCES wechat_messages(id)
            );

            CREATE TABLE IF NOT EXISTS system_settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT NOT NULL
            );
            """
        )
        ensure_column(connection, "reminder_records", "delivery_slot", "TEXT")
        seed_defaults(connection, seed_demo_data=seed_demo_data)


def ensure_column(
    connection: sqlite3.Connection,
    table_name: str,
    column_name: str,
    column_sql: str,
) -> None:
    columns = {
        row["name"]
        for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    if column_name not in columns:
        connection.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}"
        )


def seed_defaults(connection: sqlite3.Connection, *, seed_demo_data: bool) -> None:
    timestamp = now_timestamp(connection)
    templates = [
        (
            "PRE_DUE_REMINDER",
            "还款前 3 天晨间提醒",
            "pre_due",
            "【还款晨报】{{vehicle_plate}} 第{{installment_no}}期还有 {{days_until_due}} 天到期",
            "客户 {{borrower_name}} 的车辆 {{vehicle_plate}} 分期第{{installment_no}}期将在 {{due_date}} 到期，应还金额 {{amount_due}} 元。系统会在到期前 3 天内每日上午 9 点提醒，已还款后自动停发。",
        ),
        (
            "OVERDUE_RISK_ALERT",
            "逾期双时段预警",
            "overdue_risk",
            "【逾期预警】{{vehicle_plate}} 已逾期 {{overdue_days}} 天",
            "客户 {{borrower_name}} 的车辆 {{vehicle_plate}} 第{{installment_no}}期应还金额 {{amount_due}} 元已逾期 {{overdue_days}} 天。系统会在每日 09:00 和 18:00 自动提醒；逾期超过 7 天将标记为风控中，已还款后自动停发。",
        ),
    ]
    for code, name, event_type, title_template, body_template in templates:
        existing = connection.execute(
            "SELECT id, enabled, created_at FROM alert_templates WHERE code = ?",
            (code,),
        ).fetchone()
        if existing is None:
            connection.execute(
                """
                INSERT INTO alert_templates (
                    code, name, event_type, title_template, body_template, enabled, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (code, name, event_type, title_template, body_template, timestamp, timestamp),
            )
        else:
            connection.execute(
                """
                UPDATE alert_templates
                SET name = ?, event_type = ?, title_template = ?, body_template = ?, updated_at = ?
                WHERE id = ?
                """,
                (name, event_type, title_template, body_template, timestamp, existing["id"]),
            )

    setting = connection.execute(
        "SELECT key FROM system_settings WHERE key = 'business_date_override'"
    ).fetchone()
    if setting is None:
        connection.execute(
            """
            INSERT INTO system_settings (key, value, updated_at)
            VALUES ('business_date_override', NULL, ?)
            """,
            (timestamp,),
        )

    plan_count = connection.execute(
        "SELECT COUNT(*) AS count FROM repayment_plans"
    ).fetchone()["count"]
    if plan_count == 0 and seed_demo_data:
        today = date.today()
        demo_rows = [
            ("王琳", "沪A8123X", 3680.0, 3, today + timedelta(days=3), "pending"),
            ("陈峰", "粤B9Q213", 5220.0, 5, today - timedelta(days=8), "pending"),
            ("刘畅", "浙C7821D", 4510.0, 2, today - timedelta(days=2), "pending"),
            ("赵悦", "京N2D517", 3999.0, 1, today + timedelta(days=12), "pending"),
        ]
        connection.executemany(
            """
            INSERT INTO repayment_plans (
                borrower_name, vehicle_plate, amount_due, installment_no, due_date,
                status, sales_username, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'jamesduan', ?, ?)
            """,
            [
                (
                    borrower_name,
                    vehicle_plate,
                    amount_due,
                    installment_no,
                    due_date.isoformat(),
                    status,
                    timestamp,
                    timestamp,
                )
                for borrower_name, vehicle_plate, amount_due, installment_no, due_date, status in demo_rows
            ],
        )
