from datetime import date, datetime

# || Job description constants

REFERENCE_DATE = date.today()
 
# --- Hard disqualifier: consulting-only firms (JD-stated) ---
CONSULTING_FIRMS = {
    "tcs", "tata consultancy", "infosys", "wipro", "accenture",
    "cognizant", "capgemini", "hcl", "tech mahindra", "mphasis",
    "hexaware", "l&t infotech", "ltimindtree"
}
 
# --- Honeypot guard: non-technical current titles ---
# Used in Guard 2: career substance check still runs, but title is flagged
NON_TECHNICAL_TITLES = {
    "business analyst", "hr manager", "accountant", "project manager",
    "customer support", "operations manager", "content writer",
    "sales executive", "civil engineer", "graphic designer",
    "marketing manager", "mechanical engineer", "hr"
}
 
# --- Must-have keywords: score career_history description text ---
# These represent real work described in plain language (not just skill labels)
MUST_HAVE_KEYWORDS = [
    # Retrieval / ranking / search
    "retrieval", "ranking", "recommendation", "search", "ranker",
    "semantic search", "hybrid search", "retrieval system", "ranking system",
    "recommendation engine", "recommendation system", "personalization",
    "relevance", "search relevance", "reranking", "re-ranking",
    # Embeddings / vector infra
    "embedding", "embeddings", "vector", "vector database", "vector db",
    "dense retrieval", "sentence transformer", "bi-encoder", "cross-encoder",
    "pinecone", "weaviate", "qdrant", "milvus", "faiss", "opensearch",
    "elasticsearch", "pgvector", "chroma",
    # LLM / NLP depth
    "llm", "large language model", "fine-tuning", "fine-tune", "lora", "qlora",
    "rag", "retrieval augmented", "nlp", "natural language processing",
    "transformer", "bert", "gpt", "language model",
    # ML production signals
    "production", "deployed", "deployment", "a/b test", "a/b testing",
    "evaluation framework", "offline eval", "online eval", "ndcg", "mrr",
    "feature pipeline", "model serving", "inference", "mlops",
    # Learning to rank
    "learning to rank", "ltr", "xgboost", "lightgbm", "gradient boosting",
]
 
# --- Nice-to-have keywords: smaller bonus ---
NICE_TO_HAVE_KEYWORDS = [
    "open source", "open-source", "github", "paper", "research",
    "mentoring", "mentored", "distributed system", "large scale", "scale",
    "hr tech", "hrtech", "recruiting", "talent", "marketplace",
    "spark", "airflow", "kafka", "data pipeline", "feature store",
]
 
# --- Must-have skills by name (for skills array scoring) ---
MUST_HAVE_SKILLS = {
    # Retrieval / vector infra
    "pinecone", "weaviate", "qdrant", "milvus", "faiss", "opensearch",
    "elasticsearch", "pgvector", "chroma", "vector database",
    # Embeddings / NLP
    "embeddings", "sentence transformers", "nlp", "natural language processing",
    "transformers", "bert", "rag", "retrieval augmented generation",
    "semantic search", "information retrieval",
    # LLM
    "llm", "large language models", "fine-tuning llms", "fine-tuning",
    "lora", "qlora", "peft",
    # ML core
    "machine learning", "deep learning", "pytorch", "tensorflow",
    "scikit-learn", "xgboost", "lightgbm",
    # Ranking / recommendation
    "recommendation systems", "ranking", "learning to rank",
    # Production
    "mlops", "model serving", "bentoml", "triton", "ray serve",
}
 
NICE_TO_HAVE_SKILLS = {
    "python", "sql", "spark", "kafka", "airflow", "dbt",
    "aws", "gcp", "azure", "docker", "kubernetes",
    "weights & biases", "wandb", "mlflow",
    "gans", "image classification", "speech recognition",  # lower weight since JD says "not primary"
}
 
# --- Disqualifier skill clusters (primary expertise only; checked against top skills) ---
CV_SPEECH_CLUSTER = {
    "computer vision", "image classification", "object detection", "yolo",
    "speech recognition", "tts", "text to speech", "asr", "robotics",
}

# || Scoring functions

def days_since(date_str, reference=REFERENCE_DATE):
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
        return (reference - d).days
    except Exception:
        return 9999
 
 
# ── Guard helpers ─────────────────────────────────────────────────────────────
 
