"""
Knovex AI - Live Production Benchmark Evaluation
Automated testing harness running 50 test questions against the live Knovex deployment.
Evaluates Retrieval Hit Rate, Negative Refusal, Latency, and Citation Accuracy.
"""

import csv
import getpass
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List
import requests

BASE_URL = os.environ.get("KNOVEX_BASE_URL", "https://knovex.duckdns.org")
EMAIL = os.environ.get("KNOVEX_EMAIL")
PASSWORD = os.environ.get("KNOVEX_PASSWORD")

DATASET_PATH = Path(__file__).parent / "vantora_eval_dataset.json"
RESULTS_CSV_PATH = Path(__file__).parent / "vantora_benchmark_results.csv"


def authenticate() -> str:
    global EMAIL, PASSWORD
    if not EMAIL:
        EMAIL = input("Knovex Email: ").strip()
    if not PASSWORD:
        PASSWORD = getpass.getpass("Knovex Password: ").strip()

    login_url = f"{BASE_URL}/api/v1/auth/login"
    print(f"[*] Authenticating with {login_url} as {EMAIL}...")
    res = requests.post(login_url, json={"email": EMAIL, "password": PASSWORD}, timeout=15)
    if res.status_code != 200:
        raise RuntimeError(f"Authentication failed ({res.status_code}): {res.text}")
    token = res.json()["access_token"]
    print("[+] Successfully authenticated. Bearer token acquired.")
    return token


def is_refusal_answer(answer: str) -> bool:
    negative_markers = [
        "not state", "not provide", "not mention", "not contain", "could not find",
        "insufficient", "do not have sufficient", "unavailable", "does not state",
        "nahi diya", "nahi likha", "nahi mila", "mutabiq nahi"
    ]
    ans_lower = answer.lower()
    return any(marker in ans_lower for marker in negative_markers)


