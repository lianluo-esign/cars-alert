from __future__ import annotations

from datetime import date, timedelta


def create_plan(client, payload):
    response = client.post("/api/repayment-plans", json=payload)
    assert response.status_code == 200
    return response.json()


def create_template(client, payload):
    response = client.post("/api/alert-templates", json=payload)
    assert response.status_code == 200
    return response.json()


def test_healthcheck(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_repayment_plan_crud_and_query_status(client, sample_plan_payload):
    created = create_plan(client, sample_plan_payload)
    assert created["borrower_name"] == sample_plan_payload["borrower_name"]

    listing = client.get("/api/repayment-plans?business_date=2026-04-19")
    assert listing.status_code == 200
    body = listing.json()
    assert len(body) == 1
    assert body[0]["status"] == "overdue"
    assert body[0]["overdue_days"] == 1

    update_payload = {
        **sample_plan_payload,
        "borrower_name": "新客户",
        "vehicle_plate": "京A88888",
        "amount_due": 3800,
        "installment_no": 6,
        "due_date": "2026-04-21",
    }
    updated = client.put(f"/api/repayment-plans/{created['id']}", json=update_payload)
    assert updated.status_code == 200
    assert updated.json()["borrower_name"] == "新客户"

    paid = client.post(f"/api/repayment-plans/{created['id']}/mark-paid")
    assert paid.status_code == 200
    assert paid.json()["status"] == "paid"


def test_repayment_plan_validation_and_not_found(client, sample_plan_payload):
    invalid_payload = {**sample_plan_payload, "amount_due": 0}
    invalid = client.post("/api/repayment-plans", json=invalid_payload)
    assert invalid.status_code == 422

    missing_update = client.put("/api/repayment-plans/999", json=sample_plan_payload)
    assert missing_update.status_code == 404
    assert missing_update.json()["detail"] == "Repayment plan not found"

    missing_paid = client.post("/api/repayment-plans/999/mark-paid")
    assert missing_paid.status_code == 404
    assert missing_paid.json()["detail"] == "Repayment plan not found"


def test_alert_template_crud_and_duplicate_errors(client, sample_template_payload):
    defaults = client.get("/api/alert-templates")
    assert defaults.status_code == 200
    assert len(defaults.json()) == 2

    created = create_template(client, sample_template_payload)
    assert created["code"] == "CUSTOM_PRE_DUE"

    updated_payload = {
        **sample_template_payload,
        "code": "CUSTOM_PRE_DUE_UPDATED",
        "name": "更新提醒模板",
        "enabled": False,
    }
    updated = client.put(f"/api/alert-templates/{created['id']}", json=updated_payload)
    assert updated.status_code == 200
    assert updated.json()["code"] == "CUSTOM_PRE_DUE_UPDATED"
    assert updated.json()["enabled"] is False

    duplicate = client.post("/api/alert-templates", json=updated_payload)
    assert duplicate.status_code == 400
    assert duplicate.json()["detail"] == "Template code must be unique"

    missing = client.put("/api/alert-templates/999", json=updated_payload)
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Alert template not found"


def test_business_date_get_set_and_clear(client):
    initial = client.get("/api/system/business-date")
    assert initial.status_code == 200
    assert initial.json()["override_date"] is None

    updated = client.put("/api/system/business-date", json={"business_date": "2026-04-20"})
    assert updated.status_code == 200
    assert updated.json()["override_date"] == "2026-04-20"
    assert updated.json()["resolved_date"] == "2026-04-20"

    queried = client.get("/api/system/business-date")
    assert queried.json()["override_date"] == "2026-04-20"

    cleared = client.put("/api/system/business-date", json={"business_date": None})
    assert cleared.status_code == 200
    assert cleared.json()["override_date"] is None


def test_job_run_generates_reminders_and_inbox_read_flow(client, sample_plan_payload):
    create_plan(client, sample_plan_payload)
    overdue_payload = {
        **sample_plan_payload,
        "vehicle_plate": "浙A22334",
        "due_date": (date(2026, 4, 15) - timedelta(days=8)).isoformat(),
    }
    create_plan(client, overdue_payload)

    run = client.post("/api/jobs/overdue-alerts/run?business_date=2026-04-15")
    assert run.status_code == 200
    summary = run.json()
    assert summary["pre_due_count"] == 1
    assert summary["overdue_risk_count"] == 1
    assert len(summary["reminder_record_ids"]) == 2
    assert summary["delivery_slot"] == "manual"

    records = client.get("/api/reminder-records")
    assert records.status_code == 200
    records_body = records.json()
    assert len(records_body) == 2

    inbox = client.get("/api/wechat/inbox?username=jamesduan")
    assert inbox.status_code == 200
    inbox_body = inbox.json()
    assert len(inbox_body) == 2
    assert any(message["source_type"] == "pre_due" for message in inbox_body)
    assert any(message["source_type"] == "overdue_risk" for message in inbox_body)

    unread_message = next(message for message in inbox_body if not message["read_status"])
    read_response = client.post(f"/api/wechat/inbox/{unread_message['id']}/read")
    assert read_response.status_code == 200
    assert read_response.json() == {"ok": True}

    inbox_after = client.get("/api/wechat/inbox?username=jamesduan").json()
    matched = next(message for message in inbox_after if message["id"] == unread_message["id"])
    assert matched["read_status"] is True


def test_job_run_uses_business_date_override_when_query_missing(client, sample_plan_payload):
    create_plan(client, sample_plan_payload)
    set_date = client.put("/api/system/business-date", json={"business_date": "2026-04-15"})
    assert set_date.status_code == 200

    run = client.post("/api/jobs/overdue-alerts/run")
    assert run.status_code == 200
    assert run.json()["business_date"] == "2026-04-15"
    assert run.json()["pre_due_count"] == 1


def test_inbox_and_read_missing_record_return_404(client):
    inbox = client.get("/api/wechat/inbox?username=unknown-user")
    assert inbox.status_code == 200
    assert inbox.json() == []

    missing = client.post("/api/wechat/inbox/999/read")
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Message not found"


def test_job_run_and_template_validation_errors(client, sample_template_payload):
    invalid_template = {**sample_template_payload, "event_type": "bad_type"}
    invalid_response = client.post("/api/alert-templates", json=invalid_template)
    assert invalid_response.status_code == 422

    invalid_job_date = client.post("/api/jobs/overdue-alerts/run?business_date=bad-date")
    assert invalid_job_date.status_code == 422


def test_job_run_supports_daily_slots_and_pre_due_only_runs_in_morning(client, sample_plan_payload):
    create_plan(client, sample_plan_payload)
    overdue_payload = {
        **sample_plan_payload,
        "vehicle_plate": "闽A66771",
        "due_date": (date(2026, 4, 15) - timedelta(days=1)).isoformat(),
    }
    create_plan(client, overdue_payload)

    evening = client.post("/api/jobs/overdue-alerts/run?business_date=2026-04-15&delivery_slot=evening")
    assert evening.status_code == 200
    assert evening.json()["pre_due_count"] == 0
    assert evening.json()["overdue_risk_count"] == 1

    morning = client.post("/api/jobs/overdue-alerts/run?business_date=2026-04-16&delivery_slot=morning")
    assert morning.status_code == 200
    assert morning.json()["pre_due_count"] == 1
    assert morning.json()["overdue_risk_count"] == 1


def test_manual_job_run_is_immediate_and_not_bound_to_scheduled_slots(client, sample_plan_payload):
    create_plan(client, sample_plan_payload)
    overdue_payload = {
        **sample_plan_payload,
        "vehicle_plate": "鲁A99001",
        "due_date": (date(2026, 4, 15) - timedelta(days=2)).isoformat(),
    }
    create_plan(client, overdue_payload)

    run = client.post("/api/jobs/overdue-alerts/run?business_date=2026-04-15")
    assert run.status_code == 200
    assert run.json()["delivery_slot"] == "manual"
    assert run.json()["pre_due_count"] == 1
    assert run.json()["overdue_risk_count"] == 1