def guard_experience_consistency(candidate):
    """
    Guard 1: Profile YOE should roughly match sum of career_history durations.
    Honeypots sometimes inflate profile.years_of_experience vs actual history.
    Returns a multiplier: 1.0 if consistent, 0.6 if suspiciously inflated.
    """
    profile_yoe_months = candidate["profile"]["years_of_experience"] * 12
    history_months = sum(r["duration_months"] for r in candidate["career_history"])
    # Allow up to 24 months slack (gaps, freelance, etc.)
    if history_months == 0:
        return 0.5  # no verifiable history at all
    ratio = profile_yoe_months / max(history_months, 1)
    if ratio > 2.0:
        return 0.6  # claimed YOE is more than double what history shows
    return 1.0
 
 
def guard_skill_endorsement_substance(candidate):
    """
    Guard 2: Flag candidates whose AI/ML skill claims have zero endorsements
    across the board for must-have skills.
    If every single must-have skill listed has 0 endorsements → suspicious.
    Returns multiplier: 1.0 normal, 0.75 if all AI skills are unendorsed.
    """
    relevant_skills = [
        s for s in candidate["skills"]
        if s["name"].lower() in MUST_HAVE_SKILLS
    ]
    if not relevant_skills:
        return 1.0  # no AI skills listed at all — handled elsewhere
    total_endorsements = sum(s["endorsements"] for s in relevant_skills)
    if total_endorsements == 0:
        return 0.75
    return 1.0
 
 
def guard_title_vs_description(candidate):
    """
    Guard 3: If current title is in NON_TECHNICAL_TITLES, check that at least
    one career_history description contains must-have substance keywords.
    If non-technical title AND no substance in descriptions → heavy penalty.
    Returns multiplier: 1.0 normal, 0.4 if non-technical title + no substance.
    """
    title = candidate["profile"]["current_title"].lower()
    is_non_technical = any(t in title for t in NON_TECHNICAL_TITLES)
    if not is_non_technical:
        return 1.0
    all_desc = " ".join(r["description"].lower() for r in candidate["career_history"])
    substance_hits = sum(1 for kw in MUST_HAVE_KEYWORDS if kw in all_desc)
    if substance_hits < 2:
        return 0.4  # non-technical title + no real ML work described
    return 1.0  # non-technical title but career history shows ML work (e.g. EM with ML background)
 
 
def guard_recency_of_ml_work(candidate):
    """
    Guard 4: JD says if AI experience is under 12 months total → likely not enough.
    Sum months of roles whose descriptions contain must-have keywords.
    If total ML-relevant experience < 12 months → penalty.
    Returns multiplier: 1.0 normal, 0.7 if ML experience is very shallow.
    """
    ml_months = 0
    for role in candidate["career_history"]:
        desc = role["description"].lower()
        hits = sum(1 for kw in MUST_HAVE_KEYWORDS if kw in desc)
        if hits >= 2:
            ml_months += role["duration_months"]
    if ml_months == 0:
        return 0.5
    if ml_months < 12:
        return 0.7
    return 1.0
 
 
# ── Stage 1: Hard disqualifiers ───────────────────────────────────────────────
 
def stage1_disqualify(candidate):
    """
    Returns (is_disqualified, reason_str).
    Encode only JD-stated hard disqualifiers — not opinions.
    """
    profile = candidate["profile"]
    career = candidate["career_history"]
    skills = candidate["skills"]
 
    # D1: Consulting-only career
    companies = {r["company"].lower() for r in career}
    is_consulting = lambda name: any(cf in name for cf in CONSULTING_FIRMS)
    all_consulting = all(is_consulting(c) for c in companies)
    if all_consulting and len(companies) > 0:
        return True, "Entire career at consulting firms (JD-stated disqualifier)."
 
    # D2: No production deployment signal at all
    # Check: no description in any role mentions "production", "deployed", "users", "scale"
    prod_keywords = {"production", "deployed", "deploy", "users", "shipped", "live", "serving"}
    all_desc = " ".join(r["description"].lower() for r in career)
    has_prod = any(kw in all_desc for kw in prod_keywords)
    if not has_prod:
        return True, "No production deployment signal found across all roles."
 
    # D3: Primary expertise is CV/Speech/Robotics with no NLP/IR signal
    # "Primary" = top 5 skills by endorsements
    sorted_skills = sorted(skills, key=lambda s: s["endorsements"], reverse=True)
    top5_names = {s["name"].lower() for s in sorted_skills[:5]}
    is_cv_speech = len(top5_names & CV_SPEECH_CLUSTER) >= 3
    has_nlp_signal = any(kw in all_desc for kw in ["nlp", "retrieval", "embedding", "ranking", "recommendation", "language model"])
    if is_cv_speech and not has_nlp_signal:
        return True, "Primary expertise is CV/Speech/Robotics with no NLP or IR exposure."
 
    return False, ""
 
 