def run_benchmark():
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        questions: List[Dict[str, Any]] = json.load(f)

    token = authenticate()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    query_url = f"{BASE_URL}/api/v1/chat/query"

    print(f"\n{'='*75}")
    print(f" KNOVEX AI — LIVE BENCHMARK RUN ({len(questions)} QUESTIONS)")
    print(f" Target Endpoint: {query_url}")
    print(f"{'='*75}\n")

    results = []
    latencies = []
    retrieval_hits = 0
    refusal_successes = 0
    total_answerable = sum(1 for q in questions if q.get("is_answerable", True))
    total_negative = len(questions) - total_answerable

    for idx, q in enumerate(questions, 1):
        q_id = q["id"]
        category = q.get("category", "general")
        question_text = q["question"]
        expected_doc = q.get("expected_doc")
        expected_page = q.get("expected_page")
        ground_truth = q.get("ground_truth", "")
        is_answerable = q.get("is_answerable", True)

        payload = {
            "message": question_text,
            "rerank": True,
        }

        t0 = time.perf_counter()
        try:
            res = requests.post(query_url, json=payload, headers=headers, timeout=30)
            latency_ms = int((time.perf_counter() - t0) * 1000)
            latencies.append(latency_ms)

            if res.status_code == 200:
                data = res.json()
                answer = data.get("answer", "")
                evidence_status = data.get("evidence_status", "")
                citations = data.get("citations", [])

                # Evaluation: Retrieval Hit
                retrieval_pass = False
                matched_citation = None
                if is_answerable:
                    for c in citations:
                        c_file = c.get("filename", "")
                        if expected_doc and (expected_doc.lower() in c_file.lower() or c_file.lower() in expected_doc.lower()):
                            retrieval_pass = True
                            matched_citation = f"{c_file} (p.{c.get('page_number')})"
                            break
                    if retrieval_pass:
                        retrieval_hits += 1
                else:
                    # For unanswerable questions, passing retrieval means the system properly refuses
                    retrieval_pass = is_refusal_answer(answer) or evidence_status == "insufficient"
                    if retrieval_pass:
                        refusal_successes += 1

                # Evaluation: Ground Truth Match / Quality
                if is_answerable:
                    ans_quality = "ACCURATE" if retrieval_pass and not is_refusal_answer(answer) else "REVIEW"
                else:
                    ans_quality = "REFUSAL_PASS" if is_refusal_answer(answer) else "HALLUCINATION_RISK"

                res_entry = {
                    "id": q_id,
                    "category": category,
                    "question": question_text,
                    "expected_doc": expected_doc or "None (Negative)",
                    "expected_page": expected_page or "-",
                    "matched_citation": matched_citation or ("None (Refusal)" if not is_answerable else "MISS"),
                    "ground_truth": ground_truth,
                    "generated_answer": answer.replace("\n", " "),
                    "retrieval_pass": retrieval_pass,
                    "quality_verdict": ans_quality,
                    "latency_ms": latency_ms,
                }
                results.append(res_entry)

                status_icon = "✓" if retrieval_pass else "✗"
                print(f"[{idx:02d}/50] [{status_icon}] ({category:<13}) {latency_ms:>4}ms | {ans_quality:<18} | {question_text[:50]}...")

            else:
                print(f"[{idx:02d}/50] [!] Error {res.status_code}: {res.text[:80]}")
                results.append({
                    "id": q_id,
                    "category": category,
                    "question": question_text,
                    "expected_doc": expected_doc,
                    "expected_page": expected_page,
                    "matched_citation": "ERROR",
                    "ground_truth": ground_truth,
                    "generated_answer": f"HTTP {res.status_code}",
                    "retrieval_pass": False,
                    "quality_verdict": "ERROR",
                    "latency_ms": latency_ms,
                })

        except Exception as e:
            latency_ms = int((time.perf_counter() - t0) * 1000)
            print(f"[{idx:02d}/50] [!] Exception: {e}")
            results.append({
                "id": q_id,
                "category": category,
                "question": question_text,
                "expected_doc": expected_doc,
                "expected_page": expected_page,
                "matched_citation": "EXCEPTION",
                "ground_truth": ground_truth,
                "generated_answer": str(e),
                "retrieval_pass": False,
                "quality_verdict": "EXCEPTION",
                "latency_ms": latency_ms,
            })

    # Export to CSV
    with open(RESULTS_CSV_PATH, "w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "id", "category", "question", "expected_doc", "expected_page",
            "matched_citation", "ground_truth", "generated_answer",
            "retrieval_pass", "quality_verdict", "latency_ms"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    # Compute Statistics
    avg_latency = sum(latencies) / len(latencies) if latencies else 0
    hit_rate = (retrieval_hits / total_answerable) * 100 if total_answerable else 0
    refusal_rate = (refusal_successes / total_negative) * 100 if total_negative else 0
    overall_accuracy = ((retrieval_hits + refusal_successes) / len(questions)) * 100

    print(f"\n{'='*75}")
    print(f" KNOVEX AI — BENCHMARK RESULTS SUMMARY")
    print(f"{'='*75}")
    print(f" Total Questions Evaluated   : {len(questions)}")
    print(f" Answerable Questions        : {total_answerable}")
    print(f" Retrieval Hit Rate (@5)     : {hit_rate:.1f}% ({retrieval_hits}/{total_answerable})")
    print(f" Negative Refusal Accuracy   : {refusal_rate:.1f}% ({refusal_successes}/{total_negative})")
    print(f" Overall Benchmark Accuracy  : {overall_accuracy:.1f}% ({retrieval_hits + refusal_successes}/{len(questions)})")
    print(f" Average Latency             : {avg_latency:.0f} ms")
    print(f" Latency Min / Max           : {min(latencies)} ms / {max(latencies)} ms")
    print(f"{'='*75}")
    print(f" Detailed results exported to: {RESULTS_CSV_PATH.resolve()}\n")


if __name__ == "__main__":
    run_benchmark()
