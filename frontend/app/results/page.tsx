// "use client"
// import { API_URL } from "@/lib/api"
// // import { useEffect, useState } from "react"
// import { useEffect, useRef, useState } from "react"
// import { useRouter } from "next/navigation"
// import ReactMarkdown from "react-markdown"
// import remarkGfm from "remark-gfm"
// import React from "react"

// interface Issue {
//   key: string
//   summary: string
//   "priority.name": string
//   "resolution.name": string
//   comments_text: string
//   similarity: number
// }

// interface Classification {
//   category: string
//   component: string
//   root_cause_family: string
//   enriched_query: string
// }

// interface SeverityAssessment {
//   severity: string
//   sla_risk: boolean
//   production_impact: boolean
//   escalate_immediately: boolean
//   reasoning: string
// }

// interface AgentStatus {
//   classifier?: string
//   severity?: string
//   retriever?: string
//   draft_response?: string
//   escalation?: string
// }

// interface Section {
//   key         : string
//   title       : string
//   icon        : string
//   color       : string
//   defaultOpen : boolean
//   content     : string
// }

// // ── Priority / Severity badges ────────────────────────────────────────────────
// const PRIORITY_COLORS: Record<string, string> = {
//   Blocker : "bg-red-900/40 text-red-400 border-red-800",
//   Critical: "bg-orange-900/40 text-orange-400 border-orange-800",
//   Major   : "bg-yellow-900/40 text-yellow-400 border-yellow-800",
//   Minor   : "bg-blue-900/40 text-blue-400 border-blue-800",
//   Trivial : "bg-gray-800 text-gray-400 border-gray-700",
// }

// const SEVERITY_COLORS: Record<string, string> = {
//   Critical: "bg-red-900/40 text-red-400 border-red-800",
//   High    : "bg-orange-900/40 text-orange-400 border-orange-800",
//   Medium  : "bg-yellow-900/40 text-yellow-400 border-yellow-800",
//   Low     : "bg-blue-900/40 text-blue-400 border-blue-800",
// }

// function PriorityBadge({ priority }: { priority: string }) {
//   const cls = PRIORITY_COLORS[priority] ?? "bg-gray-800 text-gray-400 border-gray-700"
//   return <span className={`text-xs font-medium px-2 py-0.5 rounded border ${cls}`}>{priority}</span>
// }

// function SeverityBadge({ severity }: { severity: string }) {
//   const cls = SEVERITY_COLORS[severity] ?? "bg-gray-800 text-gray-400 border-gray-700"
//   return <span className={`text-xs font-medium px-2 py-0.5 rounded border ${cls}`}>{severity} severity</span>
// }

// function CategoryBadge({ category, component }: { category: string; component: string }) {
//   return (
//     <span className="text-xs font-medium px-2 py-0.5 rounded border bg-purple-900/40 text-purple-400 border-purple-800">
//       {category} · {component}
//     </span>
//   )
// }

// // ── Simulated live agent progress ─────────────────────────────────────────────
// // Shows agents "completing" in sequence based on realistic timing.
// // The actual /analyze call runs in parallel — this is visual feedback only.
// const AGENT_STEPS = [
//   { key: "classifier",     label: "Classifier",     model: "Gemini Flash",  delayMs: 1500  },
//   { key: "severity",       label: "Severity",       model: "Gemini Flash",  delayMs: 2000  },
//   { key: "retriever",      label: "Retriever",      model: "Weaviate + Cohere", delayMs: 5000 },
//   { key: "draft_response", label: "Draft Response", model: "Claude Sonnet", delayMs: 10000 },
//   { key: "escalation",     label: "Escalation",     model: "Rules + Groq",  delayMs: 12000 },
// ]

// function LoadingPipeline() {
//   const [completed, setCompleted] = useState<Set<string>>(new Set())
//   const [current, setCurrent]     = useState<string | null>(AGENT_STEPS[0].key)

//   useEffect(() => {
//     AGENT_STEPS.forEach(step => {
//       setTimeout(() => {
//         setCompleted(prev => new Set([...prev, step.key]))
//         const idx  = AGENT_STEPS.findIndex(s => s.key === step.key)
//         const next = AGENT_STEPS[idx + 1]
//         setCurrent(next?.key ?? null)
//       }, step.delayMs)
//     })
//   }, [])

//   return (
//     <div className="min-h-screen bg-gray-950 text-white flex flex-col items-center justify-center gap-8 px-6">
//       <div className="text-center">
//         <p className="text-lg font-medium text-gray-200 mb-1">Running 5-agent analysis</p>
//         <p className="text-sm text-gray-500">Each agent specialises in a different part of the problem</p>
//       </div>

//       <div className="w-full max-w-sm space-y-3">
//         {AGENT_STEPS.map(step => {
//           const isDone    = completed.has(step.key)
//           const isRunning = current === step.key
//           return (
//             <div key={step.key} className={`flex items-center gap-3 px-4 py-3 rounded-lg border transition-all duration-500 ${
//               isDone
//                 ? "bg-green-900/20 border-green-800/50"
//                 : isRunning
//                   ? "bg-blue-900/20 border-blue-800/50"
//                   : "bg-gray-900 border-gray-800"
//             }`}>
//               <div className={`w-5 h-5 rounded-full flex items-center justify-center shrink-0 ${
//                 isDone ? "bg-green-500" : isRunning ? "bg-blue-500 animate-pulse" : "bg-gray-700"
//               }`}>
//                 {isDone && <span className="text-white text-xs">✓</span>}
//               </div>
//               <div className="flex-1 min-w-0">
//                 <p className={`text-sm font-medium ${isDone ? "text-green-300" : isRunning ? "text-blue-300" : "text-gray-500"}`}>
//                   {step.label}
//                 </p>
//                 <p className="text-xs text-gray-600">{step.model}</p>
//               </div>
//               {isRunning && (
//                 <div className="flex gap-1">
//                   {[0,1,2].map(i => (
//                     <div key={i} className="w-1 h-1 bg-blue-400 rounded-full animate-bounce"
//                       style={{ animationDelay: `${i * 0.15}s` }} />
//                   ))}
//                 </div>
//               )}
//             </div>
//           )
//         })}
//       </div>
//     </div>
//   )
// }

// // ── Markdown renderer ─────────────────────────────────────────────────────────
// function MD({ children }: { children: string }) {
//   return (
//     <ReactMarkdown
//       remarkPlugins={[remarkGfm]}
//       components={{
//         h1: ({ children }) => <h1 className="text-base font-bold text-white mt-4 mb-2">{children}</h1>,
//         h2: ({ children }) => <h2 className="text-sm font-bold text-white mt-3 mb-1.5">{children}</h2>,
//         h3: ({ children }) => <h3 className="text-sm font-semibold text-gray-200 mt-3 mb-1">{children}</h3>,
//         // p:  ({ children }) => <p className="text-sm text-gray-300 leading-relaxed mb-2">{children}</p>,
//         p: ({ children }) => {
//           const renderWithLinks = (child: React.ReactNode): React.ReactNode => {
//             if (typeof child !== "string") return child
//             const parts = child.split(/(\b[A-Z][A-Z0-9]+-\d+\b)/g)
//             return parts.map((part, i) => {
//               if (/^[A-Z][A-Z0-9]+-\d+$/.test(part)) {
//                 return (
//                   <a key={i} href={`https://issues.apache.org/jira/browse/${part}`}
//                     target="_blank" className="text-blue-400 hover:underline font-mono text-xs">
//                     [{part}]
//                   </a>
//                 )
//               }
//               return part
//             })
//           }
//           return (
//             <p className="text-sm text-gray-300 leading-relaxed mb-2">
//               {React.Children.map(children, renderWithLinks)}
//             </p>
//           )
//         },
//         ul: ({ children }) => <ul className="list-disc list-inside space-y-1 mb-2 text-sm text-gray-300">{children}</ul>,
//         ol: ({ children }) => <ol className="list-decimal list-inside space-y-1 mb-2 text-sm text-gray-300">{children}</ol>,
//         li: ({ children }) => <li className="text-gray-300 leading-relaxed">{children}</li>,
//         strong: ({ children }) => <strong className="text-white font-semibold">{children}</strong>,
//         code: ({ children, className }) => {
//           const isBlock = className?.includes("language-")
//           return isBlock
//             ? <code className="block bg-gray-950 border border-gray-700 rounded p-3 text-xs text-green-400 font-mono overflow-x-auto my-2 whitespace-pre">{children}</code>
//             : <code className="bg-gray-800 text-green-400 font-mono text-xs px-1.5 py-0.5 rounded">{children}</code>
//         },
//         blockquote: ({ children }) => (
//           <blockquote className="border-l-2 border-blue-500 pl-3 my-2 text-gray-400 italic text-sm">{children}</blockquote>
//         ),
//         table: ({ children }) => (
//           <div className="overflow-x-auto my-3">
//             <table className="text-xs w-full border-collapse">{children}</table>
//           </div>
//         ),
//         th: ({ children }) => <th className="border border-gray-700 px-3 py-1.5 text-left text-gray-300 bg-gray-800 font-medium">{children}</th>,
//         td: ({ children }) => <td className="border border-gray-700 px-3 py-1.5 text-gray-400">{children}</td>,
//         hr: () => <hr className="border-gray-800 my-3" />,
//         a:  ({ children, href }) => <a href={href} target="_blank" className="text-blue-400 hover:underline">{children}</a>,
//       }}
//     >
//       {children}
//     </ReactMarkdown>
//   )
// }

// // ── Parse Claude response into 4 sections ─────────────────────────────────────
// const SECTION_PATTERNS = [
//   { key: "Root Cause",      icon: "🔎", color: "border-red-800/50",    title: "Root Cause Analysis",  defaultOpen: true  },
//   { key: "Recommended Fix", icon: "🔧", color: "border-green-800/50",  title: "Recommended Fix",      defaultOpen: true  },
//   { key: "Additional",      icon: "💡", color: "border-yellow-800/50", title: "Additional Checks",    defaultOpen: false },
//   { key: "Priority",        icon: "📊", color: "border-blue-800/50",   title: "Priority Assessment",  defaultOpen: false },
// ]

// function parseSections(text: string) {
//   const sections: Section[] = []
//   const lines    = text.split("\n")
//   let current    = ""
//   let currentIdx = -1

//   for (const line of lines) {
//     const matchIdx = SECTION_PATTERNS.findIndex(p =>
//       line.toLowerCase().includes(p.key.toLowerCase()) &&
//       (line.startsWith("#") || line.startsWith("**") || /^\d\./.test(line.trim()))
//     )
//     if (matchIdx !== -1) {
//       if (currentIdx !== -1 && current.trim()) {
//         sections.push({ ...SECTION_PATTERNS[currentIdx], content: current.trim() })
//       }
//       current = ""; currentIdx = matchIdx
//     } else {
//       current += line + "\n"
//     }
//   }
//   if (currentIdx !== -1 && current.trim()) {
//     sections.push({ ...SECTION_PATTERNS[currentIdx], content: current.trim() })
//   }
//   // Deduplicate — keep first occurrence of each section key
//   const seen    = new Set<string>()
//   const deduped = sections.filter(sec => {
//     if (seen.has(sec.key)) return false
//     seen.add(sec.key)
//     return true
//   })