# ── Stage 2: Substance score ──────────────────────────────────────────────────
 
def stage2_substance_score(candidate):
    """
    Returns (score 0.0-1.0, evidence_str for reasoning).
    Scores based on career_history description text + skills array.
    Career text is primary; skills array is secondary/confirming.
    """
    profile = candidate["profile"]
    career = candidate["career_history"]
    skills = candidate["skills"]
    score = 0.0
    evidence_parts = []
 
    # ── 2A: Career description keyword matching (50 pts) ──────────────────────
    # Weight recent roles more: most recent role = weight 1.0, older roles decay
    career_sorted = sorted(
        career,
        key=lambda r: r["start_date"],
        reverse=True
    )
    role_weights = [1.0, 0.8, 0.6, 0.5, 0.4, 0.3, 0.3, 0.3, 0.3, 0.3]
 
    career_score = 0.0
    best_role_evidence = None
    for i, role in enumerate(career_sorted):
        w = role_weights[i] if i < len(role_weights) else 0.2
        desc = role["description"].lower()
        hits = set(kw for kw in MUST_HAVE_KEYWORDS if kw in desc)
        nice_hits = set(kw for kw in NICE_TO_HAVE_KEYWORDS if kw in desc)
        role_score = min(len(hits) * 3.5 + len(nice_hits) * 1.0, 25.0)  # cap per role
        career_score += role_score * w
        if hits and best_role_evidence is None:
            best_role_evidence = (role["title"], role["company"], sorted(hits)[:3])
 
    career_score = min(career_score, 50.0)
    score += career_score
 
    if best_role_evidence:
        title, company, kws = best_role_evidence
        evidence_parts.append(
            f"Built {'/'.join(kws[:2])} systems as {title} at {company}"
        )
 
    # ── 2B: Years of experience fit (15 pts) ──────────────────────────────────
    yoe = profile["years_of_experience"]
    if 5 <= yoe <= 9:
        yoe_score = 15.0
    elif 4 <= yoe < 5 or 9 < yoe <= 11:
        yoe_score = 10.0
    elif 3 <= yoe < 4 or 11 < yoe <= 13:
        yoe_score = 5.0
    else:
        yoe_score = 0.0
    score += yoe_score
 
    # ── 2C: Skills array scoring (25 pts) ─────────────────────────────────────
    # Score based on endorsements (not just level), bonus for duration_months if present
    proficiency_multiplier = {
        "beginner": 0.4, "intermediate": 0.7, "advanced": 0.9, "expert": 1.0
    }
    skills_score = 0.0
    matched_skills = []
 
    for s in skills:
        name = s["name"].lower()
        endorsements = s["endorsements"]
        if endorsements == 0:
            continue  # 0 endorsements → no score for this skill (as requested)
 
        if name in MUST_HAVE_SKILLS:
            base = min(endorsements / 50.0, 1.0) * 5.0  # up to 5 pts per must-have
            prof_mult = proficiency_multiplier.get(s["proficiency"], 0.5)
            # Bonus: if duration_months is present and skill is relevant
            dur_bonus = 0.0
            if s.get("duration_months", 0) > 0:
                dur_bonus = min(s["duration_months"] / 60.0, 1.0) * 1.0  # up to 1 bonus pt
            skills_score += base * prof_mult + dur_bonus
            matched_skills.append(s["name"])
        elif name in NICE_TO_HAVE_SKILLS:
            base = min(endorsements / 50.0, 1.0) * 2.0
            prof_mult = proficiency_multiplier.get(s["proficiency"], 0.5)
            skills_score += base * prof_mult
 
    skills_score = min(skills_score, 25.0)
    score += skills_score
 
    if matched_skills:
        evidence_parts.append(f"Relevant skills: {', '.join(matched_skills[:3])}")
 
    # ── 2D: Skill assessment scores bonus (5 pts) ─────────────────────────────
    assessment_scores = candidate["redrob_signals"].get("skill_assessment_scores", {})
    relevant_assessments = [
        v for k, v in assessment_scores.items()
        if k.lower() in MUST_HAVE_SKILLS or k.lower() in NICE_TO_HAVE_SKILLS
    ]
    if relevant_assessments:
        avg_assessment = sum(relevant_assessments) / len(relevant_assessments)
        score += (avg_assessment / 100.0) * 5.0
 
    # ── 2E: Product company bonus (5 pts) ─────────────────────────────────────
    # JD explicitly says consulting-only is disqualifier but product company exp is valued
    product_industries = {
        "software", "saas", "fintech", "e-commerce", "edtech", "gaming",
        "healthtech", "ai/ml", "ai services", "conversational ai", "adtech",
        "food delivery", "insurance tech", "transportation", "healthtech ai"
    }
    has_product_exp = any(
        r.get("industry", "").lower() in product_industries
        for r in career
    )
    if has_product_exp:
        score += 5.0
 
    # Normalize to 0-1
    normalized = min(score / 100.0, 1.0)
    evidence_str = ". ".join(evidence_parts[:2]) if evidence_parts else "Matched general ML profile."
 
    return normalized, evidence_str
 
 
