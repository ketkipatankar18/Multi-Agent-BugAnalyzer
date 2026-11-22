// "use client"
// import { API_URL } from "@/lib/api"
// import { useEffect, useState } from "react"
// import { useRouter } from "next/navigation"
// import ReactMarkdown from "react-markdown"
// import remarkGfm from "remark-gfm"

// interface ReviewItem {
//   id             : string
//   bug_title      : string
//   issue_description: string
//   user_priority  : string
//   draft_response : string
//   escalation_reasons: string[]
//   severity       : string
//   confidence     : number
//   timestamp      : string
//   status         : "pending" | "approved" | "rejected" | "modified"
//   reviewer_note  ?: string
// }

// function MD({ children }: { children: string }) {
//   return (
//     <ReactMarkdown remarkPlugins={[remarkGfm]}
//       components={{
//         p: ({ children }) => <p className="text-sm text-gray-300 leading-relaxed mb-2">{children}</p>,
//         strong: ({ children }) => <strong className="text-white font-semibold">{children}</strong>,
//         // code: ({ children }) => <code className="bg-gray-800 text-green-400 font-mono text-xs px-1.5 py-0.5 rounded">{children}</code>,
//         code: ({ children, className }) => {
//           const isBlock = className?.includes("language-")
//           return isBlock
//             ? <code className="block bg-gray-950 border border-gray-700 rounded p-3 text-xs text-green-400 font-mono overflow-x-auto my-2 whitespace-pre">{children}</code>
//             : <code className="bg-gray-800 text-green-400 font-mono text-xs px-1.5 py-0.5 rounded">{children}</code>
//         },
//         pre: ({ children }) => <pre className="my-2">{children}</pre>,
//         ul: ({ children }) => <ul className="list-disc list-inside space-y-1 mb-2 text-sm text-gray-300">{children}</ul>,
//         li: ({ children }) => <li className="text-gray-300">{children}</li>,
//       }}
//     >
//       {children}
//     </ReactMarkdown>
//   )
// }

// export default function ReviewQueue() {
//   const [items, setItems]           = useState<ReviewItem[]>([])
//   const [selected, setSelected]     = useState<ReviewItem | null>(null)
//   const [reviewNote, setReviewNote] = useState("")
//   const [loading, setLoading]       = useState(true)
//   const router = useRouter()

//   // useEffect(() => {
//   //   fetch("http://127.0.0.1:8000/review/queue")
//   //     .then(r => r.json())
//   //     .then(data => { setItems(data); setLoading(false) })
//   //     .catch(() => setLoading(false))
//   // }, [])
//   useEffect(() => {
//     fetch(`${API_URL}/review/queue`)
//       .then(r => r.json())
//       .then((data: ReviewItem[]) => {
//         setItems(data)

//         // Deep link from Slack: /review?id=<request_id> → open that item
//         const id = new URLSearchParams(window.location.search).get("id")
//         if (id) {
//           const match = data.find(i => i.id === id)
//           if (match) {
//             setSelected(match)
//             setTimeout(() => {
//               document.getElementById(`item-${id}`)
//                 ?.scrollIntoView({ behavior: "smooth", block: "center" })
//             }, 100)
//           }
//         }
//         setLoading(false)
//       })
//       .catch(() => setLoading(false))
//   }, [])

//   // const handleDecision = async (id: string, status: "approved" | "rejected") => {
//   //   await fetch(`http://127.0.0.1:8000/review/${id}`, {
//   //     method : "POST",
//   //     headers: { "Content-Type": "application/json" },
//   //     body   : JSON.stringify({ status, reviewer_note: reviewNote })
//   //   })
//   const handleDecision = async (id: string, status: "approved" | "rejected") => {
//     await fetch(`${API_URL}/review/${id}`,  {
//       method : "POST",
//       headers: { "Content-Type": "application/json" },
//       body   : JSON.stringify({ status, reviewer_note: reviewNote })
//     })
//     setItems(prev => prev.map(i => i.id === id ? { ...i, status } : i))
//     setSelected(null)
//     setReviewNote("")
//   }

//   const pending  = items.filter(i => i.status === "pending")
//   const reviewed = items.filter(i => i.status !== "pending")

