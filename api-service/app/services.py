from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Literal

from .database import get_connection, now_timestamp, transaction


def parse_date(raw: str) -> date:
    return date.fromisoformat(raw)


def parse_datetime(raw: str | None) -> datetime | None:
    if raw is None:
        return None
    return datetime.fromisoformat(raw)


def get_setting(db_path: str, key: str) -> str | None:
    with get_connection(db_path) as connection:
        row = connection.execute(
            "SELECT value FROM system_settings WHERE key = ?",
            (key,),
        ).fetchone()
        return None if row is None else row["value"]


def set_setting(db_path: str, key: str, value: str | None) -> None:
    with transaction(db_path) as connection:
        timestamp = now_timestamp(connection)
        connection.execute(
            """
            INSERT INTO system_settings (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """,
            (key, value, timestamp),
        )


def resolve_business_date(db_path: str, override: date | None = None) -> date:
    if override is not None:
        return override
    stored_value = get_setting(db_path, "business_date_override")
    if stored_value:
        return date.fromisoformat(stored_value)
    return date.today()


def compute_status(row: sqlite3.Row, business_date: date) -> tuple[str, int]:
    due_date = parse_date(row["due_date"])
    overdue_days = max((business_date - due_date).days, 0)
    stored_status = row["status"]
    if stored_status == "paid":
        return "paid", overdue_days
    if stored_status == "risk_triggered":
        return "risk_triggered", overdue_days
    if overdue_days > 0:
        return "overdue", overdue_days
    return "pending", overdue_days


def plan_to_dict(row: sqlite3.Row, business_date: date) -> dict:
    status, overdue_days = compute_status(row, business_date)
    return {
        "id": row["id"],
        "borrower_name": row["borrower_name"],
        "vehicle_plate": row["vehicle_plate"],
        "amount_due": row["amount_due"],
        "installment_no": row["installment_no"],
        "due_date": parse_date(row["due_date"]),
        "sales_username": row["sales_username"],
        "status": status if row["status"] != "risk_triggered" else "risk_triggered",
        "stored_status": row["status"],
        "overdue_days": overdue_days,
        "paid_at": parse_datetime(row["paid_at"]),
        "last_risk_triggered_at": parse_datetime(row["last_risk_triggered_at"]),
        "created_at": parse_datetime(row["created_at"]),
        "updated_at": parse_datetime(row["updated_at"]),
    }


def list_repayment_plans(db_path: str, business_date: date) -> list[dict]:
    with get_connection(db_path) as connection:
        rows = connection.execute(
            "SELECT * FROM repayment_plans ORDER BY due_date ASC, id ASC"
        ).fetchall()
    return [plan_to_dict(row, business_date) for row in rows]


def get_repayment_plan(db_path: str, plan_id: int, business_date: date) -> dict | None:
    with get_connection(db_path) as connection:
        row = connection.execute(
            "SELECT * FROM repayment_plans WHERE id = ?",
            (plan_id,),
        ).fetchone()
    return None if row is None else plan_to_dict(row, business_date)


def create_repayment_plan(db_path: str, payload: dict) -> dict:
    with transaction(db_path) as connection:
        timestamp = now_timestamp(connection)
        cursor = connection.execute(
            """
            INSERT INTO repayment_plans (
                borrower_name, vehicle_plate, amount_due, installment_no, due_date,
                status, sales_username, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?)
            """,
            (
                payload["borrower_name"],
                payload["vehicle_plate"],
                payload["amount_due"],
                payload["installment_no"],
                payload["due_date"].isoformat(),
                payload["sales_username"],
                timestamp,
                timestamp,
            ),
        )
        plan_id = cursor.lastrowid
    return get_repayment_plan(db_path, plan_id, resolve_business_date(db_path))


