# Cars Alert

车辆管理系统逾期预警演示项目，采用前后端分离方式实现：

- `app/`：React.js + Vite 前端
- `api-service/`：Python FastAPI 后端
- `docker-compose.yml`：Docker Compose 容器编排
- `docs/`：补充设计文档

项目目标是演示一套“还款提醒 + 逾期预警 + 模拟微信通知”的完整链路，默认单业务员账号为 `jamesduan`。

## 功能概览

- 还款计划 CRUD
- 预警模板 CRUD
- 还款前 3 天自动预警
- 逾期后持续预警
- 超过 7 天自动进入风控状态
- 模拟微信 Inbox 收件箱
- 手动立即执行扫描
- 自动定时任务调度
- SQLite 本地数据库
- Docker Compose 部署

## 技术方案

### 前端

- React.js
- React Router
- Vite
- 原生 `fetch` 调用后端接口

### 后端

- FastAPI
- SQLite
- APScheduler
- Pydantic

### 部署

- Docker
- Docker Compose

## 目录结构

```text
.
├── app
├── api-service
├── docs
├── docker-compose.yml
└── README.md
```

## 本地运行

### 启动后端

```bash
~/.local/bin/pip install --user --break-system-packages -r api-service/requirements.txt
PYTHONPATH=api-service python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8123
```

默认地址：

- API: `http://127.0.0.1:8123`
- OpenAPI: `http://127.0.0.1:8123/docs`

### 启动前端

```bash
cd app
npm install
npm run dev
```

默认地址：

- Web: `http://127.0.0.1:5173`

前端开发环境通过 [vite.config.js](app/vite.config.js) 代理 `/api` 到本地后端。Docker 环境内通过 `http://api-service:8123` 转发。

## Docker Compose

在仓库根目录执行：

```bash
docker compose up --build -d
```

默认端口：

- 前端：`http://127.0.0.1:5173`
- 后端：`http://127.0.0.1:8123`

数据库文件通过卷挂载持久化到：

- `./api-service/data/data.db`

## 操作说明

这一节给出两种常用启动方式：

1. 本地人工手动启动前后端
2. 使用 Docker Compose 编排启动容器

### 方式一：人工手动启动前后端

适合开发联调、代码调试、接口排查。

#### 第 1 步：启动后端 FastAPI

在仓库根目录执行：

```bash
~/.local/bin/pip install --user --break-system-packages -r api-service/requirements.txt
PYTHONPATH=api-service python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8123
```

启动成功后可访问：

- 接口根地址：`http://127.0.0.1:8123`
- Swagger 文档：`http://127.0.0.1:8123/docs`
- 健康检查：`http://127.0.0.1:8123/api/health`

#### 第 2 步：启动前端 React

在另一个终端执行：

```bash
cd app
npm install
npm run dev
```

启动成功后访问：

- 前端页面：`http://127.0.0.1:5173`

#### 第 3 步：联调说明

- 前端开发服务器会把 `/api` 请求代理到本地 FastAPI
- 因此前端和后端都启动后，直接打开 `http://127.0.0.1:5173` 即可

#### 第 4 步：手动停止

- 停止前端：在前端终端按 `Ctrl+C`
- 停止后端：在后端终端按 `Ctrl+C`

### 方式二：Docker Compose 编排启动

适合本地演示、服务器部署、镜像化运行。

#### 第 1 步：准备环境

确认机器已安装：

- Docker
- Docker Compose

可执行检查：

```bash
docker --version
docker compose version
```

#### 第 2 步：启动容器

在仓库根目录执行：

```bash
docker compose up --build -d
```

启动后默认访问地址：

- 前端：`http://127.0.0.1:5173`
- 后端：`http://127.0.0.1:8123`
- OpenAPI：`http://127.0.0.1:8123/docs`

#### 第 3 步：查看运行状态

```bash
docker compose ps
docker compose logs --tail=100
```