//   const REASON_LABELS: Record<string, string> = {
//     "high_severity_immediate"  : "High severity — immediate action required",
//     "security_issue"           : "Security vulnerability detected",
//     "security_keywords_detected": "Security keywords in description",
//     "low_confidence"           : "Low model confidence",
//     "no_similar_issues_found"  : "No similar past issues found",
//     "urgent_sentiment_detected": "Urgent sentiment detected",
//   }

//   return (
//     <main className="min-h-screen bg-gray-950 text-white">

//       {/* Nav */}
//       <nav className="border-b border-gray-800 px-8 py-4 flex items-center gap-3 sticky top-0 bg-gray-950/95 backdrop-blur z-10">
//         <span className="text-lg">🐛</span>
//         <span className="font-semibold tracking-tight">BugAnalyzer</span>
//         <span className="text-gray-600 text-xs mx-2">/</span>
//         <span className="text-sm text-gray-300">Review Queue</span>
//         <button onClick={() => router.push("/")} className="ml-auto text-xs text-gray-500 hover:text-gray-300 transition-colors">
//           ← Back to search
//         </button>
//       </nav>

//       <div className="max-w-4xl mx-auto px-6 py-10">

//         {/* Header */}
//         <div className="mb-8">
//           <h1 className="text-2xl font-bold mb-2">Human Review Queue</h1>
//           <p className="text-gray-400 text-sm">
//             Bugs flagged for human review by the Escalation Agent. Review, approve, or reject
//             the AI-generated analysis before it's sent to the reporter.
//           </p>
//         </div>

//         {loading ? (
//           <p className="text-gray-500 text-sm">Loading queue...</p>
//         ) : items.length === 0 ? (
//           <div className="bg-gray-900 border border-gray-800 rounded-xl p-10 text-center">
//             <p className="text-2xl mb-3">✅</p>
//             <p className="text-gray-300 font-medium mb-1">Queue is empty</p>
//             <p className="text-gray-500 text-sm">No bugs are currently flagged for human review.</p>
//           </div>
//         ) : (
//           <div className="space-y-8">

//             {/* Pending */}
//             {pending.length > 0 && (
//               <div>
//                 <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-4">
//                   Pending review ({pending.length})
//                 </h2>
//                 <div className="space-y-3">
//                   {pending.map(item => (
//                     <div key={item.id}
//                       id={`item-${item.id}`}
//                       onClick={() => { setSelected(item); setReviewNote("") }}
//                       // onClick={() => { setSelected(item); setReviewNote("") }}
//                       className={`bg-gray-900 border rounded-xl p-5 cursor-pointer transition-all hover:border-orange-700 ${
//                         selected?.id === item.id ? "border-orange-700 bg-orange-900/10" : "border-orange-800/50"
//                       }`}>
//                       <div className="flex items-start justify-between gap-4">
//                         <div className="flex-1">
//                           <div className="flex items-center gap-2 mb-2">
//                             <span className="text-xs font-medium px-2 py-0.5 rounded border bg-orange-900/40 text-orange-400 border-orange-800">
//                               ⚠ Escalated
//                             </span>
//                             <span className="text-xs font-medium px-2 py-0.5 rounded border bg-gray-800 text-gray-400 border-gray-700">
//                               {item.user_priority}
//                             </span>
//                             <span className={`text-xs font-medium px-2 py-0.5 rounded border ${
//                               item.severity === "Critical" ? "bg-red-900/40 text-red-400 border-red-800" :
//                               item.severity === "High"     ? "bg-orange-900/40 text-orange-400 border-orange-800" :
//                               "bg-yellow-900/40 text-yellow-400 border-yellow-800"
//                             }`}>{item.severity} severity</span>
//                           </div>
//                           <p className="text-sm font-medium text-white mb-1">{item.bug_title || "Untitled bug"}</p>
//                           <p className="text-xs text-gray-500 line-clamp-2">{item.issue_description}</p>
//                           <div className="mt-2 flex flex-wrap gap-1">
//                             {item.escalation_reasons.map(r => (
//                               <span key={r} className="text-xs text-orange-400/80 bg-orange-900/20 px-2 py-0.5 rounded">
//                                 {REASON_LABELS[r] ?? r.replace(/_/g, " ")}
//                               </span>
//                             ))}
//                           </div>
//                         </div>
//                         <div className="text-right shrink-0">
//                           <p className="text-xs text-gray-600">{new Date(item.timestamp).toLocaleString()}</p>
//                           <p className="text-xs text-gray-600 mt-1">confidence {(item.confidence * 100).toFixed(0)}%</p>
//                         </div>
//                       </div>

