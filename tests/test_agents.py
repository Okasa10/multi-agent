"""
Automated Pytest Suite for Multi-Agent AI Recruiter Assistant.
Tests Agent 1 (Job Analyzer), Agent 2 (Resume Analyzer), Agent 3 (Interview Question Generator),
and RecruiterOrchestrator for correct behavior, question quality, schema conformance,
input validation, edge cases, and graceful exception handling.
"""

import pytest
import sys
import os
from unittest.mock import MagicMock

# Ensure package root is in Python path for test discovery
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.job_analyzer import JobDescriptionAnalyzer
from agents.resume_analyzer import ResumeAnalyzer
from agents.interview_generator import (
    InterviewQuestionGenerator,
    CATEGORY_RESUME_DEEP_DIVE,
    CATEGORY_JOB_SKILLS,
    VALID_CATEGORIES,
    DIFFICULTY_LEVELS
)
from orchestrator import RecruiterOrchestrator
from llm_client import LLMClient

SAMPLE_JD = """
Job Title: Senior Backend Python Engineer
Responsibilities:
- Build and deploy high throughput REST APIs using FastAPI and Python.
- Maintain PostgreSQL database queries and Redis caching systems.
- Containerize services with Docker and manage Kubernetes deployments.
Qualifications:
- 4+ years of Python, Docker, PostgreSQL, and Pytest experience.
"""

SAMPLE_RESUME = """
Alex Morgan
Email: alex.morgan@example.com
Backend Software Engineer with 4 years building scalable services.
- Architected and deployed 12+ RESTful microservices in Python and FastAPI serving over 1.5 million requests daily.
- Implemented comprehensive automated test suites using Pytest, boosting code test coverage from 62% to 91%.
- Optimized complex PostgreSQL database queries and added Redis caching layers, reducing p99 API response latencies by 38%.
- Containerized development and staging environments using Docker, ensuring consistent dependency parity across teams.
"""

SPARSE_JD = """
Job Title: Tech Helper
Skills: Basic Computer
"""

SPARSE_RESUME = """
John
Graduated recently. Interested in computing.
"""

# ==========================================
# Agent 1: Job Description Analyzer Tests
# ==========================================

def test_job_analyzer_valid_input():
    analyzer = JobDescriptionAnalyzer()
    result = analyzer.analyze(SAMPLE_JD)

    assert isinstance(result, dict)
    assert "job_title" in result
    assert "key_skills" in result
    assert "responsibilities" in result
    assert isinstance(result["key_skills"], list)
    assert len(result["key_skills"]) > 0
    assert "Python" in result["key_skills"]
    assert result["agent_name"] == "Job Description Analyzer"

def test_job_analyzer_empty_input():
    analyzer = JobDescriptionAnalyzer()
    with pytest.raises(ValueError, match="Job description cannot be empty"):
        analyzer.analyze("")

    with pytest.raises(ValueError, match="Job description cannot be empty"):
        analyzer.analyze("   \n\t  ")

# ==========================================
# Agent 2: Resume Analyzer Tests
# ==========================================

def test_resume_analyzer_valid_input():
    job_analyzer = JobDescriptionAnalyzer()
    job_result = job_analyzer.analyze(SAMPLE_JD)

    resume_analyzer = ResumeAnalyzer()
    result = resume_analyzer.analyze(SAMPLE_RESUME, job_result)

    assert isinstance(result, dict)
    assert "candidate_skills" in result
    assert "evidence" in result
    assert "clarification_needed" in result
    assert isinstance(result["evidence"], list)
    assert len(result["evidence"]) > 0

    first_evidence = result["evidence"][0]
    assert "skill" in first_evidence
    assert "evidence_snippet" in first_evidence
    assert len(first_evidence["evidence_snippet"]) > 5

    assert isinstance(result["clarification_needed"], list)
    assert result["agent_name"] == "Resume Analyzer"

def test_resume_analyzer_empty_input():
    resume_analyzer = ResumeAnalyzer()
    job_analyzer = JobDescriptionAnalyzer()
    job_result = job_analyzer.analyze(SAMPLE_JD)

    with pytest.raises(ValueError, match="Resume text cannot be empty"):
        resume_analyzer.analyze("", job_result)

    with pytest.raises(ValueError, match="Valid Job Analysis from Agent 1 is required"):
        resume_analyzer.analyze(SAMPLE_RESUME, None)

# ==========================================
# Agent 3: Interview Question Generator Tests
# ==========================================

