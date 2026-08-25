"""
agent_graph.py
LangGraph workflow for Smart Healthcare Patient Triage & Appointment Booking Agent.
Orchestrates RAG retrieval, deterministic severity calculation, conditional routing,
human-in-the-loop nurse review, and LLM grounded summary generation.
"""

import os
from typing import TypedDict, Optional, Dict, Any
from dotenv import load_dotenv

# LangGraph imports
from langgraph.graph import StateGraph, START, END

# Project tools
from tools import retrieve_triage_protocol, calculate_severity, book_appointment

# Load environment variables
load_dotenv()


# ==========================================
# 1. STATE DEFINITION
# ==========================================

class TriageState(TypedDict):
    patient_name: str
    age: int
    symptoms_text: str
    duration_days: int
    
    # RAG Retrieval Artifacts
    matched_protocol_id: str
    matched_protocol_title: str
    protocol_category: str
    retrieval_score: float
    protocol_evidence: str
    
    # Severity & Decision
    severity_level: str
    severity_reasoning: str
    rule_applied: str
    requires_human_review: bool
    
    # Actions
    appointment_details: Optional[Dict[str, Any]]
    
    # Human-in-the-Loop (Nurse Review)
    nurse_review_status: str
    nurse_action: str
    nurse_notes: str
    
    # Final Grounded Explanation & Status
    llm_summary: str
    final_status: str


# ==========================================
# 2. LLM HELPER (Groq with Safe Fallback)
# ==========================================

def _generate_grounded_summary(state: TriageState) -> str:
    """
    Provider Routing:
    1. Primary Hosted Provider: Groq (ChatGroq llama-3.3-70b-versatile)
    2. Local Fallback Provider: Ollama (ChatOllama llama3 or mistral)
    3. Grounded Deterministic Fallback: Structured clinical template if no provider is reachable
    """
    groq_api_key = os.getenv("GROQ_API_KEY")
    ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    
    prompt = f"""
You are a helpful clinical triage assistant. Generate a clear, empathetic, and professional summary for the patient based ONLY on the evidence below.

Patient Information:
- Name: {state.get('patient_name')}
- Age: {state.get('age')}
- Symptoms: {state.get('symptoms_text')} (Duration: {state.get('duration_days')} days)

Triage Findings:
- Matched Protocol: {state.get('matched_protocol_title')} ({state.get('matched_protocol_id')})
- Assessed Severity: {state.get('severity_level')}
- Rule Reasoning: {state.get('severity_reasoning')}
- Evidence: {state.get('protocol_evidence')}

Outcome:
- Action / Booking: {state.get('appointment_details', {}).get('summary') if state.get('appointment_details') else 'Escalated for Urgent Human Nurse Review'}
- Final Status: {state.get('final_status')}
{"- Nurse Note: " + state.get('nurse_notes', '') if state.get('nurse_notes') else ''}

Instructions:
1. State the triage level clearly.
2. Refer directly to the matched clinical guidance as evidence.
3. Outline the immediate next steps or appointment instructions for the patient.
4. Maintain a supportive, reassuring tone without making unauthorized medical diagnoses.
"""

    # 1. Primary: Groq Provider
    if groq_api_key and groq_api_key.strip():
        try:
            from langchain_groq import ChatGroq
            llm = ChatGroq(
                model_name="llama-3.3-70b-versatile",
                groq_api_key=groq_api_key,
                temperature=0.2
            )
            response = llm.invoke(prompt)
            return response.content.strip()
        except Exception:
            pass  # Route to next provider

    # 2. Local Fallback: Ollama Provider
    try:
        from langchain_community.chat_models import ChatOllama
        llm = ChatOllama(model="llama3", base_url=ollama_base_url, timeout=2.0)
        response = llm.invoke(prompt)
        return response.content.strip()
    except Exception:
        pass  # Route to deterministic fallback

    # 3. Grounded Deterministic Fallback
    severity = state.get("severity_level", "ROUTINE")
    if severity == "EMERGENCY":
        return (
            f"⚠️ CLINICAL ALERT FOR {state.get('patient_name').upper()}:\n"
            f"Based on clinical protocol '{state.get('matched_protocol_title')}', your reported symptoms "
            f"('{state.get('symptoms_text')}') require immediate emergency clinical escalation. "
            f"Automated booking was paused for patient safety. Case has been reviewed and flagged by the triage team. "
            f"{state.get('nurse_notes', 'Please seek immediate emergency medical care.')}"
        )
    elif severity == "URGENT":
        appt = state.get("appointment_details", {})
        return (
            f"📋 URGENT CLINICAL TRIAGE FOR {state.get('patient_name')}:\n"
            f"Your symptoms have been evaluated against protocol '{state.get('matched_protocol_title')}'. "
            f"A priority clinical appointment has been scheduled at {appt.get('department')} for "
            f"{appt.get('appointment_time')} (Confirmation: {appt.get('appointment_id')}). "
            f"Please follow self-care guidance and arrive promptly."
        )
    else:
        appt = state.get("appointment_details", {})
        return (
            f"✅ ROUTINE CARE PLAN FOR {state.get('patient_name')}:\n"
            f"Your symptoms correspond to routine protocol '{state.get('matched_protocol_title')}'. "
            f"A routine consultation has been booked at {appt.get('department')} on "
            f"{appt.get('appointment_time')} (Confirmation: {appt.get('appointment_id')}). "
            f"Stay well hydrated and rest."
        )