//   if (deduped.length === 0) {
//     return [{ 
//       key        : "analysis",
//       title      : "Analysis", 
//       icon       : "🤖", 
//       color      : "border-gray-700", 
//       content    : text, 
//       defaultOpen: true 
//     }]
//   }
//   return deduped
// }

// // ── Collapsible section card ──────────────────────────────────────────────────
// // function SectionCard({ sec }: { sec: ReturnType<typeof parseSections>[number] }) {
// function SectionCard({ sec }: { sec: Section }) {
//   const [open, setOpen] = useState(sec.defaultOpen)
//   return (
//     <div className={`bg-gray-900 border ${sec.color} rounded-xl overflow-hidden transition-all duration-200`}>
//       <button
//         onClick={() => setOpen(!open)}
//         className="w-full flex items-center justify-between px-5 py-3 border-b border-gray-800 hover:bg-gray-800/30 transition-colors"
//       >
//         <div className="flex items-center gap-2">
//           <span className="text-base">{sec.icon}</span>
//           <span className="text-sm font-semibold text-gray-200">{sec.title}</span>
//         </div>
//         <span className="text-gray-600 text-xs">{open ? "▲" : "▼"}</span>
//       </button>
//       {open && (
//         <div className="px-5 py-4">
//           <MD>{sec.content}</MD>
//         </div>
//       )}
//     </div>
//   )
// }

// // ── Copy button ───────────────────────────────────────────────────────────────
// function CopyButton({ text }: { text: string }) {
//   const [copied, setCopied] = useState(false)
//   return (
//     <button onClick={() => { navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 2000) }}
//       className="text-xs text-gray-500 hover:text-gray-300 px-2 py-1 rounded hover:bg-gray-800 transition-colors">
//       {copied ? "✓ Copied" : "Copy"}
//     </button>
//   )
// }

// // ── Similarity bar ────────────────────────────────────────────────────────────
// function SimilarityBar({ value }: { value: number }) {
//   const pct   = Math.round(value * 100)
//   const color = pct >= 85 ? "bg-green-500" : pct >= 70 ? "bg-blue-500" : "bg-gray-500"
//   return (
//     <div className="flex items-center gap-2">
//       <div className="w-16 h-1 bg-gray-800 rounded-full overflow-hidden">
//         <div className={`h-full ${color} rounded-full`} style={{ width: `${pct}%` }} />
//       </div>
//       <span className="text-xs text-gray-500">{pct}%</span>
//     </div>
//   )
// }

// // ── Feedback buttons ──────────────────────────────────────────────────────────
// function FeedbackBar({ bugTitle, solution }: { bugTitle: string; solution: string }) {
//   const [sent, setSent] = useState<"up" | "down" | null>(null)

//   const sendFeedback = async (vote: "up" | "down") => {
//     setSent(vote)
//     // try {
//     //   await fetch("http://127.0.0.1:8000/feedback", {
//     //     method : "POST",
//     //     headers: { "Content-Type": "application/json" },
//     //     body   : JSON.stringify({ bug_title: bugTitle, vote, solution_snippet: solution.slice(0, 200) })
//     //   })
//     // } catch {}
//     try {
//       await fetch(`${API_URL}/feedback`, {
//         method : "POST",
//         headers: { "Content-Type": "application/json" },
//         body   : JSON.stringify({ bug_title: bugTitle, vote, solution_snippet: solution.slice(0, 200) })
//       })
//     } catch {}
//   }

//   return (
//     <div className="flex items-center gap-3">
//       <span className="text-xs text-gray-500">Was this helpful?</span>
//       <button onClick={() => sendFeedback("up")}
//         className={`text-sm px-3 py-1 rounded border transition-colors ${sent === "up" ? "bg-green-900/40 border-green-700 text-green-400" : "border-gray-700 text-gray-500 hover:text-gray-300"}`}>
//         👍
//       </button>
//       <button onClick={() => sendFeedback("down")}
//         className={`text-sm px-3 py-1 rounded border transition-colors ${sent === "down" ? "bg-red-900/40 border-red-700 text-red-400" : "border-gray-700 text-gray-500 hover:text-gray-300"}`}>
//         👎
//       </button>
//       {sent && <span className="text-xs text-gray-500">Thanks for the feedback</span>}
//     </div>
//   )
// }

// // ── Main page ─────────────────────────────────────────────────────────────────
// export default function Results() {
//   const [solution, setSolution]             = useState("")
//   // const [sections, setSections]             = useState<ReturnType<typeof parseSections>>([])
//   const [sections, setSections] = useState<Section[]>([])
//   const [tickets, setTickets]               = useState<Issue[]>([])
//   const [classification, setClassification] = useState<Classification | null>(null)
//   const [severity, setSeverity]             = useState<SeverityAssessment | null>(null)
//   // const [agentStatus, setAgentStatus]       = useState<AgentStatus>({})
//   const [escalated, setEscalated]           = useState(false)
//   const [escalationReasons, setEscReasons]  = useState<string[]>([])
//   const [confidence, setConfidence]         = useState(0)
//   const [loading, setLoading]               = useState(true)
//   const [error, setError]                   = useState("")
//   const [messages, setMessages]             = useState<{ role: string; content: string }[]>([])
//   const [followUp, setFollowUp]             = useState("")
//   const [chatLoading, setChatLoading]       = useState(false)
//   const [showTickets, setShowTickets]       = useState(false)
//   const [showAll, setShowAll]         = useState(false)   
//   // const [expandedTicket, setExpanded]       = useState<number | null>(null)
//   const router = useRouter()
//   const hasFetched = useRef(false)

//   useEffect(() => {
//     if (hasFetched.current) return
//     hasFetched.current = true
//     const issue    = sessionStorage.getItem("issue_description")
//     const priority = sessionStorage.getItem("priority")
//     const bugTitle = sessionStorage.getItem("bug_title")
//     const stack    = sessionStorage.getItem("stack_trace") ?? ""

//     if (!issue) { router.push("/"); return }

//     const fetchSolution = async () => {
//       try {
//         // const res = await fetch("http://127.0.0.1:8000/analyze", {
//         //   method : "POST",
//         //   headers: { "Content-Type": "application/json" },
//         //   body   : JSON.stringify({
//         //     issue_description: issue,
//         //     bug_title        : bugTitle ?? "",
//         //     stack_trace      : stack,
//         //     user_priority    : priority ?? "Major",
//         //   })
//         // })
//         const res = await fetch(`${API_URL}/analyze`, {
//           method : "POST",
//           headers: { "Content-Type": "application/json" },
//           body   : JSON.stringify({
//             issue_description: issue,
//             bug_title        : bugTitle ?? "",
//             stack_trace      : stack,
//             user_priority    : priority ?? "Major",
//           })
//         })

//         if (!res.ok) {
//           setError("Could not reach the backend. Make sure the API is running on port 8000.")
//           setLoading(false)
//           return
//         }

//         const data = await res.json()
//         const reply = data.final_response ?? ""

//         setSolution(reply)
//         setSections(parseSections(reply))
//         setTickets(data.retrieved_issues ?? [])
//         setClassification(data.classification ?? null)
//         setSeverity(data.severity_assessment ?? null)
//         // setAgentStatus(data.agent_status ?? {})
//         setEscalated(data.escalated ?? false)
//         setEscReasons(data.escalation_reasons ?? [])
//         setConfidence(data.confidence_score ?? 0)
//         setLoading(false)

//       } catch {
//         setError("Something went wrong. Please go back and try again.")
//         setLoading(false)
//       }
//     }

//     fetchSolution()
//   }, [])

//   const handleFollowUp = async () => {
//     if (!followUp.trim() || chatLoading) return
//     setChatLoading(true)
//     const userMsg    = { role: "user", content: followUp }
//     const newMessages = [...messages, userMsg]
//     setMessages(newMessages)
//     setFollowUp("")

//     const res  = await fetch("/api/chat", {
//       method : "POST",
//       headers: { "Content-Type": "application/json" },
//       body   : JSON.stringify({ messages: [{ role: "assistant", content: solution }, ...newMessages] })
//     })
//     const data = await res.json()
//     setMessages([...newMessages, { role: "assistant", content: data.reply }])
//     setChatLoading(false)
//   }

//   if (loading) return <LoadingPipeline />

//   if (error) return (
//     <div className="min-h-screen bg-gray-950 text-white flex flex-col items-center justify-center gap-4 px-6">
//       <p className="text-red-400 text-center max-w-md text-sm">{error}</p>
//       <button onClick={() => router.push("/")} className="text-blue-400 hover:underline text-sm">← Go back</button>
//     </div>
//   )

//   const bugTitle = sessionStorage.getItem("bug_title") ?? ""
//   const priority = sessionStorage.getItem("priority") ?? "—"

//   return (
//     <main className="min-h-screen bg-gray-950 text-white">

//       {/* Nav */}
//       <nav className="border-b border-gray-800 px-8 py-4 flex items-center gap-3 sticky top-0 bg-gray-950/95 backdrop-blur z-10">
//         <span className="text-lg">🐛</span>
//         <span className="font-semibold tracking-tight">BugAnalyzer</span>
//         <div className="ml-auto flex items-center gap-4">
//           <a href="/review" className="text-xs text-gray-500 hover:text-gray-300 transition-colors">Review Queue</a>
//           <button onClick={() => router.push("/")} className="text-xs text-gray-500 hover:text-gray-300 transition-colors">
//             ← New search
//           </button>
//         </div>
//       </nav>

//       <div className="max-w-3xl mx-auto px-6 py-10 space-y-6">

//         {/* Bug header */}
//         <div className="flex items-start justify-between gap-4">
//           <div>
//             {bugTitle && <h1 className="text-xl font-semibold mb-1.5">{bugTitle}</h1>}
//             <div className="flex flex-wrap items-center gap-2">
//               <PriorityBadge priority={priority} />
//               {severity && <SeverityBadge severity={severity.severity} />}
//               {classification && <CategoryBadge category={classification.category} component={classification.component} />}
//               <span className="text-sm text-gray-500">{tickets.length} similar tickets found</span>
//               {confidence > 0 && (
//                 <span className="text-xs text-gray-600">· model confidence {(confidence * 100).toFixed(0)}%</span>
//               )}
//             </div>
//           </div>
//           <CopyButton text={solution} />
//         </div>