def test_interview_generator_configurable_question_count():
    """Verifies that requested target counts (e.g. 20, 30) are respected."""
    job_analyzer = JobDescriptionAnalyzer()
    resume_analyzer = ResumeAnalyzer()
    generator = InterviewQuestionGenerator()

    job_result = job_analyzer.analyze(SAMPLE_JD)
    resume_result = resume_analyzer.analyze(SAMPLE_RESUME, job_result)

    # Test target 20
    res_20 = generator.generate(job_result, resume_result, target_question_count=20)
    assert len(res_20["questions"]) == 20

    # Test target 30
    res_30 = generator.generate(job_result, resume_result, target_question_count=30)
    assert len(res_30["questions"]) == 30

def test_interview_generator_schema_and_fields():
    """Validates that each question contains all required schema keys."""
    job_analyzer = JobDescriptionAnalyzer()
    resume_analyzer = ResumeAnalyzer()
    generator = InterviewQuestionGenerator()

    job_result = job_analyzer.analyze(SAMPLE_JD)
    resume_result = resume_analyzer.analyze(SAMPLE_RESUME, job_result)

    result = generator.generate(job_result, resume_result, target_question_count=25)
    questions = result["questions"]

    assert len(questions) == 25
    for q in questions:
        assert "id" in q and isinstance(q["id"], int)
        assert "category" in q and q["category"] in VALID_CATEGORIES
        assert "difficulty" in q and q["difficulty"] in DIFFICULTY_LEVELS
        assert "question" in q and len(q["question"]) > 30 and q["question"].endswith("?")
        assert "skill_assessed" in q and len(q["skill_assessed"]) > 2
        assert "relevance" in q and len(q["relevance"]) > 5
        assert "expected_answer" in q and isinstance(q["expected_answer"], list)
        assert len(q["expected_answer"]) >= 2
        assert "follow_up" in q and len(q["follow_up"]) > 5
        assert "evaluation_rubric" in q and isinstance(q["evaluation_rubric"], dict)
        assert "weak" in q["evaluation_rubric"] and "strong" in q["evaluation_rubric"]
        assert "quality_score" in q and q["quality_score"] >= 3.5

def test_interview_generator_grounded_in_resume():
    """Verifies that resume deep dive questions specifically reference candidate facts."""
    job_analyzer = JobDescriptionAnalyzer()
    resume_analyzer = ResumeAnalyzer()
    generator = InterviewQuestionGenerator()

    job_result = job_analyzer.analyze(SAMPLE_JD)
    resume_result = resume_analyzer.analyze(SAMPLE_RESUME, job_result)

    result = generator.generate(job_result, resume_result, target_question_count=30)
    resume_questions = [q for q in result["questions"] if q["category"] == CATEGORY_RESUME_DEEP_DIVE]

    assert len(resume_questions) > 0
    # Must mention resume specific metrics from Alex Morgan's resume
    combined_resume_q_text = " ".join([q["question"] for q in resume_questions]).lower()
    assert any(term in combined_resume_q_text for term in ["1.5m", "1.5 million", "91%", "38%", "fastapi", "pytest", "redis"])

def test_interview_generator_clarification_fairness():
    """Verifies unverified skills (e.g. Kubernetes) produce fair clarification questions without false disqualification."""
    job_analyzer = JobDescriptionAnalyzer()
    resume_analyzer = ResumeAnalyzer()
    generator = InterviewQuestionGenerator()

    job_result = job_analyzer.analyze(SAMPLE_JD)
    resume_result = resume_analyzer.analyze(SAMPLE_RESUME, job_result)

    result = generator.generate(job_result, resume_result, target_question_count=30)
    job_questions = [q for q in result["questions"] if q["category"] == CATEGORY_JOB_SKILLS]

    # Look for Kubernetes question
    k8s_q = next((q for q in job_questions if "kubernetes" in q["question"].lower() or "k8s" in q["question"].lower()), None)
    assert k8s_q is not None
    assert "clarification" in k8s_q["skill_assessed"].lower() or "clarification" in k8s_q["relevance"].lower()

def test_interview_generator_sparse_input_handling():
    """Verifies that sparse inputs produce fewer questions and note the limitation rather than adding fluff."""
    job_analyzer = JobDescriptionAnalyzer()
    resume_analyzer = ResumeAnalyzer()
    generator = InterviewQuestionGenerator()

    sparse_job = job_analyzer.analyze(SPARSE_JD)
    sparse_res = resume_analyzer.analyze(SPARSE_RESUME, sparse_job)

    result = generator.generate(sparse_job, sparse_res, target_question_count=40)
    assert len(result["questions"]) < 25
    assert result.get("limitation_note") is not None
    assert "constrained" in result["limitation_note"].lower() or "sparse" in result["limitation_note"].lower()

