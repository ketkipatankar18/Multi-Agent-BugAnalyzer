"use client"
import { useEffect, useState, type FormEvent } from "react"
import { useRouter } from "next/navigation"
import { apiFetch } from "@/lib/api"

// Only allow redirects to pages on this site — never to another domain
function safeNext(): string {
  const next = new URLSearchParams(window.location.search).get("next") ?? "/review"
  return next.startsWith("/") && !next.startsWith("//") ? next : "/review"
}

export default function Login() {
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError]       = useState("")
  const [loading, setLoading]   = useState(false)
  const router = useRouter()

  // Already logged in? Skip the form.
  useEffect(() => {
    apiFetch("/auth/me")
      .then(res => { if (res.ok) router.replace(safeNext()) })
      .catch(() => {})
  }, [router])

  const handleLogin = async (e: FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError("")
    try {
      const res = await apiFetch("/auth/login", {
        method : "POST",
        headers: { "Content-Type": "application/json" },
        body   : JSON.stringify({ username, password }),
      })
      if (res.ok) {
        router.replace(safeNext())
        return
      }
      // setError(res.status === 401 ? "Invalid username or password." : "Login failed. Please try again.")
      setError(
        res.status === 401 ? "Invalid username or password." :
        res.status === 429 ? "Too many attempts — please wait a minute and try again." :
        "Login failed. Please try again."
      )
    } catch {
      setError("Could not reach the server.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="min-h-screen bg-gray-950 text-white flex flex-col">
      {/* <nav className="border-b border-gray-800 px-8 py-4 flex items-center gap-3">
        <span className="text-lg">🐛</span>
        <span className="font-semibold tracking-tight">BugAnalyzer</span>
        <button onClick={() => router.push("/")}
          className="ml-auto text-xs text-gray-500 hover:text-gray-300 transition-colors">
          ← Back to search
        </button>
      </nav> */}
      <nav className="sticky top-0 z-50 border-b border-gray-800 bg-gray-900">
        <div className="mx-auto flex h-12 max-w-5xl items-center px-4">
          <span className="text-lg font-bold text-white tracking-tight">🐛 BugAnalyzer</span>
          <div className="flex-1" />
          <button onClick={() => router.push("/")}
            className="text-sm font-medium text-gray-400 hover:text-white transition-colors">
            ← Back to search
          </button>
        </div>
      </nav>

      <div className="flex-1 flex items-center justify-center px-6">
        <form onSubmit={handleLogin}
          className="w-full max-w-sm bg-gray-900 border border-gray-800 rounded-xl p-6 space-y-4">
          <div>
            <h1 className="text-xl font-semibold mb-1">Reviewer login</h1>
            <p className="text-sm text-gray-500">The review queue is restricted to authorised reviewers.</p>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-400 mb-1.5">Username</label>
            <input
              type="text"
              autoComplete="username"
              autoFocus
              className="w-full bg-gray-950 border border-gray-700 rounded-lg px-3 py-2.5 text-white text-sm focus:outline-none focus:border-blue-500"
              value={username}
              onChange={e => setUsername(e.target.value)}
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-400 mb-1.5">Password</label>
            <input
              type="password"
              autoComplete="current-password"
              className="w-full bg-gray-950 border border-gray-700 rounded-lg px-3 py-2.5 text-white text-sm focus:outline-none focus:border-blue-500"
              value={password}
              onChange={e => setPassword(e.target.value)}
            />
          </div>

          {error && <p className="text-red-400 text-xs">{error}</p>}

          <button
            type="submit"
            disabled={loading || !username || !password}
            className="w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-white font-medium py-2.5 rounded-lg text-sm transition-colors"
          >
            {loading ? "Signing in..." : "Sign in"}
          </button>
        </form>
      </div>
    </main>
  )
}