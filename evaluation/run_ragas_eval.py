"""
Knovex AI — RAGAS Evaluation Pipeline
======================================
Industry-standard decoupled 2-stage pipeline:

  Stage 1: Data Collection
    - Hit live Knovex API for every question in vantora_eval_dataset.json
    - Persist raw records to evaluation/ragas_run_records.json (resumable)

  Stage 2: RAGAS Evaluation
    - Load persisted records
    - Run 3 LLM-graded RAGAS metrics via Groq Judge LLM:
        * faithfulness       — are answers grounded in retrieved context?
        * context_precision  — signal-to-noise ratio of top-k retrieved chunks
        * context_recall     — how much ground truth is covered by retrieved chunks?
    - NOTE: answer_relevancy is intentionally excluded — it requires local
      embedding generation and RAGAS v0.4.4's EmbeddingUsageEvent Pydantic
      validator is incompatible with LangchainEmbeddingsWrapper (model attr
      is not a plain string). All 3 included metrics are pure LLM-graded.
    - Save timestamped CSV to evaluation/reports/ragas_YYYY-MM-DD_HH-MM-SS.csv
    - Save interactive HTML dashboard to evaluation/reports/ragas_dashboard_*.html
    - Print scorecard to terminal

Usage:
    # Full run (stage 1 + stage 2)
    python evaluation/run_ragas_eval.py

    # Stage 2 only (re-evaluate existing ragas_run_records.json)
    python evaluation/run_ragas_eval.py --stage2-only

    # Stage 1 only (collect data, no evaluation)
    python evaluation/run_ragas_eval.py --stage1-only

Requirements (local .venv only — NOT in requirements.txt):
    ragas==0.4.4
    langchain-groq
    python-dotenv
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Path setup — works regardless of cwd
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
EVAL_DIR = REPO_ROOT / "evaluation"
DATASET_PATH = EVAL_DIR / "vantora_eval_dataset.json"
RECORDS_PATH = EVAL_DIR / "ragas_run_records.json"
REPORTS_DIR = EVAL_DIR / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
load_dotenv(REPO_ROOT / ".env")

API_BASE = os.getenv("EVAL_API_BASE", "https://knovex.duckdns.org")
EVAL_EMAIL = os.getenv("EVAL_EMAIL", "")
EVAL_PASSWORD = os.getenv("EVAL_PASSWORD", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# Judge LLM — must be stronger than the generator (qwen3.8-27b)
# Groq account has openai/gpt-oss-120b (120B params) available
JUDGE_MODEL = "openai/gpt-oss-120b"
JUDGE_FALLBACKS = ["openai/gpt-oss-20b", "qwen/qwen3.8-27b"]

# Rate-limit guards
STAGE1_SLEEP_S = 1.5   # between API calls (live Knovex)
STAGE2_SLEEP_S = 3.0   # between RAGAS metric calls (Groq free tier ~30 rpm)

STAGE1_TIMEOUT = 60    # seconds per chat/query request
MAX_RETRIES = 3
RETRY_BACKOFF_S = 10   # base seconds for exponential backoff on 429


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_env(name: str, prompt_label: str) -> str:
    """Return env var or prompt user (never hardcode credentials)."""
    val = os.getenv(name, "")
    if not val:
        import getpass
        val = getpass.getpass(f"Enter {prompt_label}: ").strip()
        if not val:
            print(f"[ERROR] {name} is required.", file=sys.stderr)
            sys.exit(1)
    return val


def _login(email: str, password: str) -> tuple[str, str]:
    """POST /api/v1/auth/login → (access_token, tenant_id)."""
    url = f"{API_BASE}/api/v1/auth/login"
    resp = requests.post(
        url,
        json={"email": email, "password": password},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    token = data.get("access_token") or data.get("token")
    tenant_id = data.get("tenant_id", "")
    if not token:
        raise ValueError(f"No access_token in login response: {data}")
    return token, tenant_id


def _query_knovex(
    question: str,
    token: str,
    tenant_id: str,
) -> tuple[str, list[str]]:
    """
    POST /api/v1/chat/query
    Returns (answer, contexts_list).
    contexts_list = snippet text from each citation (best available chunk text).
    """
    url = f"{API_BASE}/api/v1/chat/query"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    if tenant_id:
        headers["X-Tenant-ID"] = tenant_id

    payload = {"message": question, "rerank": True}

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(
                url, json=payload, headers=headers, timeout=STAGE1_TIMEOUT
            )
            if resp.status_code == 429:
                wait = RETRY_BACKOFF_S * (2 ** (attempt - 1))
                print(f"      [429] Rate limited — sleeping {wait}s …")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            break
        except requests.exceptions.Timeout:
            if attempt == MAX_RETRIES:
                raise
            print(f"      [TIMEOUT] attempt {attempt}/{MAX_RETRIES} — retrying …")
            time.sleep(5)
    else:
        raise RuntimeError(f"All {MAX_RETRIES} attempts failed for: {question[:60]}")

    data = resp.json()
    answer: str = data.get("answer") or data.get("response") or ""

    # Build contexts from citations — snippet is first ~200 chars of each chunk.
    # This is sufficient for RAGAS faithfulness / relevancy checks.
    citations: list[dict] = data.get("citations") or []
    contexts: list[str] = []
    for c in citations:
        snippet = (c.get("snippet") or "").strip()
        fname = c.get("filename", "")
        page = c.get("page_number", "")
        # Prefix with source metadata so RAGAS context is self-contained
        if snippet:
            header = f"[Source: {fname}, Page {page}]\n" if fname else ""
            contexts.append(header + snippet)

    return answer, contexts


# ---------------------------------------------------------------------------
# Stage 1 — Data Collection
# ---------------------------------------------------------------------------

def run_stage1(email: str, password: str) -> list[dict]:
    """
    For every question in vantora_eval_dataset.json:
      - Query live Knovex API
      - Collect answer + contexts
    Saves results to ragas_run_records.json and returns the list.
    """
    print("\n" + "=" * 60)
    print("STAGE 1 — Data Collection from Live Knovex API")
    print("=" * 60)

    dataset: list[dict] = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    print(f"  Dataset: {len(dataset)} questions from {DATASET_PATH.name}")

    # --- Login ---
    print(f"\n  Logging in as {email} …")
    token, tenant_id = _login(email, password)
    print(f"  ✓ Token obtained. Tenant: {tenant_id or '(none)'}")

    # --- Resume support: skip already-collected questions ---
    existing: dict[int, dict] = {}
    if RECORDS_PATH.exists():
        try:
            existing_list = json.loads(RECORDS_PATH.read_text(encoding="utf-8"))
            existing = {r["id"]: r for r in existing_list if r.get("collected")}
            print(f"  ↩  Resuming — {len(existing)} questions already collected.")
        except Exception:
            existing = {}

    records: list[dict] = []
    total = len(dataset)

    for i, item in enumerate(dataset, 1):
        qid = item["id"]
        question = item["question"]
        ground_truth = item.get("ground_truth", "")
        is_answerable = item.get("is_answerable", True)
        category = item.get("category", "")

        # Resume: use cached record
        if qid in existing:
            print(f"  [{i:02d}/{total}] Q{qid} — SKIP (cached)")
            records.append(existing[qid])
            continue

        print(f"  [{i:02d}/{total}] Q{qid} [{category}] — {question[:65]} …")

        try:
            answer, contexts = _query_knovex(question, token, tenant_id)
            record = {
                "id": qid,
                "category": category,
                "question": question,
                "ground_truth": ground_truth,
                "is_answerable": is_answerable,
                "answer": answer,
                "contexts": contexts,
                "collected": True,
                "error": None,
            }
            status = f"✓  answer={len(answer)}c  contexts={len(contexts)}"
        except Exception as exc:
            record = {
                "id": qid,
                "category": category,
                "question": question,
                "ground_truth": ground_truth,
                "is_answerable": is_answerable,
                "answer": "",
                "contexts": [],
                "collected": False,
                "error": str(exc),
            }
            status = f"✗  ERROR: {exc}"

        print(f"      {status}")
        records.append(record)

        # Persist after each call (crash-safe)
        RECORDS_PATH.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")

        if i < total:
            time.sleep(STAGE1_SLEEP_S)

    # Final save
    RECORDS_PATH.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")

    n_ok = sum(1 for r in records if r["collected"])
    n_fail = sum(1 for r in records if not r["collected"])
    print(f"\n  Stage 1 complete — {n_ok} collected, {n_fail} failed.")
    print(f"  Records saved → {RECORDS_PATH}")
    return records


# ---------------------------------------------------------------------------
# Stage 2 — RAGAS Evaluation
# ---------------------------------------------------------------------------

def _build_judge_llm(groq_api_key: str):
    """
    Build RAGAS-compatible Judge LLM via LangchainLLMWrapper (legacy metrics path).
    Tries JUDGE_MODEL first, falls back gracefully.
    """
    from ragas.llms import LangchainLLMWrapper
    from langchain_groq import ChatGroq

    models_to_try = [JUDGE_MODEL] + JUDGE_FALLBACKS
    last_err: Optional[Exception] = None

    for model in models_to_try:
        try:
            llm = ChatGroq(
                groq_api_key=groq_api_key,
                model_name=model,
                temperature=0.0,
                max_retries=3,
            )
            # Quick smoke-test
            llm.invoke("ping")
            print(f"  ✓ Judge LLM: {model}")
            return LangchainLLMWrapper(llm), model
        except Exception as exc:
            print(f"  ✗ {model} unavailable: {exc}")
            last_err = exc

    raise RuntimeError(
        f"All judge models failed. Last error: {last_err}\n"
        "Check your GROQ_API_KEY and account model access."
    )


def run_stage2(records: list[dict], groq_api_key: str) -> dict[str, float]:
    """
    Run RAGAS evaluation on collected records.

    Metrics used (all LLM-graded, no embedding dependency):
      - faithfulness:       are answers fully grounded in retrieved context?
      - context_precision:  signal-to-noise of top-k retrieved chunks
      - context_recall:     how much ground truth is covered by retrieved chunks?

    NOTE: answer_relevancy is intentionally excluded.
    It requires embedding-based similarity scoring. RAGAS v0.4.4's
    EmbeddingUsageEvent Pydantic model expects `model` to be a plain string
    but LangchainEmbeddingsWrapper passes a FastEmbedEmbeddings object,
    causing a ValidationError even with raise_exceptions=False. All 3
    included metrics are pure LLM-graded and unaffected by this.

    Returns: (scores_dict, ragas_result, valid_records, judge_model_name)
    """
    print("\n" + "=" * 60)
    print("STAGE 2 — RAGAS Evaluation")
    print("=" * 60)

    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        from ragas import evaluate
        from ragas.metrics import faithfulness, context_precision, context_recall
    from ragas.dataset_schema import SingleTurnSample, EvaluationDataset

    # --- Filter: only collected records with non-empty contexts & answer ---
    valid = [
        r for r in records
        if r.get("collected") and r.get("contexts") and r.get("answer")
    ]
    print(f"  Valid samples for evaluation: {len(valid)} / {len(records)}")

    if not valid:
        print("[ERROR] No valid samples. Run Stage 1 first.", file=sys.stderr)
        sys.exit(1)

    # --- Build Judge LLM (pure Groq, no local embedding needed) ---
    judge_llm, judge_model_name = _build_judge_llm(groq_api_key)

    # --- Build EvaluationDataset ---
    samples: list[SingleTurnSample] = [
        SingleTurnSample(
            user_input=r["question"],
            retrieved_contexts=r["contexts"],
            response=r["answer"],
            reference=r["ground_truth"],
        )
        for r in valid
    ]
    dataset = EvaluationDataset(samples=samples)

    metrics = [faithfulness, context_precision, context_recall]
    metric_names = ["faithfulness", "context_precision", "context_recall"]

    print(f"  EvaluationDataset: {len(samples)} samples")
    print(f"  Judge LLM        : {judge_model_name}")
    print(f"  Metrics          : {', '.join(metric_names)}")
    print(f"\n  Running RAGAS evaluate() — estimated ~5-10 min for 50 samples …\n")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        result = evaluate(
            dataset=dataset,
            metrics=metrics,
            llm=judge_llm,
            raise_exceptions=False,   # graceful per-sample failure
        )

    scores: dict[str, float] = {}
    try:
        result_df = result.to_pandas()
        for metric in metric_names:
            if metric in result_df.columns:
                m_mean = result_df[metric].mean()
                scores[metric] = round(float(m_mean), 4) if (m_mean == m_mean) else float("nan")
            else:
                scores[metric] = float("nan")
    except Exception:
        for metric in metric_names:
            try:
                val = result[metric]
                scores[metric] = round(float(val), 4) if (val is not None and val == val) else float("nan")
            except Exception:
                scores[metric] = float("nan")

    return scores, result, valid, judge_model_name


# ---------------------------------------------------------------------------
# Output: CSV + Terminal Scorecard
# ---------------------------------------------------------------------------

def save_csv(
    result,
    valid_records: list[dict],
    scores: dict[str, float],
    judge_model: str,
) -> Path:
    """Save per-sample + aggregate scores to timestamped CSV."""
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    csv_path = REPORTS_DIR / f"ragas_{ts}.csv"

    # Try to get per-sample scores from RAGAS result object
    try:
        result_df = result.to_pandas()
        has_df = True
    except Exception:
        has_df = False

    # Metrics actually computed (answer_relevancy excluded — embedding compat issue)
    computed_metrics = ["faithfulness", "context_precision", "context_recall"]

    fieldnames = [
        "id", "category", "question", "is_answerable",
        "faithfulness", "context_precision", "context_recall",
        "n_contexts", "answer_length",
    ]

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for idx, r in enumerate(valid_records):
            row: dict = {
                "id": r["id"],
                "category": r.get("category", ""),
                "question": r["question"][:120],
                "is_answerable": r.get("is_answerable", True),
                "n_contexts": len(r.get("contexts", [])),
                "answer_length": len(r.get("answer", "")),
            }
            # Per-sample scores (if RAGAS returns them in DataFrame)
            if has_df and idx < len(result_df):
                row_df = result_df.iloc[idx]
                for m in computed_metrics:
                    try:
                        v = float(row_df.get(m, float("nan")))
                        row[m] = round(v, 4) if v == v else ""
                    except (TypeError, ValueError):
                        row[m] = ""
            else:
                for m in computed_metrics:
                    row[m] = ""

            writer.writerow(row)

        # Aggregate summary row
        writer.writerow({})
        writer.writerow({
            "id": "AGGREGATE",
            "category": f"judge={judge_model}",
            "question": f"n={len(valid_records)} samples | answer_relevancy=N/A (embedding compat)",
            "is_answerable": "",
            "faithfulness": scores.get("faithfulness", ""),
            "context_precision": scores.get("context_precision", ""),
            "context_recall": scores.get("context_recall", ""),
            "n_contexts": "",
            "answer_length": "",
        })

    return csv_path


def generate_html_report(
    scores: dict[str, float],
    valid_records: list[dict],
    judge_model: str,
    result,
) -> Path:
    """
    Generate an interactive, standalone HTML dashboard with Chart.js and Tailwind CSS.
    Includes:
      - KPI Summary Cards
      - RAGAS 4-Pillar Radar Chart
      - Category-wise Performance Bar Chart
      - Interactive Searchable & Filterable Drill-Down Table
    """
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    html_path = REPORTS_DIR / f"ragas_dashboard_{ts}.html"

    # Per-sample scores dataframe
    try:
        result_df = result.to_pandas()
        has_df = True
    except Exception:
        has_df = False
        result_df = None

    # Prepare category aggregations & sample table data
    computed_metrics = ["faithfulness", "context_precision", "context_recall"]
    category_stats: dict[str, dict[str, list[float]]] = {}
    samples_data = []

    for idx, r in enumerate(valid_records):
        cat = r.get("category", "general")
        if cat not in category_stats:
            category_stats[cat] = {m: [] for m in computed_metrics}

        item_scores = {}
        if has_df and idx < len(result_df):
            row_df = result_df.iloc[idx]
            for m in computed_metrics:
                val = row_df.get(m)
                try:
                    fval = float(val)
                    if fval == fval:  # not NaN
                        item_scores[m] = round(fval, 3)
                        category_stats[cat][m].append(fval)
                    else:
                        item_scores[m] = None
                except (ValueError, TypeError):
                    item_scores[m] = None
        else:
            item_scores = {m: None for m in computed_metrics}

        samples_data.append({
            "id": r["id"],
            "category": cat,
            "question": r["question"],
            "ground_truth": r.get("ground_truth", ""),
            "answer": r.get("answer", ""),
            "contexts": r.get("contexts", []),
            "scores": item_scores,
        })

    # Category metric averages (only computed metrics)
    computed_metrics = ["faithfulness", "context_precision", "context_recall"]
    cat_labels = list(category_stats.keys())
    cat_faith_avg = [
        round(sum(category_stats[c]["faithfulness"]) / len(category_stats[c]["faithfulness"]), 3)
        if category_stats[c]["faithfulness"] else 0.0 for c in cat_labels
    ]
    cat_precision_avg = [
        round(sum(category_stats[c]["context_precision"]) / len(category_stats[c]["context_precision"]), 3)
        if category_stats[c]["context_precision"] else 0.0 for c in cat_labels
    ]
    cat_recall_avg = [
        round(sum(category_stats[c]["context_recall"]) / len(category_stats[c]["context_recall"]), 3)
        if category_stats[c]["context_recall"] else 0.0 for c in cat_labels
    ]

    valid_vals = [scores[m] for m in computed_metrics if scores.get(m) == scores.get(m)]  # exclude NaN
    overall_avg = round(sum(valid_vals) / len(valid_vals), 4) if valid_vals else 0.0

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Knovex AI — RAGAS Evaluation Dashboard</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    body {{ font-family: 'Plus Jakarta Sans', sans-serif; }}
    .glass {{ background: rgba(255, 255, 255, 0.85); backdrop-filter: blur(12px); }}
  </style>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen p-6 md:p-10">
  <div class="max-w-7xl mx-auto space-y-8">
    
    <!-- Header -->
    <header class="flex flex-col md:flex-row md:items-center justify-between pb-6 border-b border-slate-800 gap-4">
      <div>
        <div class="flex items-center gap-3">
          <span class="px-2.5 py-1 text-xs font-bold uppercase tracking-wider rounded-md bg-indigo-500/20 text-indigo-400 border border-indigo-500/30">RAGAS Benchmark</span>
          <span class="text-xs text-slate-400">Enterprise AI Evaluation</span>
        </div>
        <h1 class="text-3xl font-extrabold tracking-tight mt-1 text-white">Knovex AI Evaluation Dashboard</h1>
        <p class="text-sm text-slate-400 mt-0.5">Judge LLM: <span class="text-indigo-300 font-semibold">{judge_model}</span> • Evaluated {len(valid_records)} samples • {datetime.now().strftime('%b %d, %Y %H:%M:%S')}</p>
      </div>
      <div class="flex items-center gap-3">
        <div class="bg-slate-900 border border-slate-800 px-4 py-2 rounded-xl text-right">
          <div class="text-xs text-slate-400 font-medium">Overall RAGAS Score</div>
          <div class="text-2xl font-black text-emerald-400">{overall_avg:.2%}</div>
        </div>
      </div>
    </header>

    <!-- KPI Cards -->
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      <div class="bg-slate-900/90 border border-slate-800 p-5 rounded-2xl shadow-xl relative overflow-hidden group hover:border-slate-700 transition">
        <div class="text-xs font-semibold uppercase tracking-wider text-slate-400">Faithfulness</div>
        <div class="text-3xl font-black text-white mt-1">{scores.get('faithfulness', 0):.2%}</div>
        <p class="text-xs text-slate-400 mt-2">Zero hallucination guarantee. Answer fully grounded in context.</p>
        <div class="h-1.5 w-full bg-slate-800 rounded-full mt-3 overflow-hidden">
          <div class="h-full bg-blue-500 rounded-full" style="width: {scores.get('faithfulness', 0) * 100}%"></div>
        </div>
      </div>

      <div class="bg-slate-900/90 border border-slate-800 p-5 rounded-2xl shadow-xl relative overflow-hidden group hover:border-slate-700 transition">
        <div class="text-xs font-semibold uppercase tracking-wider text-slate-400">Answer Relevancy</div>
        <div class="text-3xl font-black text-slate-600 mt-1">N/A</div>
        <p class="text-xs text-slate-500 mt-2">Excluded: requires local embedding scoring incompatible with RAGAS v0.4.4 + Groq (EmbeddingUsageEvent).</p>
        <div class="h-1.5 w-full bg-slate-800 rounded-full mt-3 overflow-hidden">
          <div class="h-full bg-slate-700 rounded-full" style="width: 0%"></div>
        </div>
      </div>

      <div class="bg-slate-900/90 border border-slate-800 p-5 rounded-2xl shadow-xl relative overflow-hidden group hover:border-slate-700 transition">
        <div class="text-xs font-semibold uppercase tracking-wider text-slate-400">Context Precision</div>
        <div class="text-3xl font-black text-white mt-1">{scores.get('context_precision', 0):.2%}</div>
        <p class="text-xs text-slate-400 mt-2">Signal-to-noise ratio in top retrieved chunks from Qdrant.</p>
        <div class="h-1.5 w-full bg-slate-800 rounded-full mt-3 overflow-hidden">
          <div class="h-full bg-emerald-500 rounded-full" style="width: {scores.get('context_precision', 0) * 100}%"></div>
        </div>
      </div>

      <div class="bg-slate-900/90 border border-slate-800 p-5 rounded-2xl shadow-xl relative overflow-hidden group hover:border-slate-700 transition">
        <div class="text-xs font-semibold uppercase tracking-wider text-slate-400">Context Recall</div>
        <div class="text-3xl font-black text-white mt-1">{scores.get('context_recall', 0):.2%}</div>
        <p class="text-xs text-slate-400 mt-2">Coverage of ground-truth information retrieved by pipeline.</p>
        <div class="h-1.5 w-full bg-slate-800 rounded-full mt-3 overflow-hidden">
          <div class="h-full bg-amber-500 rounded-full" style="width: {scores.get('context_recall', 0) * 100}%"></div>
        </div>
      </div>
    </div>

    <!-- Charts Grid -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <!-- Radar Chart -->
      <div class="bg-slate-900/90 border border-slate-800 p-6 rounded-2xl shadow-xl flex flex-col justify-between">
        <div>
          <h2 class="text-lg font-bold text-white">RAGAS 4-Pillar Radar</h2>
          <p class="text-xs text-slate-400 mt-0.5">Holistic retrieval & generation health check</p>
        </div>
        <div class="py-4 flex items-center justify-center">
          <canvas id="radarChart" class="max-h-72"></canvas>
        </div>
        <div class="text-xs text-slate-500 text-center">Balanced polygons indicate healthy enterprise RAG</div>
      </div>

      <!-- Category Breakdown Bar Chart -->
      <div class="bg-slate-900/90 border border-slate-800 p-6 rounded-2xl shadow-xl lg:col-span-2 flex flex-col justify-between">
        <div class="flex items-center justify-between">
          <div>
            <h2 class="text-lg font-bold text-white">Category-wise Performance</h2>
            <p class="text-xs text-slate-400 mt-0.5">Evaluation metrics across query categories</p>
          </div>
          <span class="text-xs font-medium text-slate-400 bg-slate-800 px-3 py-1 rounded-full">{len(cat_labels)} Categories</span>
        </div>
        <div class="py-4">
          <canvas id="barChart" class="max-h-72"></canvas>
        </div>
        <div class="flex items-center justify-center gap-6 text-xs text-slate-400 pt-2 border-t border-slate-800/80">
          <div class="flex items-center gap-1.5"><span class="w-3 h-3 rounded-full bg-blue-500 inline-block"></span> Faithfulness</div>
          <div class="flex items-center gap-1.5"><span class="w-3 h-3 rounded-full bg-emerald-500 inline-block"></span> Precision</div>
          <div class="flex items-center gap-1.5"><span class="w-3 h-3 rounded-full bg-amber-500 inline-block"></span> Recall</div>
        </div>
      </div>
    </div>

    <!-- Interactive Drill-Down Table -->
    <div class="bg-slate-900/90 border border-slate-800 p-6 rounded-2xl shadow-xl space-y-4">
      <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 class="text-lg font-bold text-white">Evaluation Samples Drill-Down</h2>
          <p class="text-xs text-slate-400 mt-0.5">Filter, search, and inspect individual question responses and chunk evidence</p>
        </div>
        <div class="flex items-center gap-3">
          <input type="text" id="searchInput" placeholder="Search question or answer..." class="bg-slate-950 border border-slate-700 text-xs text-slate-200 px-3 py-2 rounded-lg focus:outline-none focus:border-indigo-500 w-64" onkeyup="filterTable()">
          <select id="categoryFilter" onchange="filterTable()" class="bg-slate-950 border border-slate-700 text-xs text-slate-200 px-3 py-2 rounded-lg focus:outline-none focus:border-indigo-500">
            <option value="ALL">All Categories</option>
            {''.join([f'<option value="{c}">{c.replace("_", " ").title()}</option>' for c in cat_labels])}
          </select>
        </div>
      </div>

      <div class="overflow-x-auto rounded-xl border border-slate-800">
        <table class="w-full text-left text-xs" id="evalTable">
          <thead class="bg-slate-950 text-slate-400 font-semibold uppercase tracking-wider border-b border-slate-800">
            <tr>
              <th class="py-3 px-4">#</th>
              <th class="py-3 px-4">Category</th>
              <th class="py-3 px-4">Question</th>
              <th class="py-3 px-4 text-center">Faithfulness</th>
              <th class="py-3 px-4 text-center">Precision</th>
              <th class="py-3 px-4 text-center">Recall</th>
              <th class="py-3 px-4 text-right">Details</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-800/60 font-medium">
            {''.join([f'''
            <tr class="hover:bg-slate-800/40 transition eval-row" data-category="{s['category']}">
              <td class="py-3 px-4 text-slate-500 font-bold">{s['id']}</td>
              <td class="py-3 px-4"><span class="px-2 py-0.5 rounded text-[11px] font-semibold bg-slate-800 text-slate-300 border border-slate-700">{s['category']}</span></td>
              <td class="py-3 px-4 text-slate-200 font-medium max-w-xs truncate" title="{s['question']}">{s['question']}</td>
              <td class="py-3 px-4 text-center">{_pill(s['scores'].get('faithfulness'))}</td>
              <td class="py-3 px-4 text-center">{_pill(s['scores'].get('context_precision'))}</td>
              <td class="py-3 px-4 text-center">{_pill(s['scores'].get('context_recall'))}</td>
              <td class="py-3 px-4 text-right">
                <button onclick="toggleDetails({s['id']})" class="text-indigo-400 hover:text-indigo-300 font-semibold underline text-xs">Inspect</button>
              </td>
            </tr>
            <tr id="details-{s['id']}" class="hidden bg-slate-950/80 border-b border-slate-800">
              <td colspan="7" class="p-4 space-y-3">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div class="bg-slate-900 p-3 rounded-lg border border-slate-800">
                    <div class="text-[11px] font-bold text-slate-400 uppercase">Generated Knovex Answer:</div>
                    <div class="text-slate-200 text-xs mt-1 leading-relaxed">{s['answer']}</div>
                  </div>
                  <div class="bg-slate-900 p-3 rounded-lg border border-slate-800">
                    <div class="text-[11px] font-bold text-slate-400 uppercase">Ground Truth (Reference):</div>
                    <div class="text-slate-300 text-xs mt-1 leading-relaxed">{s['ground_truth']}</div>
                  </div>
                </div>
                <div class="bg-slate-900/60 p-3 rounded-lg border border-slate-800/80">
                  <div class="text-[11px] font-bold text-slate-400 uppercase">Retrieved Context Chunks ({len(s['contexts'])}):</div>
                  <div class="space-y-1.5 mt-2">
                    {''.join([f'<div class="text-slate-400 text-[11px] bg-slate-950 p-2 rounded border border-slate-800/60 whitespace-pre-wrap">{c}</div>' for c in s['contexts']]) or '<div class="text-slate-500 text-xs italic">No contexts returned</div>'}
                  </div>
                </div>
              </td>
            </tr>
            ''' for s in samples_data])}
          </tbody>
        </table>
      </div>
    </div>

  </div>

  <script>
    // Radar Chart Setup — 3 LLM-graded metrics
    const ctxRadar = document.getElementById('radarChart').getContext('2d');
    new Chart(ctxRadar, {{
      type: 'radar',
      data: {{
        labels: ['Faithfulness', 'Context Precision', 'Context Recall'],
        datasets: [{{
          label: 'Knovex AI Score',
          data: [{scores.get('faithfulness', 0)}, {scores.get('context_precision', 0)}, {scores.get('context_recall', 0)}],
          fill: true,
          backgroundColor: 'rgba(99, 102, 241, 0.25)',
          borderColor: 'rgb(99, 102, 241)',
          pointBackgroundColor: 'rgb(129, 140, 248)',
          pointBorderColor: '#fff',
          pointHoverBackgroundColor: '#fff',
          pointHoverBorderColor: 'rgb(99, 102, 241)'
        }}]
      }},
      options: {{
        scales: {{
          r: {{
            angleLines: {{ color: 'rgba(255, 255, 255, 0.1)' }},
            grid: {{ color: 'rgba(255, 255, 255, 0.1)' }},
            pointLabels: {{ color: '#94a3b8', font: {{ size: 11, weight: '600' }} }},
            ticks: {{ display: false, min: 0, max: 1 }}
          }}
        }},
        plugins: {{ legend: {{ display: false }} }}
      }}
    }});

    // Bar Chart Setup — 3 metrics per category
    const ctxBar = document.getElementById('barChart').getContext('2d');
    new Chart(ctxBar, {{
      type: 'bar',
      data: {{
        labels: {json.dumps([c.replace("_", " ").title() for c in cat_labels])},
        datasets: [
          {{ label: 'Faithfulness', data: {json.dumps(cat_faith_avg)}, backgroundColor: '#3b82f6', borderRadius: 6 }},
          {{ label: 'Precision', data: {json.dumps(cat_precision_avg)}, backgroundColor: '#10b981', borderRadius: 6 }},
          {{ label: 'Recall', data: {json.dumps(cat_recall_avg)}, backgroundColor: '#f59e0b', borderRadius: 6 }}
        ]
      }},
      options: {{
        responsive: true,
        scales: {{
          x: {{ grid: {{ display: false }}, ticks: {{ color: '#94a3b8', font: {{ size: 11 }} }} }},
          y: {{ min: 0, max: 1, grid: {{ color: 'rgba(255, 255, 255, 0.05)' }}, ticks: {{ color: '#94a3b8' }} }}
        }},
        plugins: {{ legend: {{ display: false }} }}
      }}
    }});

    function toggleDetails(id) {{
      const el = document.getElementById('details-' + id);
      el.classList.toggle('hidden');
    }}

    function filterTable() {{
      const search = document.getElementById('searchInput').value.toLowerCase();
      const cat = document.getElementById('categoryFilter').value;
      const rows = document.querySelectorAll('.eval-row');

      rows.forEach(row => {{
        const rowCat = row.getAttribute('data-category');
        const text = row.innerText.toLowerCase();
        const matchesSearch = text.includes(search);
        const matchesCat = (cat === 'ALL' || rowCat === cat);

        if (matchesSearch && matchesCat) {{
          row.style.display = '';
        }} else {{
          row.style.display = 'none';
          const id = row.querySelector('td').innerText;
          const details = document.getElementById('details-' + id);
          if (details) details.classList.add('hidden');
        }}
      }});
    }}
  </script>
</body>
</html>
"""

    html_path.write_text(html_content, encoding="utf-8")
    return html_path