//         {/* Escalation warning */}
//         {escalated && (
//           <div className="bg-orange-900/20 border border-orange-800 rounded-xl px-5 py-4">
//             <div className="flex items-center justify-between gap-4">
//               <div>
//                 <div className="flex items-center gap-2 mb-1">
//                   <span>⚠️</span>
//                   <span className="text-sm font-semibold text-orange-400">Flagged for Human Review</span>
//                 </div>
//                 <p className="text-xs text-orange-300/70">
//                   Reasons: {escalationReasons.map(r => r.replace(/_/g, " ")).join(", ")}
//                 </p>
//                 {severity?.reasoning && (
//                   <p className="text-xs text-orange-300/60 mt-0.5">{severity.reasoning}</p>
//                 )}
//               </div>
//               <a href="/review"
//                 className="shrink-0 text-xs bg-orange-900/40 border border-orange-700 text-orange-400 px-3 py-1.5 rounded-lg hover:bg-orange-900/60 transition-colors">
//                 Open review queue →
//               </a>
//             </div>
//           </div>
//         )}

//         {/* Section cards — collapsible, root cause + fix open by default */}
//         <div className="space-y-3">
//           {sections.map((sec, i) => <SectionCard key={i} sec={sec} />)}
//         </div>

//         {/* Feedback */}
//         <FeedbackBar bugTitle={bugTitle} solution={solution} />

//         {/* Similar tickets */}
//         <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
//           <button
//             onClick={() => setShowTickets(!showTickets)}
//             className="w-full flex items-center justify-between px-5 py-4 text-sm font-medium text-gray-300 hover:text-white hover:bg-gray-800/50 transition-colors"
//           >
//             <span>📋 Supporting evidence — {tickets.length} similar resolved tickets</span>
//             <span className="text-gray-600 text-xs">{showTickets ? "▲ hide" : "▼ show"}</span>
//           </button>

//           {showTickets && (
//             <div className="border-t border-gray-800">
//               <p className="px-5 py-3 text-xs text-gray-500 border-b border-gray-800">
//                 Click any ticket key to view the full resolution on Apache JIRA ↗
//               </p>

//               <div className="divide-y divide-gray-800/50">
//                 {(showAll ? tickets : tickets.slice(0, 8)).map((t, i) => (
//                   <div key={i} className="flex items-center justify-between px-5 py-2.5 hover:bg-gray-800/30 transition-colors">
//                     <div className="flex items-center gap-3 min-w-0">
//                     <a
//                         href={`https://issues.apache.org/jira/browse/${t.key}`}
//                         target="_blank"
//                         className="text-blue-400 hover:text-blue-300 font-mono text-xs hover:underline shrink-0"
//                       >
//                         [{t.key}]
//                       </a>
//                       <p className="text-sm text-gray-300 truncate">{t.summary}</p>
//                     </div>
//                     <div className="flex items-center gap-3 shrink-0 ml-4">
//                       {t["priority.name"] && t["priority.name"] !== "Unknown" && (
//                         <PriorityBadge priority={t["priority.name"]} />
//                       )}
//                       <SimilarityBar value={t.similarity} />
//                     </div>
//                   </div>
//                 ))}
//               </div>

//               {tickets.length > 8 && (
//                 <button
//                   onClick={() => setShowAll(!showAll)}
//                   className="w-full py-2.5 text-xs text-gray-500 hover:text-gray-400 border-t border-gray-800 transition-colors"
//                 >
//                   {showAll ? "Show fewer" : `Show all ${tickets.length} tickets`}
//                 </button>
//               )}
//             </div>
//           )}
//         </div>

//         {/* Follow-up chat */}
//         <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
//           <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-4">💬 Ask a follow-up</p>
//           {messages.length > 0 && (
//             <div className="space-y-3 mb-4">
//               {messages.map((m, i) => (
//                 <div key={i} className={`rounded-lg px-4 py-3 text-sm ${
//                   m.role === "user"
//                     ? "bg-blue-900/30 border border-blue-800/50 ml-8"
//                     : "bg-gray-800 border border-gray-700/50 mr-8"
//                 }`}>
//                   <span className="text-xs text-gray-500 block mb-1">{m.role === "user" ? "You" : "BugAnalyzer"}</span>
//                   {m.role === "assistant" ? <MD>{m.content}</MD> : <p className="text-gray-200">{m.content}</p>}
//                 </div>
//               ))}
//             </div>
//           )}
//           <div className="flex gap-2">
//             <input
//               className="flex-1 bg-gray-950 border border-gray-700 rounded-lg px-3 py-2.5 text-white placeholder-gray-600 focus:outline-none focus:border-blue-500 text-sm transition-colors"
//               placeholder="e.g. How do I apply this fix on Windows?"
//               value={followUp}
//               onChange={e => setFollowUp(e.target.value)}
//               onKeyDown={e => e.key === "Enter" && !chatLoading && handleFollowUp()}
//             />
//             <button onClick={handleFollowUp} disabled={chatLoading}
//               className="bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-white px-4 rounded-lg text-sm font-medium transition-colors">
//               {chatLoading ? "..." : "Ask"}
//             </button>
//           </div>
//         </div>

//       </div>
//     </main>
//   )
// }

////////////////////////VERSION 2/////////////////////////////

// "use client"
// import { API_URL } from "@/lib/api"
// import { useEffect, useRef, useState } from "react"
// import { useRouter } from "next/navigation"
// import ReactMarkdown from "react-markdown"
// import remarkGfm from "remark-gfm"
// import React from "react"

// interface Issue {
//   key: string
//   summary: string
//   "priority.name": string
//   "resolution.name": string
//   comments_text: string
//   similarity: number
// }

// interface Classification {
//   category: string
//   component: string
//   root_cause_family: string
//   enriched_query: string
// }

// interface SeverityAssessment {
//   severity: string
//   sla_risk: boolean
//   production_impact: boolean
//   escalate_immediately: boolean
//   reasoning: string
// }

// interface Section {
//   key         : string
//   title       : string
//   icon        : string
//   color       : string
//   defaultOpen : boolean
//   content     : string
// }

// // ── Priority / Severity badges ────────────────────────────────────────────────
// const PRIORITY_COLORS: Record<string, string> = {
//   Blocker : "bg-red-900/40 text-red-400 border-red-800",
//   Critical: "bg-orange-900/40 text-orange-400 border-orange-800",
//   Major   : "bg-yellow-900/40 text-yellow-400 border-yellow-800",
//   Minor   : "bg-blue-900/40 text-blue-400 border-blue-800",
//   Trivial : "bg-gray-800 text-gray-400 border-gray-700",
// }

// const SEVERITY_COLORS: Record<string, string> = {
//   Critical: "bg-red-900/40 text-red-400 border-red-800",
//   High    : "bg-orange-900/40 text-orange-400 border-orange-800",
//   Medium  : "bg-yellow-900/40 text-yellow-400 border-yellow-800",
//   Low     : "bg-blue-900/40 text-blue-400 border-blue-800",
// }

// function PriorityBadge({ priority }: { priority: string }) {
//   const cls = PRIORITY_COLORS[priority] ?? "bg-gray-800 text-gray-400 border-gray-700"
//   return <span className={`text-xs font-medium px-2 py-0.5 rounded border ${cls}`}>{priority}</span>
// }

// function SeverityBadge({ severity }: { severity: string }) {
//   const cls = SEVERITY_COLORS[severity] ?? "bg-gray-800 text-gray-400 border-gray-700"
//   return <span className={`text-xs font-medium px-2 py-0.5 rounded border ${cls}`}>{severity} severity</span>
// }

// function CategoryBadge({ category, component }: { category: string; component: string }) {
//   return (
//     <span className="text-xs font-medium px-2 py-0.5 rounded border bg-purple-900/40 text-purple-400 border-purple-800">
//       {category} · {component}
//     </span>
//   )
// }

// // ── Simulated agent progress ──────────────────────────────────────────────────
// // Visual feedback only — replaced by real streamed events in Batch 5.
// const AGENT_STEPS = [
//   { key: "classifier",     label: "Classifier",     model: "Gemini Flash",      delayMs: 1500  },
//   { key: "severity",       label: "Severity",       model: "Gemini Flash",      delayMs: 2000  },
//   { key: "retriever",      label: "Retriever",      model: "Weaviate + Cohere", delayMs: 5000  },
//   { key: "draft_response", label: "Draft Response", model: "Claude Sonnet",     delayMs: 10000 },
//   { key: "escalation",     label: "Escalation",     model: "Rules + Groq",      delayMs: 12000 },
// ]

// function LoadingPipeline() {
//   const [completed, setCompleted] = useState<Set<string>>(new Set())
//   const [current, setCurrent]     = useState<string | null>(AGENT_STEPS[0].key)

//   useEffect(() => {
//     const timers = AGENT_STEPS.map(step =>
//       setTimeout(() => {
//         setCompleted(prev => new Set([...prev, step.key]))
//         const idx  = AGENT_STEPS.findIndex(s => s.key === step.key)
//         const next = AGENT_STEPS[idx + 1]
//         setCurrent(next?.key ?? null)
//       }, step.delayMs)
//     )
//     return () => timers.forEach(clearTimeout)
//   }, [])

//   return (
//     <div className="min-h-screen bg-gray-950 text-white flex flex-col items-center justify-center gap-8 px-6">
//       <div className="text-center">
//         <p className="text-lg font-medium text-gray-200 mb-1">Running 5-agent analysis</p>
//         <p className="text-sm text-gray-500">Each agent specialises in a different part of the problem</p>
//       </div>

//       <div className="w-full max-w-sm space-y-3">
//         {AGENT_STEPS.map(step => {
//           const isDone    = completed.has(step.key)
//           const isRunning = current === step.key
//           return (
//             <div key={step.key} className={`flex items-center gap-3 px-4 py-3 rounded-lg border transition-all duration-500 ${
//               isDone
//                 ? "bg-green-900/20 border-green-800/50"
//                 : isRunning
//                   ? "bg-blue-900/20 border-blue-800/50"
//                   : "bg-gray-900 border-gray-800"
//             }`}>
//               <div className={`w-5 h-5 rounded-full flex items-center justify-center shrink-0 ${
//                 isDone ? "bg-green-500" : isRunning ? "bg-blue-500 animate-pulse" : "bg-gray-700"
//               }`}>
//                 {isDone && <span className="text-white text-xs">✓</span>}
//               </div>
//               <div className="flex-1 min-w-0">
//                 <p className={`text-sm font-medium ${isDone ? "text-green-300" : isRunning ? "text-blue-300" : "text-gray-500"}`}>
//                   {step.label}
//                 </p>
//                 <p className="text-xs text-gray-600">{step.model}</p>
//               </div>
//               {isRunning && (
//                 <div className="flex gap-1">
//                   {[0,1,2].map(i => (
//                     <div key={i} className="w-1 h-1 bg-blue-400 rounded-full animate-bounce"
//                       style={{ animationDelay: `${i * 0.15}s` }} />
//                   ))}
//                 </div>
//               )}
//             </div>
//           )
//         })}
//       </div>
//     </div>
//   )
// }

