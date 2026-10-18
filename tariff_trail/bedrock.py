"""Amazon Bedrock access: Converse for the LLM steps, Titan for embeddings, with usage accounting.

Model ids are resolved from the account (inference profiles first, then foundation models), so
nothing here hard-codes a model version. Override any of them with environment variables:

    TT_REASONER_MODEL   fork adjudication, broker memo, the LLM baselines (default: newest invokable
                        Claude Sonnet, then Claude Opus, Nova Premier, Nova Pro)
    TT_FAST_MODEL       fact extraction from ruling text and listings (default: newest invokable
                        Claude Haiku, then Nova 2 Lite, Nova Lite)
    TT_EMBED_MODEL      precedent search                                       (default: Titan Text Embeddings V2)

Credentials: the AWS profile in AWS_PROFILE; else the "hackathon" profile if configured; else the
default chain (on the EC2 host, its instance role). Region AWS_REGION (default us-east-1).
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

import boto3
from botocore.config import Config

PROFILE = os.environ.get("AWS_PROFILE")  # None: "hackathon" if configured, else the default chain (instance role)
REGION = os.environ.get("AWS_REGION", "us-east-1")

_PREFERENCES = {
    "reasoner": [r"anthropic\.claude-sonnet", r"anthropic\.claude-opus", r"amazon\.nova-premier", r"amazon\.nova-pro"],
    "fast": [r"anthropic\.claude-haiku", r"amazon\.nova-2-lite", r"amazon\.nova-lite"],
}
_ENV = {"reasoner": "TT_REASONER_MODEL", "fast": "TT_FAST_MODEL"}
EMBED_MODEL = os.environ.get("TT_EMBED_MODEL", "amazon.titan-embed-text-v2:0")


@lru_cache(maxsize=1)
def session() -> boto3.Session:
    profile = PROFILE
    if profile is None and "hackathon" in boto3.Session().available_profiles:
        profile = "hackathon"
    return boto3.Session(profile_name=profile, region_name=REGION)


@lru_cache(maxsize=1)
def runtime():
    return session().client("bedrock-runtime", config=Config(retries={"max_attempts": 8, "mode": "adaptive"}, read_timeout=180))


def _version_key(model_id: str) -> tuple:
    return tuple(int(n) for n in re.findall(r"\d+", model_id))


def _callable(model_id: str) -> bool:
    """Listed is not the same as usable: some accounts list models they cannot invoke."""
    try:
        runtime().converse(
            modelId=model_id,
            messages=[{"role": "user", "content": [{"text": "Reply OK"}]}],
            inferenceConfig={"maxTokens": 5},
        )
        return True
    except Exception:
        return False


def candidates_for(role: str) -> list[str]:
    """Active inference profiles and on-demand models for a role, preferred family first, newest first."""
    control = session().client("bedrock")
    ids: list[str] = []
    try:
        for page in control.get_paginator("list_inference_profiles").paginate():
            ids += [p["inferenceProfileId"] for p in page["inferenceProfileSummaries"] if p.get("status") == "ACTIVE"]
    except Exception:  # older SDKs or no permission: fall back to foundation models
        pass
    models = control.list_foundation_models(byInferenceType="ON_DEMAND")["modelSummaries"]
    ids += [m["modelId"] for m in models if "TEXT" in m.get("outputModalities", [])]
    ordered: list[str] = []
    for pattern in _PREFERENCES[role]:
        matches = [c for c in ids if re.search(pattern, c) and c not in ordered]
        # prefer the US cross-region profile, then the newest version
        matches.sort(key=lambda c: (c.startswith("us."), _version_key(c)), reverse=True)
        ordered += matches
    return ordered


@lru_cache(maxsize=4)
def model_for(role: str) -> str:
    """The model id for a role: env override, else the newest candidate this account can invoke."""
    if os.environ.get(_ENV[role]):
        return os.environ[_ENV[role]]
    for model_id in candidates_for(role):
        if _callable(model_id):
            return model_id
    raise RuntimeError(f"no invokable Bedrock model for role {role!r}; set {_ENV[role]}")


@dataclass
class Usage:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
    by_model: dict[str, list[int]] = field(default_factory=dict)  # model -> [calls, in, out]

    def add(self, model: str, tokens_in: int, tokens_out: int, ms: float) -> None:
        self.calls += 1
        self.input_tokens += tokens_in
        self.output_tokens += tokens_out
        self.latency_ms += ms
        row = self.by_model.setdefault(model, [0, 0, 0])
        row[0] += 1
        row[1] += tokens_in
        row[2] += tokens_out


USAGE = Usage()
_LOCK = threading.Lock()


@dataclass
class Reply:
    text: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: float


def converse(
    prompt: str,
    *,
    role: str = "reasoner",
    system: str | None = None,
    max_tokens: int = 800,
    temperature: float | None = 0.0,
    usage: Usage | None = None,
) -> Reply:
    model = model_for(role)
    request: dict[str, Any] = {
        "modelId": model,
        "messages": [{"role": "user", "content": [{"text": prompt}]}],
        "inferenceConfig": {"maxTokens": max_tokens},
    }
    if temperature is not None:
        request["inferenceConfig"]["temperature"] = temperature
    if system:
        request["system"] = [{"text": system}]
    started = time.perf_counter()
    try:
        response = runtime().converse(**request)
    except runtime().exceptions.ValidationException as exc:
        # Some newer models reject sampling parameters; retry once without them.
        if temperature is not None and "temperature" in str(exc).lower():
            return converse(prompt, role=role, system=system, max_tokens=max_tokens, temperature=None, usage=usage)
        raise
    ms = (time.perf_counter() - started) * 1000
    text = "".join(block.get("text", "") for block in response["output"]["message"]["content"])
    tokens_in = response["usage"]["inputTokens"]
    tokens_out = response["usage"]["outputTokens"]
    with _LOCK:
        USAGE.add(model, tokens_in, tokens_out, ms)
        if usage is not None and usage is not USAGE:
            usage.add(model, tokens_in, tokens_out, ms)
    return Reply(text, model, tokens_in, tokens_out, ms)


def converse_json(prompt: str, **kwargs) -> tuple[dict, Reply]:
    """Converse and parse the first JSON object in the reply."""
    reply = converse(prompt, **kwargs)
    match = re.search(r"\{.*\}", reply.text, re.DOTALL)
    if not match:
        raise ValueError(f"no JSON object in reply: {reply.text[:200]!r}")
    return json.loads(match.group(0)), reply


def embed(text: str, dimensions: int = 512) -> list[float]:
    body = json.dumps({"inputText": text[:8000], "dimensions": dimensions, "normalize": True})
    response = runtime().invoke_model(modelId=EMBED_MODEL, body=body)
    return json.loads(response["body"].read())["embedding"]
