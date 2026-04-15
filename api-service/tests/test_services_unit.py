from __future__ import annotations

from datetime import date

from app.database import get_connection, init_database, transaction
from app.services import (
    AlertDispatcher,
    MockWechatClient,
    RenderedMessage,
    TemplateRenderer,
    WechatMessageService,
    compute_status,
    create_repayment_plan,
    create_template,
    get_repayment_plan,
    get_setting,
    list_inbox,
    list_reminder_records,
    list_repayment_plans,
    list_templates,
    mark_message_read,
    mark_plan_paid,
    plan_to_dict,
    resolve_business_date,
    set_setting,
    update_repayment_plan,
    update_template,
)


def create_plan_for_services(db_path: str, *, due_date: date, amount_due: float = 3200.0):
    return create_repayment_plan(
        db_path,
        {
            "borrower_name": "测试客户",
            "vehicle_plate": "沪A12345",
            "amount_due": amount_due,
            "installment_no": 4,
            "due_date": due_date,
            "sales_username": "jamesduan",
        },
    )


def test_template_renderer_replaces_all_supported_placeholders(db_path):
    with get_connection(db_path) as connection:
        template = connection.execute(
            "SELECT * FROM alert_templates WHERE event_type = 'overdue_risk'"
        ).fetchone()

    rendered = TemplateRenderer.render(
        template,
        {
            "borrower_name": "李四",
            "vehicle_plate": "粤B88888",
            "amount_due": "5100.00",
            "due_date": "2026-04-18",
            "installment_no": 3,
            "sales_username": "jamesduan",
            "overdue_days": 9,
        },
    )

    assert "粤B88888" in rendered.title
    assert "李四" in rendered.body
    assert "5100.00" in rendered.body
    assert "9" in rendered.title


def test_compute_status_covers_pending_overdue_risk_and_paid(db_path):
    init_database(db_path, seed_demo_data=False)
    with transaction(db_path) as connection:
        connection.execute(
            """
            INSERT INTO repayment_plans (
                borrower_name, vehicle_plate, amount_due, installment_no, due_date,
                status, sales_username, created_at, updated_at
            ) VALUES
                ('A', '牌1', 1000, 1, '2026-04-20', 'pending', 'jamesduan', '2026-04-01 00:00:00', '2026-04-01 00:00:00'),
                ('B', '牌2', 1000, 1, '2026-04-10', 'pending', 'jamesduan', '2026-04-01 00:00:00', '2026-04-01 00:00:00'),
                ('C', '牌3', 1000, 1, '2026-04-01', 'risk_triggered', 'jamesduan', '2026-04-01 00:00:00', '2026-04-01 00:00:00'),
                ('D', '牌4', 1000, 1, '2026-04-01', 'paid', 'jamesduan', '2026-04-01 00:00:00', '2026-04-01 00:00:00')
            """
        )
        rows = connection.execute(
            "SELECT * FROM repayment_plans ORDER BY id ASC"
        ).fetchall()

    business_date = date(2026, 4, 15)
    statuses = [compute_status(row, business_date) for row in rows]
    assert statuses == [
        ("pending", 0),
        ("overdue", 5),
        ("risk_triggered", 14),
        ("paid", 14),
    ]


