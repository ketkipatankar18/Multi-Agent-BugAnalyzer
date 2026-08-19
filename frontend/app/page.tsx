"use client"
import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"

const EXAMPLES = [
  {
    title      : "NullPointerException in HTTP handler",
    description: "Servlet crashes when POST request body is empty on Linux JDK 1.8. Works fine on Windows. Crashes at line 243 when request.getInputStream() returns null.",
    stack      : "java.lang.NullPointerException\n  at org.apache.HttpServlet.doPost(HttpServlet.java:243)",
    priority   : "Major",
  },
  {
    title      : "Memory leak in database connection pool",
    description: "Memory usage grows continuously over 24 hours until OutOfMemoryError. Heap dump shows large number of unclosed database connections accumulating.",
    stack      : "java.lang.OutOfMemoryError: Java heap space\n  at java.util.Arrays.copyOf(Arrays.java:3210)",
    priority   : "Critical",
  },
  {
    title      : "ClassNotFoundException after log4j upgrade",
    description: "Application fails to start after upgrading from log4j 1.x to 2.x. ClassNotFoundException on startup. Worked fine before upgrade.",
    stack      : "java.lang.ClassNotFoundException: org.apache.log4j.Logger\n  at java.net.URLClassLoader.findClass(URLClassLoader.java:382)",
    priority   : "Blocker",
  },
]

interface RecentSearch {
  title    : string
  priority : string
  timestamp: number
}