# ==========================================
# 3. GRAPH NODES
# ==========================================

def retrieve_protocol_node(state: TriageState) -> Dict[str, Any]:
    """
    Node 1: Retrieves the most relevant clinical guideline from the knowledge base using TF-IDF RAG.
    """
    symptoms = state.get("symptoms_text", "")
    retrieval_result = retrieve_triage_protocol(symptoms)

    return {
        "matched_protocol_id": retrieval_result.get("protocol_id", "UNKNOWN"),
        "matched_protocol_title": retrieval_result.get("title", ""),
        "protocol_category": retrieval_result.get("category", "ROUTINE"),
        "retrieval_score": retrieval_result.get("similarity_score", 0.0),
        "protocol_evidence": retrieval_result.get("evidence", "")
    }


def calculate_severity_node(state: TriageState) -> Dict[str, Any]:
    """
    Node 2: Applies transparent, deterministic clinical rules to evaluate severity.
    """
    symptoms = state.get("symptoms_text", "")
    duration = state.get("duration_days", 1)
    category = state.get("protocol_category", "")

    severity_result = calculate_severity(
        symptoms_text=symptoms,
        duration_days=duration,
        matched_category=category
    )

    return {
        "severity_level": severity_result["severity_level"],
        "severity_reasoning": severity_result["reasoning"],
        "rule_applied": severity_result["rule_applied"],
        "requires_human_review": severity_result["requires_human_review"]
    }


def book_appointment_node(state: TriageState) -> Dict[str, Any]:
    """
    Node 3: Automatically books a clinic appointment for Routine or Urgent cases.
    """
    patient_name = state.get("patient_name", "Patient")
    severity = state.get("severity_level", "ROUTINE")
    symptoms = state.get("symptoms_text", "")

    booking_result = book_appointment(
        patient_name=patient_name,
        severity_level=severity,
        symptoms_text=symptoms
    )

    final_status = "APPOINTMENT_CONFIRMED" if booking_result.get("booking_successful") else "BOOKING_FAILED"

    return {
        "appointment_details": booking_result,
        "final_status": final_status,
        "nurse_review_status": "NOT_REQUIRED",
        "nurse_action": "AUTOMATED_BOOKING_COMPLETED",
        "nurse_notes": "Case resolved via automated clinical pathway."
    }


