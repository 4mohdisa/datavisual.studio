"""FastAPI backend for Datavisual.studio."""

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import uuid
import json
import asyncio
import os
import shutil
from datetime import datetime
from pathlib import Path

from . import storage
from .council import run_full_council, generate_conversation_title, stage1_collect_responses, stage2_collect_rankings, stage3_synthesize_final, calculate_aggregate_rankings
from .config import COUNCIL_MODELS, DEBUG
from .data_analysis import analyse_file
from .research import build_search_plan, run_single_search, combine_findings, detect_event_status, extract_confirmed_facts
from .report_builder import build_enriched_prompt, build_report, extract_predictions
from .prediction_engine import (
    extract_dataset_probs,
    build_dataset_models,
    extract_internet_probs,
    extract_council_probs,
    compute_prediction,
    predictions_to_table,
    probs_to_prediction_results,
    format_chairman_prediction_block,
    generate_prediction_charts,
    build_match_features,
    train_xgboost_model,
    run_monte_carlo_xgboost,
    xgboost_available,
    xgboost_feature_importance,
)


# ---------------------------------------------------------------------------
# Activity events — granular SSE events for the frontend Activity Panel.
# These are ADDITIONS; all existing event types remain unchanged.
# ---------------------------------------------------------------------------

_CHART_LABELS = {
    "line": "Line chart",
    "bar": "Bar chart",
    "scatter": "Scatter plot",
    "histogram": "Histogram",
    "heatmap": "Heatmap",
}


def _activity_payload(event: str, detail: str, reasoning: str = "", links: list | None = None) -> dict:
    """Build an activity event payload. `reasoning` is a 1–2 sentence first-person
    description of what the AI is doing/why, shown in the Research Activity tab."""
    return {
        "type": "activity",
        "event": event,
        "detail": detail,
        "reasoning": reasoning,
        "links": links or [],
        "ts": datetime.utcnow().isoformat() + "Z",
    }


def _activity(event: str, detail: str, reasoning: str = "", links: list | None = None) -> str:
    """Format an activity SSE event string."""
    return f"data: {json.dumps(_activity_payload(event, detail, reasoning, links))}\n\n"


def _model_display(model: str) -> str:
    return model.split("/")[-1]

# Monte-Carlo tournament runs for the dataset ELO baseline. Surfaced verbatim in
# the council prompt, the prediction charts, and the frontend explainer box.
_N_SIMULATIONS = 10000

UPLOADS_DIR = "data/uploads"
EXPORTS_DIR = "data/exports"

Path(UPLOADS_DIR).mkdir(parents=True, exist_ok=True)
Path(EXPORTS_DIR).mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="Datavisual.studio API",
    version="1.0.0",
    description="Multi-model AI prediction platform API",
)

# Compress responses (5.2) — large report/dataset payloads shrink significantly.
from fastapi.middleware.gzip import GZipMiddleware
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CreateConversationRequest(BaseModel):
    """Request to create a new conversation."""
    pass


class SendMessageRequest(BaseModel):
    """Request to send a message in a conversation."""
    content: str


class ConversationMetadata(BaseModel):
    """Conversation metadata for list view."""
    id: str
    created_at: str
    title: str
    message_count: int


class Conversation(BaseModel):
    """Full conversation with all messages."""
    id: str
    created_at: str
    title: str
    messages: List[Dict[str, Any]]


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "Datavisual.studio API"}


class ErrorLogRequest(BaseModel):
    """A client-side error report (7.2)."""
    message: str
    stack: Optional[str] = None
    component_stack: Optional[str] = None


@app.post("/api/error-log")
async def error_log(request: ErrorLogRequest):
    """Append a client error to data/error.log (simple file append, no database).

    Example body: {"message": "x is undefined", "stack": "...", "component_stack": "..."}
    """
    try:
        Path("data").mkdir(parents=True, exist_ok=True)
        with open("data/error.log", "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts": datetime.utcnow().isoformat() + "Z",
                "message": request.message,
                "stack": request.stack,
                "component_stack": request.component_stack,
            }) + "\n")
    except Exception:
        pass  # logging must never fail the request
    return {"logged": True}


@app.get("/api/conversations", response_model=List[ConversationMetadata])
async def list_conversations():
    """List all conversations (metadata only)."""
    return storage.list_conversations()


@app.post("/api/conversations", response_model=Conversation)
async def create_conversation(request: CreateConversationRequest):
    """Create a new conversation."""
    conversation_id = str(uuid.uuid4())
    conversation = storage.create_conversation(conversation_id)
    return conversation


class CreateConversationWithIdRequest(BaseModel):
    """Create a conversation with a client-generated id (used by the router flow)."""
    conversation_id: str
    title: Optional[str] = None
    file_id: Optional[str] = None
    match_history_file_id: Optional[str] = None


@app.post("/api/conversations/create")
async def create_conversation_with_id(request: CreateConversationWithIdRequest):
    """Create the initial conversation JSON for a client-generated id.

    The frontend generates the uuid, navigates to /chat/{id}, then calls this
    before opening the SSE stream. Idempotent: an existing conversation that
    already has messages is left untouched.
    """
    existing = storage.get_conversation(request.conversation_id)
    if existing and existing.get("messages"):
        return {"conversation_id": request.conversation_id}

    conversation = {
        "id": request.conversation_id,
        "created_at": datetime.utcnow().isoformat(),
        "title": request.title or "New conversation",
        "messages": [],
        "pipeline": {},
        "status": "pending",
        "current_stage": "pending",
        "error_message": None,
    }
    if request.file_id:
        conversation["file_id"] = request.file_id
    if request.match_history_file_id:
        conversation["match_history_file_id"] = request.match_history_file_id
    storage.save_conversation(conversation)
    return {"conversation_id": request.conversation_id}


