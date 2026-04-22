# Import libraries
import streamlit as st
import requests
from langchain_community.chat_models import ChatOpenAI
from langchain.chains import ConversationChain
from langchain.memory import ConversationBufferMemory

# Clear previous chat history on fresh load
# if "chat_history" in st.session_state:
#     del st.session_state["chat_history"]
if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []

st.title("🔍 BugFinder: Finding Similar Issues & Solutions")

# ── Guard — ensure inputs exist ────────────────────────────────────────────────
required_keys = ["issue_description", "priority"]
for k in required_keys:
    if k not in st.session_state:
        st.warning("Incomplete input. Please go back to the home page.")
        st.stop()

# ── Retrieve inputs ────────────────────────────────────────────────────────────
issue_description = st.session_state["issue_description"]
priority          = st.session_state["priority"]

# ── LLM setup ─────────────────────────────────────────────────────────────────
llm = ChatOpenAI(
    openai_api_key=st.secrets["OPEN_AI_API_KEY"],
    model="gpt-4o"
)

if "memory" not in st.session_state:
    st.session_state.memory = ConversationBufferMemory(return_messages=True)

conversation = ConversationChain(
    llm=llm,
    memory=st.session_state.memory
)

# ── RAG retrieval + solution generation ───────────────────────────────────────
with st.spinner("Searching through past JIRA issues ..."):

    # Build query from user input — same pattern as SnapChef
    query = f"{issue_description} priority: {priority}"

    # Call Flask API to get top 10 similar issues from ChromaDB
    response = requests.get(
        "http://127.0.0.1:8000/search",
        params={"query": query, "n": 15}
    )
    if response.ok:
        api_response = response.json()
    else:
        st.error(f"API error {response.status_code}: {response.text}")
        st.stop()
    
    if not api_response:
        st.warning("""
            No sufficiently similar issues found in the database. 
            This appears to be a unique issue with no close historical matches.
            Consider opening a new JIRA ticket with detailed reproduction steps.
        """)
        st.stop()

    # Format retrieved issues into a readable summary for the LLM
    issues_summary = ""
    for i, issue in enumerate(api_response, 1):
        key        = issue.get("key", "N/A")
        summary    = issue.get("summary", "No summary")
        priority_  = issue.get("priority.name", "N/A")
        resolution = issue.get("resolution.name", "N/A")
        # discussion = issue.get("comments_text", "No discussion available.")
        discussion = str(issue.get("comments_text") or "")

        issues_summary += (
            f"{i}. [{key}] {summary}\n"
            f"   Priority   : {priority_}\n"
            f"   Resolution : {resolution}\n"
            f"   Discussion : {discussion[:300]}...\n\n"
        )

    # if len(api_response) < 5:
    #     confidence_note = "Note: Only a few loosely similar issues were found. The suggestions below may not directly apply."
    # else:
    #     confidence_note = ""
        
    # Build LLM prompt
    llm_prompt = f"""
You are an expert QA tester and software engineer helping resolve JIRA issues.

The user is facing the following issue:
\"{issue_description}\"
Priority: {priority}

Here are the top 15 similar issues found from past JIRA tickets:
{issues_summary}

Based on these similar past issues, provide:
1. A brief analysis of what the root cause likely is
2. The most relevant solution or fix based on how similar issues were resolved
3. Any additional suggestions or things to check

Be concise and practical. Reference specific ticket keys where relevant.
"""

    # Generate and cache solution
    if "solution_generated" not in st.session_state:
        llm_response = conversation.invoke({"input": llm_prompt})
        st.session_state.solution_generated = llm_response["response"]

st.markdown(st.session_state.solution_generated)

# ── Show retrieved similar issues in an expander ───────────────────────────────
with st.expander("View Similar Past Issues Retrieved"):
    for i, issue in enumerate(api_response, 1):
        st.markdown(f"**{i}. [{issue.get('key')}] {issue.get('summary')}**")
        # st.markdown(f"- Priority: `{issue.get('priority.name', 'N/A')}`")
        # st.markdown(f"- Resolution: `{issue.get('resolution.name', 'N/A')}`")
        # comments = issue.get('comments_text', '')

        # if not comments or str(comments) == 'nan':
        #     comments = "No discussion available."
        # else:
        #     comments = str(comments)
        # preview = comments[:300].strip()
        # if len(comments) > 300:
        #     preview += "..."
        # st.markdown(f"**Discussion:** {comments}")
        # with st.expander("Show full discussion"):
        #     st.write(comments)
        # st.markdown(f"- Discussion: {comments[:300]}...")
        # st.markdown(f"- Discussion: {issue.get('comments_text', '')[:300]}...")
        st.divider()

# ── Follow-up Q&A ──────────────────────────────────────────────────────────────
if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []

# st.markdown("### Ask a Follow-up Question")
# user_followup = st.text_input(
#     "Need more details? Ask a follow-up question:",
#     placeholder="e.g. How do I apply this fix in a Windows environment?"
# )

# if st.button("Ask") and user_followup:
#     followup_response = conversation.invoke({"input": user_followup})
#     st.session_state["chat_history"].append(
#         (user_followup, followup_response["response"])
#     )

# # Display chat history
# for q, a in st.session_state["chat_history"]:
#     st.markdown(f"**You:** {q}")
#     st.markdown(f"**BugFinder:** {a}")

user_followup = st.chat_input("Ask a follow-up question...")

if user_followup:
    response = conversation.invoke({"input": user_followup})

    st.session_state["chat_history"].append(
        (user_followup, response["response"])
    )

for q, a in st.session_state["chat_history"]:
    with st.chat_message("user"):
        st.write(q)

    with st.chat_message("assistant"):
        st.write(a)