如果只查看后端：

```bash
docker compose logs --tail=100 api-service
```

如果只查看前端：

```bash
docker compose logs --tail=100 app
```

#### 第 4 步：停止容器

```bash
docker compose down
```

如果希望保留容器数据但停止运行，也可以：

```bash
docker compose stop
```

#### 第 5 步：重新启动已有容器

```bash
docker compose up -d
```

#### 第 6 步：重新构建并发布新代码

代码更新后执行：

```bash
docker compose up --build -d
```

### 服务器部署建议

如果是在服务器上部署，推荐流程如下：

#### 方案 A：直接拉 GitHub 代码后启动

```bash
git clone <your-repo-url>
cd cars-alert
docker compose up --build -d
```

后续更新：

```bash
git pull origin main
docker compose up --build -d
```

#### 方案 B：直接拉镜像仓库镜像部署

如果服务器只负责运行，不负责构建，可以先拉取已经推送好的镜像，再使用 Compose 或 `docker run` 启动。

当前镜像仓库示例：

- `43.165.184.219:5000/cars-alert-app:latest`
- `43.165.184.219:5000/cars-alert-api-service:latest`

### 数据库文件说明

当前项目使用 SQLite，数据库文件不是固定写死在镜像里，而是通过卷挂载保存在宿主机：

- 宿主机路径：`./api-service/data/data.db`
- 容器内路径：`/app/data/data.db`

这意味着：

- 重新构建镜像不会自动清空数据库
- 删除宿主机数据目录会丢失数据
- 服务器部署时可以直接上传 `data.db` 后复用现有数据

### 常用运维命令

查看容器状态：

```bash
docker compose ps
```

查看后端健康检查：

```bash
curl http://127.0.0.1:8123/api/health
```

查看前端通过代理访问后端是否正常：

```bash
curl http://127.0.0.1:5173/api/health
```

进入后端容器：

```bash
docker exec -it cars-alert-api sh
```

进入前端容器：

```bash
docker exec -it cars-alert-web sh
```

## 数据库表设计

本项目使用 SQLite，核心表如下。

### 1. `repayment_plans`

用途：保存每一笔分期还款计划，是预警扫描的核心业务表。

关键字段：

- `id`：主键
- `borrower_name`：客户姓名
- `vehicle_plate`：车牌号
- `amount_due`：应还金额
- `installment_no`：分期期数
- `due_date`：应还日期
- `status`：`pending | overdue | risk_triggered | paid`
- `sales_username`：业务员用户名，当前固定为 `jamesduan`
- `paid_at`：还款完成时间
- `last_risk_triggered_at`：最近一次进入风控状态的时间
- `created_at / updated_at`

### 2. `alert_templates`

用途：保存预警消息模板。

关键字段：

- `code`：模板编码，例如 `PRE_DUE_REMINDER`
- `name`：模板名称
- `event_type`：事件类型，当前支持 `pre_due`、`overdue_risk`
- `title_template`：消息标题模板
- `body_template`：消息正文模板
- `enabled`：是否启用

### 3. `reminder_records`

用途：保存每一次提醒发送的业务记录，是审计和去重的核心表。

关键字段：

- `repayment_plan_id`：关联还款计划
- `template_id`：关联模板
- `event_type`：提醒类型
- `business_date`：业务日期
- `delivery_slot`：发送时段，当前支持 `morning | evening | manual`
- `trigger_reason`：触发原因
- `send_status`：发送状态
- `message_id`：关联模拟微信消息
- `rendered_title / rendered_body`：渲染后的消息内容
- `recipient_username`：接收业务员

### 4. `wechat_messages`

用途：模拟微信消息收件箱。

关键字段：

- `recipient_username`
- `message_type`
- `title`
- `body`
- `source_type`
- `source_record_id`
- `read_status`
- `sent_at`

### 5. `system_settings`

用途：保存系统级设置。

当前使用：