// // ── Markdown renderer ─────────────────────────────────────────────────────────
// function MD({ children }: { children: string }) {
//   return (
//     <ReactMarkdown
//       remarkPlugins={[remarkGfm]}
//       components={{
//         h1: ({ children }) => <h1 className="text-base font-bold text-white mt-4 mb-2">{children}</h1>,
//         h2: ({ children }) => <h2 className="text-sm font-bold text-white mt-3 mb-1.5">{children}</h2>,
//         h3: ({ children }) => <h3 className="text-sm font-semibold text-gray-200 mt-3 mb-1">{children}</h3>,
//         p: ({ children }) => {
//           const renderWithLinks = (child: React.ReactNode): React.ReactNode => {
//             if (typeof child !== "string") return child
//             const parts = child.split(/(\b[A-Z][A-Z0-9]+-\d+\b)/g)
//             return parts.map((part, i) => {
//               if (/^[A-Z][A-Z0-9]+-\d+$/.test(part)) {
//                 return (
//                   <a key={i} href={`https://issues.apache.org/jira/browse/${part}`}
//                     target="_blank" className="text-blue-400 hover:underline font-mono text-xs">
//                     [{part}]
//                   </a>
//                 )
//               }
//               return part
//             })
//           }
//           return (
//             <p className="text-sm text-gray-300 leading-relaxed mb-2">
//               {React.Children.map(children, renderWithLinks)}
//             </p>
//           )
//         },
//         ul: ({ children }) => <ul className="list-disc list-inside space-y-1 mb-2 text-sm text-gray-300">{children}</ul>,
//         ol: ({ children }) => <ol className="list-decimal list-inside space-y-1 mb-2 text-sm text-gray-300">{children}</ol>,
//         li: ({ children }) => <li className="text-gray-300 leading-relaxed">{children}</li>,
//         strong: ({ children }) => <strong className="text-white font-semibold">{children}</strong>,
//         code: ({ children, className }) => {
//           const isBlock = className?.includes("language-")
//           return isBlock
//             ? <code className="block bg-gray-950 border border-gray-700 rounded p-3 text-xs text-green-400 font-mono overflow-x-auto my-2 whitespace-pre">{children}</code>
//             : <code className="bg-gray-800 text-green-400 font-mono text-xs px-1.5 py-0.5 rounded">{children}</code>
//         },
//         blockquote: ({ children }) => (
//           <blockquote className="border-l-2 border-blue-500 pl-3 my-2 text-gray-400 italic text-sm">{children}</blockquote>
//         ),
//         table: ({ children }) => (
//           <div className="overflow-x-auto my-3">
//             <table className="text-xs w-full border-collapse">{children}</table>
//           </div>
//         ),
//         th: ({ children }) => <th className="border border-gray-700 px-3 py-1.5 text-left text-gray-300 bg-gray-800 font-medium">{children}</th>,
//         td: ({ children }) => <td className="border border-gray-700 px-3 py-1.5 text-gray-400">{children}</td>,
//         hr: () => <hr className="border-gray-800 my-3" />,
//         a:  ({ children, href }) => <a href={href} target="_blank" className="text-blue-400 hover:underline">{children}</a>,
//       }}
//     >
//       {children}
//     </ReactMarkdown>
//   )
// }

// // ── Parse Claude response into 4 sections ─────────────────────────────────────
// const SECTION_PATTERNS = [
//   { key: "Root Cause",      icon: "🔎", color: "border-red-800/50",    title: "Root Cause Analysis",  defaultOpen: true  },
//   { key: "Recommended Fix", icon: "🔧", color: "border-green-800/50",  title: "Recommended Fix",      defaultOpen: true  },
//   { key: "Additional",      icon: "💡", color: "border-yellow-800/50", title: "Additional Checks",    defaultOpen: false },
//   { key: "Priority",        icon: "📊", color: "border-blue-800/50",   title: "Priority Assessment",  defaultOpen: false },
// ]

// function parseSections(text: string): Section[] {
//   const sections: Section[] = []
//   const lines    = text.split("\n")
//   let current    = ""
//   let currentIdx = -1

//   for (const line of lines) {
//     const matchIdx = SECTION_PATTERNS.findIndex(p =>
//       line.toLowerCase().includes(p.key.toLowerCase()) &&
//       (line.startsWith("#") || line.startsWith("**") || /^\d\./.test(line.trim()))
//     )
//     if (matchIdx !== -1) {
//       if (currentIdx !== -1 && current.trim()) {
//         sections.push({ ...SECTION_PATTERNS[currentIdx], content: current.trim() })
//       }
//       current = ""; currentIdx = matchIdx
//     } else {
//       current += line + "\n"
//     }
//   }
//   if (currentIdx !== -1 && current.trim()) {
//     sections.push({ ...SECTION_PATTERNS[currentIdx], content: current.trim() })
//   }

//   // Deduplicate — keep first occurrence of each section key
//   const seen    = new Set<string>()
//   const deduped = sections.filter(sec => {
//     if (seen.has(sec.key)) return false
//     seen.add(sec.key)
//     return true
//   })

//   if (deduped.length === 0) {
//     return [{
//       key        : "analysis",
//       title      : "Analysis",
//       icon       : "🤖",
//       color      : "border-gray-700",
//       content    : text,
//       defaultOpen: true,
//     }]
//   }
//   return deduped
// }

// // ── Collapsible section card ──────────────────────────────────────────────────
// function SectionCard({ sec }: { sec: Section }) {
//   const [open, setOpen] = useState(sec.defaultOpen)
//   return (
//     <div className={`bg-gray-900 border ${sec.color} rounded-xl overflow-hidden transition-all duration-200`}>
//       <button
//         onClick={() => setOpen(!open)}
//         className="w-full flex items-center justify-between px-5 py-3 border-b border-gray-800 hover:bg-gray-800/30 transition-colors"
//       >
//         <div className="flex items-center gap-2">
//           <span className="text-base">{sec.icon}</span>
//           <span className="text-sm font-semibold text-gray-200">{sec.title}</span>
//         </div>
//         <span className="text-gray-600 text-xs">{open ? "▲" : "▼"}</span>
//       </button>
//       {open && (
//         <div className="px-5 py-4">
//           <MD>{sec.content}</MD>
//         </div>
//       )}
//     </div>
//   )
// }

// // ── Copy button ───────────────────────────────────────────────────────────────
// function CopyButton({ text }: { text: string }) {
//   const [copied, setCopied] = useState(false)
//   return (
//     <button onClick={() => { navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 2000) }}
//       className="text-xs text-gray-500 hover:text-gray-300 px-2 py-1 rounded hover:bg-gray-800 transition-colors">
//       {copied ? "✓ Copied" : "Copy"}
//     </button>
//   )
// }

// // ── Similarity bar ────────────────────────────────────────────────────────────
// function SimilarityBar({ value }: { value: number }) {
//   const pct   = Math.round(value * 100)
//   const color = pct >= 85 ? "bg-green-500" : pct >= 70 ? "bg-blue-500" : "bg-gray-500"
//   return (
//     <div className="flex items-center gap-2">
//       <div className="w-16 h-1 bg-gray-800 rounded-full overflow-hidden">
//         <div className={`h-full ${color} rounded-full`} style={{ width: `${pct}%` }} />
//       </div>
//       <span className="text-xs text-gray-500">{pct}%</span>
//     </div>
//   )
// }

// // ── Feedback buttons ──────────────────────────────────────────────────────────
// function FeedbackBar({ bugTitle, solution, analysisId }: { bugTitle: string; solution: string; analysisId: string }) {
//   const [sent, setSent] = useState<"up" | "down" | null>(null)

//   const sendFeedback = async (vote: "up" | "down") => {
//     setSent(vote)
//     try {
//       await fetch(`${API_URL}/feedback`, {
//         method : "POST",
//         headers: { "Content-Type": "application/json" },
//         body   : JSON.stringify({
//           bug_title       : bugTitle,
//           vote,
//           solution_snippet: solution.slice(0, 200),
//           analysis_id     : analysisId,
//         })
//       })
//     } catch {}
//   }

//   return (
//     <div className="flex items-center gap-3">
//       <span className="text-xs text-gray-500">Was this helpful?</span>
//       <button onClick={() => sendFeedback("up")}
//         className={`text-sm px-3 py-1 rounded border transition-colors ${sent === "up" ? "bg-green-900/40 border-green-700 text-green-400" : "border-gray-700 text-gray-500 hover:text-gray-300"}`}>
//         👍
//       </button>
//       <button onClick={() => sendFeedback("down")}
//         className={`text-sm px-3 py-1 rounded border transition-colors ${sent === "down" ? "bg-red-900/40 border-red-700 text-red-400" : "border-gray-700 text-gray-500 hover:text-gray-300"}`}>
//         👎
//       </button>
//       {sent && <span className="text-xs text-gray-500">Thanks for the feedback</span>}
//     </div>
//   )
// }

// // ── Review status for escalated analyses ──────────────────────────────────────
// function ReviewStatusPill({ status }: { status: string | null }) {
//   if (status === "approved") return (
//     <span className="shrink-0 text-xs bg-green-900/40 border border-green-700 text-green-400 px-3 py-1.5 rounded-lg">
//       ✓ Approved by reviewer
//     </span>
//   )
//   if (status === "rejected") return (
//     <span className="shrink-0 text-xs bg-red-900/40 border border-red-700 text-red-400 px-3 py-1.5 rounded-lg">
//       ✗ Reviewer: needs rework
//     </span>
//   )
//   return (
//     <span className="shrink-0 text-xs bg-orange-900/40 border border-orange-700 text-orange-400 px-3 py-1.5 rounded-lg animate-pulse">
//       ⏳ Awaiting human review
//     </span>
//   )
// }

// // ── Main page ─────────────────────────────────────────────────────────────────
// export default function Results() {
//   const [solution, setSolution]             = useState("")
//   const [sections, setSections]             = useState<Section[]>([])
//   const [tickets, setTickets]               = useState<Issue[]>([])
//   const [classification, setClassification] = useState<Classification | null>(null)
//   const [severity, setSeverity]             = useState<SeverityAssessment | null>(null)
//   const [escalated, setEscalated]           = useState(false)
//   const [escalationReasons, setEscReasons]  = useState<string[]>([])
//   const [confidence, setConfidence]         = useState(0)
//   const [requestId, setRequestId]           = useState("")
//   const [reviewStatus, setReviewStatus]     = useState<string | null>(null)
//   const [loading, setLoading]               = useState(true)
//   const [error, setError]                   = useState("")
//   const [messages, setMessages]             = useState<{ role: string; content: string }[]>([])
//   const [followUp, setFollowUp]             = useState("")
//   const [chatLoading, setChatLoading]       = useState(false)
//   const [showTickets, setShowTickets]       = useState(false)
//   const [showAll, setShowAll]               = useState(false)
//   const router     = useRouter()
//   const hasFetched = useRef(false) 
//   const chatEndRef = useRef<HTMLDivElement>(null)

