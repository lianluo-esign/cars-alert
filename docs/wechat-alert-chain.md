# 逾期预警消息封装链路

## 总览
该项目把“逾期预警”拆成 4 层：

1. `AlertDispatcher`
2. `TemplateRenderer`
3. `WechatMessageService`
4. `MockWechatClient`

链路目标是把还款计划中的业务事件，最终落成模拟微信 Inbox 中的一条消息，同时写入提醒记录表，便于审计与回放。

## 关键表关系
- `repayment_plans`：分期还款计划，驱动预警扫描
- `alert_templates`：模板定义，区分 `pre_due` 和 `overdue_risk`
- `reminder_records`：每次发送行为的业务记录
- `wechat_messages`：模拟微信 Inbox 消息
- `system_settings`：保存业务日期覆盖值

关系如下：

```text
repayment_plans
  └─(命中规则)→ alert_templates
      └─(渲染发送)→ reminder_records
          └─(映射)→ wechat_messages
```

## 自动发送链路
### 1. 调度入口
- 自动任务由 APScheduler 定时执行，默认每 60 秒扫描一次。
- 手动任务由 `POST /api/jobs/overdue-alerts/run` 触发。
- 两者都会调用同一个 `AlertDispatcher.run()`，差异只在是否显式传入 `business_date`。

### 2. 业务日期解析
- 如果任务接口传入 `business_date`，优先使用该日期。
- 否则读取 `system_settings.business_date_override`。
- 如果仍为空，回退到服务端当天日期。

### 3. 规则命中
`AlertDispatcher` 会扫描所有未还款计划：

- 还款前 3 天：`due_date - business_date == 3`
  - 触发 `pre_due`
  - 同一笔计划只发送一次
- 逾期超过 7 天：`business_date - due_date > 7`
  - 触发 `overdue_risk`
  - 每次扫描都发送
  - 首次触发后把计划状态更新为 `risk_triggered`

### 4. 模板渲染
`TemplateRenderer` 负责把模板文本里的占位符替换成业务字段。

当前支持变量：
- `{{borrower_name}}`
- `{{vehicle_plate}}`
- `{{amount_due}}`
- `{{due_date}}`
- `{{installment_no}}`
- `{{sales_username}}`
- `{{overdue_days}}`

### 5. 微信发送封装
`WechatMessageService.send()` 只关心一个统一输入：

```python
send(
    recipient_username="jamesduan",
    source_type="pre_due" | "overdue_risk",
    rendered_message=RenderedMessage(title="...", body="...")
)
```

它内部调用 `MockWechatClient.send_template_message()`，将消息写入 `wechat_messages`，模拟“微信模板消息发送成功”。

### 6. 发送结果落库
当 `MockWechatClient` 返回 `message_id` 后，`AlertDispatcher` 会继续写入 `reminder_records`：

- 记录模板来源
- 记录业务日期
- 记录触发原因
- 保存渲染后的标题与正文
- 关联 `message_id`

随后再回写 `wechat_messages.source_record_id`，形成完整链路闭环。

## 手动与自动任务的区别
### 自动任务
- 来源：APScheduler
- 用途：持续轮询并自动出消息
- 日期：优先取系统中设置的业务日期覆盖值，否则取当天

### 手动任务
- 来源：页面按钮或接口调用
- 用途：现场演示和快速验证
- 日期：可直接传查询参数 `business_date=YYYY-MM-DD`

两者共享同一套规则、模板渲染、发送封装和落库逻辑，没有分叉实现。

## 典型时序
```text
定时器 / 手动接口
  → AlertDispatcher.run()
    → 扫描 repayment_plans
    → 选中 alert_templates
    → TemplateRenderer.render()
    → WechatMessageService.send()
    → MockWechatClient.send_template_message()
    → INSERT wechat_messages
    → INSERT reminder_records
    → UPDATE repayment_plans.status（必要时）
```

## 本项目中的接口入口
- `GET /api/repayment-plans`
- `POST /api/repayment-plans`
- `PUT /api/repayment-plans/{id}`
- `POST /api/repayment-plans/{id}/mark-paid`
- `GET /api/alert-templates`
- `POST /api/alert-templates`
- `PUT /api/alert-templates/{id}`
- `GET /api/reminder-records`
- `GET /api/wechat/inbox?username=jamesduan`
- `POST /api/wechat/inbox/{id}/read`
- `GET /api/system/business-date`
- `PUT /api/system/business-date`
- `POST /api/jobs/overdue-alerts/run`

## 实现价值
- 规则层、渲染层、发送层职责清晰，后续接真实微信接口时只需要替换 `MockWechatClient`
- `reminder_records` 和 `wechat_messages` 双表保留了“业务记录”和“消息投递结果”
- 手动和自动触发共用同一条链路，演示和后续生产化改造成本都更低