- `business_date_override`：业务日期覆盖值，用于演示场景快进

## 定时任务核心逻辑设计

定时任务由 APScheduler 驱动，定义在 [main.py](api-service/app/main.py)。

### 自动任务调度

自动任务使用 `cron` 规则：

- 每天早上 `09:00` 触发一次 `morning`
- 每天晚上 `18:00` 触发一次 `evening`

自动任务特点：

- 使用服务器真实日期
- 不读取前端演示用的 `business_date_override`
- 每次执行完成后写日志，包含：
  - 时段
  - 业务日期
  - 前提醒命中数
  - 逾期提醒命中数

### 手动立即扫描

页面中的“立即执行一次扫描”走 `/api/jobs/overdue-alerts/run` 接口。

特点：

- 默认 `delivery_slot=manual`
- 点击后立即触发一次扫描，不依赖 09:00 / 18:00
- 可配合业务日期覆盖值快速演示

### 扫描规则

#### 1. 还款前 3 天提醒

命中条件：

- `1 <= due_date - business_date <= 3`
- 当前仅在 `morning` 或 `manual` 执行时发送

发送策略：

- 自动任务：每天早上 9 点发一次
- 手动任务：点击时立即发一次
- 同一笔计划在同一天同一时段只发送一次
- 一旦标记已还款，后续自动停发

#### 2. 逾期提醒

命中条件：

- `business_date > due_date`

发送策略：

- 自动任务：每天 09:00 和 18:00 各发一次
- 手动任务：点击时立即补跑一次
- 同一笔计划在同一天同一时段只发送一次
- 一旦标记已还款，后续自动停发

#### 3. 风控状态

规则：

- 当 `overdue_days > 7` 时，计划状态升级为 `risk_triggered`
- 但消息仍按逾期预警逻辑发送，只是状态变为风控中

## 微信模板消息发送接口封装思路

当前项目既实现了“模拟微信”链路，也保留了未来切换真实微信通道的清晰抽象。

### 当前模拟链路

当前后端把消息发送拆成四层：

1. `AlertDispatcher`
2. `TemplateRenderer`
3. `WechatMessageService`
4. `MockWechatClient`

### 当前模拟流程

```text
定时任务 / 手动接口
  → AlertDispatcher.run()
    → 读取 repayment_plans
    → 匹配 alert_templates
    → TemplateRenderer.render()
    → WechatMessageService.send()
    → MockWechatClient.send_template_message()
    → INSERT wechat_messages
    → INSERT reminder_records
    → UPDATE repayment_plans.status
```

### 模拟思路说明

在当前项目中，“微信发送成功”并不真正调用外部微信开放平台，而是通过 `MockWechatClient` 将消息落到 `wechat_messages` 表中，再由前端 Inbox 页面展示。

这样做的好处：

- 可以完整演示消息链路
- 可审计、可复盘
- 不依赖真实微信配置
- 开发调试成本低

### 真实链路封装思路

如果后续接入真实微信模板消息，建议保留当前的分层设计，仅替换发送客户端实现。

推荐做法：

#### 1. 保留 `AlertDispatcher`

职责不变：

- 扫描业务数据
- 决定是否命中提醒规则
- 选择模板
- 组装发送上下文

#### 2. 保留 `TemplateRenderer`

职责不变：

- 负责变量替换
- 输出统一结构的标题和正文

#### 3. 保留 `WechatMessageService`

职责升级为通用消息发送编排层：

- 负责调用真实微信 API 客户端
- 处理发送结果
- 失败时写发送失败记录
- 成功时记录微信返回的消息 ID 或 request ID

#### 4. 用真实客户端替换 `MockWechatClient`

例如新增：

- `RealWechatClient`

职责：

- 获取或刷新 access token
- 调用微信模板消息发送接口
- 处理微信错误码
- 输出统一结果对象

### 真实发送链路建议