//   // ── Run the analysis once on page load ────────────────────────────────────
//   useEffect(() => {
//     if (hasFetched.current) return
//     hasFetched.current = true

//     const issue    = sessionStorage.getItem("issue_description")
//     const priority = sessionStorage.getItem("priority")
//     const bugTitle = sessionStorage.getItem("bug_title")
//     const stack    = sessionStorage.getItem("stack_trace") ?? ""

//     if (!issue) { router.push("/"); return }

//     const fetchSolution = async () => {
//       try {
//         const res = await fetch(`${API_URL}/analyze`, {
//           method : "POST",
//           headers: { "Content-Type": "application/json" },
//           body   : JSON.stringify({
//             issue_description: issue,
//             bug_title        : bugTitle ?? "",
//             stack_trace      : stack,
//             user_priority    : priority ?? "Major",
//           })
//         })

//         if (!res.ok) {
//           const body = await res.json().catch(() => ({}))
//           setError(
//             res.status === 429
//               ? (body.detail ?? "Daily demo limit reached — please try again tomorrow.")
//               : "Could not reach the backend. Make sure the API is running on port 8000."
//           )
//           setLoading(false)
//           return
//         }

//         const data  = await res.json()
//         const reply = data.final_response ?? ""

//         setSolution(reply)
//         setSections(parseSections(reply))
//         setTickets(data.retrieved_issues ?? [])
//         setClassification(data.classification ?? null)
//         setSeverity(data.severity_assessment ?? null)
//         setEscalated(data.escalated ?? false)
//         setEscReasons(data.escalation_reasons ?? [])
//         setConfidence(data.confidence_score ?? 0)
//         setRequestId(data.request_id ?? "")
//         if (data.escalated) setReviewStatus("pending")
//         setLoading(false)

//       } catch {
//         setError("Something went wrong. Please go back and try again.")
//         setLoading(false)
//       }
//     }

//     fetchSolution()
//   }, [])

//   // ── Poll review status while an escalated analysis is pending ─────────────
//   useEffect(() => {
//     if (!requestId || reviewStatus !== "pending") return
//     const timer = setInterval(async () => {
//       try {
//         const res = await fetch(`${API_URL}/analysis/${requestId}/status`)
//         if (!res.ok) return
//         const data = await res.json()
//         if (data.review_status && data.review_status !== "pending") {
//           setReviewStatus(data.review_status)
//         }
//       } catch {}
//     }, 15000)
//     return () => clearInterval(timer)
//   }, [requestId, reviewStatus])

//     // Keep the newest chat message (or the "Thinking…" bubble) in view
//     useEffect(() => {
//       chatEndRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" })
//     }, [messages, chatLoading])

//   // ── Follow-up chat ────────────────────────────────────────────────────────
//   // const handleFollowUp = async () => {
//   //   if (!followUp.trim() || chatLoading) return
//   //   setChatLoading(true)
//   //   const userMsg     = { role: "user", content: followUp }
//   //   const newMessages = [...messages, userMsg]
//   //   setMessages(newMessages)
//   //   setFollowUp("")

//   //   try {
//   //     const res  = await fetch("/api/chat", {
//   //       method : "POST",
//   //       headers: { "Content-Type": "application/json" },
//   //       body   : JSON.stringify({ messages: [{ role: "assistant", content: solution }, ...newMessages] })
//   //     })
//   //     const data = await res.json()
//   //     setMessages([...newMessages, { role: "assistant", content: data.reply ?? "No reply received." }])
//   //   } catch {
//   //     setMessages([...newMessages, { role: "assistant", content: "Sorry, the follow-up failed. Please try again." }])
//   //   } finally {
//   //     setChatLoading(false)
//   //   }
//   // }

//   const handleFollowUp = async () => {
//     if (!followUp.trim() || chatLoading) return
//     setChatLoading(true)
//     const userMsg     = { role: "user", content: followUp }
//     const newMessages = [...messages, userMsg]
//     setMessages(newMessages)
//     setFollowUp("")

//     try {
//       const res  = await fetch(`${API_URL}/chat`, {
//         method : "POST",
//         headers: { "Content-Type": "application/json" },
//         body   : JSON.stringify({ message: userMsg.content }),
//       })
//       const data  = await res.json().catch(() => ({}))
//       const reply = res.ok
//         ? (data.reply ?? "No reply received.")
//         : (typeof data.detail === "string" ? data.detail : "Sorry, the follow-up failed. Please try again.")
//       setMessages([...newMessages, { role: "assistant", content: reply }])
//     } catch {
//       setMessages([...newMessages, { role: "assistant", content: "Sorry, the follow-up failed. Please try again." }])
//     } finally {
//       setChatLoading(false)
//     }
//   }
  
//   if (loading) return <LoadingPipeline />

//   if (error) return (
//     <div className="min-h-screen bg-gray-950 text-white flex flex-col items-center justify-center gap-4 px-6">
//       <p className="text-red-400 text-center max-w-md text-sm">{error}</p>
//       <button onClick={() => router.push("/")} className="text-blue-400 hover:underline text-sm">← Go back</button>
//     </div>
//   )

//   const bugTitle = sessionStorage.getItem("bug_title") ?? ""
//   const priority = sessionStorage.getItem("priority") ?? "—"

//   return (
//     <main className="min-h-screen bg-gray-950 text-white">

//       {/* Nav */}
//       <nav className="border-b border-gray-800 px-8 py-4 flex items-center gap-3 sticky top-0 bg-gray-950/95 backdrop-blur z-10">
//         <span className="text-lg">🐛</span>
//         <span className="font-semibold tracking-tight">BugAnalyzer</span>
//         <div className="ml-auto flex items-center gap-4">
//           <a href="/review" className="text-xs text-gray-500 hover:text-gray-300 transition-colors">Review Queue</a>
//           <button onClick={() => router.push("/")} className="text-xs text-gray-500 hover:text-gray-300 transition-colors">
//             ← New search
//           </button>
//         </div>
//       </nav>

//       <div className="max-w-3xl mx-auto px-6 py-10 space-y-6">

//         {/* Bug header */}
//         <div className="flex items-start justify-between gap-4">
//           <div>
//             {bugTitle && <h1 className="text-xl font-semibold mb-1.5">{bugTitle}</h1>}
//             <div className="flex flex-wrap items-center gap-2">
//               <PriorityBadge priority={priority} />
//               {severity && <SeverityBadge severity={severity.severity} />}
//               {classification && <CategoryBadge category={classification.category} component={classification.component} />}
//               <span className="text-sm text-gray-500">{tickets.length} similar tickets found</span>
//               {confidence > 0 && (
//                 <span className="text-xs text-gray-600">· model confidence {(confidence * 100).toFixed(0)}%</span>
//               )}
//             </div>
//           </div>
//           <CopyButton text={solution} />
//         </div>

//         {/* Escalation banner */}
//         {escalated && (
//           <div className="bg-orange-900/20 border border-orange-800 rounded-xl px-5 py-4">
//             <div className="flex items-center justify-between gap-4">
//               <div>
//                 <div className="flex items-center gap-2 mb-1">
//                   <span>⚠️</span>
//                   <span className="text-sm font-semibold text-orange-400">Flagged for Human Review</span>
//                 </div>
//                 <p className="text-xs text-orange-300/70">
//                   Reasons: {escalationReasons.map(r => r.replace(/_/g, " ")).join(", ")}
//                 </p>
//                 {severity?.reasoning && (
//                   <p className="text-xs text-orange-300/60 mt-0.5">{severity.reasoning}</p>
//                 )}
//               </div>
//               <ReviewStatusPill status={reviewStatus} />
//             </div>
//           </div>
//         )}

//         {/* Section cards — root cause + fix open by default */}
//         <div className="space-y-3">
//           {sections.map((sec, i) => <SectionCard key={i} sec={sec} />)}
//         </div>

//         {/* Feedback */}
//         <FeedbackBar bugTitle={bugTitle} solution={solution} analysisId={requestId} />

//         {/* Similar tickets */}
//         <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
//           <button
//             onClick={() => setShowTickets(!showTickets)}
//             className="w-full flex items-center justify-between px-5 py-4 text-sm font-medium text-gray-300 hover:text-white hover:bg-gray-800/50 transition-colors"
//           >
//             <span>📋 Supporting evidence — {tickets.length} similar resolved tickets</span>
//             <span className="text-gray-600 text-xs">{showTickets ? "▲ hide" : "▼ show"}</span>
//           </button>

//           {showTickets && (
//             <div className="border-t border-gray-800">
//               <p className="px-5 py-3 text-xs text-gray-500 border-b border-gray-800">
//                 Click any ticket key to view the full resolution on Apache JIRA ↗
//               </p>

//               <div className="divide-y divide-gray-800/50">
//                 {(showAll ? tickets : tickets.slice(0, 8)).map((t, i) => (
//                   <div key={i} className="flex items-center justify-between px-5 py-2.5 hover:bg-gray-800/30 transition-colors">
//                     <div className="flex items-center gap-3 min-w-0">
//                       <a
//                         href={`https://issues.apache.org/jira/browse/${t.key}`}
//                         target="_blank"
//                         className="text-blue-400 hover:text-blue-300 font-mono text-xs hover:underline shrink-0"
//                       >
//                         [{t.key}]
//                       </a>
//                       <p className="text-sm text-gray-300 truncate">{t.summary}</p>
//                     </div>
//                     <div className="flex items-center gap-3 shrink-0 ml-4">
//                       {t["priority.name"] && t["priority.name"] !== "Unknown" && (
//                         <PriorityBadge priority={t["priority.name"]} />
//                       )}
//                       <SimilarityBar value={t.similarity} />
//                     </div>
//                   </div>
//                 ))}
//               </div>

//               {tickets.length > 8 && (
//                 <button
//                   onClick={() => setShowAll(!showAll)}
//                   className="w-full py-2.5 text-xs text-gray-500 hover:text-gray-400 border-t border-gray-800 transition-colors"
//                 >
//                   {showAll ? "Show fewer" : `Show all ${tickets.length} tickets`}
//                 </button>
//               )}
//             </div>
//           )}
//         </div>