def update_repayment_plan(db_path: str, plan_id: int, payload: dict) -> dict | None:
    with transaction(db_path) as connection:
        timestamp = now_timestamp(connection)
        cursor = connection.execute(
            """
            UPDATE repayment_plans
            SET borrower_name = ?, vehicle_plate = ?, amount_due = ?, installment_no = ?,
                due_date = ?, sales_username = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                payload["borrower_name"],
                payload["vehicle_plate"],
                payload["amount_due"],
                payload["installment_no"],
                payload["due_date"].isoformat(),
                payload["sales_username"],
                timestamp,
                plan_id,
            ),
        )
    if cursor.rowcount == 0:
        return None
    return get_repayment_plan(db_path, plan_id, resolve_business_date(db_path))


def mark_plan_paid(db_path: str, plan_id: int) -> dict | None:
    with transaction(db_path) as connection:
        timestamp = now_timestamp(connection)
        cursor = connection.execute(
            """
            UPDATE repayment_plans
            SET status = 'paid', paid_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (timestamp, timestamp, plan_id),
        )
    if cursor.rowcount == 0:
        return None
    return get_repayment_plan(db_path, plan_id, resolve_business_date(db_path))


def list_templates(db_path: str) -> list[dict]:
    with get_connection(db_path) as connection:
        rows = connection.execute(
            "SELECT * FROM alert_templates ORDER BY updated_at DESC, id DESC"
        ).fetchall()
    return [
        {
            "id": row["id"],
            "code": row["code"],
            "name": row["name"],
            "event_type": row["event_type"],
            "title_template": row["title_template"],
            "body_template": row["body_template"],
            "enabled": bool(row["enabled"]),
            "created_at": parse_datetime(row["created_at"]),
            "updated_at": parse_datetime(row["updated_at"]),
        }
        for row in rows
    ]


def create_template(db_path: str, payload: dict) -> dict:
    with transaction(db_path) as connection:
        timestamp = now_timestamp(connection)
        cursor = connection.execute(
            """
            INSERT INTO alert_templates (
                code, name, event_type, title_template, body_template, enabled, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["code"],
                payload["name"],
                payload["event_type"],
                payload["title_template"],
                payload["body_template"],
                int(payload["enabled"]),
                timestamp,
                timestamp,
            ),
        )
        template_id = cursor.lastrowid
    return get_template(db_path, template_id)


def update_template(db_path: str, template_id: int, payload: dict) -> dict | None:
    with transaction(db_path) as connection:
        timestamp = now_timestamp(connection)
        cursor = connection.execute(
            """
            UPDATE alert_templates
            SET code = ?, name = ?, event_type = ?, title_template = ?, body_template = ?,
                enabled = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                payload["code"],
                payload["name"],
                payload["event_type"],
                payload["title_template"],
                payload["body_template"],
                int(payload["enabled"]),
                timestamp,
                template_id,
            ),
        )
    if cursor.rowcount == 0:
        return None
    return get_template(db_path, template_id)


def get_template(db_path: str, template_id: int) -> dict | None:
    with get_connection(db_path) as connection:
        row = connection.execute(
            "SELECT * FROM alert_templates WHERE id = ?",
            (template_id,),
        ).fetchone()
    if row is None:
        return None
    return {
        "id": row["id"],
        "code": row["code"],
        "name": row["name"],
        "event_type": row["event_type"],
        "title_template": row["title_template"],
        "body_template": row["body_template"],
        "enabled": bool(row["enabled"]),
        "created_at": parse_datetime(row["created_at"]),
        "updated_at": parse_datetime(row["updated_at"]),
    }


def list_reminder_records(db_path: str) -> list[dict]:
    with get_connection(db_path) as connection:
        rows = connection.execute(
            """
            SELECT rr.*, rp.borrower_name, rp.vehicle_plate, at.name AS template_name
            FROM reminder_records rr
            JOIN repayment_plans rp ON rr.repayment_plan_id = rp.id
            JOIN alert_templates at ON rr.template_id = at.id
            ORDER BY rr.created_at DESC, rr.id DESC
            """
        ).fetchall()
    return [
        {
            "id": row["id"],
            "repayment_plan_id": row["repayment_plan_id"],
            "template_id": row["template_id"],
            "event_type": row["event_type"],
            "business_date": parse_date(row["business_date"]),
            "delivery_slot": row["delivery_slot"],
            "trigger_reason": row["trigger_reason"],
            "send_status": row["send_status"],
            "message_id": row["message_id"],
            "rendered_title": row["rendered_title"],
            "rendered_body": row["rendered_body"],
            "recipient_username": row["recipient_username"],
            "borrower_name": row["borrower_name"],
            "vehicle_plate": row["vehicle_plate"],
            "template_name": row["template_name"],
            "created_at": parse_datetime(row["created_at"]),
        }
        for row in rows
    ]


