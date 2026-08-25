
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";
// import { useState } from "react";
import { useState, useEffect } from "react";
// import { sendChat } from "./api";
import {
  sendChat, uploadDocument, login, signup,
  getConversations, getConversationMessages,
  renameConversation, deleteConversation,
} from "./api";

// const markdownComponents = {
//   h1: (props) => <h1 className="text-lg font-semibold mt-3 mb-2" {...props} />,
//   h2: (props) => <h2 className="text-base font-semibold mt-3 mb-1.5" {...props} />,
//   h3: (props) => <h3 className="text-sm font-semibold mt-2 mb-1" {...props} />,
//   p: (props) => <p className="mb-2 last:mb-0 leading-relaxed" {...props} />,
//   ul: (props) => <ul className="list-disc pl-5 mb-2 space-y-1" {...props} />,
//   ol: (props) => <ol className="list-decimal pl-5 mb-2 space-y-1" {...props} />,
//   strong: (props) => <strong className="font-semibold" {...props} />,
//   code: (props) => (
//     <code className="bg-black/10 rounded px-1 py-0.5 text-[0.85em] font-mono" {...props} />
//   ),
//   table: (props) => (
//     <div className="overflow-x-auto my-2 rounded-lg border border-slate-300">
//       <table className="w-full text-sm border-collapse" {...props} />
//     </div>
//   ),
//   thead: (props) => <thead className="bg-slate-100" {...props} />,
//   th: (props) => (
//     <th className="border border-slate-300 px-3 py-1.5 text-left font-semibold" {...props} />
//   ),
//   td: (props) => <td className="border border-slate-300 px-3 py-1.5 align-top" {...props} />,
// };
const markdownComponents = {
  h1: (props) => <h1 className="text-lg font-semibold mt-3 mb-2" {...props} />,
  h2: (props) => <h2 className="text-base font-semibold mt-3 mb-1.5" {...props} />,
  h3: (props) => <h3 className="text-sm font-semibold mt-2 mb-1" {...props} />,
  p: (props) => <p className="mb-2 last:mb-0 leading-relaxed break-words" {...props} />,
  ul: (props) => <ul className="list-disc pl-5 mb-2 space-y-1" {...props} />,
  ol: (props) => <ol className="list-decimal pl-5 mb-2 space-y-1" {...props} />,
  strong: (props) => <strong className="font-semibold" {...props} />,

  pre: (props) => (
  <pre
    className="overflow-x-auto rounded-lg bg-slate-800 dark:bg-slate-950
               text-slate-100 p-3 my-2 text-[0.85em] font-mono"
    {...props}
  />
  ),

  // code: (props) => (
  //   <code
  //     className="bg-slate-200 dark:bg-slate-700 text-slate-800 dark:text-teal-300
  //                rounded px-1.5 py-0.5 text-[0.85em] font-mono"
  //     {...props}
  //   />
  // ),

  code: (props) => {
  const isBlock = props.className?.includes("language-");
  if (isBlock) {
    return <code className="font-mono" {...props} />;
  }
  return (
    <code
      className="bg-slate-200 dark:bg-slate-700 text-slate-800 dark:text-teal-300
                 rounded px-1.5 py-0.5 text-[0.85em] font-mono"
      {...props}
    />
    );
  },

  table: (props) => (
    <div className="overflow-x-auto my-2 rounded-lg border border-slate-300 dark:border-slate-600
                    [&_tbody_tr:nth-child(even)]:bg-slate-50
                    dark:[&_tbody_tr:nth-child(even)]:bg-slate-800/60">
      <table className="w-full text-sm border-collapse" {...props} />
    </div>
  ),
  thead: (props) => (
    <thead className="bg-slate-100 dark:bg-slate-700" {...props} />
  ),
  th: (props) => (
    <th
      className="border border-slate-300 dark:border-slate-600 px-3 py-2
                 text-left font-semibold text-slate-800 dark:text-slate-100"
      {...props}
    />
  ),
  td: (props) => (
    <td
      className="border border-slate-300 dark:border-slate-600 px-3 py-2 align-top text-slate-700 dark:text-slate-200 break-words"
      {...props}
    />
  ),
};