//         {/* Follow-up chat */}
//         <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
//           <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-4">💬 Ask a follow-up</p>
//           {messages.length > 0 && (
//             <div className="space-y-3 mb-4">
//               {messages.map((m, i) => (
//                 <div key={i} className={`rounded-lg px-4 py-3 text-sm ${
//                   m.role === "user"
//                     ? "bg-blue-900/30 border border-blue-800/50 ml-8"
//                     : "bg-gray-800 border border-gray-700/50 mr-8"
//                 }`}>
//                   <span className="text-xs text-gray-500 block mb-1">{m.role === "user" ? "You" : "BugAnalyzer"}</span>
//                   {m.role === "assistant" ? <MD>{m.content}</MD> : <p className="text-gray-200">{m.content}</p>}
//                 </div>
//                             ))}
//                             {chatLoading && (
//                               <div className="rounded-lg px-4 py-3 text-sm bg-gray-800 border border-gray-700/50 mr-8">
//                                 <span className="text-xs text-gray-500 block mb-1">BugAnalyzer</span>
//                                 <div className="flex items-center gap-2 text-gray-400">
//                                   <span>Thinking</span>
//                                   <div className="flex gap-1">
//                                     {[0, 1, 2].map(i => (
//                                       <div key={i} className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce"
//                                         style={{ animationDelay: `${i * 0.15}s` }} />
//                                     ))}
//                                   </div>
//                                 </div>
//                               </div>
//                             )}
//                             <div ref={chatEndRef} />
//                           </div>
//                         )}
//               {/* ))}
//             </div>
//           )} */}
//           <div className="flex gap-2">
//             <input
//               disabled={chatLoading}
//               className="flex-1 bg-gray-950 border border-gray-700 rounded-lg px-3 py-2.5 text-white placeholder-gray-600 focus:outline-none focus:border-blue-500 text-sm transition-colors"
//               placeholder="e.g. How do I apply this fix on Windows?"
//               value={followUp}
//               onChange={e => setFollowUp(e.target.value)}
//               onKeyDown={e => e.key === "Enter" && !chatLoading && handleFollowUp()}
//             />
//             <button onClick={handleFollowUp} disabled={chatLoading}
//               className="bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-white px-4 rounded-lg text-sm font-medium transition-colors">
//               {chatLoading ? "..." : "Ask"}
//             </button>
//           </div>
//         </div>

//       </div>
//     </main>
//   )
// }

//////////////////////////////// VERSION 3 //////////////////////////////////

"use client"
import { API_URL } from "@/lib/api"
import { useEffect, useRef, useState } from "react"
import { useRouter } from "next/navigation"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import React from "react"

interface Issue {
  key: string
  summary: string
  "priority.name": string
  "resolution.name": string
  comments_text: string
  similarity: number
}

interface Classification {
  category: string
  component: string
  root_cause_family: string
  enriched_query: string
}

interface SeverityAssessment {
  severity: string
  sla_risk: boolean
  production_impact: boolean
  escalate_immediately: boolean
  reasoning: string
}

interface Section {
  key         : string
  title       : string
  icon        : string
  color       : string
  defaultOpen : boolean
  content     : string
}

type StageStatus = "pending" | "running" | "done"
interface StageState {
  status : StageStatus
  secs  ?: number
  detail?: string
}

// ── Priority / Severity badges ────────────────────────────────────────────────
const PRIORITY_COLORS: Record<string, string> = {
  Blocker : "bg-red-900/40 text-red-400 border-red-800",
  Critical: "bg-orange-900/40 text-orange-400 border-orange-800",
  Major   : "bg-yellow-900/40 text-yellow-400 border-yellow-800",
  Minor   : "bg-blue-900/40 text-blue-400 border-blue-800",
  Trivial : "bg-gray-800 text-gray-400 border-gray-700",
}

const SEVERITY_COLORS: Record<string, string> = {
  Critical: "bg-red-900/40 text-red-400 border-red-800",
  High    : "bg-orange-900/40 text-orange-400 border-orange-800",
  Medium  : "bg-yellow-900/40 text-yellow-400 border-yellow-800",
  Low     : "bg-blue-900/40 text-blue-400 border-blue-800",
}

function PriorityBadge({ priority }: { priority: string }) {
  const cls = PRIORITY_COLORS[priority] ?? "bg-gray-800 text-gray-400 border-gray-700"
  return <span className={`text-xs font-medium px-2 py-0.5 rounded border ${cls}`}>{priority}</span>
}

function SeverityBadge({ severity }: { severity: string }) {
  const cls = SEVERITY_COLORS[severity] ?? "bg-gray-800 text-gray-400 border-gray-700"
  return <span className={`text-xs font-medium px-2 py-0.5 rounded border ${cls}`}>{severity} severity</span>
}

function CategoryBadge({ category, component }: { category: string; component: string }) {
  return (
    <span className="text-xs font-medium px-2 py-0.5 rounded border bg-purple-900/40 text-purple-400 border-purple-800">
      {category} · {component}
    </span>
  )
}

// ── Markdown renderer ─────────────────────────────────────────────────────────
function MD({ children }: { children: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        h1: ({ children }) => <h1 className="text-base font-bold text-white mt-4 mb-2">{children}</h1>,
        h2: ({ children }) => <h2 className="text-sm font-bold text-white mt-3 mb-1.5">{children}</h2>,
        h3: ({ children }) => <h3 className="text-sm font-semibold text-gray-200 mt-3 mb-1">{children}</h3>,
        p: ({ children }) => {
          const renderWithLinks = (child: React.ReactNode): React.ReactNode => {
            if (typeof child !== "string") return child
            const parts = child.split(/(\b[A-Z][A-Z0-9]+-\d+\b)/g)
            return parts.map((part, i) => {
              if (/^[A-Z][A-Z0-9]+-\d+$/.test(part)) {
                return (
                  <a key={i} href={`https://issues.apache.org/jira/browse/${part}`}
                    target="_blank" className="text-blue-400 hover:underline font-mono text-xs">
                    [{part}]
                  </a>
                )
              }
              return part
            })
          }
          return (
            <p className="text-sm text-gray-300 leading-relaxed mb-2">
              {React.Children.map(children, renderWithLinks)}
            </p>
          )
        },
        ul: ({ children }) => <ul className="list-disc list-inside space-y-1 mb-2 text-sm text-gray-300">{children}</ul>,
        ol: ({ children }) => <ol className="list-decimal list-inside space-y-1 mb-2 text-sm text-gray-300">{children}</ol>,
        li: ({ children }) => <li className="text-gray-300 leading-relaxed">{children}</li>,
        strong: ({ children }) => <strong className="text-white font-semibold">{children}</strong>,
        code: ({ children, className }) => {
          const isBlock = className?.includes("language-")
          return isBlock
            ? <code className="block bg-gray-950 border border-gray-700 rounded p-3 text-xs text-green-400 font-mono overflow-x-auto my-2 whitespace-pre">{children}</code>
            : <code className="bg-gray-800 text-green-400 font-mono text-xs px-1.5 py-0.5 rounded">{children}</code>
        },
        blockquote: ({ children }) => (
          <blockquote className="border-l-2 border-blue-500 pl-3 my-2 text-gray-400 italic text-sm">{children}</blockquote>
        ),
        table: ({ children }) => (
          <div className="overflow-x-auto my-3">
            <table className="text-xs w-full border-collapse">{children}</table>
          </div>
        ),
        th: ({ children }) => <th className="border border-gray-700 px-3 py-1.5 text-left text-gray-300 bg-gray-800 font-medium">{children}</th>,
        td: ({ children }) => <td className="border border-gray-700 px-3 py-1.5 text-gray-400">{children}</td>,
        hr: () => <hr className="border-gray-800 my-3" />,
        a:  ({ children, href }) => <a href={href} target="_blank" className="text-blue-400 hover:underline">{children}</a>,
      }}
    >
      {children}
    </ReactMarkdown>
  )
}

// ── Live pipeline progress (driven by real server events) ─────────────────────
const AGENT_STEPS = [
  { key: "classifier",     label: "Classifier",     model: "Gemini Flash"        },
  { key: "severity",       label: "Severity",       model: "Gemini Flash"        },
  { key: "retriever",      label: "Retriever",      model: "Weaviate + Cohere"   },
  { key: "draft_response", label: "Draft Response", model: "Claude Sonnet"       },
  { key: "escalation",     label: "Escalation",     model: "Rules + Slack + Jira" },
]

function initialStages(): Record<string, StageState> {
  return Object.fromEntries(AGENT_STEPS.map(s => [s.key, { status: "pending" as StageStatus }]))
}

// Claude ends its answer with "CONFIDENCE: 0.85" — hide that line while streaming
function stripConfidence(text: string): string {
  return text.split("CONFIDENCE:")[0].trimEnd()
}

function LivePipeline({ stages, queued, streamText }: {
  stages    : Record<string, StageState>
  queued    : boolean
  streamText: string
}) {
  const [elapsed, setElapsed] = useState(0)

  useEffect(() => {
    const start = Date.now()
    const timer = setInterval(() => setElapsed(Math.floor((Date.now() - start) / 1000)), 1000)
    return () => clearInterval(timer)
  }, [])

  const anyStarted = Object.values(stages).some(s => s.status !== "pending")

  return (
    <main className="min-h-screen bg-gray-950 text-white">
      <div className="max-w-3xl mx-auto px-6 py-12 space-y-8">

        <div className="text-center">
          <p className="text-lg font-medium text-gray-200 mb-1">
            {queued && !anyStarted ? "Waiting for a free worker…" : "Running 5-agent analysis"}
          </p>
          <p className="text-sm text-gray-500">{elapsed}s elapsed · each step updates live as it finishes</p>
        </div>

        <div className="max-w-sm mx-auto space-y-3">
          {AGENT_STEPS.map(step => {
            const s         = stages[step.key] ?? { status: "pending" }
            const isDone    = s.status === "done"
            const isRunning = s.status === "running"
            return (
              <div key={step.key} className={`flex items-center gap-3 px-4 py-3 rounded-lg border transition-all duration-500 ${
                isDone
                  ? "bg-green-900/20 border-green-800/50"
                  : isRunning
                    ? "bg-blue-900/20 border-blue-800/50"
                    : "bg-gray-900 border-gray-800"
              }`}>
                <div className={`w-5 h-5 rounded-full flex items-center justify-center shrink-0 ${
                  isDone ? "bg-green-500" : isRunning ? "bg-blue-500 animate-pulse" : "bg-gray-700"
                }`}>
                  {isDone && <span className="text-white text-xs">✓</span>}
                </div>
                <div className="flex-1 min-w-0">
                  <p className={`text-sm font-medium ${isDone ? "text-green-300" : isRunning ? "text-blue-300" : "text-gray-500"}`}>
                    {step.label}
                  </p>
                  <p className="text-xs text-gray-600">{step.model}</p>
                </div>
                {isDone && (
                  <span className="text-xs text-gray-500 shrink-0">
                    {s.detail ?? (s.secs !== undefined ? `${s.secs}s` : "")}
                  </span>
                )}
                {isRunning && (
                  <div className="flex gap-1">
                    {[0, 1, 2].map(i => (
                      <div key={i} className="w-1 h-1 bg-blue-400 rounded-full animate-bounce"
                        style={{ animationDelay: `${i * 0.15}s` }} />
                    ))}
                  </div>
                )}
              </div>
            )
          })}
        </div>

        {streamText && (
          <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
            <div className="px-5 py-3 border-b border-gray-800 flex items-center gap-2">
              <span>✍️</span>
              <span className="text-sm font-semibold text-gray-200">Writing analysis</span>
              <span className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-pulse ml-1" />
            </div>
            <div className="px-5 py-4">
              <MD>{stripConfidence(streamText)}</MD>
            </div>
          </div>
        )}

      </div>
    </main>
  )
}