//                       {/* Expanded review panel */}
//                       {selected?.id === item.id && (
//                         <div className="mt-5 pt-5 border-t border-gray-800">
//                           <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-3">AI Draft Response</p>
//                           {/* <div className="bg-gray-800/50 rounded-lg p-4 mb-5 max-h-64 overflow-y-auto">
//                             <MD>{item.draft_response.slice(0, 2000)}</MD>
//                             {item.draft_response.length > 2000 && (
//                               <p className="text-xs text-gray-500 mt-2">... (truncated for review)</p>
//                             )}
//                           </div> */}
//                           <div className="bg-gray-800/50 rounded-lg p-4 mb-5 max-h-[32rem] overflow-y-auto">
//                             <MD>{item.draft_response}</MD>
//                           </div>

//                           <div className="mb-4">
//                             <label className="block text-xs font-medium text-gray-400 mb-2">
//                               Reviewer note (optional)
//                             </label>
//                             <textarea
//                               className="w-full bg-gray-950 border border-gray-700 rounded-lg px-3 py-2.5 text-white placeholder-gray-600 focus:outline-none focus:border-blue-500 text-sm resize-none"
//                               rows={2}
//                               placeholder="Add any notes about this review decision..."
//                               value={reviewNote}
//                               onChange={e => setReviewNote(e.target.value)}
//                               onClick={e => e.stopPropagation()}
//                             />
//                           </div>

//                           <div className="flex gap-3" onClick={e => e.stopPropagation()}>
//                             <button
//                               onClick={() => handleDecision(item.id, "approved")}
//                               className="flex-1 bg-green-700 hover:bg-green-600 text-white font-medium py-2.5 rounded-lg text-sm transition-colors"
//                             >
//                               ✓ Approve — send to reporter
//                             </button>
//                             <button
//                               onClick={() => handleDecision(item.id, "rejected")}
//                               className="flex-1 bg-gray-800 hover:bg-red-900/40 border border-gray-700 hover:border-red-700 text-gray-300 hover:text-red-400 font-medium py-2.5 rounded-lg text-sm transition-colors"
//                             >
//                               ✗ Reject — needs rework
//                             </button>
//                           </div>
//                         </div>
//                       )}
//                     </div>
//                   ))}
//                 </div>
//               </div>
//             )}

//             {/* Reviewed */}
//             {reviewed.length > 0 && (
//               <div>
//                 <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-4">
//                   Previously reviewed ({reviewed.length})
//                 </h2>
//                 <div className="space-y-2">
//                   {reviewed.map(item => (
//                     <div key={item.id} className="bg-gray-900 border border-gray-800 rounded-xl px-5 py-3 flex items-center justify-between gap-4">
//                       <p className="text-sm text-gray-300 truncate">{item.bug_title || "Untitled bug"}</p>
//                       <div className="flex items-center gap-2 shrink-0">
//                         <span className={`text-xs font-medium px-2 py-0.5 rounded border ${
//                           item.status === "approved"
//                             ? "bg-green-900/40 text-green-400 border-green-800"
//                             : "bg-red-900/40 text-red-400 border-red-800"
//                         }`}>
//                           {item.status === "approved" ? "✓ Approved" : "✗ Rejected"}
//                         </span>
//                         <span className="text-xs text-gray-600">{new Date(item.timestamp).toLocaleDateString()}</span>
//                       </div>
//                     </div>
//                   ))}
//                 </div>
//               </div>
//             )}

//           </div>
//         )}
//       </div>
//     </main>
//   )
// }

"use client"
import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { apiFetch } from "@/lib/api"