export default function App() {
  const [token, setToken] = useState(() => localStorage.getItem("askflow-token"));
  const [authMode, setAuthMode] = useState("login");
  const [authUsername, setAuthUsername] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [authError, setAuthError] = useState("");
  const [authLoading, setAuthLoading] = useState(false);

  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");             // chat bubbles // text box value
  const [conversationId, setConversationId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [theme, setTheme] = useState(() => localStorage.getItem("askflow-theme") || "light");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [uploading, setUploading] = useState(false);

  const [conversations, setConversations] = useState([]);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [editingTitle, setEditingTitle] = useState("");
  const [username, setUsername] = useState(() => localStorage.getItem("askflow-username") || "");
    
  function handleLogout() {
    localStorage.removeItem("askflow-token");
    localStorage.removeItem("askflow-username");   // ADD
    setToken(null);
    setUsername("");                                // ADD
    setMessages([]);
    setConversationId(null);
  }

  async function handleAuthSubmit(e) {
    e.preventDefault();
    setAuthError("");
    setAuthLoading(true);
    try {
      const action = authMode === "login" ? login : signup;
      const data = await action(authUsername, authPassword);
      localStorage.setItem("askflow-token", data.access_token);
      setToken(data.access_token);
      localStorage.setItem("askflow-username", data.username ?? authUsername);   // ADD
      setUsername(data.username ?? authUsername);     
      setAuthPassword("");
    } catch (err) {
      setAuthError(err.message);
    } finally {
      setAuthLoading(false);
    }
  }

  useEffect(() => {
  document.documentElement.classList.toggle("dark", theme === "dark");
  localStorage.setItem("askflow-theme", theme);
  }, [theme]);

  useEffect(() => {
  if (!token) return;
  getConversations()
    .then(setConversations)
    .catch(() => {});
}, [token]);

  // function toggleTheme() {
  // setTheme((prev) => (prev === "light" ? "dark" : "light"));
  // }
  async function handleFileChange(e) {
  const file = e.target.files[0];
  if (!file) return;
  setUploading(true);
  try {
    const data = await uploadDocument(file);
    setMessages((prev) => [
      ...prev,
      { role: "assistant", content: `📄 Uploaded **${data.filename}** — ask me anything about it.` },
    ]);
  } catch (err) {
    setMessages((prev) => [...prev, { role: "assistant", content: "Error uploading file: " + err.message }]);
  } finally {
    setUploading(false);
    e.target.value = "";
  }
  }

  async function handleSend() {
    const text = input.trim();
    if (!text) return;
    // Optimistically show the user's message immediately.
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setInput("");
    setLoading(true);
    try {
      const data = await sendChat(text, conversationId);
      if (!conversationId) {
        setConversations((prev) => [
          { id: data.conversation_id, title: text.slice(0, 40), created_at: new Date().toISOString() },
          ...prev,
        ]);
     }
      setConversationId(data.conversation_id);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: data.reply },
      ]);
    } catch (err) {
      if (err.message === "SESSION_EXPIRED") {
        handleLogout();
        return;
      }

      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Error: " + err.message },
      ]);
    } finally {
      setLoading(false);
    }
  }

  async function selectConversation(id) {
  setConversationId(id);
  setLoading(true);
  try {
    const msgs = await getConversationMessages(id);
    setMessages(msgs.map((m) => ({ role: m.role, content: m.content })));
  } catch (err) {
    setMessages([{ role: "assistant", content: "Could not load that conversation." }]);
  } finally {
    setLoading(false);
  }
}

function startNewChat() {
  setConversationId(null);
  setMessages([]);
}

async function saveRename(id) {
  const title = editingTitle.trim();
  setEditingId(null);
  if (!title) return;
  try {
    await renameConversation(id, title);
    setConversations((prev) => prev.map((c) => (c.id === id ? { ...c, title } : c)));
  } catch {
    // silently ignore; sidebar will just keep the old title
  }
}

