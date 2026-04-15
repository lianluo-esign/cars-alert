from __future__ import annotations

import os
import sqlite3
from logging import getLogger
from contextlib import asynccontextmanager
from datetime import date
from typing import Literal
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware

from .database import get_db_path, init_database
from .schemas import (
    AlertTemplateCreate,
    AlertTemplateOut,
    AlertTemplateUpdate,
    BusinessDateSettings,
    BusinessDateUpdate,
    JobRunResponse,
    ReminderRecordOut,
    RepaymentPlanCreate,
    RepaymentPlanOut,
    RepaymentPlanUpdate,
    WechatMessageOut,
)
from .services import (
    AlertDispatcher,
    create_repayment_plan,
    create_template,
    get_setting,
    list_inbox,
    list_reminder_records,
    list_repayment_plans,
    list_templates,
    mark_message_read,
    mark_plan_paid,
    resolve_business_date,
    set_setting,
    update_repayment_plan,
    update_template,
)

logger = getLogger(__name__)


def create_app(*, db_path: str | None = None, start_scheduler: bool = True, seed_demo_data: bool = True) -> FastAPI:
    resolved_db_path = get_db_path(db_path)
    scheduler_timezone = os.getenv("ALERT_SCHEDULER_TIMEZONE", "Asia/Shanghai")
    scheduler = BackgroundScheduler(timezone=ZoneInfo(scheduler_timezone)) if start_scheduler else None

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        init_database(resolved_db_path, seed_demo_data=seed_demo_data)
        app.state.db_path = resolved_db_path
        app.state.dispatcher = AlertDispatcher(resolved_db_path)
        app.state.scheduler = scheduler
        if scheduler is not None:
            def run_scheduled_job(slot: Literal["morning", "evening"]):
                result = app.state.dispatcher.run(
                    delivery_slot=slot,
                    use_business_date_override=False,
                )
                logger.info(
                    "auto overdue alert job finished slot=%s business_date=%s pre_due=%s overdue=%s",
                    slot,
                    result["business_date"],
                    result["pre_due_count"],
                    result["overdue_risk_count"],
                )

            scheduler.add_job(
                lambda: run_scheduled_job("morning"),
                "cron",
                hour=9,
                minute=0,
                id="overdue-alert-job-morning",
                replace_existing=True,
            )
            scheduler.add_job(
                lambda: run_scheduled_job("evening"),
                "cron",
                hour=18,
                minute=0,
                id="overdue-alert-job-evening",
                replace_existing=True,
            )
            scheduler.start()
        yield
        if scheduler is not None and scheduler.running:
            scheduler.shutdown(wait=False)

    app = FastAPI(title="Cars Alert Demo", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/repayment-plans", response_model=list[RepaymentPlanOut])
    def repayment_plans(
        request: Request,
        business_date: date | None = Query(default=None),
    ):
        resolved_date = resolve_business_date(request.app.state.db_path, business_date)
        return list_repayment_plans(request.app.state.db_path, resolved_date)

    @app.post("/api/repayment-plans", response_model=RepaymentPlanOut)
    def add_repayment_plan(request: Request, payload: RepaymentPlanCreate):
        return create_repayment_plan(request.app.state.db_path, payload.model_dump())

    @app.put("/api/repayment-plans/{plan_id}", response_model=RepaymentPlanOut)
    def edit_repayment_plan(request: Request, plan_id: int, payload: RepaymentPlanUpdate):
        plan = update_repayment_plan(request.app.state.db_path, plan_id, payload.model_dump())
        if plan is None:
            raise HTTPException(status_code=404, detail="Repayment plan not found")
        return plan

    @app.post("/api/repayment-plans/{plan_id}/mark-paid", response_model=RepaymentPlanOut)
    def mark_paid(request: Request, plan_id: int):
        plan = mark_plan_paid(request.app.state.db_path, plan_id)
        if plan is None:
            raise HTTPException(status_code=404, detail="Repayment plan not found")
        return plan

    @app.get("/api/alert-templates", response_model=list[AlertTemplateOut])
    def alert_templates(request: Request):
        return list_templates(request.app.state.db_path)

    @app.post("/api/alert-templates", response_model=AlertTemplateOut)
    def add_alert_template(request: Request, payload: AlertTemplateCreate):
        try:
            return create_template(request.app.state.db_path, payload.model_dump())
        except sqlite3.IntegrityError as error:
            raise HTTPException(status_code=400, detail="Template code must be unique") from error

    @app.put("/api/alert-templates/{template_id}", response_model=AlertTemplateOut)
    def edit_alert_template(request: Request, template_id: int, payload: AlertTemplateUpdate):
        try:
            template = update_template(request.app.state.db_path, template_id, payload.model_dump())
        except sqlite3.IntegrityError as error:
            raise HTTPException(status_code=400, detail="Template code must be unique") from error
        if template is None:
            raise HTTPException(status_code=404, detail="Alert template not found")
        return template

    @app.get("/api/reminder-records", response_model=list[ReminderRecordOut])
    def reminder_records(request: Request):
        return list_reminder_records(request.app.state.db_path)

    @app.get("/api/wechat/inbox", response_model=list[WechatMessageOut])
    def inbox(request: Request, username: str = Query(default="jamesduan")):
        return list_inbox(request.app.state.db_path, username)

    @app.post("/api/wechat/inbox/{message_id}/read")
    def read_message(request: Request, message_id: int):
        if not mark_message_read(request.app.state.db_path, message_id):
            raise HTTPException(status_code=404, detail="Message not found")
        return {"ok": True}

    @app.get("/api/system/business-date", response_model=BusinessDateSettings)
    def get_business_date(request: Request):
        stored_value = get_setting(request.app.state.db_path, "business_date_override")
        resolved = resolve_business_date(request.app.state.db_path)
        return {
            "override_date": stored_value,
            "resolved_date": resolved,
        }

    @app.put("/api/system/business-date", response_model=BusinessDateSettings)
    def put_business_date(request: Request, payload: BusinessDateUpdate):
        set_setting(
            request.app.state.db_path,
            "business_date_override",
            None if payload.business_date is None else payload.business_date.isoformat(),
        )
        return {
            "override_date": payload.business_date,
            "resolved_date": resolve_business_date(
                request.app.state.db_path,
                payload.business_date,
            ),
        }

    @app.post("/api/jobs/overdue-alerts/run", response_model=JobRunResponse)
    def run_job(
        request: Request,
        business_date: date | None = Query(default=None),
        delivery_slot: Literal["morning", "evening", "manual"] = Query(default="manual"),
    ):
        return request.app.state.dispatcher.run(
            override_business_date=business_date,
            delivery_slot=delivery_slot,
        )

    @app.get("/api/health")
    def healthcheck():
        return {"ok": True}

    return app


app = create_app()
