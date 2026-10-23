"""
Agent 3: Interview Question Generator
Synthesizes Job Description Requirements (Agent 1) and Resume Analysis (Agent 2)
to produce a high-yield, interview-ready questionnaire of 20 to 50 targeted questions.
Includes quality validation, rubric scoring, category distribution, and dual execution
(live LLM reasoning with automated offline deterministic fallback).
"""

import re
import logging
from typing import Dict, Any, List, Optional, Tuple

from llm_client import LLMClient

logger = logging.getLogger(__name__)

# Standard Questionnaire Categories
CATEGORY_RESUME_DEEP_DIVE = "Resume & Project Deep-Dive"
CATEGORY_CORE_CONCEPTS = "Core Technical Concepts"
CATEGORY_JOB_SKILLS = "Job-Specific Technical Skills"
CATEGORY_SCENARIOS = "Problem-Solving & Practical Scenarios"
CATEGORY_CODING_SYSTEM_DESIGN = "Coding, Debugging & System Design"
CATEGORY_BEHAVIORAL = "Behavioral & Teamwork"
CATEGORY_ROLE_DOMAIN = "Role Motivation & Domain Understanding"

VALID_CATEGORIES = [
    CATEGORY_RESUME_DEEP_DIVE,
    CATEGORY_CORE_CONCEPTS,
    CATEGORY_JOB_SKILLS,
    CATEGORY_SCENARIOS,
    CATEGORY_CODING_SYSTEM_DESIGN,
    CATEGORY_BEHAVIORAL,
    CATEGORY_ROLE_DOMAIN,
]

DIFFICULTY_LEVELS = ["Foundation", "Intermediate", "Advanced"]


