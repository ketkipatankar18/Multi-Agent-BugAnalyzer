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
  const router = useRouter()
  const [aboutOpen, setAboutOpen] = useState(false)

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

    // sessionStorage.setItem("issue_description", combined)
    sessionStorage.setItem("issue_description", issue.trim() || title.trim())
    sessionStorage.setItem("bug_title", title)
    sessionStorage.setItem("priority", priority)
    sessionStorage.setItem("stack_trace", stackTrace)
    sessionStorage.removeItem("job_id")   // new search → new job (results page reuses job_id only on refresh)
    // router.push("/results")
    router.replace("/results")
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

      {/* Top nav
      <nav className="border-b border-gray-800 px-8 py-4 flex items-center gap-3">
        <span className="text-lg">🐛</span>
        <span className="font-semibold tracking-tight">BugAnalyzer</span>
        <div className="ml-auto flex items-center gap-4">
          <a href="/review" className="text-xs text-gray-500 hover:text-gray-300 transition-colors">
            Review Queue
          </a>
          <span className="text-xs text-gray-600 font-mono">100k+ tickets indexed</span>
        </div>
      </nav> */}

      <div className="flex-1 flex items-start justify-center pt-12 px-6 pb-16">
        <div className="w-full max-w-2xl">

          {/* Hero + description */}
          {/* <div className="mb-8">
            <p className="text-gray-400 leading-relaxed">
              Stuck on a bug? Describe it and BugAnalyzer finds how similar bugs were fixed in real open-source projects. Get a root cause, a fix recommendation, and a priority assessment in under 60 seconds.
            </p>
            <p className="text-gray-400 leading-relaxed mt-3">
              Built for teams too. Swap in your company&apos;s resolved bug history as the knowledge base and every engineer gets instant access to fixes your team has already figured out. No more rediscovering fixes your team already found.
            </p>
            <div className="grid grid-cols-2 gap-x-8 gap-y-2 text-xs text-gray-500 mt-6">
              <span>✦ Root cause analysis with code-level fix suggestions</span>
              <span>✦ Similar resolved tickets from real open-source projects</span>
              <span>✦ Priority assessment backed by historical data</span>
              <span>✦ Security bugs automatically flagged for human review</span>
              <span>✦ Follow-up Q&A on any part of the analysis</span>
            </div>
          </div> */}
          <div className="mb-6">
            <button
              onClick={() => setAboutOpen(!aboutOpen)}
              className="flex items-center gap-2 group mb-2"
            >
              <span className="text-xs font-medium text-gray-500 uppercase tracking-wider group-hover:text-gray-400 transition-colors">
                About BugAnalyzer
              </span>
              <span className="text-gray-600 text-xs group-hover:text-gray-400 transition-colors">
                {aboutOpen ? "▲" : "▼"}
              </span>
            </button>
            {aboutOpen && (
              <div className="bg-gray-900/60 border border-gray-800 rounded-xl p-5 space-y-3 mb-4">
                <p className="text-gray-400 text-sm leading-relaxed">
                  Stuck on a bug? Describe it and BugAnalyzer finds how similar bugs were fixed in real open-source projects. Get a root cause, a fix recommendation, and a priority assessment in under 60 seconds.
                </p>
                <p className="text-gray-400 text-sm leading-relaxed mt-3">
                  Built for teams too. Swap in your company&apos;s resolved bug history as the knowledge base and every engineer gets instant access to fixes your team has already figured out. No more rediscovering fixes your team already found.
                </p>
                <div className="grid grid-cols-2 gap-x-6 gap-y-1.5 text-xs text-gray-500 pt-1 border-t border-gray-800/60">
                  <span className="pt-2">✦ Root cause analysis with fix suggestions</span>
                  <span className="pt-2">✦ Similar resolved tickets from open-source</span>
                  <span>✦ Priority assessment backed by historical data</span>
                  <span>✦ Security bugs flagged for human review</span>
                </div>
              </div>
            )}
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

          {/* Form card */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 space-y-5">

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1.5">
                Bug Title
                <span className="text-gray-500 font-normal ml-1"></span>
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
                <span className="text-gray-500 font-normal ml-1"></span>
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
                Error message / Stack trace
                <span className="text-gray-500 font-normal ml-1"> (optional)</span>
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
                <label className="block text-sm font-medium text-gray-300 mb-1.5">Priority</label>
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
                  Run Analysis →
                </button>
              </div>
            </div>

          </div>

        </div>
      </div>
    </main>
  )
}