# Progress percentage for each pipeline stage (Part 2b).
_PROGRESS_PCT = {
    "pending": 0,
    "data_analysis": 15,
    "research": 30,
    "council_stage1": 50,
    "council_stage2": 65,
    "council_stage3": 80,
    "synthesis": 90,
    "done": 100,
    "complete": 100,
}


def update_conversation_status(
    conversation_id: str,
    status: str,
    stage: str | None = None,
    error_message: str | None = None,
):
    """Load → update → save the conversation's status/stage fields. Used at every
    major pipeline transition so a reloaded client can poll for progress."""
    conv = storage.get_conversation(conversation_id)
    if conv is None:
        return
    conv["status"] = status
    if stage is not None:
        conv["current_stage"] = stage
    if error_message is not None:
        conv["error_message"] = error_message
    storage.save_conversation(conv)


@app.get("/api/conversations/{conversation_id}/status")
async def get_conversation_status(conversation_id: str):
    """Poll endpoint — current pipeline status/stage/progress for a conversation."""
    conv = storage.get_conversation(conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    status = conv.get("status", "pending")
    stage = conv.get("current_stage", "pending")
    has_report = bool((conv.get("pipeline") or {}).get("report"))
    progress_pct = 100 if status == "complete" else _PROGRESS_PCT.get(stage, 0)

    return {
        "status": status,
        "current_stage": stage,
        "error_message": conv.get("error_message"),
        "has_report": has_report,
        "progress_pct": progress_pct,
    }


@app.get("/api/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """Get a specific conversation with all its messages.

    Returns the raw stored dict (no response_model) so the frontend also receives
    pipeline data — including the persisted `activity` log and `file` info — which
    a strict response_model would otherwise strip out.
    """
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@app.get("/api/dataset/{conversation_id}")
async def get_dataset_rows(conversation_id: str, limit: int = 2000):
    """Return the raw rows of a conversation's uploaded dataset (capped) for the
    interactive dashboard data table. Columns + records, JSON-safe."""
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    file_info = conversation.get("file")
    if not file_info or not file_info.get("path") or not os.path.exists(file_info["path"]):
        raise HTTPException(status_code=404, detail="No dataset file for this conversation")

    from .data_analysis import _load
    import numpy as np
    try:
        df = _load(file_info["path"])
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Could not read dataset: {e}")

    total = len(df)
    df = df.head(max(1, min(limit, 5000)))
    # JSON-safe records (NaN → None).
    df = df.replace({np.nan: None})
    return {
        "columns": [str(c) for c in df.columns],
        "rows": df.to_dict(orient="records"),
        "total_rows": total,
        "returned_rows": len(df),
    }


@app.post("/api/conversations/{conversation_id}/message")
async def send_message(conversation_id: str, request: SendMessageRequest):
    """
    Send a message and run the 3-stage council process.
    Returns the complete response with all stages.
    """
    # Check if conversation exists
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if this is the first message
    is_first_message = len(conversation["messages"]) == 0

    # Add user message
    storage.add_user_message(conversation_id, request.content)

    # If this is the first message, generate a title
    if is_first_message:
        title = await generate_conversation_title(request.content)
        storage.update_conversation_title(conversation_id, title)

    # Run the 3-stage council process
    stage1_results, stage2_results, stage3_result, metadata = await run_full_council(
        request.content
    )

    # Add assistant message with all stages
    storage.add_assistant_message(
        conversation_id,
        stage1_results,
        stage2_results,
        stage3_result
    )

    # Return the complete response with metadata
    return {
        "stage1": stage1_results,
        "stage2": stage2_results,
        "stage3": stage3_result,
        "metadata": metadata
    }


@app.post("/api/conversations/{conversation_id}/message/stream")
async def send_message_stream(conversation_id: str, request: SendMessageRequest):
    """
    Send a message and stream the 3-stage council process.
    Returns Server-Sent Events as each stage completes.
    """
    # Check if conversation exists
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if this is the first message
    is_first_message = len(conversation["messages"]) == 0

    async def event_generator():
        try:
            # Add user message
            storage.add_user_message(conversation_id, request.content)

            # Start title generation in parallel (don't await yet)
            title_task = None
            if is_first_message:
                title_task = asyncio.create_task(generate_conversation_title(request.content))

            # Stage 1: Collect responses
            yield f"data: {json.dumps({'type': 'stage1_start'})}\n\n"
            stage1_results = await stage1_collect_responses(request.content)
            yield f"data: {json.dumps({'type': 'stage1_complete', 'data': stage1_results})}\n\n"

            # Stage 2: Collect rankings
            yield f"data: {json.dumps({'type': 'stage2_start'})}\n\n"
            stage2_results, label_to_model = await stage2_collect_rankings(request.content, stage1_results)
            aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_model)
            yield f"data: {json.dumps({'type': 'stage2_complete', 'data': stage2_results, 'metadata': {'label_to_model': label_to_model, 'aggregate_rankings': aggregate_rankings}})}\n\n"

            # Stage 3: Synthesize final answer
            yield f"data: {json.dumps({'type': 'stage3_start'})}\n\n"
            stage3_result = await stage3_synthesize_final(request.content, stage1_results, stage2_results)
            yield f"data: {json.dumps({'type': 'stage3_complete', 'data': stage3_result})}\n\n"

            # Wait for title generation if it was started
            if title_task:
                title = await title_task
                storage.update_conversation_title(conversation_id, title)
                yield f"data: {json.dumps({'type': 'title_complete', 'data': {'title': title}})}\n\n"

            # Save complete assistant message
            storage.add_assistant_message(
                conversation_id,
                stage1_results,
                stage2_results,
                stage3_result
            )

            # Send completion event
            yield f"data: {json.dumps({'type': 'complete'})}\n\n"

        except Exception as e:
            # Send error event
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


# ---------------------------------------------------------------------------
# New endpoints — datavisual.studio extension
# ---------------------------------------------------------------------------

class AnalyseRequest(BaseModel):
    question: str
    file_id: Optional[str] = None
    match_history_file_id: Optional[str] = None
    conversation_id: str


class ReanalyseRequest(BaseModel):
    conversation_id: str
    filters: Dict[str, Any]


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """Accept a CSV/Excel/JSON file upload and return metadata."""
    import pandas as pd

    allowed_extensions = {".csv", ".xls", ".xlsx", ".json"}
    suffix = Path(file.filename).suffix.lower()
    if suffix not in allowed_extensions:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {suffix}")

    file_id = str(uuid.uuid4())
    save_name = f"{file_id}_{file.filename}"
    save_path = os.path.join(UPLOADS_DIR, save_name)

    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        result = analyse_file(save_path)
    except Exception as e:
        os.unlink(save_path)
        raise HTTPException(status_code=422, detail=f"Could not read file: {e}")

    if result.get("error"):
        os.unlink(save_path)
        raise HTTPException(status_code=422, detail=result["error"])
    summary = result["data_summary"]

    return {
        "file_id": file_id,
        "filename": file.filename,
        "save_name": save_name,
        "rows": summary["row_count"],
        "columns": summary["column_count"],
    }


@app.post("/api/analyse")
async def analyse(request: AnalyseRequest):
    """
    Main pipeline endpoint. Streams SSE events following the existing pattern.

    First message: full pipeline (data analysis → internet research → council → report)
    Follow-up: chairman only (or full re-run if message starts with !council)
    """
    conversation = storage.get_conversation(request.conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    is_first_message = len(conversation["messages"]) == 0
    force_council = request.question.strip().startswith("!council")
    actual_question = request.question.strip().removeprefix("!council").strip() if force_council else request.question

    async def event_generator():
        current_stage = "initialising"
        # Accumulate activity events so they can be persisted with the conversation
        # and replayed in the Activity Panel after a reload.
        activity_events: list = []

        def act(event: str, detail: str, reasoning: str = "", links: list | None = None) -> str:
            payload = _activity_payload(event, detail, reasoning, links)
            activity_events.append(payload)
            return f"data: {json.dumps(payload)}\n\n"

        try:
            storage.add_user_message(request.conversation_id, request.question)

            # ----------------------------------------------------------------
            # FIRST MESSAGE or forced council re-run
            # ----------------------------------------------------------------
            if is_first_message or force_council:
                title_task = None
                if is_first_message:
                    title_task = asyncio.create_task(generate_conversation_title(actual_question))

                # Determine mode
                mode = "data" if request.file_id else "text"

                # Mark the conversation as running so a reloaded client can poll.
                update_conversation_status(request.conversation_id, "running", "data_analysis")

                # Data analysis
                data_summary = None
                charts = []
                data_excerpt = None
                data_df = None  # in-memory dataframe — fuels the prediction engine
                if mode == "data":
                    current_stage = "data analysis"
                    yield f"data: {json.dumps({'type': 'analysis_start'})}\n\n"
                    file_record = _find_upload(request.file_id)
                    if file_record is None:
                        yield act("stage_error", "data analysis: uploaded file not found")
                        yield f"data: {json.dumps({'type': 'error', 'message': 'Uploaded file not found'})}\n\n"
                        return
                    analysis_result = analyse_file(file_record["path"])
                    # Surface a structured error from data analysis (empty/malformed file)
                    if isinstance(analysis_result, dict) and analysis_result.get("error"):
                        msg = analysis_result["error"]
                        yield act("stage_error", f"data analysis: {msg}")
                        yield f"data: {json.dumps({'type': 'error', 'message': msg})}\n\n"
                        return
                    data_summary = analysis_result["data_summary"]
                    charts = analysis_result["charts"]
                    data_excerpt = analysis_result.get("data_excerpt")
                    data_df = analysis_result.get("dataframe")
                    yield f"data: {json.dumps({'type': 'analysis_complete', 'data': {'data_summary': data_summary, 'charts': charts}})}\n\n"

                    # Activity: dataset analysed + charts generated
                    chart_titles = ", ".join(c["title"] for c in charts)
                    yield act(
                        "dataset_analysed",
                        f"{data_summary['row_count']:,} rows · {data_summary['column_count']} columns · "
                        f"{len(charts)} charts detected" + (f" ({chart_titles})" if chart_titles else ""),
                        reasoning="Profiling the uploaded dataset to understand its structure and surface the actual values the council should reason over.",
                    )
                    if charts:
                        labels = []
                        for c in charts:
                            lbl = _CHART_LABELS.get(c.get("type"), f"{str(c.get('type', '')).capitalize()} chart")
                            if lbl not in labels:
                                labels.append(lbl)
                        yield act(
                            "charts_generated",
                            " · ".join(labels),
                            reasoning="Auto-generating visualisations to reveal the key trends and distributions in the data.",
                        )

                # ----------------------------------------------------------------
                # Phase 1 — run the mathematical models (Model A = ELO Monte Carlo,
                # Model B = ELO-Poisson/Dixon-Coles). Their ensemble is the dataset
                # baseline: ALWAYS produced when numeric data exists, injected into
                # the council prompt, and the guaranteed fallback for the final table.
                # ----------------------------------------------------------------
                dataset_models = build_dataset_models(
                    data_df, data_summary.get("columns", []) if data_summary else [],
                    n_simulations=_N_SIMULATIONS,
                )
                model_a_probs = dataset_models["model_a_probs"]
                model_b_probs = dataset_models["model_b_probs"]
                ensemble_probs = dataset_models["ensemble_probs"]
                model_a_results = dataset_models["model_a_results"]
                model_b_results = dataset_models["model_b_results"]
                ensemble_results = dataset_models["ensemble_results"]
                entity_names = dataset_models["entity_names"]
                dataset_method = dataset_models["method"]
                agreement = dataset_models.get("agreement", {})

                # ----------------------------------------------------------------
                # Model C — XGBoost, only when a match-history file was uploaded.
                # Degrades gracefully (skip events) if xgboost/OpenMP is missing,
                # there's no match data, or there aren't enough rows to train on.
                # ----------------------------------------------------------------
                model_c_results = []
                model_c_match_count = 0
                model_c_features = []
                model_c_status = "no_file"  # no_file | unavailable | insufficient | trained | failed
                match_record = _find_upload(request.match_history_file_id) if request.match_history_file_id else None
                if match_record and dataset_models.get("elo_dict"):
                    if not xgboost_available():
                        model_c_status = "unavailable"
                        yield act(
                            "model_c_skipped",
                            "XGBoost unavailable in this environment",
                            reasoning="Model C requires xgboost and the OpenMP runtime (e.g. `brew install libomp`).",
                        )
                    else:
                        match_analysis = analyse_file(match_record["path"])
                        match_df = match_analysis.get("dataframe") if isinstance(match_analysis, dict) else None
                        X, y = build_match_features(
                            match_df, data_df, dataset_models["entity_col"], dataset_models["time_col"]
                        ) if match_df is not None else ([], [])
                        if len(X) >= 100:
                            xgb_model = train_xgboost_model(X, y)
                            if xgb_model is not None:
                                model_c_probs = run_monte_carlo_xgboost(
                                    dataset_models["elo_dict"], xgb_model,
                                    dataset_models["form_indices"], _N_SIMULATIONS,
                                )
                                model_c_results = probs_to_prediction_results(model_c_probs, 10, ["dataset"])
                                model_c_match_count = len(X)
                                model_c_features = xgboost_feature_importance(xgb_model)
                                model_c_status = "trained"
                                # Re-form the ensemble as the mean of A, B and C.
                                ensemble_probs = {
                                    t: (model_a_probs.get(t, 0) + model_b_probs.get(t, 0) + model_c_probs.get(t, 0)) / 3
                                    for t in set(model_a_probs) | set(model_b_probs) | set(model_c_probs)
                                }
                                ensemble_results = probs_to_prediction_results(ensemble_probs, 10, ["dataset"])
                                for r in ensemble_results:
                                    r.model_agreement = round(agreement.get(r.entity, 1.0), 3)
                                yield act(
                                    "model_c_trained",
                                    f"XGBoost trained on {len(X)} matches",
                                    reasoning=(
                                        f"Trained on {len(X)} historical match records with 8 features. "
                                        "Model C predictions now included in the ensemble alongside Models A and B."
                                    ),
                                )
                            else:
                                model_c_status = "failed"
                                yield act(
                                    "model_c_skipped",
                                    "XGBoost training failed",
                                    reasoning="The match-history features could not train a usable model; using Models A and B only.",
                                )
                        else:
                            model_c_status = "insufficient"
                            yield act(
                                "model_c_skipped",
                                f"Not enough match data ({len(X)} rows, need ≥100)",
                            )

                dataset_probs = ensemble_probs  # ensemble (incl. Model C if trained) drives the combined prediction
                dataset_baseline_results = ensemble_results
                dataset_baseline_table = predictions_to_table(dataset_baseline_results)

                # Surface model calibration in the activity log.
                if dataset_models.get("rho_fitted"):
                    yield act(
                        "model_b_calibrated",
                        f"Dixon-Coles rho fitted from data: {dataset_models['rho']:.4f}",
                        reasoning=(
                            "Calibrated Model B's low-scoring-game correction from the dataset's "
                            f"actual scorelines ({dataset_models['rho_n_matches']} matches) instead of "
                            "the default 1997 value."
                        ),
                    )
                if dataset_models.get("form_applied"):
                    yield act(
                        "form_index_computed",
                        f"Form index computed for {dataset_models['form_count']} entities",
                        reasoning=(
                            "Recent match performance weighted more heavily than historical averages. "
                            "Entities with strong recent form receive a small probability boost."
                        ),
                    )
                # Home advantage (2.2) + stability check (2.5) activity events.
                if dataset_models.get("host_entity"):
                    yield act(
                        "host_advantage",
                        f"Host advantage applied to {dataset_models['host_entity']} (+{int(dataset_models.get('host_boost', 65))} ELO)",
                        reasoning="The host nation receives the empirically-derived +65 ELO home-advantage boost in all match simulations.",
                    )
                if dataset_models.get("stability_note"):
                    yield act(
                        "prediction_validated",
                        dataset_models["stability_note"],
                        reasoning="A separate validation run confirms the Monte Carlo result is stable; otherwise the simulation count is increased automatically.",
                    )

                # Internet research — three targeted searches in sequence.
                current_stage = "internet research"
                update_conversation_status(request.conversation_id, "running", "research")
                yield f"data: {json.dumps({'type': 'research_start'})}\n\n"
                searches = []
                for step in build_search_plan(actual_question, entity_names):
                    yield act("search_started", step["query"], reasoning=step["started_reasoning"])
                    res = await run_single_search(step["query"], step.get("system"))
                    search = {
                        "query": step["query"],
                        "purpose": step["purpose"],
                        "content": res.get("content", ""),
                        "sources": res.get("sources", []),
                    }
                    searches.append(search)
                    yield act(
                        "search_complete",
                        f"Found {len(search['sources'])} sources",
                        reasoning=step["complete_reasoning"],
                        links=[{"title": s.get("title", ""), "url": s.get("url", "")} for s in search["sources"]],
                    )
                internet_findings = combine_findings(searches)
                yield f"data: {json.dumps({'type': 'research_complete', 'data': internet_findings})}\n\n"

                # Event-status check (Fix 2) — scan the search results for evidence
                # the event is already in progress, so the council can't claim it
                # "hasn't started" when sources prove otherwise.
                today_date = datetime.utcnow().strftime("%B %d, %Y")
                event_status = detect_event_status(searches, today_date)
                # Confirmed scored results (Fix 3a) — injected at the very top of the
                # prompt as non-negotiable ground truth.
                confirmed_facts = extract_confirmed_facts(searches)

                update_conversation_status(request.conversation_id, "running", "council_stage1")

                # Build enriched prompt (injects confirmed facts + dataset baseline + event status)
                enriched_prompt = build_enriched_prompt(
                    actual_question,
                    data_summary,
                    internet_findings,
                    data_excerpt,
                    dataset_baseline=dataset_baseline_table,
                    event_status=event_status,
                    dataset_method=dataset_method,
                    confirmed_facts=confirmed_facts,
                    n_simulations=_N_SIMULATIONS,
                )
                approx_tokens = len(enriched_prompt) // 4
                if DEBUG:
                    print(
                        f"[analyse] enriched prompt: {len(enriched_prompt)} chars "
                        f"(~{approx_tokens} tokens)"
                        + ("  WARNING: exceeds 16000-char budget" if len(enriched_prompt) > 16000 else ""),
                        flush=True,
                    )
                    print(f"[DEBUG] Prompt first 800 chars: {enriched_prompt[:800]}", flush=True)

                # Stage 1
                current_stage = "stage 1"
                yield f"data: {json.dumps({'type': 'stage1_start'})}\n\n"
                # Activity: one querying event per council model. (Council querying is
                # parallel inside council.py, so these are emitted up front rather than
                # interleaved with each response.)
                for m in COUNCIL_MODELS:
                    yield act(
                        "model_querying",
                        f"Querying {_model_display(m)}...",
                        reasoning="Asking each council model to analyse the data and research independently, so their conclusions stay unbiased by one another.",
                    )
                stage1_results = await stage1_collect_responses(enriched_prompt)
                yield f"data: {json.dumps({'type': 'stage1_complete', 'data': stage1_results})}\n\n"
                # Activity: one responded event per model that answered, with char count.
                for r in stage1_results:
                    yield act(
                        "model_responded",
                        f"{_model_display(r['model'])} · {len(r.get('response', ''))} chars",
                        reasoning="Received an independent analysis to weigh against the other models' reasoning.",
                    )

                # Stage 2
                current_stage = "stage 2"
                update_conversation_status(request.conversation_id, "running", "council_stage2")
                yield f"data: {json.dumps({'type': 'stage2_start'})}\n\n"
                yield act(
                    "peer_review_started",
                    "Models reviewing each other's responses",
                    reasoning="Each model now reviews the others' answers anonymously and ranks them, so the strongest reasoning rises to the top.",
                )
                stage2_results, label_to_model = await stage2_collect_rankings(enriched_prompt, stage1_results)
                aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_model)
                metadata = {"label_to_model": label_to_model, "aggregate_rankings": aggregate_rankings}
                yield f"data: {json.dumps({'type': 'stage2_complete', 'data': stage2_results, 'metadata': metadata})}\n\n"

                # ----------------------------------------------------------------
                # Phase 2 — combined prediction (Fix 1). If internet or council
                # produced any numbers, blend all three sources with the normal
                # 40/35/25 weighting; otherwise fall back to the dataset-only
                # baseline so a prediction is ALWAYS produced when numeric data
                # exists. Computed BEFORE the chairman runs and fed into its prompt.
                # ----------------------------------------------------------------
                current_stage = "prediction engine"
                internet_probs = extract_internet_probs(internet_findings, entity_names)
                council_probs = extract_council_probs(stage1_results, entity_names, aggregate_rankings)

                # Combined = ensemble (dataset) + internet + council. With empty
                # internet/council this reduces to the ensemble baseline, so it is
                # always defined.
                combined_results = compute_prediction(dataset_probs, internet_probs, council_probs)
                prediction_results = combined_results or dataset_baseline_results
                prediction_table = predictions_to_table(prediction_results)

                # Assemble the full model suite (Change 3) for the report + chairman.
                prediction_suite = {
                    "model_a": predictions_to_table(model_a_results),
                    "model_a_label": "ELO Monte Carlo",
                    "model_a_description": f"Simulates tournament outcome using ELO win probability formula. {_N_SIMULATIONS:,} runs.",
                    "model_b": predictions_to_table(model_b_results),
                    "model_b_label": "ELO-Poisson / Dixon-Coles",
                    "model_b_description": f"Simulates actual scorelines using Poisson distribution with low-score correction (rho={dataset_models.get('rho', -0.107):.3f}). {_N_SIMULATIONS:,} runs.",
                    "model_c": predictions_to_table(model_c_results),
                    "model_c_features": model_c_features,
                    "model_c_label": "XGBoost",
                    "model_c_description": (
                        f"Gradient-boosted trees trained on {model_c_match_count:,} historical matches."
                        if model_c_status == "trained"
                        else "XGBoost unavailable in this environment. Model C requires: brew install libomp"
                        if model_c_status == "unavailable"
                        else "Requires a match history CSV. Not available for this dataset."
                    ),
                    "ensemble": predictions_to_table(ensemble_results),
                    "ensemble_description": "Average of all available mathematical models.",
                    "combined": predictions_to_table(combined_results),
                    "combined_description": "Ensemble (40%) + internet research (35%) + AI council (25%)",
                    # Per-entity breakdown for the "Combined Prediction" table (Section 2):
                    # ensemble + internet + council → final range, per entity.
                    "source_breakdown": [
                        {
                            "entity": r.entity,
                            "ensemble_pct": round(dataset_probs.get(r.entity, 0) * 100, 1),
                            "internet_pct": (round(internet_probs.get(r.entity, 0) * 100, 1)
                                             if internet_probs.get(r.entity) else None),
                            "council_pct": (round(council_probs.get(r.entity, 0) * 100, 1)
                                            if council_probs.get(r.entity) else None),
                            "low_pct": r.low_pct,
                            "high_pct": r.high_pct,
                        }
                        for r in combined_results[:10]
                    ],
                }

                # Step 1d — print what the prediction engine extracted from each source.
                if DEBUG:
                    print(f"\n[PREDICTION] Dataset probs: {dataset_probs}", flush=True)
                    print(f"[PREDICTION] Internet probs: {internet_probs}", flush=True)
                    print(f"[PREDICTION] Council probs: {council_probs}", flush=True)
                    print(
                        "[PREDICTION] Final results: "
                        f"{[(r.entity, r.low_pct, r.high_pct) for r in prediction_results[:5]]}",
                        flush=True,
                    )

                # Prediction explanation charts (Part 3) + the meta the explainer box needs.
                prediction_charts = generate_prediction_charts(
                    prediction_results,
                    dataset_probs,
                    internet_probs,
                    council_probs,
                    df=data_df,
                    columns_info=(data_summary.get("columns") if data_summary else None),
                    model_a_probs=dataset_models.get("model_a_probs"),
                    model_b_probs=dataset_models.get("model_b_probs"),
                    agreement=dataset_models.get("agreement"),
                )
                prediction_meta = {
                    "n_sources": len((internet_findings or {}).get("sources", [])),
                    "n_council": len(stage1_results),
                    "today_date": today_date,
                    "n_simulations": _N_SIMULATIONS,
                    "dataset_method": dataset_method,
                    "rho": dataset_models.get("rho", -0.107),
                    "rho_fitted": dataset_models.get("rho_fitted", False),
                    "model_c_match_count": model_c_match_count,
                    "model_c_status": model_c_status,
                    "host_entity": dataset_models.get("host_entity"),
                    "host_boost": dataset_models.get("host_boost", 0),
                    "stability_note": dataset_models.get("stability_note"),
                    "n_simulations_used": dataset_models.get("n_simulations_used", _N_SIMULATIONS),
                }

                if prediction_table:
                    yield act(
                        "predictions_computed",
                        f"Algorithm computed predictions from {len(dataset_probs)} dataset entries, "
                        f"{len(internet_probs)} internet sources, {len(council_probs)} council responses",
                        reasoning=(
                            "Combining ELO simulation (40%), internet research consensus (35%), and "
                            "model agreement (25%) into a single deterministic probability."
                        ),
                    )

                prediction_context = format_chairman_prediction_block(prediction_table, suite=prediction_suite)

                # Stage 3
                current_stage = "stage 3"
                update_conversation_status(request.conversation_id, "running", "council_stage3")
                yield f"data: {json.dumps({'type': 'stage3_start'})}\n\n"
                yield act(
                    "synthesis_started",
                    "Chairman synthesising final answer",
                    reasoning="The chairman weighs every model's analysis alongside the research to produce one calibrated, final answer.",
                )
                stage3_result = await stage3_synthesize_final(
                    enriched_prompt, stage1_results, stage2_results, prediction_context
                )
                yield f"data: {json.dumps({'type': 'stage3_complete', 'data': stage3_result})}\n\n"

                # If the deterministic engine produced nothing (e.g. text mode),
                # fall back to extracting predictions from the chairman's prose.
                if not prediction_table:
                    prediction_table = await extract_predictions(
                        stage3_result.get("response", "") if stage3_result else ""
                    )

                # Build structured report
                current_stage = "report"
                update_conversation_status(request.conversation_id, "running", "synthesis")
                report = build_report(
                    question=actual_question,
                    data_summary=data_summary,
                    charts=charts,
                    internet_findings=internet_findings,
                    council_responses=stage1_results,
                    stage2_results=stage2_results,
                    chairman_synthesis=stage3_result,
                    metadata=metadata,
                    mode=mode,
                    prediction_table=prediction_table,
                    prediction_charts=prediction_charts,
                    prediction_meta=prediction_meta,
                    prediction_suite=prediction_suite,
                )
                yield f"data: {json.dumps({'type': 'report_complete', 'data': report})}\n\n"
                yield act(
                    "report_built",
                    f"Report ready · {len(report.get('sections', {}))} sections",
                    reasoning="Assembling the final structured report with the prediction table, comparison tables, and cited sources.",
                )

                # Persist enriched conversation JSON
                _save_enriched_conversation(
                    conversation_id=request.conversation_id,
                    mode=mode,
                    file_id=request.file_id,
                    data_summary=data_summary,
                    charts=charts,
                    internet_findings=internet_findings,
                    stage1_results=stage1_results,
                    stage2_results=stage2_results,
                    stage3_result=stage3_result,
                    report=report,
                    activity=activity_events,
                    prediction_charts=prediction_charts,
                )

                # Pipeline finished — mark complete so polling clients stop.
                update_conversation_status(request.conversation_id, "complete", "done")

                if title_task:
                    title = await title_task
                    storage.update_conversation_title(request.conversation_id, title)
                    yield f"data: {json.dumps({'type': 'title_complete', 'data': {'title': title}})}\n\n"

                yield f"data: {json.dumps({'type': 'complete'})}\n\n"

            # ----------------------------------------------------------------
            # FOLLOW-UP — chairman only
            # ----------------------------------------------------------------
            else:
                yield f"data: {json.dumps({'type': 'followup_start'})}\n\n"

                # Build context from stored conversation
                pipeline = conversation.get("pipeline", {})
                context_prompt = _build_followup_prompt(actual_question, conversation, pipeline)

                from .openrouter import query_model
                from .config import CHAIRMAN_MODEL
                response = await query_model(CHAIRMAN_MODEL, [{"role": "user", "content": context_prompt}])

                if response is None:
                    response = {"content": "Error: Chairman unavailable."}

                chairman_response = {"model": CHAIRMAN_MODEL, "response": response.get("content", "")}

                # Persist followup as a lightweight assistant message
                conv = storage.get_conversation(request.conversation_id)
                conv["messages"].append({
                    "role": "assistant",
                    "type": "chairman_followup",
                    "stage3": chairman_response,
                })
                storage.save_conversation(conv)

                yield f"data: {json.dumps({'type': 'followup_complete', 'data': chairman_response})}\n\n"
                yield f"data: {json.dumps({'type': 'complete'})}\n\n"

        except Exception as e:
            update_conversation_status(request.conversation_id, "error", error_message=str(e))
            yield act("stage_error", f"{current_stage}: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@app.post("/api/reanalyse")
async def reanalyse(request: ReanalyseRequest):
    """Re-run data analysis on filtered dataset. Returns updated charts and data segments only."""
    import pandas as pd

    conversation = storage.get_conversation(request.conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    pipeline = conversation.get("pipeline", {})
    file_info = conversation.get("file")
    if not file_info:
        raise HTTPException(status_code=400, detail="Conversation has no uploaded dataset")

    file_path = file_info.get("path")
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Uploaded file not found on disk")

    # Chart caching (5.4): if the filter state matches the last fingerprint, return
    # the cached charts immediately instead of recomputing from the full dataset.
    import hashlib
    fingerprint = hashlib.sha256(json.dumps(request.filters, sort_keys=True, default=str).encode()).hexdigest()[:16]
    cached = pipeline.get("chart_cache")
    if cached and cached.get("fingerprint") == fingerprint:
        return cached["result"]

    # Load and filter
    result = analyse_file(file_path)
    if result.get("error"):
        raise HTTPException(status_code=422, detail=result["error"])
    df = result["dataframe"]
    filters = request.filters

    if "date_range" in filters and filters["date_range"]:
        dr = filters["date_range"]
        date_cols = [c["name"] for c in result["data_summary"]["columns"] if c["type"] == "datetime"]
        if date_cols and len(dr) == 2:
            col = date_cols[0]
            df[col] = pd.to_datetime(df[col])
            df = df[(df[col] >= dr[0]) & (df[col] <= dr[1])]

    if "categories" in filters and filters["categories"]:
        for col, values in filters["categories"].items():
            if values and col in df.columns:
                df = df[df[col].isin(values)]

    if "numeric_ranges" in filters and filters["numeric_ranges"]:
        for col, rng in filters["numeric_ranges"].items():
            if rng and col in df.columns and len(rng) == 2:
                df = df[(df[col] >= rng[0]) & (df[col] <= rng[1])]

    # Re-run analysis on filtered df (write to temp file to reuse analyse_file)
    import tempfile
    suffix = Path(file_path).suffix
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp_path = tmp.name
    try:
        if suffix == ".csv":
            df.to_csv(tmp_path, index=False)
        elif suffix in (".xls", ".xlsx"):
            df.to_excel(tmp_path, index=False)
        else:
            df.to_json(tmp_path, orient="records")
        filtered_result = analyse_file(tmp_path)
    finally:
        os.unlink(tmp_path)

    if filtered_result.get("error"):
        raise HTTPException(status_code=400, detail="No rows match the selected filters")

    from .report_builder import _build_data_segments_table
    data_segments = _build_data_segments_table(filtered_result["data_summary"])

    response = {
        "charts": filtered_result["charts"],
        "data_segments_table": data_segments,
        "data_summary": filtered_result["data_summary"],
    }

    # Persist active filters + cache the result under its filter fingerprint (5.4).
    conv = storage.get_conversation(request.conversation_id)
    if "pipeline" not in conv:
        conv["pipeline"] = {}
    conv["pipeline"]["active_filters"] = filters
    conv["pipeline"]["chart_cache"] = {"fingerprint": fingerprint, "result": response}
    storage.save_conversation(conv)

    return response


@app.get("/api/export-format")
async def export_format():
    """Report which export format the server can produce so the UI can label the
    download button correctly ('Download PDF Report' vs 'Download HTML Report')."""
    from .pdf_export import pdf_available
    return {"format": "pdf" if pdf_available() else "html"}


@app.get("/api/export/{conversation_id}")
async def export_report_endpoint(conversation_id: str):
    """Generate and return the stored report as a PDF, or an HTML file when the
    PDF toolchain (WeasyPrint/Pango/Cairo) is unavailable."""
    from .pdf_export import export_report

    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    base = os.path.join(EXPORTS_DIR, conversation_id)
    try:
        result = await export_report(conversation, base)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {e}")

    if not os.path.exists(result["path"]):
        raise HTTPException(status_code=500, detail="Export failed (no output produced)")

    return FileResponse(
        result["path"],
        media_type=result["media_type"],
        filename=f"report-{conversation_id[:8]}.{result['extension']}",
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _find_upload(file_id: str) -> dict | None:
    """Locate an uploaded file by file_id prefix."""
    if not file_id:
        return None
    for name in os.listdir(UPLOADS_DIR):
        if name.startswith(file_id):
            return {"path": os.path.join(UPLOADS_DIR, name), "filename": name}
    return None


def _summarise_for_research(data_summary: dict | None) -> str:
    # Brief topical hint only — deliberately omit the row count and "Dataset with
    # N rows" phrasing, which makes Perplexity cite ML-dataset catalogues instead
    # of the question's actual subject.
    if not data_summary:
        return ""
    cols = ", ".join(c["name"] for c in data_summary.get("columns", []))
    return f"The user's data has these fields: {cols}."


def _build_followup_prompt(question: str, conversation: dict, pipeline: dict) -> str:
    parts = [f"You are the chairman of an AI council. Answer a follow-up question using the stored context below.\n"]

    if pipeline.get("data_summary"):
        s = pipeline["data_summary"]
        parts.append(f"Dataset: {s['row_count']} rows, {s['column_count']} columns.")

    if pipeline.get("internet_findings"):
        findings = pipeline["internet_findings"]
        parts.append(f"Internet research summary:\n{findings.get('content', '')}")

    if pipeline.get("chairman_synthesis"):
        parts.append(f"Previous council synthesis:\n{pipeline['chairman_synthesis']}")

    parts.append(f"\nFollow-up question: {question}")
    return "\n\n".join(parts)


def _save_enriched_conversation(
    conversation_id: str,
    mode: str,
    file_id: str | None,
    data_summary: dict | None,
    charts: list,
    internet_findings: dict | None,
    stage1_results: list,
    stage2_results: list,
    stage3_result: dict,
    report: dict,
    activity: list | None = None,
    prediction_charts: list | None = None,
):
    conv = storage.get_conversation(conversation_id)
    conv["mode"] = mode

    if file_id:
        file_record = _find_upload(file_id)
        if file_record:
            conv["file"] = {
                "id": file_id,
                "name": file_record["filename"],
                "path": file_record["path"],
                "rows": data_summary["row_count"] if data_summary else 0,
                "columns": data_summary["column_count"] if data_summary else 0,
            }

    council_responses_dict = {}
    for r in stage1_results:
        council_responses_dict[r["model"]] = {"stage1": r.get("response", "")}
    for r in stage2_results:
        m = r.get("model")
        if m in council_responses_dict:
            council_responses_dict[m]["stage2_review"] = r.get("ranking", "")
            council_responses_dict[m]["stage2_ranking"] = r.get("parsed_ranking", [])

    # Strip non-serialisable dataframe before saving charts
    serialisable_charts = [{"title": c["title"], "type": c["type"], "plotly_json": c["plotly_json"]} for c in charts]

    # Guarantee a flat, deduplicated top-level source list so the frontend Sources
    # tab can be restored on reload even if the activity log is missing its links.
    if isinstance(internet_findings, dict):
        flat_sources = list(internet_findings.get("sources") or [])
        if not flat_sources:
            seen = set()
            for s in internet_findings.get("searches", []) or []:
                for src in s.get("sources", []) or []:
                    url = src.get("url")
                    if url and url not in seen:
                        seen.add(url)
                        flat_sources.append(src)
        internet_findings = {**internet_findings, "all_sources": flat_sources}

    conv["pipeline"] = {
        "data_summary": data_summary,
        "charts": serialisable_charts,
        "active_filters": {},
        "internet_findings": internet_findings,
        "live_scores": (internet_findings or {}).get("live_scores", []),
        "council_responses": council_responses_dict,
        "chairman_synthesis": stage3_result.get("response", "") if stage3_result else "",
        "comparison_tables": report.get("comparison_tables", {}),
        "report": report,
        "activity": activity or [],
        "prediction_charts": prediction_charts or [],
    }

    # Also add a full assistant message (strips dataframe from charts already done above)
    conv["messages"].append({
        "role": "assistant",
        "type": "full_report",
        "stage1": stage1_results,
        "stage2": stage2_results,
        "stage3": stage3_result,
        "report": report,
    })

    storage.save_conversation(conv)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
