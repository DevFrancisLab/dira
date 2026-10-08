async function readError(response) {
  try {
    const body = await response.json();
    if (body && typeof body.error === "string" && body.error) return body.error;
  } catch {
    // Response body was not JSON.
  }
  return "The request could not be completed.";
}

export async function getCsrfToken() {
  const response = await fetch("/api/auth/csrf/", { credentials: "include" });
  if (!response.ok) throw new Error(await readError(response));
  const body = await response.json();
  if (!body.csrfToken) throw new Error("The authentication service did not issue a CSRF token.");
  return body.csrfToken;
}

async function postJson(path, payload) {
  const csrfToken = await getCsrfToken();
  return fetch(path, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": csrfToken,
    },
    body: JSON.stringify(payload),
  });
}

export async function getCurrentUser() {
  const response = await fetch("/api/auth/me/", { credentials: "include" });
  if (response.status === 401) return null;
  if (!response.ok) throw new Error(await readError(response));
  return response.json();
}

export async function register(account) {
  const response = await postJson("/api/auth/register/", account);
  if (!response.ok) throw new Error(await readError(response));
  return response.json();
}

export async function login(credentials) {
  const response = await postJson("/api/auth/login/", credentials);
  if (!response.ok) throw new Error(await readError(response));
  return response.json();
}

export async function logout() {
  const response = await postJson("/api/auth/logout/", {});
  if (response.status === 401) return;
  if (!response.ok) throw new Error(await readError(response));
}

export async function loadPortfolio() {
  const response = await fetch("/api/portfolio/", { credentials: "include" });
  if (!response.ok) {
    throw new Error("The portfolio API did not respond.");
  }
  return response.json();
}
