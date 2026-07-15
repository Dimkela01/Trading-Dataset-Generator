const BASE = '/api'

async function handleResponse(res) {
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    const detail = data.detail
    const msg = Array.isArray(detail)
      ? detail.map((d) => d.msg).join(', ')
      : detail || data.error || `Request failed: ${res.status}`
    throw new Error(msg)
  }
  return res
}

export async function uploadFile(file) {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${BASE}/upload`, { method: 'POST', body: form })
  await handleResponse(res)
  return res.json()
}

export async function previewPipeline(pipelineState, withLabel = true) {
  const res = await fetch(`${BASE}/preview?with_label=${withLabel ? 'true' : 'false'}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(pipelineState),
  })
  await handleResponse(res)
  return res.json()
}

export async function selectAsset(sessionId, symbolColumn, symbolValue) {
  const res = await fetch(`${BASE}/select_asset`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: sessionId,
      symbol_column: symbolColumn,
      symbol_value: symbolValue,
    }),
  })
  await handleResponse(res)
  return res.json()
}

export async function exportDataset(pipelineState) {
  const res = await fetch(`${BASE}/export`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(pipelineState),
  })
  await handleResponse(res)
  return res.blob()
}