interface ReviewItem {
  id                : string
  bug_title         : string
  issue_description : string
  user_priority     : string
  draft_response    : string
  escalation_reasons: string[]
  severity          : string
  confidence        : number
  timestamp         : string
  status            : "pending" | "approved" | "rejected"
  reviewer_note    ?: string
  reviewed_by      ?: string | null
  reviewed_at      ?: string | null
}

// interface SessionUser {
//   username: string
//   role    : "admin" | "viewer"
// }

const REASON_LABELS: Record<string, string> = {
  high_severity_immediate   : "High severity — immediate action required",
  security_issue            : "Security vulnerability detected",
  security_keywords_detected: "Security keywords in description",
  low_confidence            : "Low model confidence",
  no_similar_issues_found   : "No similar past issues found",
  urgent_sentiment_detected : "Urgent sentiment detected",
}

function MD({ children }: { children: string }) {
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]}
      components={{
        p: ({ children }) => <p className="text-sm text-gray-300 leading-relaxed mb-2">{children}</p>,
        strong: ({ children }) => <strong className="text-white font-semibold">{children}</strong>,
        code: ({ children, className }) => {
          const isBlock = className?.includes("language-")
          return isBlock
            ? <code className="block bg-gray-950 border border-gray-700 rounded p-3 text-xs text-green-400 font-mono overflow-x-auto my-2 whitespace-pre">{children}</code>
            : <code className="bg-gray-800 text-green-400 font-mono text-xs px-1.5 py-0.5 rounded">{children}</code>
        },
        pre: ({ children }) => <pre className="my-2">{children}</pre>,
        ul: ({ children }) => <ul className="list-disc list-inside space-y-1 mb-2 text-sm text-gray-300">{children}</ul>,
        ol: ({ children }) => <ol className="list-decimal list-inside space-y-1 mb-2 text-sm text-gray-300">{children}</ol>,
        li: ({ children }) => <li className="text-gray-300">{children}</li>,
        table: ({ children }) => (
          <div className="overflow-x-auto my-3"><table className="text-xs w-full border-collapse">{children}</table></div>
        ),
        th: ({ children }) => <th className="border border-gray-700 px-3 py-1.5 text-left text-gray-300 bg-gray-800 font-medium">{children}</th>,
        td: ({ children }) => <td className="border border-gray-700 px-3 py-1.5 text-gray-400">{children}</td>,
      }}
    >
      {children}
    </ReactMarkdown>
  )
}

