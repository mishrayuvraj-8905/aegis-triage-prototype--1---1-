const BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

async function req(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") {
        detail = body.detail;
      } else if (Array.isArray(body.detail)) {
        // FastAPI/Pydantic validation errors: an array of {loc, msg, ...}
        detail = body.detail.map((d) => d.msg || JSON.stringify(d)).join("; ");
      } else if (body.detail) {
        detail = JSON.stringify(body.detail);
      }
    } catch {}
    const err = new Error(detail);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

export const api = {
  listPatients: (status) => req(`/api/patients${status ? `?status=${status}` : ""}`),
  getPatient: (id) => req(`/api/patients/${id}`),
  createPatient: (payload) => req(`/api/patients`, { method: "POST", body: JSON.stringify(payload) }),
  ehrLookup: (name, dob) => req(`/api/patients/ehr/lookup?name=${encodeURIComponent(name)}${dob ? `&dob=${encodeURIComponent(dob)}` : ""}`),
  acknowledge: (id) => req(`/api/patients/${id}/acknowledge`, { method: "POST" }),
  confirm: (id, acknowledged = false) => req(`/api/patients/${id}/confirm`, { method: "POST", body: JSON.stringify({ acknowledged }) }),
  override: (id, to_tier, reason, acknowledged = false) =>
    req(`/api/patients/${id}/override`, { method: "POST", body: JSON.stringify({ to_tier, reason, acknowledged }) }),
  escalate: (id, reason) => req(`/api/patients/${id}/escalate`, { method: "POST", body: JSON.stringify({ reason }) }),
  markSeen: (id) => req(`/api/patients/${id}/seen`, { method: "POST" }),
  recheck: (id) => req(`/api/patients/${id}/recheck`, { method: "POST" }),
  config: () => req(`/api/config`),
};
