
const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export async function signup(username, password) {
  const res = await fetch(`${BASE}/auth/signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => null);
    throw new Error(data?.detail || "Signup failed. Please try again.");
  }
  return res.json();
}
export async function login(username, password) {
  const res = await fetch(`${BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => null);
    throw new Error(data?.detail || "Incorrect username or password.");
  }
  return res.json();
}

export async function sendChat(message, conversationId) {
    const token = localStorage.getItem("askflow-token");
    const res = await fetch(`${BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}`, },
        body: JSON.stringify({ message, conversation_id: conversationId }),
    });
     if (res.status === 401) {
    localStorage.removeItem("askflow-token");
    throw new Error("SESSION_EXPIRED");
     }

    if (!res.ok) throw new Error("Chat request failed");
    return res.json();     
    // { conversation_id, reply }
}
export async function getMessages(conversationId) {
    const res = await fetch(`${BASE}/conversations/${conversationId}/messages`);
    if (!res.ok) throw new Error("Could not load messages");
    return res.json();
}

export async function uploadDocument(file) {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${BASE}/documents/upload`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) throw new Error("Upload failed");
  return res.json();
}

export async function getConversations() {
  const token = localStorage.getItem("askflow-token");
  const res = await fetch(`${BASE}/conversations`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error("Could not load conversations");
  return res.json();
}

export async function getConversationMessages(conversationId) {
  const token = localStorage.getItem("askflow-token");
  const res = await fetch(`${BASE}/conversations/${conversationId}/messages`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error("Could not load messages");
  return res.json();
}

export async function renameConversation(conversationId, title) {
  const token = localStorage.getItem("askflow-token");
  const res = await fetch(`${BASE}/conversations/${conversationId}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ title }),
  });
  if (!res.ok) throw new Error("Rename failed");
  return res.json();
}

export async function deleteConversation(conversationId) {
  const token = localStorage.getItem("askflow-token");
  const res = await fetch(`${BASE}/conversations/${conversationId}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error("Delete failed");
}