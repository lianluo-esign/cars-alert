import { useEffect, useState, startTransition } from 'react'
import { NavLink, Route, Routes } from 'react-router-dom'
import {
  createRepaymentPlan,
  createTemplate,
  fetchBusinessDate,
  fetchInbox,
  fetchReminderRecords,
  fetchRepaymentPlans,
  fetchTemplates,
  markInboxRead,
  markPlanPaid,
  runOverdueJob,
  updateBusinessDate,
  updateRepaymentPlan,
  updateTemplate,
} from './api'
import './App.css'

const emptyPlan = {
  borrower_name: '',
  vehicle_plate: '',
  amount_due: '',
  installment_no: 1,
  due_date: '',
  sales_username: 'jamesduan',
}

const emptyTemplate = {
  code: '',
  name: '',
  event_type: 'pre_due',
  title_template: '',
  body_template: '',
  enabled: true,
}

const reminderPageSize = 5
const planPageSize = 5
const inboxPageSize = 5

function formatMoney(value) {
  return Number(value || 0).toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

function formatDate(value) {
  return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '-'
}

function statusLabel(status) {
  return {
    pending: '待还款',
    overdue: '已逾期',
    risk_triggered: '风控中',
    paid: '已还款',
  }[status] || status
}

function sourceLabel(sourceType) {
  return sourceType === 'overdue_risk' ? '风控提醒' : '还款提醒'
}

function App() {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [plans, setPlans] = useState([])
  const [templates, setTemplates] = useState([])
  const [records, setRecords] = useState([])
  const [inbox, setInbox] = useState([])
  const [businessDateState, setBusinessDateState] = useState({
    override_date: '',
    resolved_date: '',
  })
  const [jobSummary, setJobSummary] = useState(null)
  const [planForm, setPlanForm] = useState(emptyPlan)
  const [templateForm, setTemplateForm] = useState(emptyTemplate)
  const [editingPlanId, setEditingPlanId] = useState(null)
  const [editingTemplateId, setEditingTemplateId] = useState(null)

  async function loadDashboard(nextBusinessDate) {
    setLoading(true)
    setError('')
    try {
      const [settings, repaymentPlans, templateList, reminderList, inboxList] = await Promise.all([
        fetchBusinessDate(),
        fetchRepaymentPlans(nextBusinessDate),
        fetchTemplates(),
        fetchReminderRecords(),
        fetchInbox('jamesduan'),
      ])
      startTransition(() => {
        setBusinessDateState({
          override_date: settings.override_date || '',
          resolved_date: settings.resolved_date,
        })
        setPlans(repaymentPlans)
        setTemplates(templateList)
        setRecords(reminderList)
        setInbox(inboxList)
      })
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadDashboard()
  }, [])

  async function handlePlanSubmit(event) {
    event.preventDefault()
    setError('')
    try {
      const payload = {
        ...planForm,
        amount_due: Number(planForm.amount_due),
        installment_no: Number(planForm.installment_no),
      }
      if (editingPlanId) {
        await updateRepaymentPlan(editingPlanId, payload)
      } else {
        await createRepaymentPlan(payload)
      }
      setPlanForm(emptyPlan)
      setEditingPlanId(null)
      await loadDashboard(businessDateState.override_date || undefined)
    } catch (requestError) {
      setError(requestError.message)
    }
  }

  async function handleTemplateSubmit(event) {
    event.preventDefault()
    setError('')
    try {
      if (editingTemplateId) {
        await updateTemplate(editingTemplateId, templateForm)
      } else {
        await createTemplate(templateForm)
      }
      setTemplateForm(emptyTemplate)
      setEditingTemplateId(null)
      await loadDashboard(businessDateState.override_date || undefined)
    } catch (requestError) {
      setError(requestError.message)
    }
  }

  async function handleRunJob() {
    setError('')
    try {
      const summary = await runOverdueJob(businessDateState.override_date || undefined)
      setJobSummary(summary)
      await loadDashboard(businessDateState.override_date || undefined)
    } catch (requestError) {
      setError(requestError.message)
    }
  }

  async function handleBusinessDateSave(event) {
    event.preventDefault()
    setError('')
    try {
      await updateBusinessDate(businessDateState.override_date)
      await loadDashboard(businessDateState.override_date || undefined)
    } catch (requestError) {
      setError(requestError.message)
    }
  }

  async function handleMarkPaid(id) {
    setError('')
    try {
      await markPlanPaid(id)
      await loadDashboard(businessDateState.override_date || undefined)
    } catch (requestError) {
      setError(requestError.message)
    }
  }

  async function handleMarkRead(id) {
    setError('')
    try {
      await markInboxRead(id)
      await loadDashboard(businessDateState.override_date || undefined)
    } catch (requestError) {
      setError(requestError.message)
    }
  }

  return (
    <div className="shell">
      <aside className="sidebar">
        <p className="eyebrow">Cars Alert</p>
        <h1>逾期预警与模拟微信</h1>
        <p className="summary">
          业务员固定为 <strong>jamesduan</strong>。当前系统会自动扫描分期计划，并把模板消息投递到模拟微信 Inbox。
        </p>
        <nav className="nav">
          <NavLink to="/" end>
            逾期预警
          </NavLink>
          <NavLink to="/inbox">模拟微信 Inbox</NavLink>
        </nav>
        <section className="summary-card">
          <h2>业务日期</h2>
          <form onSubmit={handleBusinessDateSave} className="inline-form">
            <input
              type="date"
              value={businessDateState.override_date}
              onChange={(event) =>
                setBusinessDateState((current) => ({
                  ...current,
                  override_date: event.target.value,
                }))
              }
            />
            <button type="submit">保存覆盖日期</button>
          </form>
          <button
            type="button"
            className="ghost"
            onClick={async () => {
              setBusinessDateState((current) => ({ ...current, override_date: '' }))
              await updateBusinessDate('')
              await loadDashboard()
            }}
          >
            清除覆盖
          </button>
          <p>当前解析日期：{businessDateState.resolved_date || '-'}</p>
          <button type="button" className="highlight" onClick={handleRunJob}>
            立即执行一次扫描
          </button>
          {jobSummary ? (
            <div className="job-summary">
              <p>扫描日期：{jobSummary.business_date}</p>
              <p>
                触发方式：
                {jobSummary.delivery_slot === 'evening'
                  ? '18:00 自动任务'
                  : jobSummary.delivery_slot === 'morning'
                    ? '09:00 自动任务'
                    : '立即执行扫描'}
              </p>
              <p>还款提醒：{jobSummary.pre_due_count}</p>
              <p>风控提醒：{jobSummary.overdue_risk_count}</p>
            </div>
          ) : null}
        </section>
      </aside>

      <main className="main-panel">
        {error ? <div className="error-banner">{error}</div> : null}
        {loading ? <div className="loading">数据加载中...</div> : null}
        <Routes>
          <Route
            path="/"
            element={
              <DashboardPage
                plans={plans}
                templates={templates}
                records={records}
                planForm={planForm}
                templateForm={templateForm}
                editingPlanId={editingPlanId}
                editingTemplateId={editingTemplateId}
                setPlanForm={setPlanForm}
                setTemplateForm={setTemplateForm}
                setEditingPlanId={setEditingPlanId}
                setEditingTemplateId={setEditingTemplateId}
                onPlanSubmit={handlePlanSubmit}
                onTemplateSubmit={handleTemplateSubmit}
                onMarkPaid={handleMarkPaid}
              />
            }
          />
          <Route
            path="/inbox"
            element={<InboxPage inbox={inbox} onMarkRead={handleMarkRead} />}
          />
        </Routes>
      </main>
    </div>
  )
}

function DashboardPage({
  plans,
  templates,
  records,
  planForm,
  templateForm,
  editingPlanId,
  editingTemplateId,
  setPlanForm,
  setTemplateForm,
  setEditingPlanId,
  setEditingTemplateId,
  onPlanSubmit,
  onTemplateSubmit,
  onMarkPaid,
}) {
  const [planPage, setPlanPage] = useState(1)
  const [recordPage, setRecordPage] = useState(1)
  const totalPlanPages = Math.max(1, Math.ceil(plans.length / planPageSize))
  const totalRecordPages = Math.max(1, Math.ceil(records.length / reminderPageSize))
  const safePlanPage = Math.min(planPage, totalPlanPages)
  const safeRecordPage = Math.min(recordPage, totalRecordPages)
  const pagedPlans = plans.slice(
    (safePlanPage - 1) * planPageSize,
    safePlanPage * planPageSize,
  )
  const pagedRecords = records.slice(
    (safeRecordPage - 1) * reminderPageSize,
    safeRecordPage * reminderPageSize,
  )

  useEffect(() => {
    if (planPage !== safePlanPage) {
      setPlanPage(safePlanPage)
    }
  }, [planPage, safePlanPage])

  useEffect(() => {
    if (recordPage !== safeRecordPage) {
      setRecordPage(safeRecordPage)
    }
  }, [recordPage, safeRecordPage])

  return (
    <div className="page-grid">
      <section className="panel panel-wide">
        <div className="panel-heading">
          <div>
            <p className="panel-tag">发送规则</p>
            <h2>当前自动预警规则</h2>
          </div>
        </div>
        <div className="rule-grid">
          <article className="template-card">
            <strong>还款前 3 天</strong>
            <p>进入预警窗口后，每天上午 09:00 自动向业务员发送一次提醒。</p>
            <p>覆盖日期：到期前第 3、2、1 天。点击“立即执行一次扫描”时也会立刻触发一次检查，当天还款后自动停发。</p>
          </article>
          <article className="template-card">
            <strong>已逾期</strong>
            <p>从逾期当天开始，每天 09:00 和 18:00 各发送一次预警消息。</p>
            <p>逾期超过 7 天自动标记为风控中；点击“立即执行一次扫描”会即时补跑一次，一旦标记已还款，系统立即停止发送。</p>
          </article>
        </div>
      </section>

      <section className="panel panel-wide">
        <div className="panel-heading">
          <div>
            <p className="panel-tag">分期计划</p>
            <h2>还款计划列表</h2>
          </div>
          <div className="pagination-summary">
            <span>共 {plans.length} 条</span>
            <span>
              第 {safePlanPage} / {totalPlanPages} 页
            </span>
          </div>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>客户</th>
                <th>车牌</th>
                <th>期数</th>
                <th>应还日</th>
                <th>应还金额</th>
                <th>状态</th>
                <th>逾期天数</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {pagedPlans.map((plan) => (
                <tr key={plan.id}>
                  <td>{plan.borrower_name}</td>
                  <td>{plan.vehicle_plate}</td>
                  <td>第 {plan.installment_no} 期</td>
                  <td>{plan.due_date}</td>
                  <td>{formatMoney(plan.amount_due)}</td>
                  <td>
                    <span className={`pill pill-${plan.status}`}>{statusLabel(plan.status)}</span>
                  </td>
                  <td>{plan.overdue_days}</td>
                  <td className="actions">
                    <button
                      type="button"
                      className="ghost"
                      onClick={() => {
                        setEditingPlanId(plan.id)
                        setPlanForm({
                          borrower_name: plan.borrower_name,
                          vehicle_plate: plan.vehicle_plate,
                          amount_due: String(plan.amount_due),
                          installment_no: plan.installment_no,
                          due_date: plan.due_date,
                          sales_username: plan.sales_username,
                        })
                      }}
                    >
                      编辑
                    </button>
                    <button
                      type="button"
                      className="ghost"
                      onClick={() => onMarkPaid(plan.id)}
                      disabled={plan.status === 'paid'}
                    >
                      标记已还款
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="pagination-bar">
          <button
            type="button"
            className="ghost"
            disabled={safePlanPage <= 1}
            onClick={() => setPlanPage((page) => Math.max(1, page - 1))}
          >
            上一页
          </button>
          <div className="pagination-pages">
            {Array.from({ length: totalPlanPages }, (_, index) => index + 1).map((page) => (
              <button
                key={page}
                type="button"
                className={page === safePlanPage ? 'highlight page-pill' : 'ghost page-pill'}
                onClick={() => setPlanPage(page)}
              >
                {page}
              </button>
            ))}
          </div>
          <button
            type="button"
            className="ghost"
            disabled={safePlanPage >= totalPlanPages}
            onClick={() => setPlanPage((page) => Math.min(totalPlanPages, page + 1))}
          >
            下一页
          </button>
        </div>
      </section>

      <section className="panel">
        <div className="panel-heading">
          <div>
            <p className="panel-tag">录入</p>
            <h2>{editingPlanId ? '编辑还款计划' : '新增还款计划'}</h2>
          </div>
          {editingPlanId ? (
            <button
              type="button"
              className="ghost"
              onClick={() => {
                setEditingPlanId(null)
                setPlanForm(emptyPlan)
              }}
            >
              取消编辑
            </button>
          ) : null}
        </div>
        <form className="form-stack" onSubmit={onPlanSubmit}>
          <label>
            客户姓名
            <input
              value={planForm.borrower_name}
              onChange={(event) =>
                setPlanForm((current) => ({ ...current, borrower_name: event.target.value }))
              }
              required
            />
          </label>
          <label>
            车牌号
            <input
              value={planForm.vehicle_plate}
              onChange={(event) =>
                setPlanForm((current) => ({ ...current, vehicle_plate: event.target.value }))
              }
              required
            />
          </label>
          <label>
            应还金额
            <input
              type="number"
              min="0"
              step="0.01"
              value={planForm.amount_due}
              onChange={(event) =>
                setPlanForm((current) => ({ ...current, amount_due: event.target.value }))
              }
              required
            />
          </label>
          <label>
            分期期数
            <input
              type="number"
              min="1"
              value={planForm.installment_no}
              onChange={(event) =>
                setPlanForm((current) => ({ ...current, installment_no: event.target.value }))
              }
              required
            />
          </label>
          <label>
            应还日期
            <input
              type="date"
              value={planForm.due_date}
              onChange={(event) =>
                setPlanForm((current) => ({ ...current, due_date: event.target.value }))
              }
              required
            />
          </label>
          <button type="submit" className="highlight">
            {editingPlanId ? '保存计划' : '创建计划'}
          </button>
        </form>
      </section>

      <section className="panel panel-wide">
        <div className="panel-heading">
          <div>
            <p className="panel-tag">模板</p>
            <h2>逾期预警模板</h2>
          </div>
        </div>
        <div className="template-list">
          {templates.map((template) => (
            <article key={template.id} className="template-card">
              <div className="template-card-top">
                <div>
                  <strong>{template.name}</strong>
                  <p>{template.code}</p>
                </div>
                <span className={`pill ${template.enabled ? 'pill-paid' : 'pill-overdue'}`}>
                  {template.enabled ? '启用中' : '已停用'}
                </span>
              </div>
              <p>事件：{sourceLabel(template.event_type)}</p>
              <p>标题：{template.title_template}</p>
              <p>正文：{template.body_template}</p>
              <button
                type="button"
                className="ghost"
                onClick={() => {
                  setEditingTemplateId(template.id)
                  setTemplateForm({
                    code: template.code,
                    name: template.name,
                    event_type: template.event_type,
                    title_template: template.title_template,
                    body_template: template.body_template,
                    enabled: template.enabled,
                  })
                }}
              >
                编辑模板
              </button>
            </article>
          ))}
        </div>
      </section>

      <section className="panel">
        <div className="panel-heading">
          <div>
            <p className="panel-tag">模板表单</p>
            <h2>{editingTemplateId ? '编辑模板' : '新增模板'}</h2>
          </div>
          {editingTemplateId ? (
            <button
              type="button"
              className="ghost"
              onClick={() => {
                setEditingTemplateId(null)
                setTemplateForm(emptyTemplate)
              }}
            >
              取消编辑
            </button>
          ) : null}
        </div>
        <form className="form-stack" onSubmit={onTemplateSubmit}>
          <label>
            模板编码
            <input
              value={templateForm.code}
              onChange={(event) =>
                setTemplateForm((current) => ({ ...current, code: event.target.value }))
              }
              required
            />
          </label>
          <label>
            模板名称
            <input
              value={templateForm.name}
              onChange={(event) =>
                setTemplateForm((current) => ({ ...current, name: event.target.value }))
              }
              required
            />
          </label>
          <label>
            事件类型
            <select
              value={templateForm.event_type}
              onChange={(event) =>
                setTemplateForm((current) => ({ ...current, event_type: event.target.value }))
              }
            >
              <option value="pre_due">还款前提醒</option>
              <option value="overdue_risk">逾期风控提醒</option>
            </select>
          </label>
          <label>
            标题模板
            <input
              value={templateForm.title_template}
              onChange={(event) =>
                setTemplateForm((current) => ({ ...current, title_template: event.target.value }))
              }
              required
            />
          </label>
          <label>
            正文模板
            <textarea
              rows="5"
              value={templateForm.body_template}
              onChange={(event) =>
                setTemplateForm((current) => ({ ...current, body_template: event.target.value }))
              }
              required
            />
          </label>
          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={templateForm.enabled}
              onChange={(event) =>
                setTemplateForm((current) => ({ ...current, enabled: event.target.checked }))
              }
            />
            是否启用
          </label>
          <button type="submit" className="highlight">
            {editingTemplateId ? '保存模板' : '创建模板'}
          </button>
        </form>
      </section>

      <section className="panel panel-wide">
        <div className="panel-heading">
          <div>
            <p className="panel-tag">链路审计</p>
            <h2>提醒记录</h2>
          </div>
          <div className="pagination-summary">
            <span>共 {records.length} 条</span>
            <span>
              第 {safeRecordPage} / {totalRecordPages} 页
            </span>
          </div>
        </div>
        <div className="record-list">
          {pagedRecords.map((record) => (
            <article key={record.id} className="record-card">
              <header>
                <strong>{record.rendered_title}</strong>
                <span>{record.business_date}</span>
              </header>
              <p>{record.rendered_body}</p>
              <footer>
                <span>{record.delivery_slot === 'evening' ? '18:00' : '09:00'}</span>
                <span>{record.vehicle_plate}</span>
                <span>{record.template_name}</span>
                <span>{record.trigger_reason}</span>
              </footer>
            </article>
          ))}
        </div>
        <div className="pagination-bar">
          <button
            type="button"
            className="ghost"
            disabled={safeRecordPage <= 1}
            onClick={() => setRecordPage((page) => Math.max(1, page - 1))}
          >
            上一页
          </button>
          <div className="pagination-pages">
            {Array.from({ length: totalRecordPages }, (_, index) => index + 1).map((page) => (
              <button
                key={page}
                type="button"
                className={page === safeRecordPage ? 'highlight page-pill' : 'ghost page-pill'}
                onClick={() => setRecordPage(page)}
              >
                {page}
              </button>
            ))}
          </div>
          <button
            type="button"
            className="ghost"
            disabled={safeRecordPage >= totalRecordPages}
            onClick={() => setRecordPage((page) => Math.min(totalRecordPages, page + 1))}
          >
            下一页
          </button>
        </div>
      </section>
    </div>
  )
}

function InboxPage({ inbox, onMarkRead }) {
  const [inboxPage, setInboxPage] = useState(1)
  const totalInboxPages = Math.max(1, Math.ceil(inbox.length / inboxPageSize))
  const safeInboxPage = Math.min(inboxPage, totalInboxPages)
  const pagedInbox = inbox.slice(
    (safeInboxPage - 1) * inboxPageSize,
    safeInboxPage * inboxPageSize,
  )

  useEffect(() => {
    if (inboxPage !== safeInboxPage) {
      setInboxPage(safeInboxPage)
    }
  }, [inboxPage, safeInboxPage])

  return (
    <div className="page-grid">
      <section className="panel panel-wide inbox-panel">
        <div className="panel-heading">
          <div>
            <p className="panel-tag">模拟微信</p>
            <h2>jamesduan 的 Inbox</h2>
          </div>
          <div className="pagination-summary">
            <span>共 {inbox.length} 条</span>
            <span>
              第 {safeInboxPage} / {totalInboxPages} 页
            </span>
          </div>
        </div>
        <div className="inbox-list">
          {pagedInbox.map((message) => (
            <article key={message.id} className={`message-card ${message.read_status ? 'read' : 'unread'}`}>
              <div className="message-top">
                <div>
                  <span className={`pill ${message.read_status ? 'pill-paid' : 'pill-risk_triggered'}`}>
                    {message.read_status ? '已读' : '未读'}
                  </span>
                  <strong>{message.title}</strong>
                </div>
                <button
                  type="button"
                  className="ghost"
                  disabled={message.read_status}
                  onClick={() => onMarkRead(message.id)}
                >
                  标记已读
                </button>
              </div>
              <p>{message.body}</p>
              <footer>
                <span>{sourceLabel(message.source_type)}</span>
                <span>{formatDate(message.sent_at)}</span>
                <span>记录 ID: {message.source_record_id || '-'}</span>
              </footer>
            </article>
          ))}
        </div>
        <div className="pagination-bar">
          <button
            type="button"
            className="ghost"
            disabled={safeInboxPage <= 1}
            onClick={() => setInboxPage((page) => Math.max(1, page - 1))}
          >
            上一页
          </button>
          <div className="pagination-pages">
            {Array.from({ length: totalInboxPages }, (_, index) => index + 1).map((page) => (
              <button
                key={page}
                type="button"
                className={page === safeInboxPage ? 'highlight page-pill' : 'ghost page-pill'}
                onClick={() => setInboxPage(page)}
              >
                {page}
              </button>
            ))}
          </div>
          <button
            type="button"
            className="ghost"
            disabled={safeInboxPage >= totalInboxPages}
            onClick={() => setInboxPage((page) => Math.min(totalInboxPages, page + 1))}
          >
            下一页
          </button>
        </div>
      </section>
    </div>
  )
}

export default App
