const jsonHeaders = {
  'Content-Type': 'application/json',
}

async function request(path, options = {}) {
  const response = await fetch(path, options)
  if (!response.ok) {
    let detail = 'Request failed'
    try {
      const data = await response.json()
      detail = data.detail || detail
    } catch {
      // Ignore invalid JSON and keep the fallback message.
    }
    throw new Error(detail)
  }
  if (response.status === 204) {
    return null
  }
  return response.json()
}

export function fetchRepaymentPlans(businessDate) {
  const query = businessDate ? `?business_date=${businessDate}` : ''
  return request(`/api/repayment-plans${query}`)
}

export function createRepaymentPlan(payload) {
  return request('/api/repayment-plans', {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify(payload),
  })
}

export function updateRepaymentPlan(id, payload) {
  return request(`/api/repayment-plans/${id}`, {
    method: 'PUT',
    headers: jsonHeaders,
    body: JSON.stringify(payload),
  })
}

export function markPlanPaid(id) {
  return request(`/api/repayment-plans/${id}/mark-paid`, {
    method: 'POST',
  })
}

export function fetchTemplates() {
  return request('/api/alert-templates')
}

export function createTemplate(payload) {
  return request('/api/alert-templates', {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify(payload),
  })
}

export function updateTemplate(id, payload) {
  return request(`/api/alert-templates/${id}`, {
    method: 'PUT',
    headers: jsonHeaders,
    body: JSON.stringify(payload),
  })
}

export function fetchReminderRecords() {
  return request('/api/reminder-records')
}

export function fetchInbox(username = 'jamesduan') {
  return request(`/api/wechat/inbox?username=${username}`)
}

export function markInboxRead(id) {
  return request(`/api/wechat/inbox/${id}/read`, {
    method: 'POST',
  })
}

export function fetchBusinessDate() {
  return request('/api/system/business-date')
}

export function updateBusinessDate(businessDate) {
  return request('/api/system/business-date', {
    method: 'PUT',
    headers: jsonHeaders,
    body: JSON.stringify({
      business_date: businessDate || null,
    }),
  })
}

export function runOverdueJob(businessDate) {
  const query = businessDate ? `?business_date=${businessDate}` : ''
  return request(`/api/jobs/overdue-alerts/run${query}`, {
    method: 'POST',
  })
}
