from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.database import init_database
from app.main import create_app


@pytest.fixture
def db_path(tmp_path) -> str:
    path = tmp_path / "test.db"
    init_database(str(path), seed_demo_data=False)
    return str(path)


@pytest.fixture
def client(tmp_path):
    path = tmp_path / "api.db"
    app = create_app(db_path=str(path), start_scheduler=False, seed_demo_data=False)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def sample_plan_payload():
    return {
        "borrower_name": "测试客户",
        "vehicle_plate": "沪A12345",
        "amount_due": 3200,
        "installment_no": 4,
        "due_date": date(2026, 4, 18).isoformat(),
        "sales_username": "jamesduan",
    }


@pytest.fixture
def sample_template_payload():
    return {
        "code": "CUSTOM_PRE_DUE",
        "name": "自定义还款提醒",
        "event_type": "pre_due",
        "title_template": "【提醒】{{vehicle_plate}} 即将到期",
        "body_template": "客户 {{borrower_name}} 将于 {{due_date}} 还款",
        "enabled": True,
    }