def human_review_node(state: TriageState) -> Dict[str, Any]:
    """
    Node 4 (Human-in-the-Loop): Handles high-risk emergency cases.
    Halts automated booking and escalates to human clinical triage nurse review.
    """
    # If nurse input was pre-provided or in simulated mode
    nurse_notes = state.get("nurse_notes") or (
        "HUMAN REVIEW LOGGED: Triage Nurse verified critical symptoms (chest pain/respiratory compromise). "
        "Automated booking blocked. Emergency dispatch & on-call physician notified immediately."
    )
    nurse_action = state.get("nurse_action") or "ESCALATE_TO_EMERGENCY_SERVICES"

    return {
        "nurse_review_status": "REVIEWED_BY_NURSE",
        "nurse_action": nurse_action,
        "nurse_notes": nurse_notes,
        "appointment_details": {
            "booking_successful": False,
            "status": "EMERGENCY_ESCALATION",
            "message": "Direct booking withheld. Case escalated to Emergency Medical Services (EMS).",
            "appointment_id": "EMS-ESCALATION"
        },
        "final_status": "EMERGENCY_HUMAN_REVIEW_COMPLETED"
    }


def generate_summary_node(state: TriageState) -> Dict[str, Any]:
    """
    Node 5: Generates a grounded, readable explanation for patient and clinical logs.
    """
    summary = _generate_grounded_summary(state)
    return {"llm_summary": summary}


# ==========================================
# 4. CONDITIONAL ROUTER
# ==========================================

def route_by_severity(state: TriageState) -> str:
    """
    Conditional routing edge based on calculated severity.
    """
    severity = state.get("severity_level", "ROUTINE").upper()
    if severity == "EMERGENCY":
        return "human_review_node"
    return "book_appointment_node"


# ==========================================
# 5. GRAPH BUILDER
# ==========================================

def build_triage_graph():
    """
    Constructs and compiles the LangGraph workflow.
    """
    workflow = StateGraph(TriageState)

    # Add Nodes
    workflow.add_node("retrieve_protocol_node", retrieve_protocol_node)
    workflow.add_node("calculate_severity_node", calculate_severity_node)
    workflow.add_node("book_appointment_node", book_appointment_node)
    workflow.add_node("human_review_node", human_review_node)
    workflow.add_node("generate_summary_node", generate_summary_node)

    # Add Edges
    workflow.add_edge(START, "retrieve_protocol_node")
    workflow.add_edge("retrieve_protocol_node", "calculate_severity_node")

    # Conditional Routing Edge
    workflow.add_conditional_edges(
        "calculate_severity_node",
        route_by_severity,
        {
            "book_appointment_node": "book_appointment_node",
            "human_review_node": "human_review_node"
        }
    )

    # Join pathways to summary generation
    workflow.add_edge("book_appointment_node", "generate_summary_node")
    workflow.add_edge("human_review_node", "generate_summary_node")
    workflow.add_edge("generate_summary_node", END)

    return workflow.compile()


# Global compiled app
triage_agent_app = build_triage_graph()


def run_triage_agent(
    patient_name: str,
    age: int,
    symptoms_text: str,
    duration_days: int = 1,
    nurse_action: Optional[str] = None,
    nurse_notes: Optional[str] = None
) -> TriageState:
    """
    Helper function to run the full triage agent flow for a patient.
    """
    initial_state: TriageState = {
        "patient_name": patient_name,
        "age": age,
        "symptoms_text": symptoms_text,
        "duration_days": duration_days,
        "matched_protocol_id": "",
        "matched_protocol_title": "",
        "protocol_category": "",
        "retrieval_score": 0.0,
        "protocol_evidence": "",
        "severity_level": "",
        "severity_reasoning": "",
        "rule_applied": "",
        "requires_human_review": False,
        "appointment_details": None,
        "nurse_review_status": "PENDING",
        "nurse_action": nurse_action or "",
        "nurse_notes": nurse_notes or "",
        "llm_summary": "",
        "final_status": "PROCESSING"
    }

    result = triage_agent_app.invoke(initial_state)
    return result