# ── Stage 3: Behavioral multiplier ───────────────────────────────────────────
 
def stage3_behavioral_multiplier(candidate):
    """
    Returns (multiplier 0.3-1.2, flag_str for reasoning).
    Multiplicative: scales substance score up or down.
    Does not erase a strong candidate — floor is 0.3.
    """
    sig = candidate["redrob_signals"]
    mult = 1.0
    flags = []
 
    # Open to work — most direct availability signal
    if sig["open_to_work_flag"]:
        mult += 0.10
    else:
        mult -= 0.15
        flags.append("not open to work")
 
    # Recency of last login
    days_inactive = days_since(sig["last_active_date"])
    if days_inactive <= 14:
        mult += 0.05
    elif days_inactive <= 30:
        pass  # neutral
    elif days_inactive <= 90:
        mult -= 0.05
    elif days_inactive <= 180:
        mult -= 0.15
        flags.append(f"inactive {days_inactive}d")
    else:
        mult -= 0.25
        flags.append(f"inactive {days_inactive}d")
 
    # Recruiter response rate — key availability proxy
    rrr = sig["recruiter_response_rate"]
    if rrr >= 0.6:
        mult += 0.08
    elif rrr >= 0.3:
        mult += 0.02
    elif rrr < 0.1:
        mult -= 0.12
        flags.append(f"low recruiter response ({rrr:.0%})")
 
    # Notice period — JD says sub-30 preferred, can buy out up to 30
    notice = sig["notice_period_days"]
    if notice <= 30:
        mult += 0.05
    elif notice <= 60:
        pass  # neutral
    elif notice > 90:
        mult -= 0.08
        flags.append(f"notice {notice}d")
 
    # Interview completion rate
    icr = sig["interview_completion_rate"]
    if icr >= 0.8:
        mult += 0.03
    elif icr < 0.4:
        mult -= 0.05
 
    # GitHub activity (only if linked; -1 means not linked)
    gh = sig["github_activity_score"]
    if gh >= 50:
        mult += 0.05
    elif gh == -1:
        pass  # neutral — not penalized for no GitHub
 
    # Verified contact — basic trust signal
    if sig["verified_email"] and sig["verified_phone"]:
        mult += 0.03
    elif not sig["verified_email"] and not sig["verified_phone"]:
        mult -= 0.03
 
    # Location / work mode fit — JD says Pune/Noida, open to relocation from Tier-1 cities
    if sig["willing_to_relocate"] or sig["preferred_work_mode"] in ("hybrid", "flexible"):
        mult += 0.02
 
    # Clamp multiplier to [0.3, 1.2]
    mult = max(0.3, min(1.2, mult))
 
    flag_str = "; ".join(flags) if flags else ""
    return mult, flag_str


# || Helpers for ranking step

def score_candidate(candidate):
    """
    Full pipeline: guards → disqualify → substance × behavioral multiplier.
    Returns (final_score, reasoning_str) or None if disqualified.
    """
    # Stage 1: Hard disqualify
    disqualified, disq_reason = stage1_disqualify(candidate)
    if disqualified:
        return None, disq_reason
 
    # Apply honeypot guards (as multipliers on substance score)
    guard_mult = 1.0
    guard_mult *= guard_experience_consistency(candidate)
    guard_mult *= guard_skill_endorsement_substance(candidate)
    guard_mult *= guard_title_vs_description(candidate)
    guard_mult *= guard_recency_of_ml_work(candidate)
 
    # Stage 2: Substance score
    substance, evidence_str = stage2_substance_score(candidate)
 
    # Stage 3: Behavioral multiplier
    behavioral_mult, flag_str = stage3_behavioral_multiplier(candidate)
 
    # Final score: substance × guards × behavioral
    final_score = substance * guard_mult * behavioral_mult
 
    # Reasoning: 1-2 sentences from actual signals
    reasoning_parts = []
    if evidence_str:
        reasoning_parts.append(evidence_str)
    if flag_str:
        reasoning_parts.append(f"Behavioral flags: {flag_str}")
    reasoning = ". ".join(reasoning_parts) + "." if reasoning_parts else "Strong ML profile with good availability signals."
 
    return final_score, reasoning