// ── Parse Claude response into 4 sections ─────────────────────────────────────
const SECTION_PATTERNS = [
  { key: "Root Cause",      icon: "🔎", color: "border-red-800/50",    title: "Root Cause Analysis",  defaultOpen: true  },
  { key: "Recommended Fix", icon: "🔧", color: "border-green-800/50",  title: "Recommended Fix",      defaultOpen: true  },
  { key: "Additional",      icon: "💡", color: "border-yellow-800/50", title: "Additional Checks",    defaultOpen: false },
  { key: "Priority",        icon: "📊", color: "border-blue-800/50",   title: "Priority Assessment",  defaultOpen: false },
]

function parseSections(text: string): Section[] {
  const sections: Section[] = []
  const lines    = text.split("\n")
  let current    = ""
  let currentIdx = -1

  for (const line of lines) {
    const matchIdx = SECTION_PATTERNS.findIndex(p =>
      line.toLowerCase().includes(p.key.toLowerCase()) &&
      (line.startsWith("#") || line.startsWith("**") || /^\d\./.test(line.trim()))
    )
    if (matchIdx !== -1) {
      if (currentIdx !== -1 && current.trim()) {
        sections.push({ ...SECTION_PATTERNS[currentIdx], content: current.trim() })
      }
      current = ""; currentIdx = matchIdx
    } else {
      current += line + "\n"
    }
  }
  if (currentIdx !== -1 && current.trim()) {
    sections.push({ ...SECTION_PATTERNS[currentIdx], content: current.trim() })
  }

  const seen    = new Set<string>()
  const deduped = sections.filter(sec => {
    if (seen.has(sec.key)) return false
    seen.add(sec.key)
    return true
  })

  if (deduped.length === 0) {
    return [{
      key        : "analysis",
      title      : "Analysis",
      icon       : "🤖",
      color      : "border-gray-700",
      content    : text,
      defaultOpen: true,
    }]
  }
  return deduped
}

// ── Collapsible section card ──────────────────────────────────────────────────
function SectionCard({ sec }: { sec: Section }) {
  const [open, setOpen] = useState(sec.defaultOpen)
  return (
    <div className={`bg-gray-900 border ${sec.color} rounded-xl overflow-hidden transition-all duration-200`}>
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-5 py-3 border-b border-gray-800 hover:bg-gray-800/30 transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className="text-base">{sec.icon}</span>
          <span className="text-sm font-semibold text-gray-200">{sec.title}</span>
        </div>
        <span className="text-gray-600 text-xs">{open ? "▲" : "▼"}</span>
      </button>
      {open && (
        <div className="px-5 py-4">
          <MD>{sec.content}</MD>
        </div>
      )}
    </div>
  )
}

// ── Copy button ───────────────────────────────────────────────────────────────
function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  return (
    <button onClick={() => { navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 2000) }}
      className="text-xs text-gray-500 hover:text-gray-300 px-2 py-1 rounded hover:bg-gray-800 transition-colors">
      {copied ? "✓ Copied" : "Copy"}
    </button>
  )
}

// ── Similarity bar ────────────────────────────────────────────────────────────
function SimilarityBar({ value }: { value: number }) {
  const pct   = Math.round(value * 100)
  const color = pct >= 85 ? "bg-green-500" : pct >= 70 ? "bg-blue-500" : "bg-gray-500"
  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-1 bg-gray-800 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-gray-500">{pct}%</span>
    </div>
  )
}

// ── Feedback buttons ──────────────────────────────────────────────────────────
function FeedbackBar({ bugTitle, solution, analysisId }: { bugTitle: string; solution: string; analysisId: string }) {
  const [sent, setSent] = useState<"up" | "down" | null>(null)

  const sendFeedback = async (vote: "up" | "down") => {
    setSent(vote)
    try {
      await fetch(`${API_URL}/feedback`, {
        method : "POST",
        headers: { "Content-Type": "application/json" },
        body   : JSON.stringify({
          bug_title       : bugTitle,
          vote,
          solution_snippet: solution.slice(0, 200),
          analysis_id     : analysisId,
        })
      })
    } catch {}
  }

  return (
    <div className="flex items-center gap-3">
      <span className="text-xs text-gray-500">Was this helpful?</span>
      <button onClick={() => sendFeedback("up")}
        className={`text-sm px-3 py-1 rounded border transition-colors ${sent === "up" ? "bg-green-900/40 border-green-700 text-green-400" : "border-gray-700 text-gray-500 hover:text-gray-300"}`}>
        👍
      </button>
      <button onClick={() => sendFeedback("down")}
        className={`text-sm px-3 py-1 rounded border transition-colors ${sent === "down" ? "bg-red-900/40 border-red-700 text-red-400" : "border-gray-700 text-gray-500 hover:text-gray-300"}`}>
        👎
      </button>
      {sent && <span className="text-xs text-gray-500">Thanks for the feedback</span>}
    </div>
  )
}

