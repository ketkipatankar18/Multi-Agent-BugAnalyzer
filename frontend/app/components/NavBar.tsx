"use client"
import { useEffect, useState } from "react"
import { useRouter, usePathname } from "next/navigation"
import Link from "next/link"
import { apiFetch } from "@/lib/api"

interface User { username: string; role: "admin" | "viewer" }

export default function NavBar() {
  const [user, setUser]   = useState<User | null>(null)
  const [ready, setReady] = useState(false)
  const router   = useRouter()
  const pathname = usePathname()

  useEffect(() => {
    apiFetch("/auth/me")
      .then(r => r.ok ? r.json() : null)
      .then(data => { setUser(data); setReady(true) })
      .catch(() => setReady(true))
  }, [pathname])

  const logout = async () => {
    await apiFetch("/auth/logout", { method: "POST" })
    setUser(null)
    router.replace("/")
  }

  // Don't render on login page or until we know auth state
  if (!ready || pathname === "/login") return null

  // Not logged in — show subtle admin login link
  // if (!user) return (
  //   <header className="sticky top-0 z-50 border-b border-gray-800 bg-gray-950/90 backdrop-blur">
  //     <div className="mx-auto flex h-12 max-w-5xl items-center px-4">
  //       <div className="flex-1" />
  //       <Link href="/login" className="text-xs text-gray-600 hover:text-gray-400 transition-colors">
  //         Admin Login
  //       </Link>
  //     </div>
  //   </header>
  // )
  if (!user) return (
    <header className="sticky top-0 z-50 border-b border-gray-800 bg-gray-900 backdrop-blur">
      <div className="mx-auto flex h-12 max-w-5xl items-center px-4">
        <span className="text-lg font-bold text-white tracking-tight">🐛 BugAnalyzer</span>
        <div className="flex-1" />
        <Link href="/login" className="text-sm font-medium text-gray-400 hover:text-white transition-colors">
          Admin Login
        </Link>
      </div>
    </header>
  )

  // Logged in
  return (
    <header className="sticky top-0 z-50 border-b border-gray-800 bg-gray-900 backdrop-blur">
      <div className="mx-auto flex h-12 max-w-5xl items-center gap-4 px-4">
        <Link href="/" className="text-lg font-bold text-white tracking-tight">🐛 BugAnalyzer</Link>
        <div className="flex-1" />
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-400">{user.username}</span>
          <span className={`rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${
            user.role === "admin" ? "bg-orange-500/20 text-orange-400" : "bg-gray-700 text-gray-400"
          }`}>{user.role}</span>
        </div>
        <button onClick={logout} className="text-sm text-gray-500 hover:text-red-400 transition-colors">
          Log out
        </button>
      </div>
    </header>
  )
}