async function handleDeleteConversation(id) {
  if (!window.confirm("Delete this conversation? This cannot be undone.")) return;
  try {
    await deleteConversation(id);
    setConversations((prev) => prev.filter((c) => c.id !== id));
    if (conversationId === id) startNewChat();
  } catch {
    // ignore
  }
 }


  if (!token) {
    return (
      <div className="min-h-screen bg-slate-100 dark:bg-slate-950 flex flex-col items-center justify-center p-4">
        <div className="w-full max-w-sm bg-white dark:bg-slate-900 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 p-6">
          <h1 className="font-mono text-lg text-center mb-1 text-slate-800 dark:text-slate-100">
            askflow<span className="text-teal-600 dark:text-teal-400">_</span>
          </h1>
          <p className="text-center text-sm text-slate-400 mb-5">
            {authMode === "login" ? "Log in to continue" : "Create an account"}
          </p>

          <form onSubmit={handleAuthSubmit} className="space-y-3">
            <div>
              <input
                type="text"
                required
                minLength={3}
                maxLength={20}
                placeholder="Username"
                value={authUsername}
                onChange={(e) => setAuthUsername(e.target.value)}
                className="w-full border border-slate-300 dark:border-slate-600 dark:bg-slate-800
                           dark:text-slate-100 rounded-lg px-3 py-2 focus:outline-none
                           focus:ring-2 focus:ring-teal-600"
              />
              {authMode === "signup" && (
                <p className="text-xs text-slate-400 mt-1">
                  3–20 characters: letters, numbers, and underscores only.
                </p>
              )}
            </div>

            <div>
              <input
                type="password"
                required
                minLength={8}
                placeholder="Password"
                value={authPassword}
                onChange={(e) => setAuthPassword(e.target.value)}
                className="w-full border border-slate-300 dark:border-slate-600 dark:bg-slate-800
                           dark:text-slate-100 rounded-lg px-3 py-2 focus:outline-none
                           focus:ring-2 focus:ring-teal-600"
              />
              {authMode === "signup" && (
                <p className="text-xs text-slate-400 mt-1">At least 8 characters.</p>
              )}
            </div>

            {authError && (
              <p className="text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-950/40
                            border border-red-200 dark:border-red-900 rounded-lg px-3 py-2">
                {authError}
              </p>
            )}

            <button
              type="submit"
              disabled={authLoading}
              className="w-full bg-teal-700 text-white py-2 rounded-lg
                         hover:bg-teal-800 disabled:opacity-50"
            >
              {authLoading ? "Please wait..." : authMode === "login" ? "Log In" : "Sign Up"}
            </button>
          </form>

          <button
            onClick={() => {
              setAuthMode(authMode === "login" ? "signup" : "login");
              setAuthError("");
            }}
            className="w-full text-center text-sm text-teal-700 dark:text-teal-400 mt-4 hover:underline"
          >
            {authMode === "login" ? "Need an account? Sign up" : "Already have an account? Log in"}
          </button>
        </div>
      </div>
    );
  }
  return (
    <div className="min-h-screen flex bg-slate-100 dark:bg-slate-950">
      {/* Sidebar */}
      <aside
        className={
          "flex flex-col shrink-0 bg-slate-900 dark:bg-black text-slate-100 " +
          "transition-all duration-200 " +
          (sidebarCollapsed ? "w-14" : "w-64")
        }
      >
        <div className="px-3 py-4 flex items-center justify-between border-b border-white/10">
          {!sidebarCollapsed && (
            <h1 className="font-mono text-sm tracking-wide">
              askflow<span className="text-teal-400">_</span>
            </h1>
          )}
          <button
            onClick={() => setSidebarCollapsed((prev) => !prev)}
            className="p-1 rounded hover:bg-white/10 text-slate-300"
            aria-label="Toggle sidebar"
          >
            {sidebarCollapsed ? "»" : "«"}
          </button>
        </div>

        <div className="px-2 pt-2">
          <button
            onClick={startNewChat}
            className={
              "w-full flex items-center gap-2 rounded-lg px-2 py-2 text-sm hover:bg-white/10 " +
              (sidebarCollapsed ? "justify-center" : "")
            }
          >
            <span>＋</span>
            {!sidebarCollapsed && <span>New chat</span>}
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-2 py-2 space-y-0.5">
          {!sidebarCollapsed && (
            <>
              {conversations.length === 0 && (
                <p className="text-xs text-slate-500 px-2 py-2">No conversations yet</p>
              )}
              {conversations.map((c) => (
                <div
                  key={c.id}
                  className={
                    "group flex items-center gap-1 rounded-lg px-2 py-1.5 text-sm cursor-pointer " +
                    (c.id === conversationId ? "bg-white/10" : "hover:bg-white/5")
                  }
                >
                  {editingId === c.id ? (
                    <input
                      autoFocus
                      value={editingTitle}
                      onChange={(e) => setEditingTitle(e.target.value)}
                      onBlur={() => saveRename(c.id)}
                      onKeyDown={(e) => e.key === "Enter" && saveRename(c.id)}
                      className="flex-1 bg-slate-800 rounded px-1 py-0.5 text-sm outline-none"
                    />
                  ) : (
                    <span onClick={() => selectConversation(c.id)} className="flex-1 truncate">
                      {c.title}
                    </span>
                  )}

                  <button
                    onClick={() => { setEditingId(c.id); setEditingTitle(c.title); }}
                    className="opacity-0 group-hover:opacity-100 text-xs text-slate-400 hover:text-slate-100 px-1"
                    aria-label="Rename"
                  >
                    ✎
                  </button>
                  <button
                    onClick={() => handleDeleteConversation(c.id)}
                    className="opacity-0 group-hover:opacity-100 text-xs text-slate-400 hover:text-red-400 px-1"
                    aria-label="Delete"
                  >
                    🗑
                  </button>
                </div>
              ))}
            </>
          )}
        </div>

        <div className="border-t border-white/10 p-2 relative">
          <button
            onClick={() => setSettingsOpen((prev) => !prev)}
            className={
              "w-full flex items-center gap-2 rounded-lg px-2 py-2 hover:bg-white/10 " +
              (sidebarCollapsed ? "justify-center" : "")
            }
          >
            <div className="w-6 h-6 rounded-full bg-teal-600 flex items-center justify-center text-xs font-semibold shrink-0">
              {username ? username[0].toUpperCase() : "?"}
            </div>
            {!sidebarCollapsed && (
              <span className="text-sm truncate flex-1 text-left">{username || "Account"}</span>
            )}
          </button>

          {settingsOpen && (
            <div className="absolute bottom-full left-2 mb-2 w-44 bg-white dark:bg-slate-800
                            text-slate-800 dark:text-slate-100 rounded-lg shadow-lg border
                            border-slate-200 dark:border-slate-700 p-2 z-10">
              <p className="text-xs text-slate-400 px-2 pb-1">Appearance</p>
              <button
                onClick={() => { setTheme("light"); setSettingsOpen(false); }}
                className={"w-full text-left px-2 py-1.5 rounded text-sm " +
                  (theme === "light" ? "bg-teal-600 text-white" : "hover:bg-slate-100 dark:hover:bg-slate-700")}
              >
                ☀️ Light
              </button>
              <button
                onClick={() => { setTheme("dark"); setSettingsOpen(false); }}
                className={"w-full text-left px-2 py-1.5 rounded text-sm " +
                  (theme === "dark" ? "bg-teal-600 text-white" : "hover:bg-slate-100 dark:hover:bg-slate-700")}
              >
                🌙 Dark
              </button>
              <div className="border-t border-slate-200 dark:border-slate-700 my-1.5" />
              <button
                onClick={handleLogout}
                className="w-full text-left px-2 py-1.5 rounded text-sm text-red-600 dark:text-red-400
                          hover:bg-red-50 dark:hover:bg-red-950/40"
              >
                Log out
              </button>
            </div>
          )}
        </div>
      </aside>

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0">
        <main className="flex-1 w-full max-w-3xl lg:max-w-4xl xl:max-w-4xl mx-auto flex flex-col p-4 min-h-0">
          <div className="flex-1 min-h-0 bg-white dark:bg-slate-900 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 p-4 space-y-3 overflow-y-auto">
            {messages.length === 0 && !loading && (
              <p className="text-slate-400 text-sm">
                Ask something, or say "save a note: ..."
              </p>
            )}

            {messages.map((m, i) => (
              <div key={i} className={m.role === "user" ? "text-right" : "text-left"}>
                <span
                  className={
                    "inline-block px-3 py-2 rounded-lg max-w-[95%] md:max-w-[95%] text-left " +
                    (m.role === "user"
                      ? "bg-teal-700 text-white"
                      : "bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-100")
                  }
                >
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    rehypePlugins={[rehypeRaw]}
                    components={markdownComponents}
                  >
                    {m.content}
                  </ReactMarkdown>
                </span>
              </div>
            ))}

            {loading && <div className="text-slate-400 text-sm">AskFlow is thinking...</div>}
          </div>

          <div className="w-full flex gap-2 mt-4 shrink-0">
            <input
              className="flex-1 border border-slate-300 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-teal-600"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSend()}
              placeholder="Ask something, or say 'save a note: ...'"
            />
            <button
              onClick={handleSend}
              className="bg-teal-700 text-white px-4 py-2 rounded-lg hover:bg-teal-800 disabled:opacity-50"
              disabled={loading}
            >
              Send
            </button>
            <label className="cursor-pointer px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-600
                    text-sm hover:bg-slate-100 dark:hover:bg-slate-700 flex items-center">
              {uploading ? "Uploading..." : "📎"}
              <input
                type="file"
                accept=".pdf,.txt"
                className="hidden"
                onChange={handleFileChange}
                disabled={uploading}
              />
            </label>
          </div>
        </main>
      </div>
    </div>
  );
}