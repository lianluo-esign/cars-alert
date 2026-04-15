from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RepaymentPlanBase(BaseModel):
    borrower_name: str = Field(min_length=1, max_length=50)
    vehicle_plate: str = Field(min_length=1, max_length=20)
    amount_due: float = Field(gt=0)
    installment_no: int = Field(ge=1)
    due_date: date
    sales_username: str = "jamesduan"


class RepaymentPlanCreate(RepaymentPlanBase):
    pass


class RepaymentPlanUpdate(RepaymentPlanBase):
    pass


class RepaymentPlanOut(RepaymentPlanBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: Literal["pending", "paid", "overdue", "risk_triggered"]
    stored_status: str
    overdue_days: int
    paid_at: datetime | None = None
    last_risk_triggered_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class AlertTemplateBase(BaseModel):
    code: str = Field(min_length=2, max_length=50)
    name: str = Field(min_length=1, max_length=50)
    event_type: Literal["pre_due", "overdue_risk"]
    title_template: str = Field(min_length=1)
    body_template: str = Field(min_length=1)
    enabled: bool = True


class AlertTemplateCreate(AlertTemplateBase):
    pass


class AlertTemplateUpdate(AlertTemplateBase):
    pass


class AlertTemplateOut(AlertTemplateBase):
    id: int
    created_at: datetime
    updated_at: datetime


class ReminderRecordOut(BaseModel):
    id: int
    repayment_plan_id: int
    template_id: int
    event_type: str
    business_date: date
    delivery_slot: str | None = None
    trigger_reason: str
    send_status: str
    message_id: int | None = None
    rendered_title: str
    rendered_body: str
    recipient_username: str
    borrower_name: str
    vehicle_plate: str
    template_name: str
    created_at: datetime


class WechatMessageOut(BaseModel):
    id: int
    recipient_username: str
    message_type: str
    title: str
    body: str
    source_type: str
    source_record_id: int | None = None
    read_status: bool
    sent_at: datetime


class BusinessDateSettings(BaseModel):
    override_date: date | None = None
    resolved_date: date


class BusinessDateUpdate(BaseModel):
    business_date: date | None = None


class JobRunResponse(BaseModel):
    business_date: date
    delivery_slot: str
    pre_due_count: int
    overdue_risk_count: int
    reminder_record_ids: list[int]
