"""
Orchestrator Module: RecruiterOrchestrator
Coordinates the sequential execution of Agent 1 (Job Analyzer),
Agent 2 (Resume Analyzer), and Agent 3 (Interview Question Generator).
Maintains execution trace, handles exceptions gracefully, and aggregates responses.
"""

import time
import logging
from typing import Dict, Any, Optional

from agents.job_analyzer import JobDescriptionAnalyzer
from agents.resume_analyzer import ResumeAnalyzer
from agents.interview_generator import InterviewQuestionGenerator
from llm_client import LLMClient

logger = logging.getLogger(__name__)

class RecruiterOrchestrator:
    """Coordinates the Multi-Agent AI Recruiter workflow."""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or LLMClient()
        # Initialize three distinct agents
        self.job_analyzer = JobDescriptionAnalyzer(self.llm_client)
        self.resume_analyzer = ResumeAnalyzer(self.llm_client)
        self.interview_generator = InterviewQuestionGenerator(self.llm_client)

    def run_workflow(
        self,
        job_description: str,
        resume_text: str,
        target_question_count: int = 30
    ) -> Dict[str, Any]:
        """
        Executes the full 3-agent pipeline:
        1. Validate inputs
        2. Execute Agent 1 (Job Description Analyzer)
        3. Execute Agent 2 (Resume Analyzer) using Agent 1's output
        4. Execute Agent 3 (Interview Question Generator) with configurable target count
        5. Return consolidated result with trace and execution logs
        """
        start_time = time.time()
        trace = []

        # Step 0: Input Validation
        if not job_description or not job_description.strip():
            return {
                "success": False,
                "error": "Job description cannot be empty. Please provide job details.",
                "trace": trace
            }
        if not resume_text or not resume_text.strip():
            return {
                "success": False,
                "error": "Candidate resume cannot be empty. Please paste or upload a resume.",
                "trace": trace
            }

        try:
            # Step 1: Execute Agent 1 (Job Description Analyzer)
            step1_start = time.time()
            job_output = self.job_analyzer.analyze(job_description)
            step1_duration = round(time.time() - step1_start, 3)
            trace.append({
                "step": 1,
                "agent": self.job_analyzer.agent_name,
                "mode": job_output.get("mode", "unknown"),
                "duration_seconds": step1_duration,
                "status": "COMPLETED",
                "summary": f"Identified role '{job_output.get('job_title')}' with {len(job_output.get('key_skills', []))} skills."
            })

            # Step 2: Execute Agent 2 (Resume Analyzer)
            step2_start = time.time()
            resume_output = self.resume_analyzer.analyze(resume_text, job_output)
            step2_duration = round(time.time() - step2_start, 3)
            trace.append({
                "step": 2,
                "agent": self.resume_analyzer.agent_name,
                "mode": resume_output.get("mode", "unknown"),
                "duration_seconds": step2_duration,
                "status": "COMPLETED",
                "summary": f"Verified {len(resume_output.get('candidate_skills', []))} skills and flagged {len(resume_output.get('clarification_needed', []))} clarification areas."
            })

            # Step 3: Execute Agent 3 (Interview Question Generator)
            step3_start = time.time()
            interview_output = self.interview_generator.generate(
                job_output,
                resume_output,
                target_question_count=target_question_count
            )
            step3_duration = round(time.time() - step3_start, 3)
            questions_count = len(interview_output.get("questions", []))
            categories_count = len(interview_output.get("categories_covered", []))
            trace.append({
                "step": 3,
                "agent": self.interview_generator.agent_name,
                "mode": interview_output.get("mode", "unknown"),
                "duration_seconds": step3_duration,
                "status": "COMPLETED",
                "summary": f"Synthesized {questions_count} targeted questions across {categories_count} categories with evaluation rubrics."
            })

            total_duration = round(time.time() - start_time, 3)

            return {
                "success": True,
                "job_analysis": job_output,
                "resume_analysis": resume_output,
                "interview_generation": interview_output,
                "trace": trace,
                "total_duration_seconds": total_duration,
                "active_provider": self.llm_client.get_active_provider()
            }

        except Exception as e:
            logger.exception("Error during multi-agent workflow execution")
            return {
                "success": False,
                "error": f"Workflow failed during execution: {str(e)}",
                "trace": trace,
                "total_duration_seconds": round(time.time() - start_time, 3)
            }