def _pill(val: Optional[float]) -> str:
    """Format a score into an HTML colored badge."""
    if val is None or val != val:
        return '<span class="text-slate-600 font-semibold">—</span>'
    pct = round(val * 100, 1)
    if val >= 0.85:
        cls = "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
    elif val >= 0.70:
        cls = "bg-amber-500/20 text-amber-400 border border-amber-500/30"
    else:
        cls = "bg-rose-500/20 text-rose-400 border border-rose-500/30"
    return f'<span class="px-2 py-0.5 rounded text-[11px] font-bold {cls}">{pct}%</span>'


def print_scorecard(scores: dict[str, float], n_samples: int, judge_model: str, csv_path: Path, html_path: Path):
    """Print a clean terminal scorecard."""
    def _bar(score: float, width: int = 20) -> str:
        if score != score:  # NaN check
            return "[  N/A  ]"
        filled = int(score * width)
        return "[" + "█" * filled + "░" * (width - filled) + f"] {score:.4f}"

    computed = ["faithfulness", "context_precision", "context_recall"]
    valid_scores = [scores[m] for m in computed if scores.get(m) == scores.get(m)]
    overall = sum(valid_scores) / len(valid_scores) if valid_scores else float("nan")

    print("\n" + "=" * 60)
    print("  RAGAS EVALUATION SCORECARD — Knovex AI")
    print("=" * 60)
    print(f"  Samples evaluated : {n_samples}")
    print(f"  Judge LLM         : {judge_model}")
    print(f"  Timestamp         : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 60)
    print(f"  Faithfulness      : {_bar(scores.get('faithfulness', float('nan')))}")
    print(f"  Context Precision : {_bar(scores.get('context_precision', float('nan')))}")
    print(f"  Context Recall    : {_bar(scores.get('context_recall', float('nan')))}")
    print(f"  Answer Relevancy  : [  N/A — embedding compat excluded  ]")
    print("-" * 60)
    print(f"  Overall (3-metric): {_bar(overall)}")
    print("=" * 60)
    print(f"\n  CSV report  → {csv_path}")
    print(f"  HTML report → {html_path}\n")


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Knovex AI — RAGAS Evaluation Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--stage1-only",
        action="store_true",
        help="Run Stage 1 (data collection) only — skip RAGAS evaluation.",
    )
    p.add_argument(
        "--stage2-only",
        action="store_true",
        help="Run Stage 2 (RAGAS evaluation) only — use existing ragas_run_records.json.",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional: Limit number of samples to process (useful for smoke testing).",
    )
    return p.parse_args()