def test_plan_to_dict_preserves_risk_triggered_status(db_path):
    with transaction(db_path) as connection:
        connection.execute(
            """
            INSERT INTO repayment_plans (
                borrower_name, vehicle_plate, amount_due, installment_no, due_date,
                status, sales_username, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "张三",
                "京A10001",
                2000,
                2,
                "2026-04-01",
                "risk_triggered",
                "jamesduan",
                "2026-04-01 00:00:00",
                "2026-04-01 00:00:00",
            ),
        )
        row = connection.execute(
            "SELECT * FROM repayment_plans WHERE vehicle_plate = '京A10001'"
        ).fetchone()

    plan = plan_to_dict(row, date(2026, 4, 15))
    assert plan["status"] == "risk_triggered"
    assert plan["overdue_days"] == 14


def test_business_date_settings_support_override_and_clear(db_path):
    assert get_setting(db_path, "business_date_override") is None
    fallback_value = resolve_business_date(db_path)
    assert isinstance(fallback_value, date)

    set_setting(db_path, "business_date_override", "2026-05-01")
    assert get_setting(db_path, "business_date_override") == "2026-05-01"
    assert resolve_business_date(db_path) == date(2026, 5, 1)
    assert resolve_business_date(db_path, date(2026, 5, 2)) == date(2026, 5, 2)

    set_setting(db_path, "business_date_override", None)
    assert get_setting(db_path, "business_date_override") is None


def test_repayment_plan_service_crud_and_mark_paid(db_path):
    created = create_plan_for_services(db_path, due_date=date(2026, 4, 18))
    assert created["status"] == "pending"

    updated = update_repayment_plan(
        db_path,
        created["id"],
        {
            "borrower_name": "更新客户",
            "vehicle_plate": "沪A99999",
            "amount_due": 4200,
            "installment_no": 5,
            "due_date": date(2026, 4, 20),
            "sales_username": "jamesduan",
        },
    )
    assert updated["borrower_name"] == "更新客户"
    assert updated["vehicle_plate"] == "沪A99999"

    all_plans = list_repayment_plans(db_path, date(2026, 4, 15))
    assert len(all_plans) == 1
    assert get_repayment_plan(db_path, created["id"], date(2026, 4, 15))["vehicle_plate"] == "沪A99999"

    paid = mark_plan_paid(db_path, created["id"])
    assert paid["status"] == "paid"
    assert paid["paid_at"] is not None


def test_template_service_create_update_and_list(db_path):
    initial_templates = list_templates(db_path)
    assert len(initial_templates) == 2

    created = create_template(
        db_path,
        {
            "code": "CUSTOM_RISK",
            "name": "自定义风控模板",
            "event_type": "overdue_risk",
            "title_template": "风控 {{vehicle_plate}}",
            "body_template": "逾期 {{overdue_days}} 天",
            "enabled": False,
        },
    )
    assert created["code"] == "CUSTOM_RISK"
    assert created["enabled"] is False

    updated = update_template(
        db_path,
        created["id"],
        {
            "code": "CUSTOM_RISK_2",
            "name": "自定义风控模板2",
            "event_type": "overdue_risk",
            "title_template": "风控 {{vehicle_plate}} 更新",
            "body_template": "逾期 {{overdue_days}} 天，立即处理",
            "enabled": True,
        },
    )
    assert updated["code"] == "CUSTOM_RISK_2"
    assert updated["enabled"] is True
    assert len(list_templates(db_path)) == 3


def test_mock_wechat_client_and_read_flow(db_path):
    with transaction(db_path) as connection:
        message_id = MockWechatClient(db_path).send_template_message(
            "jamesduan",
            "pre_due",
            RenderedMessage(title="测试标题", body="测试正文"),
            connection=connection,
        )

    inbox_before = list_inbox(db_path, "jamesduan")
    assert len(inbox_before) == 1
    assert inbox_before[0]["read_status"] is False

    with get_connection(db_path) as connection:
        sent_message_id = WechatMessageService(db_path).send(
            recipient_username="jamesduan",
            source_type="overdue_risk",
            rendered_message=RenderedMessage(title="第二条", body="第二条正文"),
            connection=connection,
        )
        connection.commit()
    assert sent_message_id > message_id

    assert mark_message_read(db_path, message_id) is True
    assert mark_message_read(db_path, 99999) is False
    inbox_after = list_inbox(db_path, "jamesduan")
    assert inbox_after[1]["read_status"] is True


def test_alert_dispatcher_updates_status_and_records(db_path):
    create_plan_for_services(db_path, due_date=date(2026, 4, 18))
    overdue_plan = create_plan_for_services(db_path, due_date=date(2026, 4, 1), amount_due=5000)

    dispatcher = AlertDispatcher(db_path)
    result = dispatcher.run(override_business_date=date(2026, 4, 15), delivery_slot="manual")

    assert result["pre_due_count"] == 1
    assert result["overdue_risk_count"] == 1
    assert len(result["reminder_record_ids"]) == 2
    assert result["delivery_slot"] == "manual"

    records = list_reminder_records(db_path)
    assert len(records) == 2
    assert {record["event_type"] for record in records} == {"pre_due", "overdue_risk"}
    assert {record["delivery_slot"] for record in records} == {"manual"}

    plans = list_repayment_plans(db_path, date(2026, 4, 15))
    matched = next(plan for plan in plans if plan["id"] == overdue_plan["id"])
    assert matched["status"] == "risk_triggered"


def test_pre_due_dispatcher_is_deduplicated_per_day_and_only_in_morning(db_path):
    create_plan_for_services(db_path, due_date=date(2026, 4, 18))
    dispatcher = AlertDispatcher(db_path)

    first = dispatcher.run(override_business_date=date(2026, 4, 15), delivery_slot="morning")
    second = dispatcher.run(override_business_date=date(2026, 4, 15), delivery_slot="morning")
    evening = dispatcher.run(override_business_date=date(2026, 4, 15), delivery_slot="evening")
    next_day = dispatcher.run(override_business_date=date(2026, 4, 16), delivery_slot="morning")

    assert first["pre_due_count"] == 1
    assert second["pre_due_count"] == 0
    assert evening["pre_due_count"] == 0
    assert next_day["pre_due_count"] == 1
    assert len([record for record in list_reminder_records(db_path) if record["event_type"] == "pre_due"]) == 2


def test_overdue_dispatcher_sends_morning_and_evening_until_paid(db_path):
    plan = create_plan_for_services(db_path, due_date=date(2026, 4, 10))
    dispatcher = AlertDispatcher(db_path)

    morning = dispatcher.run(override_business_date=date(2026, 4, 15), delivery_slot="morning")
    evening = dispatcher.run(override_business_date=date(2026, 4, 15), delivery_slot="evening")
    duplicate_evening = dispatcher.run(override_business_date=date(2026, 4, 15), delivery_slot="evening")

    assert morning["overdue_risk_count"] == 1
    assert evening["overdue_risk_count"] == 1
    assert duplicate_evening["overdue_risk_count"] == 0

    paid = mark_plan_paid(db_path, plan["id"])
    assert paid["status"] == "paid"

    after_paid = dispatcher.run(override_business_date=date(2026, 4, 16), delivery_slot="morning")
    assert after_paid["overdue_risk_count"] == 0


def test_dispatcher_can_ignore_business_date_override_for_auto_runs(db_path):
    create_plan_for_services(db_path, due_date=date(2026, 4, 18))
    set_setting(db_path, "business_date_override", "2026-04-30")
    dispatcher = AlertDispatcher(db_path)

    result = dispatcher.run(
        delivery_slot="morning",
        override_business_date=None,
        use_business_date_override=False,
    )

    assert result["business_date"] == date.today()


def test_manual_dispatcher_runs_immediately_without_time_slot_schedule(db_path):
    create_plan_for_services(db_path, due_date=date(2026, 4, 18))
    overdue_plan = create_plan_for_services(db_path, due_date=date(2026, 4, 14), amount_due=4100)
    dispatcher = AlertDispatcher(db_path)

    result = dispatcher.run(override_business_date=date(2026, 4, 15), delivery_slot="manual")

    assert result["delivery_slot"] == "manual"
    assert result["pre_due_count"] == 1
    assert result["overdue_risk_count"] == 1
    records = list_reminder_records(db_path)
    assert {record["delivery_slot"] for record in records} == {"manual"}

    paid = mark_plan_paid(db_path, overdue_plan["id"])
    assert paid["status"] == "paid"
    second = dispatcher.run(override_business_date=date(2026, 4, 15), delivery_slot="manual")
    assert second["overdue_risk_count"] == 0