export default function ReviewQueue() {
  const [items, setItems]           = useState<ReviewItem[]>([])
  const [mode, setMode]             = useState<"full" | "demo">("full")
  // const [user, setUser]             = useState<SessionUser | null>(null)
  const [selected, setSelected]     = useState<ReviewItem | null>(null)
  const [reviewNote, setReviewNote] = useState("")
  const [loading, setLoading]       = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError]           = useState("")
  const [highlightId, setHighlightId] = useState<string | null>(null)
  const [notice, setNotice]           = useState("")
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const router = useRouter()

  // const canAct = mode === "full" && user?.role === "admin"
  const canAct = true

  // Send to login, then come back to this exact page (including ?id= from Slack)
  const goToLogin = () => {
    const here = window.location.pathname + window.location.search
    router.replace(`/login?next=${encodeURIComponent(here)}`)
  }

  // ── Load the queue ──────────────────────────────────────────────────────────
  useEffect(() => {
    const load = async () => {
      try {
        // const res = await apiFetch("/review/queue")
        const res = await apiFetch("/review-queue")
        if (res.status === 401) { goToLogin(); return }
        if (res.status === 403) { router.replace("/"); return } 
        if (!res.ok) {
          setError("Could not load the review queue.")
          setLoading(false)
          return
        }

        const data = await res.json()
        const list: ReviewItem[] = data.items ?? []
        setItems(list)
        setMode(data.mode ?? "full")
        // setUser(data.user ?? null)

        // Deep link from Slack: /review?id=<request_id>
        const id = new URLSearchParams(window.location.search).get("id")
        if (id) {
          const match = list.find(i => i.id === id)
          if (!match) {
            setNotice("That bug is no longer in the review queue.")
          } else {
            setHighlightId(id)
            if (match.status === "pending") {
              setSelected(match)                       // open it for review
            } else {
              const by = match.reviewed_by ? ` by ${match.reviewed_by}` : ""
              const at = match.reviewed_at ? ` on ${new Date(match.reviewed_at).toLocaleString()}` : ""
              setNotice(`This bug was already ${match.status}${by}${at}.`)
              setExpandedId(id)                        // show its details
            }
            setTimeout(() => {
              document.getElementById(`item-${id}`)
                ?.scrollIntoView({ behavior: "smooth", block: "center" })
            }, 100)
          }
        }
      } catch {
        setError("Could not reach the server.")
      }
      setLoading(false)
    }
    load()
  }, [])

  // ── Approve / reject ────────────────────────────────────────────────────────
  const handleDecision = async (id: string, status: "approved" | "rejected") => {
    setSubmitting(true)
    setError("")
    try {
      const res = await apiFetch(`/review-queue/${id}`, {
        method : "PATCH",
        headers: { "Content-Type": "application/json" },
        body   : JSON.stringify({ status, reviewer_note: reviewNote }),
      })
      if (res.status === 401) { goToLogin(); return }
      if (res.status === 403) { setError("Only admins can approve or reject."); return }
      if (!res.ok)            { setError("Could not save the decision. Please try again."); return }

      // Update the screen only after the server confirmed the save
      setItems(prev => prev.map(i =>
        i.id === id
          // ? { ...i, status, reviewer_note: reviewNote, reviewed_by: user?.username ?? null }
          ? { ...i, status, reviewer_note: reviewNote, reviewed_by: null }
          : i
      ))
      setSelected(null)
      setReviewNote("")
    } catch {
      setError("Could not reach the server.")
    } finally {
      setSubmitting(false)
    }
  }

  // const handleLogout = async () => {
  //   try { await apiFetch("/auth/logout", { method: "POST" }) } catch {}
  //   router.replace("/")
  // }

  const pending  = items.filter(i => i.status === "pending")
  const reviewed = items.filter(i => i.status !== "pending")

  return (
    <main className="min-h-screen bg-gray-950 text-white">
      <div className="max-w-4xl mx-auto px-6 py-10">

        {/* Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold mb-2">Human Review Queue</h1>
          <p className="text-gray-400 text-sm">
            Bugs flagged for human review by the Escalation Agent. Review, approve, or reject
            the AI-generated analysis before it&apos;s sent to the reporter.
          </p>
        </div>

        {mode === "demo" && (
          <div className="mb-6 bg-blue-900/20 border border-blue-800/50 rounded-xl px-5 py-3 text-xs text-blue-300">
            Read-only demo view — security reports are hidden and AI drafts are not shown.
          </div>
        )}

        {notice && (
          <div className="mb-6 bg-gray-800/60 border border-gray-700 rounded-xl px-5 py-3 text-sm text-gray-300">
            ℹ️ {notice}
          </div>
        )}

        {error && (
          <div className="mb-6 bg-red-900/20 border border-red-800/50 rounded-xl px-5 py-3 text-sm text-red-300">
            {error}
          </div>
        )}

        {loading ? (
          <p className="text-gray-500 text-sm">Loading queue...</p>
        ) : items.length === 0 ? (
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-10 text-center">
            <p className="text-2xl mb-3">✅</p>
            <p className="text-gray-300 font-medium mb-1">Queue is empty</p>
            <p className="text-gray-500 text-sm">No bugs are currently flagged for human review.</p>
          </div>
        ) : (
          <div className="space-y-8">

            {/* Pending */}
            {pending.length > 0 && (
              <div>
                <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-4">
                  Pending review ({pending.length})
                </h2>
                <div className="space-y-3">
                  {pending.map(item => (
                    <div key={item.id}
                      id={`item-${item.id}`}
                      onClick={() => { setSelected(item); setReviewNote("") }}
                      className={`bg-gray-900 border rounded-xl p-5 cursor-pointer transition-all hover:border-orange-700 ${
                        selected?.id === item.id ? "border-orange-700 bg-orange-900/10" : "border-orange-800/50"
                      }`}>
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-2">
                            <span className="text-xs font-medium px-2 py-0.5 rounded border bg-orange-900/40 text-orange-400 border-orange-800">
                              ⚠ Escalated
                            </span>
                            <span className="text-xs font-medium px-2 py-0.5 rounded border bg-gray-800 text-gray-400 border-gray-700">
                              {item.user_priority}
                            </span>
                            <span className={`text-xs font-medium px-2 py-0.5 rounded border ${
                              item.severity === "Critical" ? "bg-red-900/40 text-red-400 border-red-800" :
                              item.severity === "High"     ? "bg-orange-900/40 text-orange-400 border-orange-800" :
                              "bg-yellow-900/40 text-yellow-400 border-yellow-800"
                            }`}>{item.severity} severity</span>
                          </div>
                          <p className="text-sm font-medium text-white mb-1">{item.bug_title || "Untitled bug"}</p>
                          <p className="text-xs text-gray-500 line-clamp-2">{item.issue_description}</p>
                          <div className="mt-2 flex flex-wrap gap-1">
                            {item.escalation_reasons.map(r => (
                              <span key={r} className="text-xs text-orange-400/80 bg-orange-900/20 px-2 py-0.5 rounded">
                                {REASON_LABELS[r] ?? r.replace(/_/g, " ")}
                              </span>
                            ))}
                          </div>
                        </div>
                        <div className="text-right shrink-0">
                          <p className="text-xs text-gray-600">{new Date(item.timestamp).toLocaleString()}</p>
                          <p className="text-xs text-gray-600 mt-1">confidence {(item.confidence * 100).toFixed(0)}%</p>
                        </div>
                      </div>

                      {/* Expanded review panel */}
                      {selected?.id === item.id && (
                        <div className="mt-5 pt-5 border-t border-gray-800" onClick={e => e.stopPropagation()}>
                          {item.draft_response ? (
                            <>
                              <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-3">AI Draft Response</p>
                              <div className="bg-gray-800/50 rounded-lg p-4 mb-5 max-h-[32rem] overflow-y-auto">
                                <MD>{item.draft_response}</MD>
                              </div>
                            </>
                          ) : (
                            <p className="text-xs text-gray-500 mb-2">Details are hidden in the demo view.</p>
                          )}

                          {canAct ? (
                            <>
                              <div className="mb-4">
                                <label className="block text-xs font-medium text-gray-400 mb-2">
                                  Reviewer note (optional)
                                </label>
                                <textarea
                                  className="w-full bg-gray-950 border border-gray-700 rounded-lg px-3 py-2.5 text-white placeholder-gray-600 focus:outline-none focus:border-blue-500 text-sm resize-none"
                                  rows={2}
                                  placeholder="Add any notes about this review decision..."
                                  value={reviewNote}
                                  onChange={e => setReviewNote(e.target.value)}
                                />
                              </div>
                              <div className="flex gap-3">
                                <button
                                  disabled={submitting}
                                  onClick={() => handleDecision(item.id, "approved")}
                                  className="flex-1 bg-green-700 hover:bg-green-600 disabled:opacity-40 text-white font-medium py-2.5 rounded-lg text-sm transition-colors"
                                >
                                  ✓ Approve — send to reporter
                                </button>
                                <button
                                  disabled={submitting}
                                  onClick={() => handleDecision(item.id, "rejected")}
                                  className="flex-1 bg-gray-800 hover:bg-red-900/40 disabled:opacity-40 border border-gray-700 hover:border-red-700 text-gray-300 hover:text-red-400 font-medium py-2.5 rounded-lg text-sm transition-colors"
                                >
                                  ✗ Reject — needs rework
                                </button>
                              </div>
                            </>
                          ) : null}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Reviewed */}
            {reviewed.length > 0 && (
              <div>
                <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-4">
                  Previously reviewed ({reviewed.length})
                </h2>
                <div className="space-y-2">
                  {/* {reviewed.map(item => (
                    <div key={item.id} id={`item-${item.id}`}
                      // className="bg-gray-900 border border-gray-800 rounded-xl px-5 py-3 flex items-center justify-between gap-4">
                      className={`bg-gray-900 border rounded-xl px-5 py-3 flex items-center justify-between gap-4 transition-colors ${
                        highlightId === item.id ? "border-blue-600 ring-1 ring-blue-600/50" : "border-gray-800"
                      }`}>
                      <p className="text-sm text-gray-300 truncate">{item.bug_title || "Untitled bug"}</p>
                      <div className="flex items-center gap-2 shrink-0">
                        <span className={`text-xs font-medium px-2 py-0.5 rounded border ${
                          item.status === "approved"
                            ? "bg-green-900/40 text-green-400 border-green-800"
                            : "bg-red-900/40 text-red-400 border-red-800"
                        }`}>
                          {item.status === "approved" ? "✓ Approved" : "✗ Rejected"}
                        </span>
                        {item.reviewed_by && (
                          <span className="text-xs text-gray-600">by {item.reviewed_by}</span>
                        )}
                        <span className="text-xs text-gray-600">{new Date(item.timestamp).toLocaleDateString()}</span>
                      </div>
                    </div>
                  ))} */}
                  {reviewed.map(item => {
                    const isOpen = expandedId === item.id
                    return (
                      <div key={item.id} id={`item-${item.id}`}
                        className={`bg-gray-900 border rounded-xl transition-colors ${
                          highlightId === item.id ? "border-blue-600 ring-1 ring-blue-600/50" : "border-gray-800"
                        }`}>

                        {/* Summary row — click to expand */}
                        <button
                          onClick={() => setExpandedId(isOpen ? null : item.id)}
                          className="w-full px-5 py-3 flex items-center justify-between gap-4 text-left hover:bg-gray-800/30 rounded-xl transition-colors"
                        >
                          <p className="text-sm text-gray-300 truncate">{item.bug_title || "Untitled bug"}</p>
                          <div className="flex items-center gap-2 shrink-0">
                            <span className={`text-xs font-medium px-2 py-0.5 rounded border ${
                              item.status === "approved"
                                ? "bg-green-900/40 text-green-400 border-green-800"
                                : "bg-red-900/40 text-red-400 border-red-800"
                            }`}>
                              {item.status === "approved" ? "✓ Approved" : "✗ Rejected"}
                            </span>
                            {item.reviewed_by && (
                              <span className="text-xs text-gray-600">by {item.reviewed_by}</span>
                            )}
                            <span className="text-xs text-gray-600">{new Date(item.timestamp).toLocaleDateString()}</span>
                            <span className="text-gray-600 text-xs ml-1">{isOpen ? "▲" : "▼"}</span>
                          </div>
                        </button>

                        {/* Read-only details */}
                        {isOpen && (
                          <div className="px-5 pb-5 pt-1 border-t border-gray-800 space-y-4">
                            <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-gray-500 pt-3">
                              <span>Priority: <span className="text-gray-300">{item.user_priority}</span></span>
                              <span>Severity: <span className="text-gray-300">{item.severity}</span></span>
                              <span>Confidence: <span className="text-gray-300">{(item.confidence * 100).toFixed(0)}%</span></span>
                              {item.reviewed_at && (
                                <span>Reviewed: <span className="text-gray-300">{new Date(item.reviewed_at).toLocaleString()}</span></span>
                              )}
                            </div>

                            <div className="flex flex-wrap gap-1">
                              {item.escalation_reasons.map(r => (
                                <span key={r} className="text-xs text-orange-400/80 bg-orange-900/20 px-2 py-0.5 rounded">
                                  {REASON_LABELS[r] ?? r.replace(/_/g, " ")}
                                </span>
                              ))}
                            </div>

                            <div>
                              <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-2">Bug description</p>
                              <p className="text-sm text-gray-400 whitespace-pre-wrap">{item.issue_description}</p>
                            </div>

                            {item.reviewer_note && (
                              <div>
                                <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-2">Reviewer note</p>
                                <p className="text-sm text-gray-300 bg-gray-800/50 rounded-lg px-4 py-3">{item.reviewer_note}</p>
                              </div>
                            )}

                            {item.draft_response ? (
                              <div>
                                <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-2">AI Draft Response</p>
                                <div className="bg-gray-800/50 rounded-lg p-4 max-h-[32rem] overflow-y-auto">
                                  <MD>{item.draft_response}</MD>
                                </div>
                              </div>
                            ) : (
                              <p className="text-xs text-gray-500">Details are hidden in the demo view.</p>
                            )}
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              </div>
            )}

          </div>
        )}
      </div>
    </main>
  )
}