def list_inbox(db_path: str, username: str) -> list[dict]:
    with get_connection(db_path) as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM wechat_messages
            WHERE recipient_username = ?
            ORDER BY sent_at DESC, id DESC
            """,
            (username,),
        ).fetchall()
    return [
        {
            "id": row["id"],
            "recipient_username": row["recipient_username"],
            "message_type": row["message_type"],
            "title": row["title"],
            "body": row["body"],
            "source_type": row["source_type"],
            "source_record_id": row["source_record_id"],
            "read_status": bool(row["read_status"]),
            "sent_at": parse_datetime(row["sent_at"]),
        }
        for row in rows
    ]


def mark_message_read(db_path: str, message_id: int) -> bool:
    with transaction(db_path) as connection:
        cursor = connection.execute(
            "UPDATE wechat_messages SET read_status = 1 WHERE id = ?",
            (message_id,),
        )
    return cursor.rowcount > 0


@dataclass
class RenderedMessage:
    title: str
    body: str


class TemplateRenderer:
    @staticmethod
    def render(template: sqlite3.Row, context: dict) -> RenderedMessage:
        title = template["title_template"]
        body = template["body_template"]
        for key, value in context.items():
            placeholder = "{{" + key + "}}"
            title = title.replace(placeholder, str(value))
            body = body.replace(placeholder, str(value))
        return RenderedMessage(title=title, body=body)


class MockWechatClient:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def send_template_message(
        self,
        recipient_username: str,
        source_type: str,
        payload: RenderedMessage,
        *,
        connection: sqlite3.Connection,
    ) -> int:
        timestamp = now_timestamp(connection)
        cursor = connection.execute(
            """
            INSERT INTO wechat_messages (
                recipient_username, message_type, title, body, source_type, sent_at
            ) VALUES (?, 'template', ?, ?, ?, ?)
            """,
            (recipient_username, payload.title, payload.body, source_type, timestamp),
        )
        return cursor.lastrowid


class WechatMessageService:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.client = MockWechatClient(db_path)

    def send(
        self,
        *,
        recipient_username: str,
        source_type: str,
        rendered_message: RenderedMessage,
        connection: sqlite3.Connection,
    ) -> int:
        return self.client.send_template_message(
            recipient_username,
            source_type,
            rendered_message,
            connection=connection,
        )


class AlertDispatcher:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.renderer = TemplateRenderer()
        self.message_service = WechatMessageService(db_path)

    def run(
        self,
        *,
        override_business_date: date | None = None,
        delivery_slot: Literal["morning", "evening", "manual"] = "manual",
        reference_now: datetime | None = None,
        use_business_date_override: bool = True,
    ) -> dict:
        if override_business_date is not None:
            business_date = override_business_date
        elif use_business_date_override:
            business_date = resolve_business_date(self.db_path)
        else:
            business_date = (reference_now or datetime.now(UTC)).date()
        with transaction(self.db_path) as connection:
            plans = connection.execute(
                "SELECT * FROM repayment_plans WHERE status != 'paid' ORDER BY due_date ASC, id ASC"
            ).fetchall()
            templates = {
                row["event_type"]: row
                for row in connection.execute(
                    """
                    SELECT *
                    FROM alert_templates
                    WHERE enabled = 1
                    ORDER BY updated_at DESC, id DESC
                    """
                ).fetchall()
            }
            reminder_ids: list[int] = []
            pre_due_count = 0
            overdue_risk_count = 0
            timestamp = now_timestamp(connection)

            for plan in plans:
                due_date = parse_date(plan["due_date"])
                days_until_due = (due_date - business_date).days
                overdue_days = max((business_date - due_date).days, 0)

                if overdue_days > 0:
                    target_status = "risk_triggered" if overdue_days > 7 else "overdue"
                    connection.execute(
                        """
                        UPDATE repayment_plans
                        SET status = ?, updated_at = ?, last_risk_triggered_at = CASE
                            WHEN ? = 'risk_triggered' THEN ?
                            ELSE last_risk_triggered_at
                        END
                        WHERE id = ? AND status != 'paid'
                        """,
                        (target_status, timestamp, target_status, timestamp, plan["id"]),
                    )
                    if delivery_slot in {"morning", "evening", "manual"} and "overdue_risk" in templates:
                        if not self._already_sent(
                            connection=connection,
                            plan_id=plan["id"],
                            event_type="overdue_risk",
                            business_date=business_date,
                            delivery_slot=delivery_slot,
                        ):
                            record_id = self._dispatch_event(
                                connection=connection,
                                plan=plan,
                                template=templates["overdue_risk"],
                                event_type="overdue_risk",
                                business_date=business_date,
                                delivery_slot=delivery_slot,
                                trigger_reason=f"逾期第 {overdue_days} 天 {slot_label(delivery_slot)}预警",
                                overdue_days=overdue_days,
                                days_until_due=days_until_due,
                            )
                            reminder_ids.append(record_id)
                            overdue_risk_count += 1
                    continue

                if delivery_slot in {"morning", "manual"} and 1 <= days_until_due <= 3 and "pre_due" in templates:
                    if not self._already_sent(
                        connection=connection,
                        plan_id=plan["id"],
                        event_type="pre_due",
                        business_date=business_date,
                        delivery_slot=delivery_slot,
                    ):
                        record_id = self._dispatch_event(
                            connection=connection,
                            plan=plan,
                            template=templates["pre_due"],
                            event_type="pre_due",
                            business_date=business_date,
                            delivery_slot=delivery_slot,
                            trigger_reason=f"到期前 {days_until_due} 天 {slot_label(delivery_slot)}提醒",
                            overdue_days=overdue_days,
                            days_until_due=days_until_due,
                        )
                        reminder_ids.append(record_id)
                        pre_due_count += 1

            return {
                "business_date": business_date,
                "delivery_slot": delivery_slot,
                "pre_due_count": pre_due_count,
                "overdue_risk_count": overdue_risk_count,
                "reminder_record_ids": reminder_ids,
            }

    def _already_sent(
        self,
        *,
        connection: sqlite3.Connection,
        plan_id: int,
        event_type: str,
        business_date: date,
        delivery_slot: str,
    ) -> bool:
        row = connection.execute(
            """
            SELECT id
            FROM reminder_records
            WHERE repayment_plan_id = ?
              AND event_type = ?
              AND business_date = ?
              AND delivery_slot = ?
            LIMIT 1
            """,
            (plan_id, event_type, business_date.isoformat(), delivery_slot),
        ).fetchone()
        return row is not None

    def _dispatch_event(
        self,
        *,
        connection: sqlite3.Connection,
        plan: sqlite3.Row,
        template: sqlite3.Row,
        event_type: str,
        business_date: date,
        delivery_slot: str,
        trigger_reason: str,
        overdue_days: int,
        days_until_due: int,
    ) -> int:
        rendered_message = self.renderer.render(
            template,
            {
                "borrower_name": plan["borrower_name"],
                "vehicle_plate": plan["vehicle_plate"],
                "amount_due": f"{plan['amount_due']:.2f}",
                "due_date": plan["due_date"],
                "installment_no": plan["installment_no"],
                "sales_username": plan["sales_username"],
                "overdue_days": overdue_days,
                "days_until_due": max(days_until_due, 0),
            },
        )
        message_id = self.message_service.send(
            recipient_username=plan["sales_username"],
            source_type=event_type,
            rendered_message=rendered_message,
            connection=connection,
        )
        timestamp = now_timestamp(connection)
        record_cursor = connection.execute(
            """
            INSERT INTO reminder_records (
                repayment_plan_id, template_id, event_type, business_date, delivery_slot, trigger_reason,
                send_status, message_id, rendered_title, rendered_body, recipient_username, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'sent', ?, ?, ?, ?, ?)
            """,
            (
                plan["id"],
                template["id"],
                event_type,
                business_date.isoformat(),
                delivery_slot,
                trigger_reason,
                message_id,
                rendered_message.title,
                rendered_message.body,
                plan["sales_username"],
                timestamp,
            ),
        )
        record_id = record_cursor.lastrowid
        connection.execute(
            """
            UPDATE wechat_messages
            SET source_record_id = ?
            WHERE id = ?
            """,
            (record_id, message_id),
        )
        return record_id


def slot_label(delivery_slot: str) -> str:
    return {
        "morning": "09:00",
        "evening": "18:00",
        "manual": "立即触发",
    }.get(delivery_slot, delivery_slot)