// ── Review status for escalated analyses ──────────────────────────────────────
function ReviewStatusPill({ status }: { status: string | null }) {
  if (status === "approved") return (
    <span className="shrink-0 text-xs bg-green-900/40 border border-green-700 text-green-400 px-3 py-1.5 rounded-lg">
      ✓ Approved by reviewer
    </span>
  )
  if (status === "rejected") return (
    <span className="shrink-0 text-xs bg-red-900/40 border border-red-700 text-red-400 px-3 py-1.5 rounded-lg">
      ✗ Reviewer: needs rework
    </span>
  )
  return (
    <span className="shrink-0 text-xs bg-orange-900/40 border border-orange-700 text-orange-400 px-3 py-1.5 rounded-lg animate-pulse">
      ⏳ Awaiting human review
    </span>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function Results() {
  // Final result
  const [solution, setSolution]             = useState("")
  const [sections, setSections]             = useState<Section[]>([])
  const [tickets, setTickets]               = useState<Issue[]>([])
  const [classification, setClassification] = useState<Classification | null>(null)
  const [severity, setSeverity]             = useState<SeverityAssessment | null>(null)
  const [escalated, setEscalated]           = useState(false)
  const [escalationReasons, setEscReasons]  = useState<string[]>([])
  const [confidence, setConfidence]         = useState(0)
  const [responseTime, setResponseTime]     = useState<number | null>(null)
  const [requestId, setRequestId]           = useState("")
  const [reviewStatus, setReviewStatus]     = useState<string | null>(null)

  // Live progress
  const [jobId, setJobId]                   = useState("")
  const [stages, setStages]                 = useState<Record<string, StageState>>(initialStages)
  const [queued, setQueued]                 = useState(false)
  const [streamText, setStreamText]         = useState("")

  // Page state
  const [loading, setLoading]               = useState(true)
  const [error, setError]                   = useState("")
  const [messages, setMessages]             = useState<{ role: string; content: string }[]>([])
  const [followUp, setFollowUp]             = useState("")
  const [chatLoading, setChatLoading]       = useState(false)
  const [showTickets, setShowTickets]       = useState(false)
  const [showAll, setShowAll]               = useState(false)

  const router     = useRouter()
  const hasStarted = useRef(false)   // guards against React Strict Mode's double effect run
  const chatEndRef = useRef<HTMLDivElement>(null)

  // ── 1. Start a new job — or resume the existing one after a page refresh ──
  useEffect(() => {
    if (hasStarted.current) return
    hasStarted.current = true

    // const issue    = sessionStorage.getItem("issue_description")
    const priority = sessionStorage.getItem("priority")
    const bugTitle = sessionStorage.getItem("bug_title")
    const stack    = sessionStorage.getItem("stack_trace") ?? ""

    // if (!issue) { router.push("/"); return }

    const urlParams = new URLSearchParams(window.location.search)
    const jobFromUrl = urlParams.get("job")
    if (jobFromUrl) {
      setJobId(jobFromUrl)
      sessionStorage.setItem("job_id", jobFromUrl)
      return
    }

    const issue = sessionStorage.getItem("issue_description")
    if (!issue) { router.push("/"); return }
    
    const existing = sessionStorage.getItem("job_id")
    if (existing) { setJobId(existing); return }   // refresh → reconnect, no new analysis

    const startJob = async () => {
      try {
        const res = await fetch(`${API_URL}/analyze`, {
          method : "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",   
          body   : JSON.stringify({
            issue_description: issue,
            bug_title        : bugTitle ?? "",
            stack_trace      : stack,
            user_priority    : priority ?? "Major",
          })
        })
        const data = await res.json().catch(() => ({}))
        if (!res.ok) {
          if (res.status === 429) {
            const detail = typeof data.detail === "string" ? data.detail : ""
            // slowapi returns raw "5 per 1 minute" — turn that into readable text
            setError(/^\d+ per \d+/.test(detail)
              ? "Too many requests — please wait a minute and try again."
              : (detail || "Server is busy — please wait a moment and retry."))
          } else {
            setError(typeof data.detail === "string"
              ? data.detail
              : "Could not reach the backend. Make sure the API is running on port 8000.")
          }
          setLoading(false)
          return
        }
        sessionStorage.setItem("job_id", data.job_id)
        window.history.replaceState({}, "", `/results?job=${data.job_id}`)
        setJobId(data.job_id)
      } catch {
        setError("Could not reach the backend. Make sure the API is running on port 8000.")
        setLoading(false)
      }
    }
    startJob()
  }, [])

  useEffect(() => {
    if (!loading) return
    const handler = (e: BeforeUnloadEvent) => { e.preventDefault(); e.returnValue = "" }
    window.addEventListener("beforeunload", handler)
    return () => window.removeEventListener("beforeunload", handler)
  }, [loading])

  // ── 2. Stream live progress + result (Server-Sent Events) ─────────────────
  useEffect(() => {
    if (!jobId) return

    // The server replays every event from the start, so rebuild progress from scratch
    setStages(initialStages())
    setQueued(false)
    setStreamText("")

    let finished = false
    const es = new EventSource(`${API_URL}/jobs/${jobId}/stream`, { withCredentials: true })

    es.addEventListener("queued", () => setQueued(true))

    es.addEventListener("stage", (e) => {
      const d = JSON.parse((e as MessageEvent).data)
      setQueued(false)
      setStages(prev => ({ ...prev, [d.agent]: { status: d.status, secs: d.secs, detail: d.detail } }))
    })

    es.addEventListener("draft_reset", () => setStreamText(""))

    es.addEventListener("token", (e) => {
      const d = JSON.parse((e as MessageEvent).data)
      setStreamText(prev => prev + d.text)
    })

    es.addEventListener("result", (e) => {
      finished = true
      es.close()
      const data  = JSON.parse((e as MessageEvent).data)
      const reply = data.final_response ?? ""
      setSolution(reply)
      setSections(parseSections(reply))
      setTickets(data.retrieved_issues ?? [])
      setClassification(data.classification ?? null)
      setSeverity(data.severity_assessment ?? null)
      setEscalated(data.escalated ?? false)
      setEscReasons(data.escalation_reasons ?? [])
      setConfidence(data.confidence_score ?? 0)
      setResponseTime(data.response_time_secs ?? null)
      setRequestId(data.request_id ?? "")
      if (data.escalated) setReviewStatus("pending")
      setLoading(false)
    })

    // "error" fires for BOTH our server's error event (has data)
    // and for connection problems (no data)
    es.addEventListener("error", (e) => {
      const payload = (e as MessageEvent).data
      if (payload) {
        finished = true
        es.close()
        let detail = "Analysis failed. Please go back and try again."
        try { detail = JSON.parse(payload).detail ?? detail } catch {}
        sessionStorage.removeItem("job_id")
        setError(detail)
        setLoading(false)
        return
      }
      // Connection dropped: while CONNECTING, the browser retries automatically
      // (resuming via Last-Event-ID). CLOSED means the server refused, e.g. job expired.
      if (!finished && es.readyState === EventSource.CLOSED) {
        sessionStorage.removeItem("job_id")
        setError("This analysis is no longer available — it may have expired. Please go back and run it again.")
        setLoading(false)
      }
    })

    return () => es.close()
  }, [jobId])

  // ── 3. Poll review status while an escalated analysis is pending ──────────
  useEffect(() => {
    if (!requestId || reviewStatus !== "pending") return
    const timer = setInterval(async () => {
      try {
        // const res = await fetch(`${API_URL}/analysis/${requestId}/status`)
        const res = await fetch(`${API_URL}/analyses/${requestId}`)
        if (!res.ok) return
        const data = await res.json()
        if (data.review_status && data.review_status !== "pending") {
          setReviewStatus(data.review_status)
        }
      } catch {}
    }, 15000)
    return () => clearInterval(timer)
  }, [requestId, reviewStatus])

  // ── 4. Keep the newest chat message (or "Thinking…") in view ──────────────
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" })
  }, [messages, chatLoading])

  // ── Follow-up chat ────────────────────────────────────────────────────────
  const handleFollowUp = async () => {
    if (!followUp.trim() || chatLoading) return
    setChatLoading(true)
    const userMsg     = { role: "user", content: followUp }
    const newMessages = [...messages, userMsg]
    setMessages(newMessages)
    setFollowUp("")

    try {
      // const res  = await fetch(`${API_URL}/chat`, {
      const res = await fetch(`${API_URL}/chat/${requestId}`, {
        method : "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include", 
        body   : JSON.stringify({ message: userMsg.content }),
      })
      const data  = await res.json().catch(() => ({}))
      const reply = res.ok
        ? (data.reply ?? "No reply received.")
        : (typeof data.detail === "string" ? data.detail : "Sorry, the follow-up failed. Please try again.")
      setMessages([...newMessages, { role: "assistant", content: reply }])
    } catch {
      setMessages([...newMessages, { role: "assistant", content: "Sorry, the follow-up failed. Please try again." }])
    } finally {
      setChatLoading(false)
    }
  }

  if (error) return (
    <div className="min-h-screen bg-gray-950 text-white flex flex-col items-center justify-center gap-4 px-6">
      <p className="text-red-400 text-center max-w-md text-sm">{error}</p>
      <button onClick={() => router.push("/")} className="text-blue-400 hover:underline text-sm">← Go back</button>
    </div>
  )

  if (loading) return <LivePipeline stages={stages} queued={queued} streamText={streamText} />

  const bugTitle = sessionStorage.getItem("bug_title") ?? ""
  const priority = sessionStorage.getItem("priority") ?? "—"

  return (
    <main className="min-h-screen bg-gray-950 text-white">

      <div className="max-w-3xl mx-auto px-6 py-10 space-y-6">

      <button onClick={() => router.push("/")} className="text-xs text-gray-500 hover:text-gray-300 transition-colors">
        ← New search
      </button>

        {/* Bug header */}
        <div className="flex items-start justify-between gap-4">
          <div>
            {bugTitle && <h1 className="text-xl font-semibold mb-1.5">{bugTitle}</h1>}
            <div className="flex flex-wrap items-center gap-2">
              <PriorityBadge priority={priority} />
              {severity && <SeverityBadge severity={severity.severity} />}
              {classification && <CategoryBadge category={classification.category} component={classification.component} />}
              <span className="text-sm text-gray-500">{tickets.length} similar tickets found</span>
              {confidence > 0 && (
                <span className="text-xs text-gray-600">· model confidence {(confidence * 100).toFixed(0)}%</span>
              )}
              {responseTime !== null && (
                <span className="text-xs text-gray-600">· analysed in {Math.round(responseTime)}s</span>
              )}
            </div>
          </div>
          <CopyButton text={solution} />
        </div>

        {/* Escalation banner */}
        {escalated && (
          <div className="bg-orange-900/20 border border-orange-800 rounded-xl px-5 py-4">
            <div className="flex items-center justify-between gap-4">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <span>⚠️</span>
                  <span className="text-sm font-semibold text-orange-400">Flagged for Human Review</span>
                </div>
                <p className="text-xs text-orange-300/70">
                  Reasons: {escalationReasons.map(r => r.replace(/_/g, " ")).join(", ")}
                </p>
                {severity?.reasoning && (
                  <p className="text-xs text-orange-300/60 mt-0.5">{severity.reasoning}</p>
                )}
              </div>
              <ReviewStatusPill status={reviewStatus} />
            </div>
          </div>
        )}

        {/* Section cards — root cause + fix open by default */}
        <div className="space-y-3">
          {sections.map((sec, i) => <SectionCard key={i} sec={sec} />)}
        </div>

        {/* Feedback */}
        <FeedbackBar bugTitle={bugTitle} solution={solution} analysisId={requestId} />

        {/* Similar tickets */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
          <button
            onClick={() => setShowTickets(!showTickets)}
            className="w-full flex items-center justify-between px-5 py-4 text-sm font-medium text-gray-300 hover:text-white hover:bg-gray-800/50 transition-colors"
          >
            <span>📋 Supporting evidence — {tickets.length} similar resolved tickets</span>
            <span className="text-gray-600 text-xs">{showTickets ? "▲ hide" : "▼ show"}</span>
          </button>

          {showTickets && (
            <div className="border-t border-gray-800">
              <p className="px-5 py-3 text-xs text-gray-500 border-b border-gray-800">
                Click any ticket key to view the full resolution on Apache JIRA ↗
              </p>

              <div className="divide-y divide-gray-800/50">
                {(showAll ? tickets : tickets.slice(0, 8)).map((t, i) => (
                  <div key={i} className="flex items-center justify-between px-5 py-2.5 hover:bg-gray-800/30 transition-colors">
                    <div className="flex items-center gap-3 min-w-0">
                      <a
                        href={`https://issues.apache.org/jira/browse/${t.key}`}
                        target="_blank"
                        className="text-blue-400 hover:text-blue-300 font-mono text-xs hover:underline shrink-0"
                      >
                        [{t.key}]
                      </a>
                      <p className="text-sm text-gray-300 truncate">{t.summary}</p>
                    </div>
                    <div className="flex items-center gap-3 shrink-0 ml-4">
                      {t["priority.name"] && t["priority.name"] !== "Unknown" && (
                        <PriorityBadge priority={t["priority.name"]} />
                      )}
                      <SimilarityBar value={t.similarity} />
                    </div>
                  </div>
                ))}
              </div>

              {tickets.length > 8 && (
                <button
                  onClick={() => setShowAll(!showAll)}
                  className="w-full py-2.5 text-xs text-gray-500 hover:text-gray-400 border-t border-gray-800 transition-colors"
                >
                  {showAll ? "Show fewer" : `Show all ${tickets.length} tickets`}
                </button>
              )}
            </div>
          )}
        </div>

        {/* Follow-up chat */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-4">💬 Ask a follow-up</p>
          {messages.length > 0 && (
            <div className="space-y-3 mb-4">
              {messages.map((m, i) => (
                <div key={i} className={`rounded-lg px-4 py-3 text-sm ${
                  m.role === "user"
                    ? "bg-blue-900/30 border border-blue-800/50 ml-8"
                    : "bg-gray-800 border border-gray-700/50 mr-8"
                }`}>
                  <span className="text-xs text-gray-500 block mb-1">{m.role === "user" ? "You" : "BugAnalyzer"}</span>
                  {m.role === "assistant" ? <MD>{m.content}</MD> : <p className="text-gray-200">{m.content}</p>}
                </div>
              ))}
              {chatLoading && (
                <div className="rounded-lg px-4 py-3 text-sm bg-gray-800 border border-gray-700/50 mr-8">
                  <span className="text-xs text-gray-500 block mb-1">BugAnalyzer</span>
                  <div className="flex items-center gap-2 text-gray-400">
                    <span>Thinking</span>
                    <div className="flex gap-1">
                      {[0, 1, 2].map(i => (
                        <div key={i} className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce"
                          style={{ animationDelay: `${i * 0.15}s` }} />
                      ))}
                    </div>
                  </div>
                </div>
              )}
              <div ref={chatEndRef} />
            </div>
          )}
          <div className="flex gap-2">
            <input
              disabled={chatLoading}
              className="flex-1 bg-gray-950 border border-gray-700 rounded-lg px-3 py-2.5 text-white placeholder-gray-600 focus:outline-none focus:border-blue-500 text-sm transition-colors disabled:opacity-50"
              placeholder={chatLoading ? "Waiting for the answer…" : "e.g. How do I apply this fix on Windows?"}
              value={followUp}
              onChange={e => setFollowUp(e.target.value)}
              onKeyDown={e => e.key === "Enter" && !chatLoading && handleFollowUp()}
            />
            <button onClick={handleFollowUp} disabled={chatLoading}
              className="bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-white px-4 rounded-lg text-sm font-medium transition-colors">
              {chatLoading ? "..." : "Ask"}
            </button>
          </div>
        </div>

      </div>
    </main>
  )
}