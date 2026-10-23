"""
Agent 2: Resume Analyzer
Responsible for examining candidate resumes against Agent 1's extracted job requirements.
Identifies demonstrable skills, extracts verifiable evidence snippets, and flags areas
requiring recruiter clarification without prematurely assuming disqualification.
"""

import re
import logging
from typing import Dict, Any, List
from llm_client import LLMClient

logger = logging.getLogger(__name__)

class ResumeAnalyzer:
    """Agent 2: Maps resume evidence against job requirements and identifies clarification areas."""

    def __init__(self, llm_client: LLMClient = None):
        self.llm_client = llm_client or LLMClient()
        self.agent_name = "Resume Analyzer"

    def analyze(self, resume_text: str, job_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyzes the resume text using context from Agent 1 (job_analysis).
        Raises ValueError if inputs are invalid.
        """
        if not resume_text or not resume_text.strip():
            raise ValueError("Resume text cannot be empty or blank.")
        if not job_analysis or not isinstance(job_analysis, dict):
            raise ValueError("Valid Job Analysis from Agent 1 is required.")

        clean_resume = resume_text.strip()
        required_skills = job_analysis.get("key_skills", [])
        job_title = job_analysis.get("job_title", "Target Role")

        # Try LLM first if configured
        if self.llm_client.is_configured():
            system_prompt = (
                "You are an objective AI Recruiter Agent specialized in candidate resume verification. "
                "CRITICAL PRINCIPLE: Never assume a candidate lacks competence merely because a specific keyword is absent. "
                "Assess transferable experience and mark unstated aspects as areas for conversation/clarification.\n\n"
                "Given the Job Analysis requirements and Candidate Resume, return strictly valid JSON containing:\n"
                "1. 'candidate_skills': list of confirmed skills with direct mention in the resume\n"
                "2. 'evidence': list of objects [{'skill': str, 'evidence_snippet': str (direct resume sentence)}]\n"
                "3. 'clarification_needed': list of objects [{'requirement': str, 'reason': str (why clarification is needed)}]\n"
                "4. 'summary': 2-3 sentence balanced overview of alignment and potential"
            )
            user_prompt = (
                f"JOB TITLE: {job_title}\n"
                f"REQUIRED SKILLS: {', '.join(required_skills)}\n\n"
                f"CANDIDATE RESUME:\n{clean_resume}"
            )
            result = self.llm_client.generate_json(system_prompt, user_prompt)
            if result and self._validate_schema(result):
                result["agent_name"] = self.agent_name
                result["mode"] = "llm_powered"
                result["provider"] = self.llm_client.get_active_provider()
                return result
            logger.info("LLM extraction failed or schema mismatch in ResumeAnalyzer; falling back to deterministic.")

        # Deterministic Rule-Based Fallback
        return self._deterministic_extract(clean_resume, required_skills, job_analysis)

    def _validate_schema(self, data: Dict[str, Any]) -> bool:
        """Validates that LLM output adheres to expected types."""
        return (
            "candidate_skills" in data and isinstance(data["candidate_skills"], list) and
            "evidence" in data and isinstance(data["evidence"], list) and
            "clarification_needed" in data and isinstance(data["clarification_needed"], list)
        )

    def _deterministic_extract(self, resume_text: str, required_skills: List[str], job_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Extracts candidate skills, evidence snippets, and clarification items deterministically."""
        lines = [line.strip() for line in resume_text.splitlines() if line.strip()]

        # Break text into searchable sentences
        raw_sentences = re.split(r"(?<=[.!?\n])\s+", resume_text)
        sentences = [s.strip() for s in raw_sentences if len(s.strip()) > 10]

        evidence_list = []
        confirmed_skills = []
        clarification_needed = []

        def snippet_priority(sentence: str) -> int:
            score = 0
            low = sentence.lower()
            if any(verb in low for verb in ["architected", "deployed", "built", "implemented", "optimized", "engineered", "maintained", "automated", "serving", "reduced", "boosted", "created", "designed"]):
                score += 10
            if any(ch.isdigit() for ch in sentence) or "%" in sentence:
                score += 5
            if any(h in low for h in ["technical skills", "languages:", "frameworks:", "tools:"]):
                score -= 20
            return score

        # 1. Match required skills against resume sentences
        for skill in required_skills:
            pattern = r"\b" + re.escape(skill) + r"\b"
            matching_snippets = [
                s[:180].strip() for s in sentences if re.search(pattern, s, re.IGNORECASE)
            ]

            if matching_snippets:
                # Pick the most descriptive, action-oriented snippet
                best_snippet = max(matching_snippets, key=snippet_priority)
                confirmed_skills.append(skill)
                evidence_list.append({
                    "skill": skill,
                    "evidence_snippet": best_snippet
                })
            else:
                # Skill is not explicitly highlighted; do not reject, flag for clarification
                clarification_needed.append({
                    "requirement": skill,
                    "reason": f"No explicit project or metric mentions '{skill}'. Recommended for conversational verification."
                })

        # 2. Extract additional candidate skills present in resume
        broad_skills_catalog = [
            "Git", "Docker", "SQL", "Python", "FastAPI", "React", "AWS", "Linux",
            "TypeScript", "CI/CD", "Redis", "PostgreSQL", "MongoDB", "Kubernetes",
            "Pytest", "Agile", "GraphQL", "Django", "Machine Learning"
        ]
        for extra in broad_skills_catalog:
            if extra not in confirmed_skills:
                pattern = r"\b" + re.escape(extra) + r"\b"
                for sentence in sentences:
                    if re.search(pattern, sentence, re.IGNORECASE):
                        confirmed_skills.append(extra)
                        evidence_list.append({
                            "skill": extra,
                            "evidence_snippet": sentence[:180].strip()
                        })
                        break

        # Fallback if resume is sparse
        if not evidence_list:
            snippet = lines[0] if lines else "Candidate profile details provided"
            confirmed_skills = ["Software Development", "Communication"]
            evidence_list.append({
                "skill": "Software Development",
                "evidence_snippet": snippet[:150]
            })

        # Ensure clarification list has meaningful items
        if not clarification_needed:
            clarification_needed.append({
                "requirement": "Architectural Scale & Production Ownership",
                "reason": "Clarify the candidate's exact role in deploying and scaling high-traffic systems."
            })

        summary = (
            f"Candidate demonstrates concrete evidence for {len(confirmed_skills)} technical capabilities. "
            f"Identified {len(clarification_needed)} requirement area(s) to explore in depth during interview discussions."
        )

        return {
            "candidate_skills": list(dict.fromkeys(confirmed_skills)),
            "evidence": evidence_list,
            "clarification_needed": clarification_needed,
            "summary": summary,
            "agent_name": self.agent_name,
            "mode": "deterministic_fallback",
            "provider": "Rule-based NLP Engine (Deterministic)"
        }
