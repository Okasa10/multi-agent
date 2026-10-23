"""
AI Recruiter Assistant - Streamlit Application
A multi-agent workflow comparing job descriptions and resumes to produce:
1. Structured job requirements (Agent 1)
2. Evidence-backed resume analysis & clarification areas (Agent 2)
3. High-yield, structured 20-50 question interview questionnaire with evaluation rubrics (Agent 3)
"""

import os
import sys
import io
import csv
import textwrap
from pathlib import Path
from typing import List, Dict, Any
from dotenv import load_dotenv
import streamlit as st

# Ensure local modules can be imported
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from orchestrator import RecruiterOrchestrator
from llm_client import LLMClient

# Load environment variables if present
load_dotenv()

# Streamlit Page Configuration
st.set_page_config(
    page_title="AI Recruiter Assistant | Multi-Agent System",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling for Clean Academic Presentation
st.markdown("""
<style>
    .main-header {
        font-size: 2.1rem;
        font-weight: 700;
        color: #1E293B;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.02rem;
        color: #475569;
        margin-bottom: 1.2rem;
    }
    .agent-card {
        background-color: #F8FAFC;
        border-radius: 8px;
        padding: 1rem;
        border-left: 4px solid #3B82F6;
        margin-bottom: 0.8rem;
    }
    .badge-llm {
        background-color: #DCFCE7;
        color: #166534;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .badge-fallback {
        background-color: #FEF3C7;
        color: #92400E;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .safeguard-box {
        background-color: #EFF6FF;
        border: 1px solid #BFDBFE;
        border-radius: 6px;
        padding: 0.85rem;
        font-size: 0.85rem;
        color: #1E3A8A;
        margin-bottom: 1.2rem;
    }
    .question-card {
        background-color: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 1.1rem;
        margin-bottom: 1rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }
    .badge-foundation {
        background-color: #E0F2FE;
        color: #0369A1;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .badge-intermediate {
        background-color: #EDE9FE;
        color: #6D28D9;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .badge-advanced {
        background-color: #FEE2E2;
        color: #B91C1C;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .badge-category {
        background-color: #F1F5F9;
        color: #334155;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .follow-up-box {
        background-color: #FFFBEB;
        border-left: 3px solid #F59E0B;
        padding: 8px 12px;
        border-radius: 4px;
        margin-top: 8px;
        font-size: 0.88rem;
        color: #78350F;
    }
    .rubric-box {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 6px;
        padding: 8px 12px;
        margin-top: 8px;
        font-size: 0.85rem;
    }
</style>
""", unsafe_allow_html=True)


# Helper function to read sample data
def load_sample_file(filename: str) -> str:
    path = Path(__file__).parent / "sample_data" / filename
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def generate_markdown_export(questions: List[Dict[str, Any]], role: str, level: str) -> str:
    """Generates a cleanly formatted Markdown questionnaire for download."""
    lines = [
        f"# Technical Interview Questionnaire",
        f"**Target Role:** {role}  ",
        f"**Candidate Experience Tier:** {level}  ",
        f"**Total Questions Formulated:** {len(questions)}  ",
        "",
        "---",
        ""
    ]
    current_cat = None
    for q in questions:
        cat = q.get("category", "General")
        if cat != current_cat:
            current_cat = cat
            lines.append(f"\n## 📂 {current_cat}\n")

        diff = q.get("difficulty", "Intermediate")
        skill = q.get("skill_assessed", "Competency")
        lines.append(f"### Question #{q.get('id')}: {q.get('question')}")
        lines.append(f"- **Difficulty:** `{diff}` | **Skill Assessed:** `{skill}`")
        lines.append(f"- **Relevance / Grounding:** {q.get('relevance')}")
        lines.append(f"- **Expected Answer Key Points:**")
        for pt in q.get("expected_answer", []):
            lines.append(f"  - {pt}")
        if q.get("follow_up"):
            lines.append(f"- **Follow-up Probe:** *\"{q.get('follow_up')}\"*")
        rubric = q.get("evaluation_rubric", {})
        if isinstance(rubric, dict):
            lines.append(f"- **Evaluation Rubric:**")
            lines.append(f"  - ⚠️ **Weak Answer:** {rubric.get('weak', 'N/A')}")
            lines.append(f"  - ✅ **Strong Answer:** {rubric.get('strong', 'N/A')}")
        lines.append("")
    return "\n".join(lines)


def generate_csv_export(questions: List[Dict[str, Any]]) -> str:
    """Generates a CSV export of all interview questions."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID", "Category", "Difficulty", "Question", "Skill Assessed",
        "Relevance", "Expected Answer Key Points", "Follow-up Probe",
        "Weak Answer Rubric", "Strong Answer Rubric"
    ])
    for q in questions:
        rubric = q.get("evaluation_rubric", {})
        expected_ans_str = " | ".join(q.get("expected_answer", []))
        writer.writerow([
            q.get("id"),
            q.get("category"),
            q.get("difficulty"),
            q.get("question"),
            q.get("skill_assessed"),
            q.get("relevance"),
            expected_ans_str,
            q.get("follow_up"),
            rubric.get("weak", ""),
            rubric.get("strong", "")
        ])
    return output.getvalue()


def main():
    # Sidebar - Configuration, Metrics & Architecture
    with st.sidebar:
        st.title("🤖 Multi-Agent Setup")
        st.markdown("**Academic Submission:** OJT / AI Project")

        # Check LLM status
        client = LLMClient()
        active_provider = client.get_active_provider()

        if active_provider != "none":
            st.success(f"Active LLM: **{active_provider}**")
        else:
            st.info("Mode: **Deterministic Fallback**\n(Offline rule-based NLP & heuristic synthesis)")

        st.markdown("---")
        st.subheader("🎯 Questionnaire Depth")
        target_count = st.slider(
            "Target Number of Questions:",
            min_value=20,
            max_value=50,
            value=30,
            step=5,
            help="Select desired questionnaire depth (20-50 questions). Adaptively scales based on information detail."
        )

        st.markdown("---")
        st.subheader("System Architecture")
        st.markdown("""
        **Coordinated Workflow:**
        1. 📋 **Agent 1:** Job Description Analyzer
        2. 🔍 **Agent 2:** Resume Analyzer
        3. 💡 **Agent 3:** Interview Question Generator
        4. 🎛️ **Orchestrator:** Sequential Pipeline
        """)

        st.markdown("---")
        st.subheader("Sample Test Data")
        if st.button("Load Sample Inputs"):
            st.session_state["sample_jd"] = load_sample_file("job_description.txt")
            st.session_state["sample_resume"] = load_sample_file("resume.txt")
            st.rerun()

    # Main Header
    st.markdown("<div class='main-header'>AI Recruiter Assistant Using a Multi-Agent System</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='sub-header'>An academic multi-agent application that coordinates three specialized agents to parse job requirements, extract resume evidence, and formulate a targeted 20-50 question interview questionnaire.</div>",
        unsafe_allow_html=True
    )

    # Responsible-Use Safeguards Notice
    st.markdown("""
    <div class='safeguard-box'>
        <strong>🛡️ Responsible-Use & Ethical Safeguards:</strong>
        This system is purely advisory for human recruiters. It does not automatically accept, reject, or rank candidates. 
        It does not assess protected demographic characteristics. All inputs are held strictly in temporary session memory and are never persisted.
    </div>
    """, unsafe_allow_html=True)

    # Input Columns: Job Description and Resume
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("1. Job Description")
        jd_default = st.session_state.get("sample_jd", "")
        job_description_input = st.text_area(
            "Paste Job Description text here:",
            value=jd_default,
            height=250,
            placeholder="e.g. Job Title: Senior Backend AI Engineer\nResponsibilities...\nRequirements..."
        )

    with col2:
        st.subheader("2. Candidate Resume")
        resume_default = st.session_state.get("sample_resume", "")
        uploaded_file = st.file_uploader("Optional: Upload Resume (.txt)", type=["txt"])

        if uploaded_file is not None:
            resume_default = uploaded_file.read().decode("utf-8")

        resume_input = st.text_area(
            "Paste or view Candidate Resume text here:",
            value=resume_default,
            height=200,
            placeholder="e.g. Alex Morgan\nSkills: Python, FastAPI, Docker, PostgreSQL...\nExperience..."
        )

    # Analyze Button
    analyze_clicked = st.button("🚀 Analyze Resume & Formulate Questionnaire", type="primary", use_container_width=True)

    if analyze_clicked:
        if not job_description_input.strip():
            st.error("⚠️ Please enter a Job Description before proceeding.")
            return
        if not resume_input.strip():
            st.error("⚠️ Please enter or upload a Candidate Resume before proceeding.")
            return

        orchestrator = RecruiterOrchestrator()

        with st.spinner("Multi-Agent Workflow executing (Agent 1 ➔ Agent 2 ➔ Agent 3)..."):
            result = orchestrator.run_workflow(
                job_description_input,
                resume_input,
                target_question_count=target_count
            )

        if not result.get("success", False):
            st.error(f"❌ Workflow Error: {result.get('error', 'Unknown failure')}")
            return

        # Success: Display Multi-Agent Proof & Results
        st.success(f"✅ Multi-Agent Workflow Completed in {result['total_duration_seconds']}s")

        # Multi-Agent Execution Proof / Trace Expandable
        with st.expander("🔍 View Multi-Agent Execution Trace & Proof of Agent Separation", expanded=True):
            trace_cols = st.columns(3)
            for i, step in enumerate(result["trace"]):
                with trace_cols[i]:
                    mode_badge = "badge-llm" if step["mode"] == "llm_powered" else "badge-fallback"
                    mode_label = "LLM Powered" if step["mode"] == "llm_powered" else "Deterministic"
                    st.markdown(
                        f"<div class='agent-card'>"
                        f"<strong>Step {step['step']}: {step['agent']}</strong><br/>"
                        f"<span class='{mode_badge}'>{mode_label}</span><br/>"
                        f"<small>Time: {step['duration_seconds']}s | Status: {step['status']}</small><br/>"
                        f"<p style='margin-top:6px; font-size:0.85rem;'>{step['summary']}</p>"
                        f"</div>",
                        unsafe_allow_html=True
                    )

        st.markdown("---")

        # Result Section 1: Extracted Job Requirements (Agent 1 Output)
        job_data = result["job_analysis"]
        st.subheader("📋 1. Extracted Job Requirements (Agent 1: Job Description Analyzer)")

        col_role, col_level = st.columns([2, 1])
        with col_role:
            st.write(f"**Identified Role:** {job_data.get('job_title', 'Not specified')}")
        with col_level:
            st.write(f"**Experience Level:** {job_data.get('experience_level', 'Not specified')}")

        st.write("**Extracted Key Skills:**")
        skills = job_data.get("key_skills", [])
        if skills:
            st.write(" • ".join([f"`{s}`" for s in skills]))
        else:
            st.write("None detected.")

        with st.expander("View Core Responsibilities", expanded=False):
            for resp in job_data.get("responsibilities", []):
                st.markdown(f"- {resp}")

        st.markdown("---")

        # Result Section 2: Resume Skills and Supporting Evidence (Agent 2 Output)
        resume_data = result["resume_analysis"]
        st.subheader("🔍 2. Resume Evidence & Clarification Areas (Agent 2: Resume Analyzer)")

        st.info(resume_data.get("summary", "Analysis completed."))

        col_ev1, col_ev2 = st.columns(2)

        with col_ev1:
            st.markdown("##### ✅ Confirmed Skills with Evidence Snippets")
            evidence_items = resume_data.get("evidence", [])
            if evidence_items:
                for item in evidence_items:
                    st.markdown(f"**Skill:** `{item.get('skill')}`")
                    st.markdown(f"> *\"{item.get('evidence_snippet')}\"*")
            else:
                st.write("No direct evidence snippets matched.")

        with col_ev2:
            st.markdown("##### ⚠️ Requirements Needing Clarification")
            st.caption("*(Per ethical safeguards, omission does not indicate absence of skill)*")
            clarification_items = resume_data.get("clarification_needed", [])
            if clarification_items:
                for item in clarification_items:
                    st.markdown(f"**Target:** `{item.get('requirement')}`")
                    st.markdown(f"- {item.get('reason')}")
            else:
                st.write("All core requirements have matching mentions.")

        st.markdown("---")

        # Result Section 3: Generated Interview Questions (Agent 3 Output)
        interview_data = result["interview_generation"]
        questions = interview_data.get("questions", [])
        categories = interview_data.get("categories_covered", [])
        cand_level = interview_data.get("candidate_level", "Mid-Level")
        limitation_note = interview_data.get("limitation_note")

        st.subheader(f"💡 3. Targeted Technical Interview Questionnaire ({len(questions)} Questions)")
        st.caption(f"Inferred Candidate Tier: **{cand_level}** | Categories Covered: **{len(categories)}** | Target Requested: **{interview_data.get('target_requested', 30)}**")

        if limitation_note:
            st.warning(f"ℹ️ **Adaptive Depth Notice:** {limitation_note}")

        # Export Buttons
        col_exp1, col_exp2 = st.columns([1, 1])
        with col_exp1:
            md_content = generate_markdown_export(questions, job_data.get('job_title', 'Software Engineer'), cand_level)
            st.download_button(
                label="📥 Download Questionnaire (.md)",
                data=md_content,
                file_name="interview_questionnaire.md",
                mime="text/markdown",
                use_container_width=True
            )
        with col_exp2:
            csv_content = generate_csv_export(questions)
            st.download_button(
                label="📥 Download Questionnaire (.csv)",
                data=csv_content,
                file_name="interview_questionnaire.csv",
                mime="text/csv",
                use_container_width=True
            )

        # View Tabs: All Questions vs By Category
        view_mode = st.radio("Display View:", ["Grouped by Category", "Full Sequential List"], horizontal=True)

        if view_mode == "Grouped by Category":
            # Group questions into a dict
            grouped: Dict[str, List[Dict[str, Any]]] = {}
            for q in questions:
                cat = q.get("category", "General")
                grouped.setdefault(cat, []).append(q)

            for cat_name, cat_questions in grouped.items():
                with st.expander(f"📁 {cat_name} ({len(cat_questions)} questions)", expanded=True):
                    for q in cat_questions:
                        render_question_card(q)
        else:
            for q in questions:
                render_question_card(q)


def render_question_card(q: Dict[str, Any]):
    """Renders a single question card with difficulty badge, rubric, and expected answers."""
    diff = q.get("difficulty", "Intermediate")
    if diff == "Foundation":
        diff_badge = "<span class='badge-foundation'>Foundation</span>"
    elif diff == "Advanced":
        diff_badge = "<span class='badge-advanced'>Advanced</span>"
    else:
        diff_badge = "<span class='badge-intermediate'>Intermediate</span>"

    cat = q.get("category", "Technical")
    cat_badge = f"<span class='badge-category'>{cat}</span>"
    skill = q.get("skill_assessed", "General Competency")
    relevance = q.get("relevance", "Job alignment")
    follow_up = q.get("follow_up", "")
    rubric = q.get("evaluation_rubric", {})

    expected_pts_html = "".join([f"<li>{pt}</li>" for pt in q.get("expected_answer", [])])

    card_html = (
        f"<div class='question-card'>"
        f"<div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;'>"
        f"<div><strong style='color:#1E3A8A; font-size:1.05rem;'>Q#{q.get('id', 1)}: {skill}</strong></div>"
        f"<div>{cat_badge} {diff_badge}</div>"
        f"</div>"
        f"<p style='font-size:1.05rem; font-weight:600; color:#0F172A; margin: 8px 0;'>{q.get('question')}</p>"
        f"<p style='font-size:0.85rem; color:#475569; margin: 4px 0;'><strong>Relevance:</strong> {relevance}</p>"
        f"<div style='background-color:#F8FAFC; border-radius:6px; padding:8px 12px; margin-top:8px;'>"
        f"<strong style='font-size:0.88rem; color:#1E293B;'>Expected Key Answer Points:</strong>"
        f"<ul style='font-size:0.85rem; color:#334155; margin-bottom:0; padding-left:20px;'>{expected_pts_html}</ul>"
        f"</div>"
        + (f"<div class='follow-up-box'><strong>Follow-up Probe:</strong> <em>\"{follow_up}\"</em></div>" if follow_up else "")
        + f"<div class='rubric-box'>"
        f"<strong style='color:#1E293B;'>Evaluation Rubric:</strong><br/>"
        f"<span style='color:#991B1B;'>⚠️ <strong>Weak:</strong> {rubric.get('weak', 'N/A')}</span><br/>"
        f"<span style='color:#166534;'>✅ <strong>Strong:</strong> {rubric.get('strong', 'N/A')}</span>"
        f"</div>"
        f"</div>"
    )

    st.markdown(card_html, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
