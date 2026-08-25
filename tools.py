"""
tools.py
Core tools for the Smart Healthcare Patient Triage & Appointment Booking Agent:
1. Triage Protocol Retriever (RAG with TF-IDF & Cosine Similarity)
2. Severity Calculator (Deterministic Clinical Safety Rules)
3. Appointment Booking Tool (Simulated Clinical Scheduling)
"""

import os
import re
import uuid
import datetime
from typing import Dict, Any, List, Optional
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


# ==========================================
# TOOL 1: TRIAGE PROTOCOL RETRIEVER (RAG)
# ==========================================

class TriageProtocolRetriever:
    """
    RAG Retriever that loads clinical triage guidelines and performs
    TF-IDF vectorization and Cosine Similarity search to retrieve relevant protocols.
    """
    def __init__(self, guidelines_path: Optional[str] = None):
        if guidelines_path is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            guidelines_path = os.path.join(base_dir, "data", "clinical_triage_guidelines.txt")
        self.guidelines_path = guidelines_path
        self.protocols: List[Dict[str, str]] = []
        self.vectorizer: Optional[TfidfVectorizer] = None
        self.tfidf_matrix = None
        self._load_and_index()

    def _load_and_index(self):
        if not os.path.exists(self.guidelines_path):
            raise FileNotFoundError(f"Guidelines file not found at: {self.guidelines_path}")

        with open(self.guidelines_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Parse protocols from text file
        raw_blocks = content.strip().split("\n\n")
        self.protocols = []
        corpus_texts = []

        for block in raw_blocks:
            lines = block.strip().split("\n")
            if not lines:
                continue
            
            proto_id = lines[0].strip("[]")
            proto_data = {"id": proto_id, "raw": block}
            for line in lines[1:]:
                if ":" in line:
                    key, val = line.split(":", 1)
                    proto_data[key.strip().lower()] = val.strip()
            
            self.protocols.append(proto_data)
            # Create a rich search text combining title, keywords, category, and description
            searchable_text = f"{proto_data.get('title', '')} {proto_data.get('keywords', '')} {proto_data.get('category', '')} {proto_data.get('description', '')}"
            corpus_texts.append(searchable_text)

        # Initialize TF-IDF Vectorizer
        self.vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
        self.tfidf_matrix = self.vectorizer.fit_transform(corpus_texts)

    def retrieve(self, symptoms_text: str, top_k: int = 1) -> Dict[str, Any]:
        """
        Retrieves the most relevant triage protocol based on patient symptoms.
        """
        if not symptoms_text.strip():
            return {
                "matched": False,
                "protocol_id": "NONE",
                "title": "No Symptoms Provided",
                "category": "UNKNOWN",
                "similarity_score": 0.0,
                "guideline_text": "Please provide symptom details.",
                "action": "Request patient symptoms."
            }

        query_vec = self.vectorizer.transform([symptoms_text])
        similarities = cosine_similarity(query_vec, self.tfidf_matrix).flatten()
        top_idx = int(similarities.argmax())
        best_score = float(similarities[top_idx])
        matched_proto = self.protocols[top_idx]

        return {
            "matched": True,
            "protocol_id": matched_proto.get("id", "UNKNOWN"),
            "title": matched_proto.get("title", ""),
            "category": matched_proto.get("category", "ROUTINE").upper(),
            "similarity_score": round(best_score, 4),
            "description": matched_proto.get("description", ""),
            "action": matched_proto.get("action", ""),
            "raw_protocol": matched_proto.get("raw", ""),
            "evidence": f"[{matched_proto.get('id')}] {matched_proto.get('title')}: {matched_proto.get('description')} (Action: {matched_proto.get('action')})"
        }


# Global singleton instance for easy functional access
_retriever_instance = None

def retrieve_triage_protocol(symptoms_text: str) -> Dict[str, Any]:
    """
    Tool function to search clinical triage knowledge base using TF-IDF & Cosine Similarity.
    """
    global _retriever_instance
    if _retriever_instance is None:
        _retriever_instance = TriageProtocolRetriever()
    return _retriever_instance.retrieve(symptoms_text)


# ==========================================
# TOOL 2: SEVERITY CALCULATOR
# ==========================================

def calculate_severity(symptoms_text: str, duration_days: int = 1, matched_category: str = "") -> Dict[str, Any]:
    """
    Tool function that uses deterministic clinical safety rules to classify case severity.
    Returns: ROUTINE, URGENT, or EMERGENCY.
    """
    text_lower = symptoms_text.lower()
    
    # Red-flag emergency indicators
    emergency_patterns = [
        r"\bchest pain\b",
        r"\bcrushing (pressure|pain)\b",
        r"\bdifficulty breathing\b",
        r"\bshortness of breath\b",
        r"\bsevere dyspnea\b",
        r"\bheavy bleeding\b",
        r"\buncontrollable (bleeding|hemorrhage)\b",
        r"\bfacial drooping\b",
        r"\bslurred speech\b",
        r"\b(stroke|seizure)\b",
        r"\bunconscious(ness)?\b",
        r"\bsudden numbness\b",
        r"\bsudden weakness\b"
    ]

    for pattern in emergency_patterns:
        if re.search(pattern, text_lower):
            return {
                "severity_level": "EMERGENCY",
                "reasoning": f"Critical red-flag symptom detected matching clinical emergency trigger ({pattern.strip(r'\b')}).",
                "rule_applied": "RULE-EMERGENCY-REDFLAG",
                "requires_human_review": True
            }

    if matched_category.upper() == "EMERGENCY":
        return {
            "severity_level": "EMERGENCY",
            "reasoning": "RAG protocol matching confirmed an EMERGENCY clinical category.",
            "rule_applied": "RULE-EMERGENCY-PROTOCOL-MATCH",
            "requires_human_review": True
        }

    # Urgent indicators
    urgent_patterns = [
        r"\b(persistent|high) fever\b",
        r"\bsevere (abdominal|stomach) pain\b",
        r"\b(constant|persistent) vomiting\b",
        r"\bfracture\b",
        r"\bunable to (walk|bear weight)\b",
        r"\bdehydration\b"
    ]

    for pattern in urgent_patterns:
        if re.search(pattern, text_lower):
            return {
                "severity_level": "URGENT",
                "reasoning": f"Urgent symptom presentation detected ({pattern.strip(r'\b')}) requiring priority clinical evaluation.",
                "rule_applied": "RULE-URGENT-SYMPTOM",
                "requires_human_review": False
            }

    # Duration-based escalation
    if "fever" in text_lower and duration_days >= 3:
        return {
            "severity_level": "URGENT",
            "reasoning": f"Fever persisting for {duration_days} days exceeds safe routine threshold (>= 3 days).",
            "rule_applied": "RULE-URGENT-DURATION-ESCALATION",
            "requires_human_review": False
        }

    if matched_category.upper() == "URGENT":
        return {
            "severity_level": "URGENT",
            "reasoning": "RAG protocol matching categorized case as URGENT clinical review.",
            "rule_applied": "RULE-URGENT-PROTOCOL-MATCH",
            "requires_human_review": False
        }

    # Default to Routine
    return {
        "severity_level": "ROUTINE",
        "reasoning": "Mild or standard symptom presentation with no emergency red flags or urgent escalation criteria.",
        "rule_applied": "RULE-ROUTINE-STANDARD",
        "requires_human_review": False
    }


# ==========================================
# TOOL 3: APPOINTMENT BOOKING TOOL
# ==========================================

def book_appointment(patient_name: str, severity_level: str, symptoms_text: str) -> Dict[str, Any]:
    """
    Tool function that simulates clinic appointment scheduling based on severity level.
    """
    if severity_level.upper() == "EMERGENCY":
        return {
            "booking_successful": False,
            "status": "BLOCKED_EMERGENCY",
            "message": "Direct appointment booking is blocked for emergency cases. Immediate clinical triage required.",
            "appointment_id": None
        }

    # Generate appointment reference
    short_code = uuid.uuid4().hex[:6].upper()
    appointment_id = f"APT-{short_code}"

    # Determine timing and department
    now = datetime.datetime.now()
    if severity_level.upper() == "URGENT":
        appt_time = (now + datetime.timedelta(hours=3)).strftime("%Y-%m-%d %I:%M %p")
        department = "Priority Urgent Care Clinic"
        slot_type = "Same-Day Priority Slot (Within 3 Hours)"
        instructions = "Please check in at the Urgent Care desk 15 minutes prior. Bring identification and current medications."
    else:
        appt_time = (now + datetime.timedelta(days=1)).strftime("%Y-%m-%d 10:00 AM")
        department = "Primary Care & Family Medicine"
        slot_type = "Next-Day Routine Consultation"
        instructions = "Standard clinic check-in. Telehealth option also available upon request."

    return {
        "booking_successful": True,
        "status": "CONFIRMED",
        "appointment_id": appointment_id,
        "patient_name": patient_name,
        "department": department,
        "appointment_time": appt_time,
        "slot_type": slot_type,
        "severity_tier": severity_level.upper(),
        "special_instructions": instructions,
        "summary": f"Appointment {appointment_id} confirmed for {patient_name} in {department} at {appt_time}."
    }
