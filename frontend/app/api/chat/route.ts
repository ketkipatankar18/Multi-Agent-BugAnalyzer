import { NextRequest, NextResponse } from "next/server"
import Anthropic from "@anthropic-ai/sdk"

const anthropic = new Anthropic({
  apiKey: process.env.ANTHROPIC_API_KEY
})

export async function POST(req: NextRequest) {
  const { messages } = await req.json()

  const response = await anthropic.messages.create({
    model: "claude-sonnet-4-6",
    max_tokens: 2048,
    system: "You are an expert QA engineer and software engineer helping resolve JIRA bugs.",
    messages: messages
  })

  return NextResponse.json({
    reply: response.content[0].type === "text" ? response.content[0].text : ""
  })
}