def test_interview_generator_quality_filter_rejects_vague():
    """Verifies quality scoring rejects generic interview questions like 'Tell me about yourself'."""
    generator = InterviewQuestionGenerator()
    vague_questions = [
        {"question": "Tell me about yourself?", "category": "General", "difficulty": "Foundation"},
        {"question": "What is Python?", "category": "Technical", "difficulty": "Foundation"},
        {"question": "What are your strengths?", "category": "Behavioral", "difficulty": "Foundation"},
        {"question": "Valid specific question about FastAPI connection pooling and asyncio event loop?", "category": "Job-Specific Technical Skills", "difficulty": "Intermediate"}
    ]
    filtered = generator._evaluate_and_filter_questions(vague_questions, ["FastAPI", "Python"], ["FastAPI"], target_count=10)
    # Only the valid question should pass
    assert len(filtered) == 1
    assert "FastAPI" in filtered[0]["question"]

def test_interview_generator_deduplication():
    """Verifies that near-identical duplicate questions are filtered out."""
    generator = InterviewQuestionGenerator()
    dupes = [
        {
            "question": "How do you optimize slow queries in PostgreSQL using execution plans and indexing strategies?",
            "category": "Core Technical Concepts",
            "difficulty": "Intermediate"
        },
        {
            "question": "How do you optimize slow queries in PostgreSQL using execution plans and indexing strategies?",
            "category": "Core Technical Concepts",
            "difficulty": "Intermediate"
        }
    ]
    filtered = generator._evaluate_and_filter_questions(dupes, ["PostgreSQL"], ["PostgreSQL"], target_count=5)
    assert len(filtered) == 1

def test_interview_generator_llm_fallback_on_api_error():
    """Verifies graceful fallback to deterministic engine if LLM raises an error."""
    mock_client = MagicMock(spec=LLMClient)
    mock_client.is_configured.return_value = True
    mock_client.generate_json.side_effect = Exception("API connection timed out")
    mock_client.get_active_provider.return_value = "MockProvider"

    generator = InterviewQuestionGenerator(llm_client=mock_client)
    job_analyzer = JobDescriptionAnalyzer()
    resume_analyzer = ResumeAnalyzer()

    job_result = job_analyzer.analyze(SAMPLE_JD)
    resume_result = resume_analyzer.analyze(SAMPLE_RESUME, job_result)

    result = generator.generate(job_result, resume_result, target_question_count=20)
    assert result["mode"] == "deterministic_fallback"
    assert len(result["questions"]) == 20

def test_interview_generator_invalid_input():
    generator = InterviewQuestionGenerator()
    with pytest.raises(ValueError):
        generator.generate(None, {})
    with pytest.raises(ValueError):
        generator.generate({}, None)

# ==========================================
# Orchestrator Integration Tests
# ==========================================

def test_orchestrator_full_workflow():
    orchestrator = RecruiterOrchestrator()
    result = orchestrator.run_workflow(SAMPLE_JD, SAMPLE_RESUME, target_question_count=30)

    assert result["success"] is True
    assert "job_analysis" in result
    assert "resume_analysis" in result
    assert "interview_generation" in result
    assert "trace" in result
    assert "total_duration_seconds" in result

    # Check that trace records all 3 agent steps in sequential order
    trace = result["trace"]
    assert len(trace) == 3
    assert trace[0]["step"] == 1
    assert trace[0]["agent"] == "Job Description Analyzer"
    assert trace[1]["step"] == 2
    assert trace[1]["agent"] == "Resume Analyzer"
    assert trace[2]["step"] == 3
    assert trace[2]["agent"] == "Interview Question Generator"

    # Verify Agent 3 output inside orchestrator payload
    interview_gen = result["interview_generation"]
    assert len(interview_gen["questions"]) == 30
    assert len(interview_gen["categories_covered"]) >= 4

def test_orchestrator_handles_empty_inputs_gracefully():
    orchestrator = RecruiterOrchestrator()

    # Empty JD
    res1 = orchestrator.run_workflow("", SAMPLE_RESUME)
    assert res1["success"] is False
    assert "Job description cannot be empty" in res1["error"]

    # Empty Resume
    res2 = orchestrator.run_workflow(SAMPLE_JD, "   ")
    assert res2["success"] is False
    assert "Candidate resume cannot be empty" in res2["error"]
