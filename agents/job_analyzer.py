"""
Agent 1: Job Description Analyzer
Responsible for parsing job descriptions, extracting job titles, core skills,
and principal responsibilities into a structured, validated format.
"""

import re
import logging
from typing import Dict, Any, List
from llm_client import LLMClient

logger = logging.getLogger(__name__)

class JobDescriptionAnalyzer:
    """Agent 1: Extracts structured requirements from raw Job Description text."""

    def __init__(self, llm_client: LLMClient = None):
        self.llm_client = llm_client or LLMClient()
        self.agent_name = "Job Description Analyzer"

    def analyze(self, job_description: str) -> Dict[str, Any]:
        """
        Analyzes the given job description.
        Raises ValueError if the input is empty or invalid.
        """
        if not job_description or not job_description.strip():
            raise ValueError("Job description cannot be empty or blank.")

        clean_jd = job_description.strip()

        # Try LLM first if configured
        if self.llm_client.is_configured():
            system_prompt = (
                "You are an expert HR and recruitment AI agent specializing in job requirement analysis. "
                "Analyze the job description and extract:\n"
                "1. 'job_title': specific role title\n"
                "2. 'key_skills': list of technical & domain skills required\n"
                "3. 'responsibilities': list of 3-6 core job responsibilities\n"
                "4. 'experience_level': e.g., 'Junior', 'Mid-Level', 'Senior', or 'Not Specified'\n"
                "Return strictly valid JSON with these exact keys."
            )
            result = self.llm_client.generate_json(system_prompt, clean_jd)
            if result and self._validate_schema(result):
                result["agent_name"] = self.agent_name
                result["mode"] = "llm_powered"
                result["provider"] = self.llm_client.get_active_provider()
                return result
            logger.info("LLM extraction failed or schema mismatch; falling back to deterministic extraction.")

        # Deterministic Rule-Based Fallback
        return self._deterministic_extract(clean_jd)

    def _validate_schema(self, data: Dict[str, Any]) -> bool:
        """Validates that LLM output matches required schema."""
        required = ["job_title", "key_skills", "responsibilities"]
        return all(k in data and isinstance(data[k], (list if k != "job_title" else str)) for k in required)

    def _deterministic_extract(self, text: str) -> Dict[str, Any]:
        """Rule-based extractor used when LLM is unavailable or unconfigured."""
        lines = [line.strip() for line in text.splitlines() if line.strip()]

        # 1. Job Title extraction heuristic
        job_title = "Specialized Technical Role"
        for line in lines[:5]:
            lower = line.lower()
            if any(term in lower for term in ["title:", "position:", "role:", "engineer", "developer", "architect", "lead", "analyst", "manager"]):
                cleaned = re.sub(r"^(title|position|role|job title)\s*:\s*", "", line, flags=re.IGNORECASE).strip()
                if 4 < len(cleaned) < 60:
                    job_title = cleaned
                    break
        if job_title == "Specialized Technical Role" and lines:
            job_title = lines[0][:60]

        # 2. Key Skills extraction using comprehensive vocabulary & bullet points
        common_skills = [
            "Python", "JavaScript", "TypeScript", "React", "Node.js", "Java", "C++", "C#",
            "SQL", "PostgreSQL", "MySQL", "MongoDB", "Redis", "Docker", "Kubernetes",
            "AWS", "Azure", "GCP", "CI/CD", "Git", "REST APIs", "GraphQL", "FastAPI",
            "Django", "Flask", "Machine Learning", "Pandas", "PyTorch", "TensorFlow",
            "Agile", "Scrum", "Microservices", "System Design", "Unit Testing", "Pytest",
            "Linux", "TailwindCSS", "HTML", "CSS", "Next.js", "DevOps", "Cybersecurity"
        ]

        detected_skills = []
        for skill in common_skills:
            pattern = r"\b" + re.escape(skill) + r"\b"
            if re.search(pattern, text, re.IGNORECASE):
                detected_skills.append(skill)

        # Fallback skills if none found
        if not detected_skills:
            detected_skills = ["Python", "Problem Solving", "Software Design", "Git", "Communication"]

        # 3. Responsibilities extraction
        responsibilities = []
        in_resp_section = False
        for line in lines:
            lower = line.lower()
            if any(h in lower for h in ["responsibilities", "duties", "what you will do", "what you'll do", "day to day"]):
                in_resp_section = True
                continue
            if in_resp_section:
                if any(h in lower for h in ["qualifications", "requirements", "skills required", "about us", "benefits", "nice to have"]):
                    break
                if line.startswith(("-", "*", "•")) or re.match(r"^\d+\.", line):
                    cleaned_bullet = re.sub(r"^[-*•\d.]+\s*", "", line).strip()
                    if len(cleaned_bullet) > 10:
                        responsibilities.append(cleaned_bullet)

        # If section header was absent, pick bullet lines
        if not responsibilities:
            for line in lines:
                if (line.startswith(("-", "*", "•")) or re.match(r"^\d+\.", line)) and len(line) > 15:
                    cleaned_bullet = re.sub(r"^[-*•\d.]+\s*", "", line).strip()
                    if cleaned_bullet not in detected_skills:
                        responsibilities.append(cleaned_bullet)
                if len(responsibilities) >= 4:
                    break

        if not responsibilities:
            responsibilities = [
                "Design and maintain scalable software modules and APIs.",
                "Collaborate with cross-functional engineering and product teams.",
                "Ensure code quality through unit testing, documentation, and reviews."
            ]

        # 4. Experience level
        exp_level = "Mid-Senior Level"
        if re.search(r"\b(entry|junior|fresher|intern)\b", text, re.IGNORECASE):
            exp_level = "Entry / Junior Level"
        elif re.search(r"\b(lead|principal|staff|director|head)\b", text, re.IGNORECASE):
            exp_level = "Lead / Principal Level"
        elif re.search(r"\b(senior|5\+\s*years|7\+\s*years)\b", text, re.IGNORECASE):
            exp_level = "Senior Level"

        return {
            "job_title": job_title,
            "key_skills": list(dict.fromkeys(detected_skills)),
            "responsibilities": responsibilities[:6],
            "experience_level": exp_level,
            "agent_name": self.agent_name,
            "mode": "deterministic_fallback",
            "provider": "Rule-based Heuristics (Deterministic)"
        }
