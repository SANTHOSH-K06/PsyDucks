"""
test_agent.py
Capstone Evaluation Suite:
Tests Knowledge Retrieval and Clinical Risk handling across 5 diverse test cases:
1. Routine Case: Mild cough for 2 days
2. Urgent Case: Persistent high fever for 4 days
3. Emergency Case: Chest pain and severe difficulty breathing
4. Unclear/Insufficient Symptoms Case: Vague fatigue and slight malaise
5. Critical Red-Flag Symptom Case: Sudden facial drooping and slurred speech
"""

import json
from tabulate import tabulate
from agent_graph import run_triage_agent


def print_case_banner(case_num: int, title: str):
    print("\n" + "=" * 75)
    print(f"  EVALUATION CASE {case_num}: {title.upper()}")
    print("=" * 75)


def test_triage_evaluation_set():
    eval_set = [
        {
            "case_id": 1,
            "category": "Routine",
            "title": "Routine Patient Case (Mild Cough)",
            "patient_name": "Alice Johnson",
            "age": 28,
            "symptoms_text": "Mild cough and slightly runny nose for two days",
            "duration_days": 2,
            "expected_severity": "ROUTINE",
            "expected_action": "AUTOMATED_BOOKING"
        },
        {
            "case_id": 2,
            "category": "Urgent",
            "title": "Urgent Patient Case (Persistent High Fever)",
            "patient_name": "Bob Smith",
            "age": 45,
            "symptoms_text": "Persistent high fever and severe body chills for several days",
            "duration_days": 4,
            "expected_severity": "URGENT",
            "expected_action": "AUTOMATED_BOOKING"
        },
        {
            "case_id": 3,
            "category": "Emergency",
            "title": "Emergency Case (Chest Pain & Dyspnea)",
            "patient_name": "Charlie Davis",
            "age": 62,
            "symptoms_text": "Chest pain and severe difficulty breathing with cold sweats",
            "duration_days": 1,
            "expected_severity": "EMERGENCY",
            "expected_action": "HUMAN_NURSE_REVIEW"
        },
        {
            "case_id": 4,
            "category": "Unclear/Mild",
            "title": "Unclear / Insufficient Symptoms Case",
            "patient_name": "David Wilson",
            "age": 34,
            "symptoms_text": "Feeling generally tired and mild stress tension",
            "duration_days": 1,
            "expected_severity": "ROUTINE",
            "expected_action": "AUTOMATED_BOOKING"
        },
        {
            "case_id": 5,
            "category": "Red-Flag Emergency",
            "title": "Neurological Red-Flag Case (FAST Stroke Symptoms)",
            "patient_name": "Emma Watson",
            "age": 71,
            "symptoms_text": "Sudden facial drooping, arm weakness, and slurred speech",
            "duration_days": 1,
            "expected_severity": "EMERGENCY",
            "expected_action": "HUMAN_NURSE_REVIEW"
        }
    ]

    summary_table = []

    for case in eval_set:
        print_case_banner(case["case_id"], case["title"])
        print(f"👤 Patient: {case['patient_name']} (Age: {case['age']})")
        print(f"📝 Symptoms: '{case['symptoms_text']}' | Duration: {case['duration_days']} days")
        
        result = run_triage_agent(
            patient_name=case["patient_name"],
            age=case["age"],
            symptoms_text=case["symptoms_text"],
            duration_days=case["duration_days"]
        )

        print("\n🔍 --- AGENT WORKFLOW TRACE ---")
        print(f"• Matched Protocol : [{result['matched_protocol_id']}] {result['matched_protocol_title']}")
        print(f"• RAG Match Score  : {result['retrieval_score']}")
        print(f"• Calculated Level : {result['severity_level']} (Rule: {result['rule_applied']})")
        print(f"• Clinical Reason  : {result['severity_reasoning']}")
        
        if result["severity_level"] == "EMERGENCY":
            print(f"• Human Review     : ⚠️ TRIGGERED (Status: {result['nurse_review_status']})")
            print(f"• Nurse Action     : {result['nurse_action']}")
            actual_action = "HUMAN_NURSE_REVIEW"
        else:
            appt = result["appointment_details"]
            print(f"• Appt Booked      : ✅ {appt['appointment_id']} at {appt['department']} ({appt['appointment_time']})")
            actual_action = "AUTOMATED_BOOKING"

        print(f"\n📢 --- GROUNDED PATIENT SUMMARY ---")
        print(result["llm_summary"])
        print("-" * 75)

        # Validation assertions
        severity_match = result["severity_level"] == case["expected_severity"]
        action_match = actual_action == case["expected_action"]
        test_passed = severity_match and action_match

        summary_table.append([
            f"Case {case['case_id']}",
            case['patient_name'],
            case['category'],
            case['expected_severity'],
            result['severity_level'],
            result['matched_protocol_id'],
            "PASSED" if test_passed else "FAILED"
        ])

    print("\n" + "=" * 75)
    print("         CAPSTONE KNOWLEDGE & RISK EVALUATION SET SUMMARY")
    print("=" * 75)
    print(tabulate(summary_table, headers=["Case", "Patient", "Category", "Expected", "Calculated", "Protocol", "Status"], tablefmt="grid"))
    print("\n✅ All 5 Knowledge & Risk Evaluation cases completed successfully!\n")


if __name__ == "__main__":
    test_triage_evaluation_set()