export default function Home() {
  const [title, setTitle]               = useState("")
  const [issue, setIssue]               = useState("")
  const [stackTrace, setStackTrace]     = useState("")
  const [priority, setPriority]         = useState("Major")
  const [error, setError]               = useState("")
  const [showRecent, setShowRecent]     = useState(false)
  const [recentSearches, setRecent]     = useState<RecentSearch[]>([])
  const router = useRouter()

  // Load recent searches from localStorage on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem("buganalyzer_recent")
      if (stored) setRecent(JSON.parse(stored))
    } catch {}
  }, [])

  const fillExample = (ex: typeof EXAMPLES[0]) => {
    setTitle(ex.title)
    setIssue(ex.description)
    setStackTrace(ex.stack)
    setPriority(ex.priority)
    setError("")
  }

  const handleSubmit = () => {
    if (!title.trim() && !issue.trim()) {
      setError("Please add a bug title or description before searching.")
      return
    }
    setError("")

    // Save to recent searches
    const newSearch: RecentSearch = {
      title   : title.trim() || issue.trim().slice(0, 50),
      priority,
      timestamp: Date.now(),
    }
    try {
      const updated = [newSearch, ...recentSearches.filter(r => r.title !== newSearch.title)].slice(0, 5)
      localStorage.setItem("buganalyzer_recent", JSON.stringify(updated))
    } catch {}

    const combined = [
      title.trim(),
      issue.trim(),
      stackTrace.trim() ? `Stack trace: ${stackTrace.trim()}` : ""
    ].filter(Boolean).join("\n\n")

    sessionStorage.setItem("issue_description", combined)
    sessionStorage.setItem("bug_title", title)
    sessionStorage.setItem("priority", priority)
    sessionStorage.setItem("stack_trace", stackTrace)
    router.push("/results")
  }

  const PRIORITY_COLORS: Record<string, string> = {
    Blocker : "text-red-400",
    Critical: "text-orange-400",
    Major   : "text-yellow-400",
    Minor   : "text-blue-400",
    Trivial : "text-gray-400",
  }

  return (
    <main className="min-h-screen bg-gray-950 text-white flex flex-col">

      {/* Top nav */}
      <nav className="border-b border-gray-800 px-8 py-4 flex items-center gap-3">
        <span className="text-lg">🐛</span>
        <span className="font-semibold tracking-tight">BugAnalyzer</span>
        <div className="ml-auto flex items-center gap-4">
          <a href="/review" className="text-xs text-gray-500 hover:text-gray-300 transition-colors">
            Review Queue
          </a>
          <span className="text-xs text-gray-600 font-mono">100k+ tickets indexed</span>
        </div>
      </nav>

      <div className="flex-1 flex items-start justify-center pt-12 px-6 pb-16">
        <div className="w-full max-w-2xl">

          {/* Hero + description */}
          <div className="mb-8">
            <h1 className="text-4xl font-bold tracking-tight mb-3">
              Find fixes for your bug
            </h1>
            <p className="text-gray-400 text-base leading-relaxed mb-4">
              Describe a software bug and BugAnalyzer searches 100k+ resolved Apache JIRA
              tickets using semantic AI search — then generates a structured root cause
              analysis, fix recommendation, and priority assessment using a 5-agent pipeline.
            </p>
            <div className="flex flex-wrap gap-4 text-xs text-gray-500">
              <span>✦ Works best for Java, C++, Python, and web framework bugs</span>
              <span>✦ Include a stack trace for more precise results</span>
              <span>✦ Security bugs are automatically escalated for human review</span>
            </div>
          </div>

          {/* Example queries */}
          <div className="mb-6">
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-3">
              Try an example
            </p>
            <div className="flex flex-col gap-2">
              {EXAMPLES.map((ex, i) => (
                <button
                  key={i}
                  onClick={() => fillExample(ex)}
                  className="flex items-center justify-between text-left px-4 py-3 bg-gray-900 border border-gray-800 rounded-lg hover:border-gray-600 hover:bg-gray-800/50 transition-all group"
                >
                  <span className="text-sm text-gray-300 group-hover:text-white transition-colors">
                    {ex.title}
                  </span>
                  <span className={`text-xs font-medium ml-3 shrink-0 ${PRIORITY_COLORS[ex.priority]}`}>
                    {ex.priority}
                  </span>
                </button>
              ))}
            </div>
          </div>

          {/* Recent searches */}
          {recentSearches.length > 0 && (
            <div className="mb-6">
              <button
                onClick={() => setShowRecent(!showRecent)}
                className="text-xs text-gray-500 hover:text-gray-400 transition-colors flex items-center gap-1"
              >
                <span>{showRecent ? "▲" : "▼"}</span>
                <span>Recent searches ({recentSearches.length})</span>
              </button>

              {showRecent && (
                <div className="mt-3 flex flex-col gap-2">
                  {recentSearches.map((r, i) => (
                    <button
                      key={i}
                      onClick={() => {
                        setTitle(r.title)
                        setPriority(r.priority)
                      }}
                      className="flex items-center justify-between text-left px-4 py-2.5 bg-gray-900/50 border border-gray-800 rounded-lg hover:border-gray-700 transition-all"
                    >
                      <span className="text-sm text-gray-400">{r.title}</span>
                      <div className="flex items-center gap-3 shrink-0 ml-3">
                        <span className={`text-xs ${PRIORITY_COLORS[r.priority] ?? "text-gray-500"}`}>
                          {r.priority}
                        </span>
                        <span className="text-xs text-gray-600">
                          {new Date(r.timestamp).toLocaleDateString()}
                        </span>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Form card */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 space-y-5">

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1.5">
                Bug title
                <span className="text-gray-500 font-normal ml-1">— short summary</span>
              </label>
              <input
                type="text"
                className="w-full bg-gray-950 border border-gray-700 rounded-lg px-3 py-2.5 text-white placeholder-gray-600 focus:outline-none focus:border-blue-500 text-sm transition-colors"
                placeholder="e.g. NullPointerException in HTTP handler"
                value={title}
                onChange={e => setTitle(e.target.value)}
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1.5">
                Description
                <span className="text-gray-500 font-normal ml-1">— steps to reproduce, environment, context</span>
              </label>
              <textarea
                className="w-full bg-gray-950 border border-gray-700 rounded-lg px-3 py-2.5 text-white placeholder-gray-600 focus:outline-none focus:border-blue-500 text-sm resize-none transition-colors"
                rows={4}
                placeholder="e.g. Occurs when POST request body is empty on Linux with JDK 1.8. Works fine on Windows."
                value={issue}
                onChange={e => setIssue(e.target.value)}
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1.5">
                Error message / stack trace
                <span className="text-gray-500 font-normal ml-1">— optional but improves results significantly</span>
              </label>
              <textarea
                className="w-full bg-gray-950 border border-gray-700 rounded-lg px-3 py-2.5 text-white placeholder-gray-600 focus:outline-none focus:border-blue-500 text-sm resize-none font-mono transition-colors"
                rows={3}
                placeholder={"java.lang.NullPointerException\n  at org.apache.HttpServlet.doPost(HttpServlet.java:243)"}
                value={stackTrace}
                onChange={e => setStackTrace(e.target.value)}
              />
            </div>

            <div className="flex gap-3 pt-1">
              <div className="w-44">
                <label className="block text-xs font-medium text-gray-400 mb-1.5">Priority</label>
                <select
                  className="w-full bg-gray-950 border border-gray-700 rounded-lg px-3 py-2.5 text-white focus:outline-none focus:border-blue-500 text-sm transition-colors"
                  value={priority}
                  onChange={e => setPriority(e.target.value)}
                >
                  {["Blocker", "Critical", "Major", "Minor", "Trivial"].map(p => (
                    <option key={p} value={p}>{p}</option>
                  ))}
                </select>
              </div>

              <div className="flex-1 flex flex-col justify-end">
                {error && <p className="text-red-400 text-xs mb-1.5">{error}</p>}
                <button
                  onClick={handleSubmit}
                  className="w-full bg-blue-600 hover:bg-blue-500 text-white font-medium py-2.5 rounded-lg text-sm transition-colors"
                >
                  Analyse bug with 5 agents →
                </button>
              </div>
            </div>

          </div>

          {/* Trust signals */}
          <div className="mt-5 flex flex-wrap gap-5 text-xs text-gray-600">
            <span>📦 Apache JIRA — 100k resolved tickets</span>
            <span>🔍 Weaviate semantic search + Cohere reranking</span>
            <span>🤖 Gemini Flash · Claude Sonnet · Groq Llama</span>
          </div>

        </div>
      </div>
    </main>
  )
}