```text
AlertDispatcher
  → TemplateRenderer
  → WechatMessageService
    → RealWechatClient
      → WeChat Open API
    → 落 reminder_records
    → 落 wechat_messages / send_logs
```

### 真实接口落地建议

如果接入微信，建议补这些能力：

- `access_token` 缓存
- 接收人 openid / unionid 映射
- 模板 ID 管理
- 失败重试
- 限流与熔断
- 死信队列或失败补偿
- 发送日志和错误码归档

## 关键接口

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

## 测试与校验

### 前端

```bash
cd app
npm install
npm run lint
npm run build
```

### 后端

```bash
~/.local/bin/pip install --user --break-system-packages -r api-service/requirements.txt
~/.local/bin/pytest api-service/tests -q
```

当前后端自动化测试已覆盖：

- 单元测试
- 接口测试
- 调度逻辑测试
- 手动触发与定时触发的规则差异
- 还款停发逻辑

## 如何使用 AI 提示词完成这个项目

本项目是通过 Codex CLI 协助完成的，采用：

- React.js 作为前端框架
- Python FastAPI 作为后端框架
- Docker Compose 作为容器编排与部署方式

### AI 协作方式

本项目适合拆成以下几个提示词阶段：

#### 1. 需求澄清阶段

目标：

- 把产品需求转成可执行技术方案
- 明确表设计、定时规则、模拟微信链路、页面结构

提示词示例：

```text
请基于当前仓库设计一个 React 前端 + Python FastAPI 后端的逾期预警系统。
要求包含：
1. 还款计划管理
2. 逾期预警模板
3. 模拟微信 Inbox
4. 自动定时预警
5. 手动触发扫描
先输出一个完整实施方案，不要直接写代码。
```

#### 2. 框架初始化阶段

目标：

- 初始化 `app/` 和 `api-service/`
- 搭建前后端基本骨架

提示词示例：

```text
请在当前仓库中初始化：
- app: React + Vite
- api-service: Python FastAPI
并建立基础目录结构、启动方式和 Docker Compose 配置。
```

#### 3. 业务实现阶段

目标：

- 落地数据库设计
- 实现调度规则
- 实现消息发送封装

提示词示例：

```text
请实现逾期预警业务逻辑：
- 到期前 3 天每日 09:00 提醒
- 逾期后每日 09:00 和 18:00 提醒
- 超过 7 天标记风控
- 已还款停发
同时实现模拟微信消息发送链路和提醒记录落库。
```

#### 4. 测试补齐阶段

目标：

- 补齐后端单元测试和接口测试

提示词示例：

```text
请为当前 FastAPI 项目补齐完整后端测试：
- 单元测试
- 接口测试
- 调度规则测试
- 已还款停发测试
- 手动与自动时段测试
```

#### 5. 部署阶段

目标：

- Docker 化
- 推送镜像
- 调整端口

提示词示例：

```text
请把当前项目整理成可 Docker Compose 部署的结构，
要求：
- 前端端口 5173
- 后端端口 8123
- 输出可推送镜像的构建方案
- 说明数据库卷挂载方式
```

### 使用 Codex CLI 的优势

- 可以直接在真实仓库中操作
- 可以同时完成代码、测试、文档、容器配置
- 适合分阶段迭代，不需要一次性给出完整大提示词
- 可以边实现边校验，减少“只会写方案不会落地”的问题

### 本项目的 AI 实践经验

建议把提示词写成以下风格：

- 明确目标
- 明确技术栈
- 明确目录结构
- 明确边界条件
- 明确是否需要计划、代码、测试、文档

例如：

```text
请直接在当前仓库实现，不要只给方案。
前端用 React.js，后端用 FastAPI。
目录固定为 app 和 api-service。
实现后补充测试、Docker Compose 和 README 文档。
```

这种方式比笼统地说“帮我做一个项目”更稳定。

## 相关文档

- 发送链路说明见 [wechat-alert-chain.md](docs/wechat-alert-chain.md)