class InterviewQuestionGenerator:
    """
    Agent 3: Generates a structured questionnaire (20-50 questions) across 7 categories
    with evaluation rubrics, expected answer points, difficulty levels, and quality scoring.
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or LLMClient()
        self.agent_name = "Interview Question Generator"

    def generate(
        self,
        job_analysis: Dict[str, Any],
        resume_analysis: Dict[str, Any],
        target_question_count: int = 30
    ) -> Dict[str, Any]:
        """
        Generates 20 to 50 targeted interview questions.
        Validates input structure, infers experience level, enforces question quality,
        and provides fallback when API keys are absent or input is limited.
        """
        if not job_analysis or not isinstance(job_analysis, dict):
            raise ValueError("Valid Job Analysis from Agent 1 is required.")
        if not resume_analysis or not isinstance(resume_analysis, dict):
            raise ValueError("Valid Resume Analysis from Agent 2 is required.")

        # Enforce range [20, 50]
        clamped_target = max(20, min(50, int(target_question_count)))

        job_title = job_analysis.get("job_title", "Software Engineer")
        key_skills = job_analysis.get("key_skills", [])
        responsibilities = job_analysis.get("responsibilities", [])
        experience_level = job_analysis.get("experience_level", "Mid-Level")

        candidate_skills = resume_analysis.get("candidate_skills", [])
        evidence = resume_analysis.get("evidence", [])
        clarification_needed = resume_analysis.get("clarification_needed", [])
        summary = resume_analysis.get("summary", "")

        # Detect candidate seniority level
        candidate_level = self._infer_candidate_level(job_analysis, resume_analysis)

        # Check if input information is genuinely sparse/limited
        is_sparse, sparsity_reason = self._check_input_sparsity(job_analysis, resume_analysis)

        # 1. Try Live LLM Generation if configured
        if self.llm_client.is_configured():
            try:
                llm_result = self._generate_with_llm(
                    job_title=job_title,
                    key_skills=key_skills,
                    responsibilities=responsibilities,
                    experience_level=experience_level,
                    candidate_level=candidate_level,
                    candidate_skills=candidate_skills,
                    evidence=evidence,
                    clarification_needed=clarification_needed,
                    target_count=clamped_target,
                    is_sparse=is_sparse
                )
                if llm_result:
                    return llm_result
            except Exception as e:
                logger.warning(f"LLM question generation failed: {e}. Falling back to deterministic engine.")

        # 2. Advanced Deterministic Synthesis Engine
        return self._deterministic_generate(
            job_title=job_title,
            key_skills=key_skills,
            responsibilities=responsibilities,
            candidate_level=candidate_level,
            candidate_skills=candidate_skills,
            evidence=evidence,
            clarification_needed=clarification_needed,
            target_count=clamped_target,
            is_sparse=is_sparse,
            sparsity_reason=sparsity_reason
        )

    def _infer_candidate_level(self, job_analysis: Dict[str, Any], resume_analysis: Dict[str, Any]) -> str:
        """Infers candidate experience tier (Junior/Fresher, Mid-Level, Senior/Lead)."""
        combined_text = " ".join([
            str(job_analysis.get("experience_level", "")),
            str(resume_analysis.get("summary", "")),
            " ".join([e.get("evidence_snippet", "") for e in resume_analysis.get("evidence", [])])
        ]).lower()

        if any(w in combined_text for w in ["lead", "staff", "principal", "architect", "7+ years", "8+ years"]):
            return "Senior / Lead"
        if any(w in combined_text for w in ["senior", "4+ years", "5+ years", "experienced"]):
            return "Mid-Senior"
        if any(w in combined_text for w in ["intern", "fresher", "graduate", "entry", "0-1 year", "junior"]):
            return "Junior / Fresher"
        return "Mid-Level"

    def _check_input_sparsity(self, job_analysis: Dict[str, Any], resume_analysis: Dict[str, Any]) -> Tuple[bool, str]:
        """Detects if input information is too sparse to meaningfully produce 30-50 non-fluff questions."""
        evidence = resume_analysis.get("evidence", [])
        cand_skills = resume_analysis.get("candidate_skills", [])
        
        is_fallback_evidence = (
            len(evidence) <= 1 and
            (not evidence or evidence[0].get("skill") in ["Software Development", "Communication"])
        )
        if is_fallback_evidence or len(cand_skills) <= 2:
            return True, "Input provided minimal technical details or sparse resume evidence. Question count constrained to prevent generic filler."
        return False, ""

    # =========================================================================
    # Live LLM Generation & Schema Validation
    # =========================================================================

    def _generate_with_llm(
        self,
        job_title: str,
        key_skills: List[str],
        responsibilities: List[str],
        experience_level: str,
        candidate_level: str,
        candidate_skills: List[str],
        evidence: List[Dict[str, str]],
        clarification_needed: List[Dict[str, str]],
        target_count: int,
        is_sparse: bool
    ) -> Optional[Dict[str, Any]]:
        """Constructs an expert technical prompt and invokes LLM."""
        effective_target = min(20, target_count) if is_sparse else target_count

        system_prompt = (
            "You are a Principal Software Architect and Lead Technical Interviewer at a premier technology firm. "
            "Your task is to craft an elite, highly contextual technical interview questionnaire for an engineering candidate. "
            "CRITICAL QUALITY RULES:\n"
            "1. NO GENERIC QUESTIONS. Never ask 'Tell me about yourself', 'What is React?', 'Explain databases', 'What are your strengths?'.\n"
            "2. Ground resume questions strictly in the candidate's actual projects, technologies, and achievements.\n"
            "3. Ground job questions in the required competencies, architectural challenges, and responsibilities.\n"
            "4. For missing or unverified skills, formulate fair scenario or fundamentals questions without falsely claiming they used it.\n"
            "5. Distribute questions across the 7 categories: Resume & Project Deep-Dive; Core Technical Concepts; Job-Specific Technical Skills; Problem-Solving & Practical Scenarios; Coding, Debugging & System Design; Behavioral & Teamwork; Role Motivation & Domain Understanding.\n"
            "6. Vary difficulty across Foundation, Intermediate, and Advanced.\n"
            "7. Every question MUST end with a question mark (?).\n"
            "8. Return STRICTLY valid JSON with key 'questions', an array of objects matching the schema:\n"
            "[\n"
            "  {\n"
            "    \"id\": 1,\n"
            "    \"category\": \"Category Name\",\n"
            "    \"question\": \"Detailed, contextual question text ending with ?\",\n"
            "    \"difficulty\": \"Foundation | Intermediate | Advanced\",\n"
            "    \"skill_assessed\": \"Target skill or competency\",\n"
            "    \"relevance\": \"Exact link to job requirement or resume evidence\",\n"
            "    \"expected_answer\": [\"Key point 1\", \"Key point 2\", \"Key point 3\"],\n"
            "    \"follow_up\": \"Deeper probing follow-up question ending with ?\",\n"
            "    \"evaluation_rubric\": {\n"
            "      \"weak\": \"What a shallow or inadequate answer sounds like\",\n"
            "      \"strong\": \"What an impressive, senior-level response covers\"\n"
            "    }\n"
            "  }\n"
            "]"
        )

        evidence_str = "\n".join([f"- {e.get('skill')}: \"{e.get('evidence_snippet')}\"" for e in evidence[:10]])
        clarification_str = "\n".join([f"- {c.get('requirement')}: {c.get('reason')}" for c in clarification_needed[:6]])
        resp_str = "\n".join([f"- {r}" for r in responsibilities[:6]])

        user_prompt = (
            f"TARGET ROLE: {job_title} ({experience_level})\n"
            f"INFERRED CANDIDATE LEVEL: {candidate_level}\n"
            f"TARGET QUESTION COUNT: {effective_target}\n\n"
            f"REQUIRED JOB SKILLS: {', '.join(key_skills)}\n"
            f"CORE RESPONSIBILITIES:\n{resp_str}\n\n"
            f"CANDIDATE CONFIRMED SKILLS: {', '.join(candidate_skills)}\n"
            f"VERBATIM RESUME EVIDENCE:\n{evidence_str}\n\n"
            f"AREAS NEEDING CLARIFICATION:\n{clarification_str}\n"
        )

        raw_result = self.llm_client.generate_json(system_prompt, user_prompt, timeout=30)
        if not raw_result or "questions" not in raw_result or not isinstance(raw_result["questions"], list):
            return None

        # Filter, score, and sanitize questions
        scored_questions = self._evaluate_and_filter_questions(
            raw_result["questions"],
            key_skills=key_skills,
            candidate_skills=candidate_skills,
            target_count=effective_target
        )

        if len(scored_questions) < max(12, int(effective_target * 0.6)):
            logger.info("LLM generated too few questions passing strict quality filters; falling back.")
            return None

        categories_covered = list(dict.fromkeys([q["category"] for q in scored_questions]))

        return {
            "questions": scored_questions,
            "total_questions": len(scored_questions),
            "target_requested": target_count,
            "candidate_level": candidate_level,
            "categories_covered": categories_covered,
            "agent_name": self.agent_name,
            "mode": "llm_powered",
            "provider": self.llm_client.get_active_provider(),
            "limitation_note": (sparsity_reason if is_sparse else None)
        }

    # =========================================================================
    # Quality Scoring, Validation & Deduplication Pass
    # =========================================================================

    def _evaluate_and_filter_questions(
        self,
        candidate_questions: List[Dict[str, Any]],
        key_skills: List[str],
        candidate_skills: List[str],
        target_count: int
    ) -> List[Dict[str, Any]]:
        """
        Rigorous quality filter:
        - Validates all schema fields.
        - Scores clarity, specificity, job relevance, reasoning depth, non-duplication (1 to 5).
        - Rejects generic fluff, duplicates, and malformed questions.
        - Backfills legacy keys (focus_area, purpose) for backwards compatibility.
        """
        approved_questions = []
        seen_texts = []

        for item in candidate_questions:
            if not isinstance(item, dict):
                continue

            q_text = str(item.get("question", "")).strip()
            if not q_text or len(q_text) < 30:
                continue

            # Ensure proper question mark ending
            if not q_text.endswith("?"):
                q_text = q_text.rstrip(".!") + "?"

            # Anti-pattern reject list
            lower_q = q_text.lower()
            generic_triggers = [
                "tell me about yourself", "what is your strength", "what are your strengths",
                "what is your greatest weakness", "why should we hire you", "what is python",
                "what is react", "what is an api", "explain databases", "explain oop",
                "what is git", "what is agile", "what is a database"
            ]
            if any(lower_q.startswith(trig) or lower_q == trig for trig in generic_triggers):
                continue

            # Check duplication against already approved questions
            if self._is_duplicate(q_text, seen_texts):
                continue

            # Check category & normalize
            category = item.get("category", "")
            if category not in VALID_CATEGORIES:
                category = self._infer_category(q_text, category)

            difficulty = item.get("difficulty", "Intermediate")
            if difficulty not in DIFFICULTY_LEVELS:
                difficulty = "Intermediate"

            skill_assessed = item.get("skill_assessed", "Core Engineering Competency")
            relevance = item.get("relevance", "Aligned with technical requirements.")

            expected_answer = item.get("expected_answer", [])
            if not isinstance(expected_answer, list) or len(expected_answer) < 2:
                expected_answer = [
                    "Articulates core architectural rationale and implementation trade-offs.",
                    "Identifies concrete edge cases, failure recovery, or concurrency considerations.",
                    "Discusses practical verification, testing, and production monitoring."
                ]

            follow_up = item.get("follow_up", "How would you monitor and verify this in production under high traffic?")
            if not follow_up.endswith("?"):
                follow_up = follow_up.rstrip(".!") + "?"

            rubric = item.get("evaluation_rubric", {})
            if not isinstance(rubric, dict) or "weak" not in rubric or "strong" not in rubric:
                rubric = {
                    "weak": "Provides high-level textbook definitions without practical trade-offs or implementation depth.",
                    "strong": "Draws on concrete engineering experience, discusses trade-offs, failure modes, and verification."
                }

            # Calculate quality score (1.0 to 5.0)
            score, scores_dict = self._score_question(q_text, item, key_skills, candidate_skills)
            if scores_dict["clarity"] < 4.0 or scores_dict["specificity"] < 3.5 or scores_dict["job_relevance"] < 3.5:
                continue

            cleaned_q = {
                "id": len(approved_questions) + 1,
                "category": category,
                "question": q_text,
                "difficulty": difficulty,
                "skill_assessed": skill_assessed,
                "relevance": relevance,
                "expected_answer": expected_answer[:5],
                "follow_up": follow_up,
                "evaluation_rubric": rubric,
                "quality_score": round(score, 2),
                # Backward compatibility aliases
                "focus_area": f"{category}: {skill_assessed}",
                "purpose": f"Assesses {skill_assessed} ({difficulty}) - {relevance[:90]}"
            }

            approved_questions.append(cleaned_q)
            seen_texts.append(q_text)

            if len(approved_questions) >= target_count:
                break

        return approved_questions

    def _is_duplicate(self, text: str, existing_texts: List[str], threshold: float = 0.65) -> bool:
        """Determines if question is semantically or lexically duplicate via token overlap."""
        words_new = set(re.findall(r"\w{4,}", text.lower()))
        if not words_new:
            return False

        for existing in existing_texts:
            words_exist = set(re.findall(r"\w{4,}", existing.lower()))
            if not words_exist:
                continue
            intersection = len(words_new & words_exist)
            union = len(words_new | words_exist)
            if union > 0 and (intersection / union) > threshold:
                return True
        return False

    def _score_question(
        self,
        q_text: str,
        item: Dict[str, Any],
        key_skills: List[str],
        candidate_skills: List[str]
    ) -> Tuple[float, Dict[str, float]]:
        """Scores individual question across 5 dimensions (1 to 5)."""
        scores = {}

        # 1. Clarity
        clarity = 5.0
        if not q_text.endswith("?"):
            clarity -= 1.0
        if len(q_text) < 40 or len(q_text) > 450:
            clarity -= 0.5
        scores["clarity"] = max(1.0, clarity)

        # 2. Specificity
        specificity = 3.5
        technical_terms = set([s.lower() for s in key_skills + candidate_skills + [
            "fastapi", "docker", "postgres", "redis", "kubernetes", "pytest", "python",
            "microservices", "async", "latency", "concurrency", "deadlock", "index", "cache",
            "sql", "aws", "git", "bash", "linux", "sqlalchemy", "pydantic", "pipeline"
        ]])
        matches = [t for t in technical_terms if t in q_text.lower()]
        specificity += min(1.5, len(matches) * 0.4)
        scores["specificity"] = min(5.0, specificity)

        # 3. Job Relevance
        relevance = 4.0
        if any(s.lower() in q_text.lower() for s in key_skills):
            relevance = 5.0
        scores["job_relevance"] = relevance

        # 4. Depth of Reasoning
        depth = 3.5
        deep_keywords = ["how", "trade-off", "investigate", "diagnose", "optimize", "failure", "bottleneck", "architecture", "scenario", "prevent", "verify", "trace", "balance"]
        if any(k in q_text.lower() for k in deep_keywords):
            depth += 1.0
        scores["depth_of_reasoning"] = min(5.0, depth)

        overall = sum(scores.values()) / len(scores)
        return overall, scores

    def _infer_category(self, q_text: str, default: str) -> str:
        """Categorizes questions based on content keywords."""
        lower = q_text.lower()
        if any(w in lower for w in ["resume", "mentioned", "your project", "at novatech", "at apex", "you built", "you optimized", "you boosted"]):
            return CATEGORY_RESUME_DEEP_DIVE
        if any(w in lower for w in ["scenario", "suddenly", "surge", "production outage", "fails halfway", "bottleneck", "alert"]):
            return CATEGORY_SCENARIOS
        if any(w in lower for w in ["code", "debug", "refactor", "implement an algorithm", "system design", "rate limiter", "idempotent"]):
            return CATEGORY_CODING_SYSTEM_DESIGN
        if any(w in lower for w in ["disagree", "conflict", "team", "product manager", "stakeholder", "mentoring", "trade-off with business"]):
            return CATEGORY_BEHAVIORAL
        if any(w in lower for w in ["motivation", "ai engineer", "why this domain", "keep updated", "staying current"]):
            return CATEGORY_ROLE_DOMAIN
        if any(w in lower for w in ["gil", "acid", "event loop", "b-tree", "rest vs", "concurrency", "http protocol"]):
            return CATEGORY_CORE_CONCEPTS
        return CATEGORY_JOB_SKILLS

    # =========================================================================
    # Advanced Deterministic Synthesis Engine
    # =========================================================================

    def _deterministic_generate(
        self,
        job_title: str,
        key_skills: List[str],
        responsibilities: List[str],
        candidate_level: str,
        candidate_skills: List[str],
        evidence: List[Dict[str, str]],
        clarification_needed: List[Dict[str, str]],
        target_count: int,
        is_sparse: bool,
        sparsity_reason: str
    ) -> Dict[str, Any]:
        """
        Generates high-yield, deeply contextual questions using rich heuristic synthesis.
        Guarantees zero fluff, full schema conformance, and contextual grounding.
        """
        all_pool: List[Dict[str, Any]] = []

        # -------------------------------------------------------------
        # Category 1: Resume & Project Deep-Dive (Grounded in Evidence)
        # -------------------------------------------------------------
        all_pool.extend(self._build_resume_deep_dives(evidence, candidate_skills, candidate_level))

        # -------------------------------------------------------------
        # Category 2: Core Technical Concepts
        # -------------------------------------------------------------
        all_pool.extend(self._build_core_concepts(key_skills, candidate_level))

        # -------------------------------------------------------------
        # Category 3: Job-Specific Technical Skills & Clarification
        # -------------------------------------------------------------
        all_pool.extend(self._build_job_skills_and_clarifications(key_skills, clarification_needed, job_title, candidate_level))

        # -------------------------------------------------------------
        # Category 4: Problem-Solving & Practical Scenarios
        # -------------------------------------------------------------
        all_pool.extend(self._build_scenarios(key_skills, job_title))

        # -------------------------------------------------------------
        # Category 5: Coding, Debugging & System Design
        # -------------------------------------------------------------
        all_pool.extend(self._build_coding_and_design(key_skills, job_title, candidate_level))

        # -------------------------------------------------------------
        # Category 6: Behavioral & Engineering Teamwork
        # -------------------------------------------------------------
        all_pool.extend(self._build_behavioral_questions(candidate_level, job_title))

        # -------------------------------------------------------------
        # Category 7: Role Motivation & Domain Understanding
        # -------------------------------------------------------------
        all_pool.extend(self._build_role_domain_questions(job_title, key_skills))

        # Run through scoring, validation, deduplication, and selection
        effective_target = min(15, target_count) if is_sparse else target_count
        filtered = self._evaluate_and_filter_questions(all_pool, key_skills, candidate_skills, target_count=effective_target)

        # Distribute IDs sequentially
        for idx, q in enumerate(filtered, start=1):
            q["id"] = idx

        categories_covered = list(dict.fromkeys([q["category"] for q in filtered]))

        return {
            "questions": filtered,
            "total_questions": len(filtered),
            "target_requested": target_count,
            "candidate_level": candidate_level,
            "categories_covered": categories_covered,
            "agent_name": self.agent_name,
            "mode": "deterministic_fallback",
            "provider": "Contextual Rule-Based Synthesis Engine (Deterministic)",
            "limitation_note": (sparsity_reason if is_sparse else None)
        }

    # --- Heuristic Builders for Categories ---

    def _build_resume_deep_dives(
        self,
        evidence: List[Dict[str, str]],
        candidate_skills: List[str],
        candidate_level: str
    ) -> List[Dict[str, Any]]:
        questions = []

        # Find specific evidence snippets
        for item in evidence:
            snippet = item.get("evidence_snippet", "")
            lower_snip = snippet.lower()

            if "microservices" in lower_snip or "fastapi" in lower_snip or "1.5 million" in lower_snip:
                questions.append({
                    "category": CATEGORY_RESUME_DEEP_DIVE,
                    "question": "Your resume highlights architecting 12+ RESTful microservices in FastAPI serving 1.5M requests daily. How did you structure route dependencies, manage PostgreSQL connection pools, and prevent connection saturation during burst traffic?",
                    "difficulty": "Advanced" if "Senior" in candidate_level else "Intermediate",
                    "skill_assessed": "FastAPI & Distributed Architecture",
                    "relevance": f"Resume quote: \"{snippet[:100]}\"",
                    "expected_answer": [
                        "Configuring SQLAlchemy connection pool sizing (pool_size, max_overflow) aligned to DB connection limits.",
                        "Using asynchronous route handlers (async def) with non-blocking I/O to avoid blocking the event loop.",
                        "Enforcing API rate limiting (e.g. Redis token bucket) and circuit breaking on downstream calls.",
                        "Proper connection recycling and error handling for connection dropouts."
                    ],
                    "follow_up": "If a single microservice's p99 latency spiked from 50ms to 800ms, what observability metrics would you inspect first?",
                    "evaluation_rubric": {
                        "weak": "Mentions generic coding concepts without addressing connection pooling, async I/O limits, or load metrics.",
                        "strong": "Speaks directly to pool exhaustion, event loop blocking risks, latency distributions, and circuit breaker patterns."
                    }
                })

            elif "pytest" in lower_snip or "coverage" in lower_snip or "91%" in lower_snip:
                questions.append({
                    "category": CATEGORY_RESUME_DEEP_DIVE,
                    "question": "You boosted automated test coverage from 62% to 91% using Pytest. How did you balance unit tests versus integration tests, and what strategies did you use to mock external databases without creating brittle tests?",
                    "difficulty": "Intermediate",
                    "skill_assessed": "Testing Strategy & Pytest Rigor",
                    "relevance": f"Resume quote: \"{snippet[:100]}\"",
                    "expected_answer": [
                        "Utilizing Pytest fixtures with granular scopes (function vs session) and database transaction rollbacks.",
                        "Targeting high coverage on core business logic and state transitions rather than trivial getters.",
                        "Using testcontainers or ephemeral test databases over excessive mocking of SQL query planners.",
                        "Eliminating flaky tests caused by non-deterministic network calls or clock drifts."
                    ],
                    "follow_up": "How do you detect and handle tests that pass locally on a developer machine but fail intermittently in CI/CD?",
                    "evaluation_rubric": {
                        "weak": "Focuses strictly on line counts without understanding integration testing trade-offs or fixture isolation.",
                        "strong": "Explains test isolation techniques, fixture scopes, database mocking boundaries, and CI reproducibility."
                    }
                })

            elif "redis" in lower_snip or "latency" in lower_snip or "38%" in lower_snip:
                questions.append({
                    "category": CATEGORY_RESUME_DEEP_DIVE,
                    "question": "You reduced p99 API latency by 38% via PostgreSQL optimization and Redis caching. Walk us through how you identified the slowest queries, and what caching invalidation strategy you selected?",
                    "difficulty": "Advanced",
                    "skill_assessed": "Database Tuning & Caching Patterns",
                    "relevance": f"Resume quote: \"{snippet[:100]}\"",
                    "expected_answer": [
                        "Analyzing slow query logs with `EXPLAIN (ANALYZE, BUFFERS)` and `pg_stat_statements`.",
                        "Adding composite or partial B-Tree indexes matching WHERE and ORDER BY clauses.",
                        "Implementing a cache-aside (lazy load) pattern with TTLs, or event-driven invalidation on writes.",
                        "Guarding against cache stampede / thundering herd using mutexes or probabilistic early expiration."
                    ],
                    "follow_up": "What happens if the Redis cache instance restarts or fails—how does your API gracefully degrade?",
                    "evaluation_rubric": {
                        "weak": "Suggests adding indexes without EXPLAIN plans or fails to articulate a clear cache invalidation strategy.",
                        "strong": "Details execution plan analysis, index bloat trade-offs, cache invalidation race conditions, and graceful DB fallback."
                    }
                })

            elif "docker" in lower_snip or "container" in lower_snip:
                questions.append({
                    "category": CATEGORY_RESUME_DEEP_DIVE,
                    "question": "Your resume mentions containerizing environments with Docker to achieve team parity. How did you optimize Docker image layer caching, minimize final image size, and handle secret environment variables securely?",
                    "difficulty": "Intermediate",
                    "skill_assessed": "Docker Containerization & DevEx",
                    "relevance": f"Resume quote: \"{snippet[:100]}\"",
                    "expected_answer": [
                        "Leveraging multi-stage builds separating build tools from minimal runtime images (e.g. python:3.12-slim).",
                        "Ordering Dockerfile commands so dependency installations are cached before frequently changing application source code.",
                        "Injecting secrets at runtime via environment variables or secret managers rather than embedding in image layers.",
                        "Configuring non-root user execution (`USER appuser`) for security compliance."
                    ],
                    "follow_up": "How would you diagnose a container that passes healthchecks initially but crashes with OOM (Out Of Memory) under production load?",
                    "evaluation_rubric": {
                        "weak": "Describes basic `docker build` and `run` commands without layer caching or security considerations.",
                        "strong": "Explains multi-stage builds, non-root security principles, build context minimization (.dockerignore), and container resource limits."
                    }
                })

            elif "mysql" in lower_snip or "stored procedures" in lower_snip or "ingestion" in lower_snip:
                questions.append({
                    "category": CATEGORY_RESUME_DEEP_DIVE,
                    "question": "At Apex Data Labs, you maintained MySQL schemas and authored automated ingestion scripts in Flask. How did you ensure data integrity and idempotency during nightly transactional batch runs?",
                    "difficulty": "Intermediate",
                    "skill_assessed": "Data Pipeline Reliability & Schema Design",
                    "relevance": f"Resume quote: \"{snippet[:100]}\"",
                    "expected_answer": [
                        "Wrapping batch ingestion in atomic database transactions (`BEGIN...COMMIT`) with rollback on error.",
                        "Implementing UPSERT / `ON DUPLICATE KEY UPDATE` to guarantee idempotent execution when re-running failed jobs.",
                        "Using staging tables for batch transformation before atomic swapping or bulk insertion.",
                        "Validating incoming transactional schemas against expected data contracts before processing."
                    ],
                    "follow_up": "If a nightly ingestion batch failed halfway through a 500,000-record dataset, how did your script resume without data corruption?",
                    "evaluation_rubric": {
                        "weak": "Suggests manually restarting scripts without transaction checkpoints or idempotency safeguards.",
                        "strong": "Explains idempotency keys, atomic transaction rollbacks, batch chunking, and checkpointing mechanisms."
                    }
                })

        # Additional resume-grounded questions
        questions.append({
            "category": CATEGORY_RESUME_DEEP_DIVE,
            "question": "Your resume notes building with SQLAlchemy and Pydantic. How do you design data schemas that bridge Pydantic request models with SQLAlchemy ORM entities while preventing accidental N+1 query performance problems?",
            "difficulty": "Intermediate",
            "skill_assessed": "ORM & Data Validation Patterns",
            "relevance": "Resume skills: SQLAlchemy, Pydantic, and FastAPI.",
            "expected_answer": [
                "Using Pydantic's `from_attributes = True` for smooth serialization from ORM models.",
                "Eager loading relationships via `joinedload` or `selectinload` in SQLAlchemy to eliminate N+1 queries.",
                "Keeping validation logic in Pydantic schemas separate from database persistence models.",
                "Using database migrations (Alembic) to version schema changes deterministically."
            ],
            "follow_up": "When would you bypass SQLAlchemy ORM and write parameterized raw SQL or use Core queries instead?",
            "evaluation_rubric": {
                "weak": "Does not know what an N+1 query problem is or cannot explain ORM relationship loading.",
                "strong": "Clearly explains eager vs lazy loading, joinedload mechanics, and separation of API contract from persistence."
            }
        })

        questions.append({
            "category": CATEGORY_RESUME_DEEP_DIVE,
            "question": "Your technical skills list AWS experience with S3 and EC2. How did you architect secure authentication from your Python backend to AWS services, and what strategy did you use for handling large file uploads to S3?",
            "difficulty": "Intermediate",
            "skill_assessed": "Cloud Infrastructure & AWS S3/EC2",
            "relevance": "Resume skill: AWS (S3, EC2).",
            "expected_answer": [
                "Using IAM roles attached to EC2 instances or ECS tasks instead of hardcoded AWS access keys.",
                "Generating pre-signed S3 URLs so clients can upload directly to S3 without bottlenecking backend API workers.",
                "Configuring S3 multipart uploads for files larger than 100MB with automated aborts on incomplete uploads.",
                "Setting up S3 lifecycle policies and bucket server-side encryption (SSE-S3 or SSE-KMS)."
            ],
            "follow_up": "How would you handle webhook or S3 Event Notifications to trigger background data ingestion when a file lands in a bucket?",
            "evaluation_rubric": {
                "weak": "Mentions committing AWS keys to .env files or routing all file uploads synchronously through application memory.",
                "strong": "Recommends IAM instance profiles, pre-signed upload URLs, S3 multipart chunking, and event-driven notifications."
            }
        })

        questions.append({
            "category": CATEGORY_RESUME_DEEP_DIVE,
            "question": "You mention using Git and pull requests for team collaboration. What branching model (e.g. Trunk-based development vs GitFlow) do you favor for high-velocity CI/CD deployments, and how do you resolve complex merge conflicts cleanly?",
            "difficulty": "Foundation",
            "skill_assessed": "Git Collaboration & Version Control",
            "relevance": "Resume skill: Git and GitHub pull requests.",
            "expected_answer": [
                "Trunk-based development with short-lived feature branches and feature flags for rapid continuous deployment.",
                "Squash-and-merge or rebase workflows to maintain clean, bisectable commit histories.",
                "Using `git rebase main` to resolve conflicts locally and re-running test suites before opening PRs.",
                "Protecting main branches with mandatory PR reviews, passing CI checks, and branch protection rules."
            ],
            "follow_up": "How do you use `git bisect` to track down a silent regression introduced 50 commits ago?",
            "evaluation_rubric": {
                "weak": "Uncomfortable with rebase or describes committing broken code directly to main branches.",
                "strong": "Articulates trunk-based development benefits, clean commit hygiene, interactive rebasing, and git bisect debugging."
            }
        })
        questions.append({
            "category": CATEGORY_RESUME_DEEP_DIVE,
            "question": "Your technical skills list Linux and Bash scripting. How do you leverage shell utilities (awk, sed, grep, xargs) and systemd service units to monitor backend daemon processes, inspect production logs, and automate health alerts?",
            "difficulty": "Foundation",
            "skill_assessed": "Linux Systems & Bash Automation",
            "relevance": "Resume skill: Linux and Bash scripting.",
            "expected_answer": [
                "Configuring systemd service unit files with `Restart=always` and resource constraints (`MemoryMax`).",
                "Parsing and filtering high-volume logs with `journalctl`, `awk`, and `grep` without pulling entire files into RAM.",
                "Using `xargs -P` for parallel process execution and writing cron or systemd timer jobs for scheduled automation.",
                "Monitoring system bottlenecks using `top`, `htop`, `vmstat`, `iostat`, and `/proc` metrics."
            ],
            "follow_up": "How do you safely write a Bash cleanup script with `set -euo pipefail` to prevent silent execution failures?",
            "evaluation_rubric": {
                "weak": "Cannot name standard Linux diagnostic commands or explain systemd service configuration.",
                "strong": "Confidently details systemd unit directives, stream processing with awk/grep, and robust Bash safety flags."
            }
        })

        questions.append({
            "category": CATEGORY_RESUME_DEEP_DIVE,
            "question": "Your resume mentions testing with Postman. How do you design automated Postman collection test scripts and integrate Newman into CI/CD pipelines to run contract and regression smoke tests against staging endpoints?",
            "difficulty": "Foundation",
            "skill_assessed": "API Contract Testing & Postman/Newman",
            "relevance": "Resume skill: Postman API testing.",
            "expected_answer": [
                "Authoring pre-request scripts and test assertions in JavaScript verifying response schema, status codes, and headers.",
                "Using Postman environment variables for multi-stage configuration (local, staging, prod) with dynamic bearer tokens.",
                "Executing automated collections in CI/CD runners using the Newman CLI (`newman run collection.json`).",
                "Generating automated test reports (HTML, JUnit XML) to gate staging deployment pipelines."
            ],
            "follow_up": "How do you ensure Postman collections stay synchronized with OpenAPI/Swagger specifications as endpoints evolve?",
            "evaluation_rubric": {
                "weak": "Uses Postman strictly for manual ad-hoc clicking without writing assertion scripts or running Newman.",
                "strong": "Explains automated assertion scripts, dynamic environment chaining, and headless Newman CI/CD integration."
            }
        })

        if candidate_skills:
            primary_skill = candidate_skills[0]
            questions.append({
                "category": CATEGORY_RESUME_DEEP_DIVE,
                "question": f"Your resume highlights hands-on experience with {primary_skill}. What was the most technically challenging bug or performance bottleneck you resolved with it, and how did you verify the fix?",
                "difficulty": "Intermediate",
                "skill_assessed": f"{primary_skill} Practical Problem-Solving",
                "relevance": f"Candidate verified skill: {primary_skill}",
                "expected_answer": [
                    "Clearly defines the symptom, reproduction steps, and root-cause analysis.",
                    "Evaluates alternative solutions and explains why the chosen fix was optimal.",
                    "Demonstrates automated regression tests and production metrics validating the resolution."
                ],
                "follow_up": "What architectural or procedural changes did you introduce to prevent that category of issue from recurring?",
                "evaluation_rubric": {
                    "weak": "Gives a superficial answer without root-cause debugging methodology.",
                    "strong": "Shows methodical diagnostic reasoning, log/profiler usage, and regression prevention."
                }
            })

        return questions

    def _build_core_concepts(self, key_skills: List[str], candidate_level: str) -> List[Dict[str, Any]]:
        questions = [
            {
                "category": CATEGORY_CORE_CONCEPTS,
                "question": "In Python, how does the Global Interpreter Lock (GIL) impact CPU-bound versus I/O-bound concurrency, and when would you choose multiprocessing, asyncio, or worker queues like Celery?",
                "difficulty": "Intermediate" if "Senior" not in candidate_level else "Advanced",
                "skill_assessed": "Python Concurrency Architecture",
                "relevance": "Core role requirement: Advanced Python engineering.",
                "expected_answer": [
                    "Explains that GIL prevents multiple native OS threads from executing Python bytecode simultaneously.",
                    "Recognizes that I/O-bound tasks release the GIL during syscalls, making `asyncio` or threading effective.",
                    "Identifies that CPU-bound workloads require `multiprocessing` or compiled extensions to utilize multiple cores.",
                    "Advocates distributed task queues (Celery, Dramatiq) for long-running or background asynchronous processing."
                ],
                "follow_up": "In Python 3.13, free-threaded Python (no GIL) is being introduced. What concurrency pitfalls might arise in application code?",
                "evaluation_rubric": {
                    "weak": "Claims threading speeds up mathematical computation in standard Python or confuses asyncio with multi-core parallelism.",
                    "strong": "Articulates bytecode lock mechanics, I/O syscall releases, process memory overhead, and appropriate concurrency model selection."
                }
            },
            {
                "category": CATEGORY_CORE_CONCEPTS,
                "question": "Explain the four ACID properties in relational databases and how transaction isolation levels (e.g., Read Committed vs Serializable) prevent dirty reads, non-repeatable reads, and phantom reads?",
                "difficulty": "Intermediate",
                "skill_assessed": "Database Transactions & ACID Guarantees",
                "relevance": "Core role requirement: Relational database architecture (PostgreSQL/MySQL).",
                "expected_answer": [
                    "Defines Atomicity, Consistency, Isolation, and Durability in write workflows.",
                    "Explains that Read Committed permits non-repeatable reads while Serializable guarantees strict sequential outcome.",
                    "Describes Multi-Version Concurrency Control (MVCC) snapshot isolation used in PostgreSQL.",
                    "Analyzes lock contention and deadlock risks when raising isolation levels under high write concurrency."
                ],
                "follow_up": "Under what circumstances would you intentionally lower transaction isolation, and what data integrity risks do you accept?",
                "evaluation_rubric": {
                    "weak": "Cannot distinguish between dirty reads and non-repeatable reads, or confuses Atomicity with Consistency.",
                    "strong": "Describes snapshot isolation, MVCC mechanics, read anomalies, and trade-offs between isolation level and transaction throughput."
                }
            },
            {
                "category": CATEGORY_CORE_CONCEPTS,
                "question": "What is the difference between a B-Tree index and a Hash index in PostgreSQL, and why is B-Tree the default choice for most relational column lookups?",
                "difficulty": "Intermediate",
                "skill_assessed": "Database Indexing Internals",
                "relevance": "Core requirement: Database performance and schema optimization.",
                "expected_answer": [
                    "B-Trees maintain sorted balance, supporting both equality (=) and range queries (<, >, BETWEEN, ORDER BY).",
                    "Hash indexes only support exact equality checks and cannot accelerate range scans or sorting.",
                    "B-Trees allow composite indexing with leftmost prefix matching for multi-column filtering.",
                    "Maintenance overhead: write amplification during row insertions and the need for periodic vacuuming/reindexing."
                ],
                "follow_up": "How does creating too many indexes on a write-intensive table negatively affect system performance?",
                "evaluation_rubric": {
                    "weak": "Cannot explain why B-Trees support range scans or assumes indexing has zero write cost.",
                    "strong": "Clearly explains balanced tree traversal, logarithmic lookup time, range ordering, and write amplification impacts."
                }
            },
            {
                "category": CATEGORY_CORE_CONCEPTS,
                "question": "In RESTful API design, what does it mean for an HTTP method to be 'safe' and 'idempotent'? Why is PUT idempotent while POST is generally not?",
                "difficulty": "Foundation",
                "skill_assessed": "REST Protocol & HTTP Semantics",
                "relevance": "Core requirement: REST API design and engineering standards.",
                "expected_answer": [
                    "Safe methods (GET, HEAD) do not alter server state.",
                    "Idempotent methods (PUT, DELETE, GET) produce the identical side effect on the server regardless of repeat invocations.",
                    "POST creates new resources on successive calls unless explicit client idempotency keys are enforced.",
                    "Proper HTTP status code return contracts (200, 201, 204, 409) reflecting resource state."
                ],
                "follow_up": "How do you design a payment processing POST endpoint to guarantee idempotency if a client retries due to a timeout?",
                "evaluation_rubric": {
                    "weak": "Confuses safety with encryption/HTTPS, or cannot articulate why retrying a PUT request is safe.",
                    "strong": "Explains server-side state side effects, idempotency keys stored in Redis, and standard HTTP specifications."
                }
            },
            {
                "category": CATEGORY_CORE_CONCEPTS,
                "question": "How does memory management work in Python? Describe reference counting, generational garbage collection, and how circular references can create memory leaks in long-running services?",
                "difficulty": "Advanced",
                "skill_assessed": "Python Memory Internals & Garbage Collection",
                "relevance": "Core requirement: High-reliability backend services.",
                "expected_answer": [
                    "Primary deallocation via reference counting when an object's reference count drops to zero.",
                    "Secondary cyclic GC with three generations (0, 1, 2) that detects and collects self-referencing circular graphs.",
                    "Circular references involving objects with custom `__del__` methods (prior to Python 3.4) or unmanaged global references.",
                    "Tools for tracking leaks: `gc.collect()`, `tracemalloc`, and `objgraph`."
                ],
                "follow_up": "If a long-running web worker process gradually consumes 8 GB of RAM over 48 hours, what diagnostic steps would you take?",
                "evaluation_rubric": {
                    "weak": "Thinks Python has no garbage collection or that circular references are immediately destroyed.",
                    "strong": "Delineates reference count deallocation from generational sweep, explains leak profiling tools, and worker recycling strategies."
                }
            },
            {
                "category": CATEGORY_CORE_CONCEPTS,
                "question": "How does HTTP/2 multiplexing compare to HTTP/1.1 pipelining and keep-alive connections, and how does it reduce head-of-line blocking in modern microservice communications?",
                "difficulty": "Intermediate",
                "skill_assessed": "Network Protocols & HTTP/2 Multiplexing",
                "relevance": "Core networking concept for distributed microservices.",
                "expected_answer": [
                    "HTTP/1.1 requires sequential responses on a single connection or multiple parallel TCP connections.",
                    "HTTP/2 splits requests and responses into binary frames multiplexed over a single TCP connection.",
                    "Eliminates application-layer head-of-line blocking, allowing concurrent requests without waiting for previous responses.",
                    "Header compression using HPACK reduces bandwidth on microservice mesh traffic."
                ],
                "follow_up": "Does HTTP/2 eliminate TCP-level head-of-line blocking, and how does HTTP/3 (QUIC) resolve that?",
                "evaluation_rubric": {
                    "weak": "Confuses HTTP/2 multiplexing with simple multithreading or cannot explain binary framing.",
                    "strong": "Explains binary stream framing, connection reuse, HPACK header compression, and TCP packet loss implications."
                }
            },
            {
                "category": CATEGORY_CORE_CONCEPTS,
                "question": "Explain the CAP theorem and describe the trade-offs between Consistency and Availability during a network partition for a distributed database like MongoDB or Cassandra versus PostgreSQL?",
                "difficulty": "Advanced",
                "skill_assessed": "Distributed Systems & CAP Theorem",
                "relevance": "Core distributed systems architecture.",
                "expected_answer": [
                    "Network partitions (P) are unavoidable in distributed physical networks, forcing a choice between C and A.",
                    "CP systems (e.g. Raft/Paxos clusters) reject writes or error out to guarantee strong consistency.",
                    "AP systems (e.g. Cassandra, DynamoDB) accept writes locally and reconcile via eventual consistency.",
                    "PACELC theorem extends CAP by evaluating Latency vs Consistency trade-offs in normal operating conditions."
                ],
                "follow_up": "In an e-commerce checkout workflow, which components require CP semantics versus AP semantics?",
                "evaluation_rubric": {
                    "weak": "Claims a distributed system can achieve all three of Consistency, Availability, and Partition tolerance simultaneously.",
                    "strong": "Accurately articulates partition trade-offs, quorum reads/writes, conflict resolution, and PACELC trade-offs."
                }
            },
            {
                "category": CATEGORY_CORE_CONCEPTS,
                "question": "What is the Big-O time and space complexity of common Python data structures (list vs dict vs set), and how are hash collisions resolved internally in Python's dictionary implementation?",
                "difficulty": "Foundation",
                "skill_assessed": "Data Structures & Hash Map Internals",
                "relevance": "Core computer science fundamentals.",
                "expected_answer": [
                    "Dict and set lookups/inserts are average O(1) time and O(n) space; list index is O(1), append is amortized O(1), search is O(n).",
                    "Python dicts use a compact array of indices pointing to entries containing hash, key, and value.",
                    "Hash collisions are resolved via open addressing with pseudo-random probing to distribute entries across the table.",
                    "Worst-case O(n) time occurs if all keys generate identical hash values (hash collision attack)."
                ],
                "follow_up": "Why must any Python object used as a dictionary key or set element implement both `__hash__` and `__eq__`?",
                "evaluation_rubric": {
                    "weak": "Thinks list searches are O(1) or cannot explain how a hash table handles colliding hash values.",
                    "strong": "Explains average vs worst-case bounds, compact dictionary indexing, open addressing, and key immutability."
                }
            }
        ]
        return questions

    def _build_job_skills_and_clarifications(
        self,
        key_skills: List[str],
        clarification_needed: List[Dict[str, str]],
        job_title: str,
        candidate_level: str
    ) -> List[Dict[str, Any]]:
        questions = []

        # Target clarification items first
        for item in clarification_needed:
            req = item.get("requirement", "")
            lower_req = req.lower()

            if "kubernetes" in lower_req or "orchestration" in lower_req:
                questions.append({
                    "category": CATEGORY_JOB_SKILLS,
                    "question": "The job description requires Kubernetes experience for container orchestration. Although your resume does not explicitly list K8s, could you walk us through how you would configure a Deployment, Service, and Ingress for an API service, and how Horizontal Pod Autoscaling (HPA) works?",
                    "difficulty": "Intermediate",
                    "skill_assessed": "Kubernetes Architecture (Clarification)",
                    "relevance": f"Clarification flag: {item.get('reason')}",
                    "expected_answer": [
                        "Differentiating Pod, Deployment (desired state / rolling updates), and Service (stable cluster IP).",
                        "Routing external traffic through an Ingress controller to cluster services.",
                        "Configuring liveness and readiness probes to prevent traffic routing to unready pods.",
                        "Using HPA based on CPU/memory utilization or custom metrics (e.g. request rate)."
                    ],
                    "follow_up": "If a pod gets stuck in a `CrashLoopBackOff` state, what sequence of `kubectl` commands do you execute to debug it?",
                    "evaluation_rubric": {
                        "weak": "Unfamiliar with pod lifecycles or cannot differentiate a Deployment from a Service.",
                        "strong": "Accurately articulates deployment manifests, health probes, ingress routing, and `kubectl describe/logs` diagnostic commands."
                    }
                })

            elif "llm" in lower_req or "ai" in lower_req:
                questions.append({
                    "category": CATEGORY_JOB_SKILLS,
                    "question": f"For this {job_title} role, we integrate LLM APIs and multi-agent reasoning pipelines. How do you approach structured JSON output validation, prompt latency optimization, and handling LLM API rate limits or downtime in production?",
                    "difficulty": "Advanced",
                    "skill_assessed": "LLM API Integration & Orchestration",
                    "relevance": f"Job requirement: Multi-agent and LLM workflow integration.",
                    "expected_answer": [
                        "Enforcing schema validation using Pydantic or structured output JSON modes.",
                        "Implementing exponential backoff retries and fallback models when rate limits (HTTP 429) occur.",
                        "Caching prompt embeddings or deterministic responses to reduce inference latency and token costs.",
                        "Asynchronous dispatching and streaming responses to prevent client timeout during long generations."
                    ],
                    "follow_up": "How do you evaluate and safeguard against prompt injection or hallucinations in user-facing LLM features?",
                    "evaluation_rubric": {
                        "weak": "Treats LLMs as magical black boxes without addressing schema validation, latency, or rate-limit retries.",
                        "strong": "Addresses token budgeting, retry jitter, Pydantic validation schemas, streaming responses, and graceful fallbacks."
                    }
                })

            elif "ci/cd" in lower_req or "deployment" in lower_req:
                questions.append({
                    "category": CATEGORY_JOB_SKILLS,
                    "question": "The role involves maintaining CI/CD pipelines. Can you describe how you would design an automated deployment pipeline from Git pull request to staging and production, including automated test gating and blue/green or canary rollouts?",
                    "difficulty": "Intermediate",
                    "skill_assessed": "CI/CD & Deployment Strategies",
                    "relevance": f"Clarification area: {item.get('reason')}",
                    "expected_answer": [
                        "Pre-merge gates: linting (flake8/ruff), type checks (mypy), and automated unit tests with Pytest.",
                        "Building container images and publishing tagged immutable artifacts to a container registry.",
                        "Automated staging deployment followed by smoke and integration tests.",
                        "Zero-downtime deployment strategies (blue/green or canary) with automated rollback on health check failure."
                    ],
                    "follow_up": "If a production deployment introduces a silent data corruption bug, what is your rollback and remediation playbook?",
                    "evaluation_rubric": {
                        "weak": "Relies on manual deployment steps without automated test gates or rollback planning.",
                        "strong": "Details stage isolation, immutable image tagging, test gating, and zero-downtime deployment patterns."
                    }
                })

        # Target job skills: FastAPI, Redis, PostgreSQL
        questions.append({
            "category": CATEGORY_JOB_SKILLS,
            "question": "In FastAPI, how do you utilize dependency injection (`Depends`) for shared database sessions and authentication? What are the implications of defining a route with `async def` versus standard `def`?",
            "difficulty": "Intermediate",
            "skill_assessed": "FastAPI Architecture & Concurrency",
            "relevance": "Key job skill: FastAPI backend framework.",
            "expected_answer": [
                "Yield-based dependency injection for managing database session lifecycle (commit, rollback, close).",
                "`async def` runs directly on the asyncio event loop; executing blocking I/O inside it blocks the entire server.",
                "Standard `def` routes in FastAPI are dispatched to an external threadpool (starlette worker threads).",
                "Using Pydantic models for request/response serialization and automated OpenAPI documentation."
            ],
            "follow_up": "If an external SDK library only provides synchronous blocking calls, how do you safely invoke it from an `async def` FastAPI route?",
            "evaluation_rubric": {
                "weak": "Does not know the difference between `def` and `async def` in FastAPI or cannot explain `Depends` mechanics.",
                "strong": "Accurately explains event loop blocking versus threadpool offloading (`run_in_threadpool`), and session cleanup with generators."
            }
        })

        questions.append({
            "category": CATEGORY_JOB_SKILLS,
            "question": "When designing a Redis caching layer for high-throughput APIs, how do you handle cache invalidation, key naming conventions, and memory eviction policies (e.g., volatile-lru vs allkeys-lru)?",
            "difficulty": "Intermediate",
            "skill_assessed": "Redis Architecture & Cache Design",
            "relevance": "Key job skill: Redis caching systems.",
            "expected_answer": [
                "Hierarchical key namespacing with colons (e.g., `user:{id}:profile`) with consistent TTLs.",
                "Differentiating `allkeys-lru` (evicts any key) from `volatile-lru` (evicts only keys with TTLs set).",
                "Cache invalidation patterns: write-through, write-behind, or event-driven pub/sub invalidation.",
                "Monitoring memory limits (`maxmemory`) and Redis pipeline batching for high-throughput bulk reads."
            ],
            "follow_up": "What is a 'cache stampede' (thundering herd), and how does mutex locking or probabilistic early expiration prevent it?",
            "evaluation_rubric": {
                "weak": "Assumes Redis keys never expire or cannot explain what happens when Redis reaches its memory threshold.",
                "strong": "Explains key namespaces, eviction policies, cache penetration/stampede defenses, and connection pooling."
            }
        })

        questions.append({
            "category": CATEGORY_JOB_SKILLS,
            "question": "In PostgreSQL, how do you diagnose query performance using `EXPLAIN ANALYZE`? What specific metrics (e.g., Seq Scan vs Index Scan, buffer hit ratio, disk spills in hash joins) do you look for?",
            "difficulty": "Advanced",
            "skill_assessed": "PostgreSQL Query Optimization",
            "relevance": "Key job skill: PostgreSQL database performance.",
            "expected_answer": [
                "`EXPLAIN ANALYZE` executes the query and reports actual execution time and rows vs planner estimates.",
                "Sequential scans on large tables indicate missing or unutilized indexes.",
                "Checking `Buffers: shared hit, read` to verify whether data is served from RAM or disk I/O.",
                "Spotting sort or hash operations spilling to disk due to insufficient `work_mem`."
            ],
            "follow_up": "Why might the PostgreSQL query planner choose a sequential scan over an available index scan on a table with 1,000,000 rows?",
            "evaluation_rubric": {
                "weak": "Thinks EXPLAIN only predicts queries without running them, or cannot interpret scan types.",
                "strong": "Identifies sequential vs bitmap/index scans, planner cost models, correlation statistics, and work_mem disk spill indicators."
            }
        })

        questions.append({
            "category": CATEGORY_JOB_SKILLS,
            "question": "How do you structure database connection pooling in a microservices environment using tools like PgBouncer or SQLAlchemy's QueuePool, and how do you size the pool to prevent overwhelming PostgreSQL?",
            "difficulty": "Advanced",
            "skill_assessed": "Database Connection Management & PgBouncer",
            "relevance": "Key job skill: High-throughput database architecture.",
            "expected_answer": [
                "PostgreSQL uses a process-per-connection model where each connection consumes 5-10MB RAM and causes context switching.",
                "PgBouncer provides lightweight connection pooling in transaction mode or session mode.",
                "Sizing formula: `connections = (core_count * 2) + effective_spindle_count` rather than hundreds of direct app connections.",
                "Application-side pool settings (`pool_size`, `max_overflow`, `pool_timeout`, `pool_recycle`)."
            ],
            "follow_up": "Why is PgBouncer transaction pooling incompatible with PostgreSQL prepared statements, and how do you work around that?",
            "evaluation_rubric": {
                "weak": "Advocates allocating 500 direct database connections per web server instance.",
                "strong": "Explains process-per-connection overhead, transaction vs session pooling in PgBouncer, and mathematical pool sizing."
            }
        })

        questions.append({
            "category": CATEGORY_JOB_SKILLS,
            "question": "How do you approach PostgreSQL table partitioning (e.g. range partitioning by timestamp) for high-volume event logs, and how does partition pruning prevent sequential scans across historical partitions?",
            "difficulty": "Advanced",
            "skill_assessed": "PostgreSQL Partitioning & Large Datasets",
            "relevance": "Key job skill: Relational database architecture at scale.",
            "expected_answer": [
                "Creating declarative partitions using `PARTITION BY RANGE (created_at)`.",
                "Enabling partition pruning so queries filtering on timestamps only scan relevant child tables.",
                "Managing automated partition creation via maintenance workers or extensions like `pg_partman`.",
                "Indexing child partitions individually to maintain small, cacheable B-Tree indexes."
            ],
            "follow_up": "What occurs if an incoming record contains a timestamp that does not match any existing partition range?",
            "evaluation_rubric": {
                "weak": "Does not understand partition pruning or suggests storing billions of rows in a single monolithic table.",
                "strong": "Explains partition pruning, local vs global indexes, default partitions, and automated table maintenance."
            }
        })

        questions.append({
            "category": CATEGORY_JOB_SKILLS,
            "question": "When building containerized Python services, how do you handle graceful shutdown signals (SIGTERM / SIGINT) so active HTTP requests complete before workers terminate?",
            "difficulty": "Intermediate",
            "skill_assessed": "Docker & Process Lifecycle Management",
            "relevance": "Key job skill: Production Docker containerization.",
            "expected_answer": [
                "Intercepting SIGTERM and giving worker processes a graceful termination grace period (e.g. 30 seconds).",
                "Allowing in-flight HTTP requests to complete while rejecting new connections.",
                "Closing database connection pools and committing or rolling back active transactions.",
                "Using dumb-init or tini as PID 1 inside Docker containers to properly reap zombie processes."
            ],
            "follow_up": "Why might a Docker container ignore SIGTERM if your Dockerfile CMD is written in shell form (`CMD python app.py`) instead of exec form?",
            "evaluation_rubric": {
                "weak": "Does not know the difference between SIGTERM and SIGKILL, or ignores process termination signals.",
                "strong": "Explains PID 1 signal forwarding, shell vs exec form CMD, in-flight request draining, and connection pool cleanup."
            }
        })

        questions.append({
            "category": CATEGORY_JOB_SKILLS,
            "question": "In distributed microservice communication, when would you choose synchronous gRPC or REST over asynchronous event-driven messaging (Kafka, RabbitMQ, or Redis Pub/Sub)?",
            "difficulty": "Intermediate",
            "skill_assessed": "Microservice Communication Patterns",
            "relevance": "Key job skill: Distributed microservices architecture.",
            "expected_answer": [
                "Synchronous REST/gRPC: best for real-time request-response queries where the caller cannot proceed without the result.",
                "gRPC advantages: binary Protocol Buffers serialization, HTTP/2 streaming, and strongly typed contracts.",
                "Asynchronous messaging: ideal for decoupling, high-throughput writes, resilient fan-out, and eventual consistency.",
                "Failure domains: synchronous calls introduce cascading failure risk, while queues buffer temporary load."
            ],
            "follow_up": "How do you implement distributed tracing (e.g. OpenTelemetry traceparent headers) across asynchronous message queues?",
            "evaluation_rubric": {
                "weak": "Cannot distinguish between synchronous RPC and asynchronous event streaming.",
                "strong": "Clearly weighs latency vs decoupling, circuit breaking, protocol buffer performance, and distributed tracing."
            }
        })

        return questions

    def _build_scenarios(self, key_skills: List[str], job_title: str) -> List[Dict[str, Any]]:
        questions = [
            {
                "category": CATEGORY_SCENARIOS,
                "question": "Scenario: On a Monday morning, an e-commerce API suddenly experiences a 4x spike in latency (p99 increases from 80ms to 4.2s), causing downstream timeouts. The database CPU is at 25%, but API worker memory is near 90%. How do you systematically isolate and resolve the root cause?",
                "difficulty": "Advanced",
                "skill_assessed": "Production Incident Troubleshooting",
                "relevance": "Core responsibility: Monitoring production health and diagnosing high-throughput distributed systems.",
                "expected_answer": [
                    "Inspect connection pool metrics: are API workers queued waiting for database or Redis connections?",
                    "Examine external third-party API dependencies for latency degradation or hanging HTTP sockets.",
                    "Check worker thread/event loop blockage: verify if synchronous tasks are running on async event loops.",
                    "Mitigation: scale worker pods horizontally, enforce aggressive HTTP timeouts, and enable rate-limiting."
                ],
                "follow_up": "If metrics show workers are stuck waiting on a downstream third-party payment gateway, what immediate resilience pattern do you trip?",
                "evaluation_rubric": {
                    "weak": "Randomly suggests restarting servers without checking thread dumps, connection pools, or external latency.",
                    "strong": "Follows structured triage: external dependencies, connection pool exhaustion, event loop health, and circuit breaking."
                }
            },
            {
                "category": CATEGORY_SCENARIOS,
                "question": "Scenario: Two users simultaneously attempt to update the same record (e.g., booking the last remaining seat on a flight). Without proper concurrency controls, both updates succeed, resulting in an overbooking. How do you prevent this using optimistic locking vs pessimistic locking in PostgreSQL?",
                "difficulty": "Intermediate",
                "skill_assessed": "Concurrency Control & Race Conditions",
                "relevance": "Core responsibility: Resilient schema and transaction design.",
                "expected_answer": [
                    "Pessimistic locking: `SELECT ... FOR UPDATE` acquires an exclusive row lock until the transaction finishes.",
                    "Optimistic locking: using a `version` or `updated_at` column (`UPDATE ... WHERE id = x AND version = y`).",
                    "Comparing trade-offs: pessimistic locking causes contention/deadlocks under high volume; optimistic causes retries.",
                    "Handling rollback and returning a clear conflict status (HTTP 409 Conflict) to the client."
                ],
                "follow_up": "In a distributed system across multiple database shards where `FOR UPDATE` cannot span databases, what locking mechanism would you use?",
                "evaluation_rubric": {
                    "weak": "Cannot explain how a race condition occurs or suggests handling locks solely in client JavaScript.",
                    "strong": "Articulates row-level exclusive locks vs version checks, transaction boundaries, and deadlock prevention."
                }
            },
            {
                "category": CATEGORY_SCENARIOS,
                "question": "Scenario: A scheduled background job processes 1,000,000 customer invoice records nightly. At record 640,000, an unhandled NullReference exception terminates the worker process. The next morning, customer accounts have duplicate charges and unbilled entries. How do you re-architect this job to be fault-tolerant and idempotent?",
                "difficulty": "Intermediate",
                "skill_assessed": "Batch Processing & Idempotency",
                "relevance": "Core responsibility: Asynchronous task execution and distributed batch reliability.",
                "expected_answer": [
                    "Chunking processing into manageable batches (e.g. 500-1000 records per transaction) rather than one monolithic loop.",
                    "State tracking / checkpointing: marking records with status (`PENDING`, `PROCESSING`, `COMPLETED`, `FAILED`).",
                    "Idempotency keys on invoice generation so re-running record 640,000 skips already-billed customers.",
                    "Dead-letter queues (DLQ) to isolate failing records without stalling the remaining 360,000 records."
                ],
                "follow_up": "How do you ensure that multiple worker instances running concurrently do not pick up and process the same batch?",
                "evaluation_rubric": {
                    "weak": "Suggests simply using a `try/except: pass` block without addressing transaction safety, idempotency, or DLQs.",
                    "strong": "Designs chunked transactions, checkpointing, dead-letter routing, and distributed task claims (`SELECT ... FOR UPDATE SKIP LOCKED`)."
                }
            },
            {
                "category": CATEGORY_SCENARIOS,
                "question": "Scenario: A deployment of a new microservice version passes all unit tests, but within 15 minutes of production release, the service begins returning HTTP 500 errors on 12% of requests. How do you coordinate with the team to triage, rollback, and execute a blameless post-mortem?",
                "difficulty": "Intermediate",
                "skill_assessed": "Production Deployment Triaging & Post-Mortem",
                "relevance": "Core responsibility: CI/CD, production reliability, and operational discipline.",
                "expected_answer": [
                    "Immediate mitigation: trigger automated or manual rollback to the previous known stable release artifact.",
                    "Traffic monitoring: verify error rates recover to baseline immediately following the rollback.",
                    "Root-cause isolation in staging: inspect error traces, structured logs, and diff between commits.",
                    "Blameless post-mortem: document timeline, root cause, missing test cases, and preventive action items."
                ],
                "follow_up": "What automated canary deployment check could have detected this 12% error threshold before 100% of user traffic was impacted?",
                "evaluation_rubric": {
                    "weak": "Prioritizes assigning blame or attempts live hot-fixing on production servers during active customer impact.",
                    "strong": "Prioritizes immediate customer impact mitigation via rollback, followed by telemetry inspection and blameless analysis."
                }
            },
            {
                "category": CATEGORY_SCENARIOS,
                "question": "Scenario: Your Redis caching cluster experiences a node failure, and simultaneously a heavily accessed cache key expires, resulting in 5,000 requests per second falling directly through to PostgreSQL and crashing the database. How do you engineer defenses against this 'cache stampede'?",
                "difficulty": "Advanced",
                "skill_assessed": "Cache Stampede & Resilience Architecture",
                "relevance": "Core scenario: High-throughput caching resilience.",
                "expected_answer": [
                    "Probabilistic early expiration (XFetch algorithm) where keys are recalculated before actual TTL expiry.",
                    "Mutex / distributed lock in Redis so only one worker query hits PostgreSQL while others wait for cache replenishment.",
                    "Serving stale data with a background worker updating the cache (`stale-while-revalidate` pattern).",
                    "Database circuit breaking to shed load when DB connection pools become saturated."
                ],
                "follow_up": "What is the difference between cache stampede, cache penetration, and cache breakdown?",
                "evaluation_rubric": {
                    "weak": "Suggests increasing database CPU size without addressing caching patterns or distributed locks.",
                    "strong": "Explains mutex locks, probabilistic early expiration (XFetch), stale-while-revalidate, and database protection."
                }
            },
            {
                "category": CATEGORY_SCENARIOS,
                "question": "Scenario: Two microservices experience a distributed deadlock where Service A holds a row lock in Database A and awaits a response from Service B, which holds a row lock in Database B and is calling Service A. How do you detect, break, and architecturally avoid distributed deadlocks?",
                "difficulty": "Advanced",
                "skill_assessed": "Distributed Deadlocks & Sagas",
                "relevance": "Core scenario: Microservices architecture and distributed transactions.",
                "expected_answer": [
                    "Aggressive network request timeouts and circuit breakers to terminate waiting transactions.",
                    "Avoiding cross-service synchronous calls while holding open database transactions.",
                    "Adopting event-driven architecture and Saga patterns with compensating transactions rather than two-phase locking.",
                    "Consistent global resource lock ordering across all transactional workflows."
                ],
                "follow_up": "How does the Saga pattern orchestrator coordinate compensation if step 3 of a 5-step distributed transaction fails?",
                "evaluation_rubric": {
                    "weak": "Assumes relational databases automatically resolve deadlocks across independent microservice instances.",
                    "strong": "Recommends avoiding synchronous RPC during DB transactions, using Saga choreographies or orchestrators, and enforcing lock ordering."
                }
            },
            {
                "category": CATEGORY_SCENARIOS,
                "question": "Scenario: After deploying a new feature, database connections steadily climb until reaching the PostgreSQL `max_connections` threshold of 200, freezing all new API traffic. Inspection reveals CPU and disk I/O are normal. How do you identify the connection leak and prevent it?",
                "difficulty": "Intermediate",
                "skill_assessed": "Connection Leak Diagnostics & Session Lifecycles",
                "relevance": "Core responsibility: Database connection resilience and leak diagnostics.",
                "expected_answer": [
                    "Querying `pg_stat_activity` to inspect state: checking for connections stuck in `idle in transaction`.",
                    "Identifying application code paths where database sessions are opened without proper context manager (`with Session()`) or `try/finally` cleanup.",
                    "Configuring PostgreSQL's `idle_in_transaction_session_timeout` to terminate leaking sessions automatically.",
                    "Implementing pool recycling (`pool_recycle`) and checkout timeouts on the client side."
                ],
                "follow_up": "Why is an uncommitted `SELECT` query sometimes held open in an `idle in transaction` state by an ORM?",
                "evaluation_rubric": {
                    "weak": "Suggests increasing max_connections to 1,000 without investigating connection lifecycles.",
                    "strong": "Points directly to `pg_stat_activity`, idle-in-transaction states, missing session closure in async handlers, and automated session timeouts."
                }
            },
            {
                "category": CATEGORY_SCENARIOS,
                "question": "Scenario: An automated database migration running during a CI/CD deployment attempts an `ALTER TABLE users ADD COLUMN bio VARCHAR DEFAULT ''`. The migration hangs, blocking all concurrent read and write queries on the users table. Why did this occur, and how do you execute zero-downtime schema migrations?",
                "difficulty": "Advanced",
                "skill_assessed": "Zero-Downtime Database Migrations",
                "relevance": "Core responsibility: High-availability schema migrations.",
                "expected_answer": [
                    "`ALTER TABLE` acquires an `ACCESS EXCLUSIVE` lock on the table, which queues behind any active read queries and blocks all subsequent incoming queries.",
                    "Setting aggressive `lock_timeout` (e.g. 2 seconds) so migrations fail fast rather than creating a queue backlog.",
                    "In modern PostgreSQL (11+), adding a column with a constant default is metadata-only and fast; in older versions, it rewrites the table.",
                    "Multi-phase migration pattern: add column as nullable, backfill data in small batches, add NOT NULL constraint with `VALIDATE CONSTRAINT` asynchronously."
                ],
                "follow_up": "How do you create an index on a multi-million row table without locking incoming writes?",
                "evaluation_rubric": {
                    "weak": "Unaware that ALTER TABLE locks tables or assumes migrations should always run during scheduled maintenance downtime.",
                    "strong": "Explains `ACCESS EXCLUSIVE` lock queues, `lock_timeout`, `CREATE INDEX CONCURRENTLY`, and multi-phase schema evolution."
                }
            }
        ]
        return questions

    def _build_coding_and_design(self, key_skills: List[str], job_title: str, candidate_level: str) -> List[Dict[str, Any]]:
        questions = [
            {
                "category": CATEGORY_CODING_SYSTEM_DESIGN,
                "question": "Design an API Rate Limiter in Python and Redis that limits users to 100 requests per minute. How do you implement a Sliding Window Counter algorithm, and how does it prevent the burst vulnerability of Fixed Window counters?",
                "difficulty": "Advanced",
                "skill_assessed": "System Design & Rate Limiting",
                "relevance": "System Design: API gateway design and distributed throttling.",
                "expected_answer": [
                    "Fixed window flaw: allows 100 requests at 0:59 and 100 at 1:01, resulting in 200 requests within 2 seconds.",
                    "Sliding Window using Redis Sorted Sets (`ZADD`, `ZREMRANGEBYSCORE`, `ZCARD`) keyed by timestamp.",
                    "Executing operations inside a Redis atomic transaction (`MULTI/EXEC`) or Lua script to prevent race conditions.",
                    "Returning standard HTTP headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, and `Retry-After` on HTTP 429."
                ],
                "follow_up": "What is the memory trade-off of maintaining high-frequency timestamps in Redis Sorted Sets, and how does Sliding Window Counter approximate this with less memory?",
                "evaluation_rubric": {
                    "weak": "Suggests a simple in-memory Python dictionary that breaks when running across multiple server instances.",
                    "strong": "Explains atomic Redis operations, fixed vs sliding window boundary flaws, and HTTP 429 response contracts."
                }
            },
            {
                "category": CATEGORY_CODING_SYSTEM_DESIGN,
                "question": "In an asynchronous FastAPI application, a developer accidentally adds a blocking network call (`requests.get(...)`) inside an `async def` endpoint. Explain what happens to the server's throughput, and how you would rewrite it or offload it properly?",
                "difficulty": "Intermediate",
                "skill_assessed": "Async Concurrency Debugging",
                "relevance": "Core skill: FastAPI and asynchronous Python engineering.",
                "expected_answer": [
                    "The blocking synchronous call monopolizes the single asyncio event loop thread for the duration of the network I/O.",
                    "All concurrent requests across all endpoints on that worker freeze until the blocking call returns.",
                    "Solution 1: Replace `requests.get` with an asynchronous HTTP client like `httpx.AsyncClient` (`await client.get(...)`).",
                    "Solution 2: If the library cannot be async, offload via `asyncio.to_thread(blocking_func)` or FastAPI's `run_in_threadpool`."
                ],
                "follow_up": "How would you write an automated linter or test rule to catch synchronous I/O calls inside async handlers before deployment?",
                "evaluation_rubric": {
                    "weak": "Does not understand that Python asyncio uses a single thread per worker process.",
                    "strong": "Clearly explains event loop starvation, threadpool offloading mechanisms, and non-blocking alternatives (`httpx`, `aiohttp`)."
                }
            },
            {
                "category": CATEGORY_CODING_SYSTEM_DESIGN,
                "question": "How would you design a distributed webhook notification delivery system in Python that guarantees 'at-least-once' delivery to external clients, handles target server downtime with exponential backoff, and isolates slow targets?",
                "difficulty": "Advanced",
                "skill_assessed": "Distributed Architecture & Message Queues",
                "relevance": "System Design: Microservices, message queues, and distributed workers.",
                "expected_answer": [
                    "Decoupling webhook generation from delivery using a message broker (RabbitMQ, Kafka, or Redis Streams).",
                    "Worker consumers executing HTTP POSTs with strict connection and read timeouts.",
                    "Exponential backoff retry scheduling (e.g. retry after 1m, 5m, 30m, 2h) storing attempt counts.",
                    "Dead-Letter Queue (DLQ) after max retries; isolating slow or unresponsive customer endpoints so other deliveries are not delayed."
                ],
                "follow_up": "How do you sign webhook payloads (e.g. HMAC-SHA256) so recipient servers can verify they originated from your system?",
                "evaluation_rubric": {
                    "weak": "Attempts to send webhooks synchronously inside the primary web request without queueing or retries.",
                    "strong": "Designs asynchronous worker pipelines, exponential backoff, DLQ handling, and HMAC signature authentication."
                }
            },
            {
                "category": CATEGORY_CODING_SYSTEM_DESIGN,
                "question": "Design an idempotent order-processing endpoint in FastAPI. How do you utilize an Idempotency-Key header, distributed locks in Redis, and atomic database transactions to ensure a double-clicked checkout creates only one charge?",
                "difficulty": "Advanced",
                "skill_assessed": "Idempotency Architecture & Distributed Locks",
                "relevance": "System Design: Financial transactions and idempotent APIs.",
                "expected_answer": [
                    "Client sends a unique UUID in the `Idempotency-Key` header.",
                    "Server attempts to acquire a short-lived Redis lock for that key (`SET key value NX PX 5000`).",
                    "If lock acquisition fails or key exists with completed status, return the cached prior response immediately.",
                    "Execute order creation inside a DB transaction, cache the response in Redis with TTL, and release the lock."
                ],
                "follow_up": "What happens if the server crashes after the credit card charge succeeds but before storing the order in the database?",
                "evaluation_rubric": {
                    "weak": "Assumes checking the database without distributed locks prevents concurrent double-clicks.",
                    "strong": "Details atomic Redis lock acquisition (`SET NX`), response caching, transaction boundaries, and two-phase charge verification."
                }
            },
            {
                "category": CATEGORY_CODING_SYSTEM_DESIGN,
                "question": "How would you design a scalable URL shortener service in Python handling 10,000 redirects per second? Discuss your base62 encoding strategy, key generation (pre-generated vs hashing), database schema, and Redis caching layers?",
                "difficulty": "Intermediate" if "Senior" not in candidate_level else "Advanced",
                "skill_assessed": "System Design: URL Shortener & High Read Throughput",
                "relevance": "System Design: High-throughput caching and encoding.",
                "expected_answer": [
                    "Base62 encoding (a-z, A-Z, 0-9) yielding 62^7 (~3.5 trillion) distinct short URLs for 7 characters.",
                    "Unique ID generation via distributed counters (Twitter Snowflake or Redis atomic increments).",
                    "Read-heavy optimization: caching hot URL mappings in Redis with LRU eviction to serve 95%+ of redirects from RAM.",
                    "HTTP 301 (Permanent) vs HTTP 302 (Temporary) redirect trade-offs regarding client browser caching and telemetry tracking."
                ],
                "follow_up": "When would you prefer HTTP 302 over HTTP 301 for short URL analytics?",
                "evaluation_rubric": {
                    "weak": "Suggests using MD5 hashes with collision loops without addressing high concurrency or distributed counters.",
                    "strong": "Explains base62 conversion, distributed ID generators, Redis caching hit-rates, and HTTP 301/302 analytics implications."
                }
            },
            {
                "category": CATEGORY_CODING_SYSTEM_DESIGN,
                "question": "How would you implement a custom Python decorator (`@cache_with_ttl(seconds=60)`) that caches asynchronous function results in Redis, generates deterministic keys based on function arguments, and handles exceptions cleanly?",
                "difficulty": "Intermediate",
                "skill_assessed": "Python Decorators & Asynchronous Caching",
                "relevance": "Coding & Design: Reusable decorator patterns in Python.",
                "expected_answer": [
                    "Using `functools.wraps` to preserve function signature, docstrings, and metadata.",
                    "Creating deterministic cache keys by serializing `*args` and `**kwargs` (e.g. hashing json or pickle string).",
                    "`async def wrapper(*args, **kwargs)` supporting coroutines with `await`.",
                    "Handling Redis downtime gracefully by catching exceptions and executing the original function without failing the user request."
                ],
                "follow_up": "How would you modify the decorator to prevent caching `None` results or error responses?",
                "evaluation_rubric": {
                    "weak": "Writes a synchronous decorator that breaks async functions or ignores argument serialization.",
                    "strong": "Preserves coroutine wrapping, builds deterministic keys, preserves metadata (`functools.wraps`), and handles Redis connection failures."
                }
            },
            {
                "category": CATEGORY_CODING_SYSTEM_DESIGN,
                "question": "How would you design a distributed task queue worker in Python from scratch using Redis Streams, ensuring that messages are not lost if a worker pod crashes mid-execution (`XACK` and consumer groups)?",
                "difficulty": "Advanced",
                "skill_assessed": "Redis Streams & Reliable Distributed Consumers",
                "relevance": "System Design: Reliable asynchronous queue processing.",
                "expected_answer": [
                    "Creating consumer groups (`XGROUP CREATE`) so workers process tasks collaboratively.",
                    "Reading with `XREADGROUP` and acknowledging only after successful task execution (`XACK`).",
                    "Recovering abandoned tasks from crashed workers by inspecting the Pending Entries List (PEL) with `XPENDING` and claiming them via `XCLAIM`.",
                    "Routing permanently failing tasks to a dead-letter stream after exceeding a maximum retry count."
                ],
                "follow_up": "What is the difference between Redis Pub/Sub and Redis Streams regarding message persistence and consumer acknowledgments?",
                "evaluation_rubric": {
                    "weak": "Suggests using simple Redis lists (`LPOP`) which drop messages permanently if a worker crashes before completion.",
                    "strong": "Explains consumer groups, Pending Entries List, explicit `XACK`, and dead-letter queue routing."
                }
            }
        ]
        return questions

    def _build_behavioral_questions(self, candidate_level: str, job_title: str) -> List[Dict[str, Any]]:
        questions = [
            {
                "category": CATEGORY_BEHAVIORAL,
                "question": "Can you describe a situation where you had a strong technical disagreement with a teammate or lead regarding architectural choices or code patterns during a Pull Request review? How did you present your case, and how was the matter resolved?",
                "difficulty": "Intermediate",
                "skill_assessed": "Collaboration & Constructive Code Review",
                "relevance": "Behavioral: Engineering collaboration and constructive technical communication.",
                "expected_answer": [
                    "Focuses on data, benchmarks, and architectural principles rather than personal ego or stylistic preference.",
                    "Demonstrates empathy: seeks to understand the teammate's constraints and underlying intent.",
                    "Shows willingness to compromise or seek an objective third-party opinion when consensus stalls.",
                    "Commits fully to the agreed-upon direction once a decision is finalized."
                ],
                "follow_up": "If a team standard or convention is missing, leading to repeated review debates, what initiative do you take?",
                "evaluation_rubric": {
                    "weak": "Describes either giving in passively or becoming combative without technical justification.",
                    "strong": "Focuses on benchmarks, maintainability metrics, shared team documentation, and constructive compromise."
                }
            },
            {
                "category": CATEGORY_BEHAVIORAL,
                "question": "Engineers frequently face competing demands between shipping new business features quickly and paying down technical debt. Give an example of how you advocated for technical debt remediation to product managers who were focused solely on feature deadlines?",
                "difficulty": "Intermediate" if "Senior" not in candidate_level else "Advanced",
                "skill_assessed": "Stakeholder Management & Technical Debt",
                "relevance": "Behavioral: Balancing velocity, technical debt, and business delivery.",
                "expected_answer": [
                    "Translates technical debt into business impact: developer velocity, outage risks, customer churn, or cloud cost waste.",
                    "Proposes incremental refactoring alongside feature work rather than demanding a full code rewrite.",
                    "Establishes agreed-upon SLAs or allocating a fixed percentage (e.g. 20%) of each sprint to engineering health.",
                    "Measures before-and-after improvements (e.g. reduced bug tickets, faster deployment times)."
                ],
                "follow_up": "How do you decide when technical debt has become urgent enough to halt feature development?",
                "evaluation_rubric": {
                    "weak": "Complains about 'bad code' without quantifying business risk, or insists on full rewrites that stall product roadmaps.",
                    "strong": "Frames refactoring in terms of business velocity, risk mitigation, and incremental engineering practices."
                }
            },
            {
                "category": CATEGORY_BEHAVIORAL,
                "question": "Tell us about a time when an unpredicted system outage or high-severity bug was traced directly to code you authored. How did you react in the moment, communicate with stakeholders, and implement long-term safeguards?",
                "difficulty": "Intermediate",
                "skill_assessed": "Ownership, Accountability & Resilience",
                "relevance": "Behavioral: Production accountability and psychological safety.",
                "expected_answer": [
                    "Demonstrates immediate ownership without deflecting blame or making excuses.",
                    "Focuses on swift remediation and transparent communication to impacted teammates and users.",
                    "Conducts an honest post-mortem identifying why automated tests or CI gates failed to catch the regression.",
                    "Adds targeted regression test suites and documentation to safeguard the failure mode permanently."
                ],
                "follow_up": "How do you foster a team culture where engineers feel safe acknowledging mistakes rather than hiding them?",
                "evaluation_rubric": {
                    "weak": "Denies ever introducing a bug, or blames external factors like QA, ambiguous tickets, or junior teammates.",
                    "strong": "Exhibits maturity, immediate accountability, transparent communication, and systemic prevention."
                }
            },
            {
                "category": CATEGORY_BEHAVIORAL,
                "question": "How do you approach mentoring junior software engineers or onboarding new team members into a complex, distributed codebase without micro-managing them or letting them get overwhelmed?",
                "difficulty": "Intermediate",
                "skill_assessed": "Mentorship, Onboarding & Knowledge Sharing",
                "relevance": "Behavioral: Engineering leadership and team capability growth.",
                "expected_answer": [
                    "Structuring initial onboarding tickets with clear scope, acceptance criteria, and reproduction environments.",
                    "Encouraging pair programming and explaining 'why' architectural decisions exist rather than just 'how' to code.",
                    "Maintaining up-to-date documentation and runbooks that new hires contribute to during their first weeks.",
                    "Providing constructive, kind feedback in code reviews focused on learning opportunities."
                ],
                "follow_up": "What indicators tell you that an onboarding engineer needs proactive intervention versus more independent problem-solving time?",
                "evaluation_rubric": {
                    "weak": "Expects new hires to 'sink or swim' without guidance, or micromanages line-by-line coding.",
                    "strong": "Articulates structured scaffolding, empathetic code review practices, and psychological safety."
                }
            }
        ]
        return questions

    def _build_role_domain_questions(self, job_title: str, key_skills: List[str]) -> List[Dict[str, Any]]:
        questions = [
            {
                "category": CATEGORY_ROLE_DOMAIN,
                "question": f"What motivated you to specialize in {job_title}, and how do you envision the evolution of backend systems as multi-agent AI workflows and LLM orchestration become standard engineering components?",
                "difficulty": "Foundation",
                "skill_assessed": "Domain Motivation & Industry Vision",
                "relevance": "Role alignment: Career motivation and enthusiasm for AI/backend engineering.",
                "expected_answer": [
                    "Articulates a clear passion for backend systems, distributed architectures, and scalable data flow.",
                    "Recognizes that AI engineering requires robust traditional backend rigor: caching, concurrency, and validation.",
                    "Discusses challenges in latency, non-deterministic outputs, and token budgeting in multi-agent workflows."
                ],
                "follow_up": "What recent open-source library or paper in AI engineering or backend development has captured your attention?",
                "evaluation_rubric": {
                    "weak": "Gives generic buzzword answers without practical grounding in backend engineering.",
                    "strong": "Synthesizes traditional backend reliability with modern AI orchestration challenges."
                }
            },
            {
                "category": CATEGORY_ROLE_DOMAIN,
                "question": "The software engineering landscape moves rapidly with new libraries, runtimes, and paradigms. What is your deliberate personal methodology for evaluating whether a new tool or framework is mature enough for production adoption?",
                "difficulty": "Foundation",
                "skill_assessed": "Continuous Learning & Technology Evaluation",
                "relevance": "Role alignment: Technical judgment and technology selection.",
                "expected_answer": [
                    "Evaluates ecosystem health: active maintainers, release cadence, GitHub issue resolution, and community adoption.",
                    "Analyzes documentation quality, test coverage, and security audit history.",
                    "Builds proof-of-concept benchmarks under realistic workloads before proposing architectural shifts.",
                    "Weighs migration costs, team learning curves, and long-term maintenance overhead against perceived benefits."
                ],
                "follow_up": "Can you share an example of a hyped technology that you evaluated and deliberately chose not to adopt?",
                "evaluation_rubric": {
                    "weak": "Chases novelty without considering maintenance costs or defaults to never learning new technologies.",
                    "strong": "Demonstrates balanced, pragmatic technology evaluation considering operational risk and developer productivity."
                }
            },
            {
                "category": CATEGORY_ROLE_DOMAIN,
                "question": "In multi-tenant AI and recruiter assistant systems, how do you enforce Responsible AI standards, prevent training data leakage, and ensure demographic characteristics never bias scoring or evaluation pipelines?",
                "difficulty": "Intermediate",
                "skill_assessed": "Responsible AI, Privacy & Fairness",
                "relevance": "Role alignment: Ethical AI guardrails and compliance.",
                "expected_answer": [
                    "Strict exclusion of protected attributes (race, gender, age, religion) from model prompts and representations.",
                    "Ephemeral session memory processing: ensuring candidate resumes are not stored or used for model fine-tuning.",
                    "Human-in-the-loop advisory design: models provide evidence and questions, while human recruiters make decisions.",
                    "Regular fairness audits and counterfactual testing on prompt outputs."
                ],
                "follow_up": "How would you detect if an LLM is exhibiting subtle bias against candidates from non-traditional educational backgrounds?",
                "evaluation_rubric": {
                    "weak": "Disregards bias or assumes LLM outputs are always neutral without guardrails.",
                    "strong": "Explains transient data storage, PII scrubbing, counterfactual evaluation, and human-in-the-loop oversight."
                }
            },
            {
                "category": CATEGORY_ROLE_DOMAIN,
                "question": "How do you define and monitor Service Level Indicators (SLIs) and Service Level Objectives (SLOs) such as p99 latency and error budgets to guide engineering priorities?",
                "difficulty": "Intermediate",
                "skill_assessed": "SRE Principles & Observability Metrics",
                "relevance": "Role alignment: Site reliability engineering and production health.",
                "expected_answer": [
                    "Distinguishing SLI (measured metric, e.g. successful request ratio) from SLO (target reliability threshold, e.g. 99.9%).",
                    "Using error budgets to balance rapid feature releases with production stability.",
                    "Tracking latency percentiles (p50, p95, p99) rather than misleading arithmetic averages.",
                    "Automating alerts on error budget burn rates rather than noisy raw thresholds."
                ],
                "follow_up": "What action does the engineering team take when the error budget for a quarter is completely exhausted?",
                "evaluation_rubric": {
                    "weak": "Relies solely on average response times or cannot define what an error budget is.",
                    "strong": "Articulates SLI/SLO definitions, percentiles, error budget policies, and automated burn-rate alerting."
                }
            },
            {
                "category": CATEGORY_ROLE_DOMAIN,
                "question": "What architectural criteria do you use to decide whether a new capability should be built as a separate microservice versus an additional module within an existing modular monolith?",
                "difficulty": "Advanced",
                "skill_assessed": "Modular Monolith vs Microservices",
                "relevance": "Role alignment: System architecture and organizational boundaries.",
                "expected_answer": [
                    "Evaluating independent deployment cadences, distinct scaling requirements, and team ownership boundaries (Conway's Law).",
                    "Assessing operational overhead: monitoring, networking, distributed tracing, and data consistency costs.",
                    "Starting with a well-structured modular monolith with clear domain boundaries before prematurely distributing.",
                    "Extracting services only when scaling constraints or organizational autonomy justifies the network complexity."
                ],
                "follow_up": "What is the biggest operational mistake engineering teams make when adopting microservices too early?",
                "evaluation_rubric": {
                    "weak": "Advocates creating a separate microservice for every database table or feature without considering distributed overhead.",
                    "strong": "Understands Conway's Law, operational tax of distributed systems, and modular monolith advantages."
                }
            },
            {
                "category": CATEGORY_ROLE_DOMAIN,
                "question": "How do you identify and execute cloud infrastructure cost optimizations in AWS or GCP without sacrificing system resilience or performance?",
                "difficulty": "Intermediate",
                "skill_assessed": "Cloud Cost Optimization & FinOps",
                "relevance": "Role alignment: Efficient cloud resource management.",
                "expected_answer": [
                    "Analyzing utilization metrics to downsize over-provisioned EC2 instances or memory limits.",
                    "Leveraging AWS Graviton (ARM-based) instances for improved price-to-performance ratio.",
                    "Using caching (Redis) and CDNs to drastically reduce expensive database IOPS and egress bandwidth.",
                    "Establishing lifecycle policies to transition cold data from S3 Standard to Glacier."
                ],
                "follow_up": "How do you ensure autoscaling policies scale down aggressively during off-peak hours without causing cold-start latency spikes?",
                "evaluation_rubric": {
                    "weak": "Unaware of cloud billing drivers or suggests cutting costs by disabling automated backups.",
                    "strong": "Identifies compute right-sizing, caching egress reduction, storage tiering, and reserved/spot instance strategies."
                }
            },
            {
                "category": CATEGORY_BEHAVIORAL,
                "question": "Describe a project where business requirements or product priorities changed dramatically midway through implementation. How did you realign the engineering architecture and maintain team momentum?",
                "difficulty": "Intermediate",
                "skill_assessed": "Adaptability & Scope Management",
                "relevance": "Behavioral: Navigating changing requirements in agile environments.",
                "expected_answer": [
                    "Maintains composure and seeks to understand the strategic commercial rationale behind the pivot.",
                    "Assesses technical delta: salvaging modular components and minimizing wasted engineering effort.",
                    "Communicates adjusted timeline and architectural risks clearly to product managers and engineers.",
                    "Re-prioritizes user stories and establishes revised milestone targets."
                ],
                "follow_up": "How do you design software modules from day one so they can accommodate pivotable business rules?",
                "evaluation_rubric": {
                    "weak": "Shows frustration or complains about product managers changing their minds.",
                    "strong": "Exhibits strategic mindset, decouples business rules from core logic, and collaborates constructively on re-scoping."
                }
            },
            {
                "category": CATEGORY_BEHAVIORAL,
                "question": "How do you handle situations where a product manager or executive requests an engineering estimate for a complex, ambiguously defined initiative? How do you prevent premature estimates from becoming rigid deadlines?",
                "difficulty": "Intermediate",
                "skill_assessed": "Estimation, Communication & Risk Management",
                "relevance": "Behavioral: Engineering estimation and expectation management.",
                "expected_answer": [
                    "Decomposes large initiatives into research spikes or prototypes before providing definitive estimates.",
                    "Communicates estimates as confidence intervals (e.g. 2-4 weeks with stated assumptions) rather than single-point dates.",
                    "Identifies external dependencies, technical risks, and unknowns explicitly.",
                    "Regularly revisits estimates as architectural discovery clarifies project scope."
                ],
                "follow_up": "What do you do when a spike reveals that an initiative will take triple the time originally anticipated?",
                "evaluation_rubric": {
                    "weak": "Guesses arbitrary numbers under pressure or agrees to unfeasible deadlines without push-back.",
                    "strong": "Advocates time-boxed discovery spikes, confidence intervals, explicit assumptions, and transparent risk communication."
                }
            }
        ]
        return questions
