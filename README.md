# Cars Alert

逾期预警演示系统，包含：

- `app/`：React + Vite 前端
- `api-service/`：FastAPI + SQLite 后端
- `docs/`：发送链路与实现说明

系统默认模拟一个业务员 `jamesduan`，支持：

- 还款计划 CRUD
- 预警模板 CRUD
- 还款日前 3 天自动提醒
- 逾期超过 7 天自动触发风控提醒
- 模拟微信 Inbox 收件箱
- 自动调度 + 手动立即执行
- 业务日期覆盖，便于本地快进演示

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

### 1. 启动后端

在仓库根目录执行：

```bash
~/.local/bin/pip install --user --break-system-packages -r api-service/requirements.txt
PYTHONPATH=api-service python3 -m uvicorn app.main:app --reload
```

默认地址：

- API: `http://127.0.0.1:8123`
- OpenAPI: `http://127.0.0.1:8123/docs`

### 2. 启动前端

在另一个终端执行：

```bash
cd app
npm install
npm run dev
```

默认地址：

- Web: `http://127.0.0.1:5173`

前端已在 [vite.config.js](/home/jamesduan/cars-alert/app/vite.config.js) 中代理 `/api` 到 `http://127.0.0.1:8000`。
前端已在 [vite.config.js](/home/jamesduan/cars-alert/app/vite.config.js) 中代理 `/api` 到本地后端；Docker 环境内会通过 `http://api-service:8123` 转发。

## Docker Compose

如果你的机器已安装 Docker / Docker Compose，可以在仓库根目录执行：

```bash
docker compose up --build
```

默认端口：

- 前端：`http://127.0.0.1:5173`
- 后端：`http://127.0.0.1:8123`

数据文件通过卷挂载保存到：

- `./api-service/data/data.db`

## 测试与校验

### 前端

```bash
cd app
npm install
npm run lint
npm run build
```

### 后端

在仓库根目录执行：

```bash
~/.local/bin/pip install --user --break-system-packages -r api-service/requirements.txt
~/.local/bin/pytest api-service/tests -q
```

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

## 文档

- 发送链路说明见 [wechat-alert-chain.md](/home/jamesduan/cars-alert/docs/wechat-alert-chain.md)