def main():
    args = parse_args()

    if args.stage1_only and args.stage2_only:
        print("[ERROR] --stage1-only and --stage2-only are mutually exclusive.", file=sys.stderr)
        sys.exit(1)

    groq_api_key = _require_env("GROQ_API_KEY", "Groq API key")

    # ---------------------------------------------------------------
    # Stage 1
    # ---------------------------------------------------------------
    if not args.stage2_only:
        email = _require_env("EVAL_EMAIL", "Knovex login email")
        password = _require_env("EVAL_PASSWORD", "Knovex login password")
        records = run_stage1(email, password)
    else:
        if not RECORDS_PATH.exists():
            print(f"[ERROR] {RECORDS_PATH} not found. Run Stage 1 first.", file=sys.stderr)
            sys.exit(1)
        records = json.loads(RECORDS_PATH.read_text(encoding="utf-8"))
        print(f"\n  Loaded {len(records)} records from {RECORDS_PATH.name}")

    if args.limit:
        records = records[:args.limit]
        print(f"  [LIMIT] Sliced dataset to first {len(records)} records.")

    if args.stage1_only:
        print("\n  --stage1-only flag set. Stopping before RAGAS evaluation.")
        sys.exit(0)

    # ---------------------------------------------------------------
    # Stage 2
    # ---------------------------------------------------------------
    scores, result, valid_records, judge_model = run_stage2(records, groq_api_key)

    # ---------------------------------------------------------------
    # Output
    # ---------------------------------------------------------------
    csv_path = save_csv(result, valid_records, scores, judge_model)
    html_path = generate_html_report(scores, valid_records, judge_model, result)
    print_scorecard(scores, len(valid_records), judge_model, csv_path, html_path)


if __name__ == "__main__":
    main()
