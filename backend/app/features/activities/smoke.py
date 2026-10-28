import json
import logging
import sys
import time

from app.core.config import Settings
from app.features.activities.fixtures import create_dev_task_context
from app.features.activities.schemas import SupportMode
from app.features.activities.service import ActivityService
from app.providers.gateway import OllamaGateway

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def run_smoke() -> int:
    settings = Settings()
    print("=" * 65)
    print("PrepWise — Person 1 Activities Learning Engine Smoke Test (Stage 2)")
    print("=" * 65)
    print(f"Backend DB:         {settings.resolved_database_url}")
    print(f"Model Endpoint:     {settings.model_base_url}")
    print(f"Reasoning Model:    {settings.reasoning_model or 'None'}")
    print(f"Embedding Model:    {settings.embedding_model or 'None'}")

    gateway = OllamaGateway(settings)
    caps = gateway.capabilities()
    print(f"Gateway Caps:       {caps}")

    if not caps.get("reasoning_available"):
        print("\nERROR: Configured reasoning model is not available in local Ollama.")
        return 1

    service = ActivityService(gateway=gateway, model_id=settings.reasoning_model)
    context = create_dev_task_context()

    print("\n--- 1. Testing Full Live StudyPackage Generation (Normal Mode) ---")
    start_time = time.time()
    pkg = service.get_or_generate_study_package(context, SupportMode.normal)
    elapsed = round(time.time() - start_time, 2)
    print(f"SUCCESS in {elapsed}s (Model latency: {pkg.provenance.latency_ms}ms)!")
    print(f"  Title:            {pkg.title}")
    print(f"  Support Mode:     {pkg.support_mode.value}")
    print(f"  Explanation:      {pkg.explanation[:120]}...")
    print(f"  Worked Example:   Problem: {pkg.worked_example.problem[:80]}...")
    print(f"                    Steps: {len(pkg.worked_example.steps)} steps")
    print(f"  Practice Prompt:  {pkg.practice.prompt[:100]}...")
    print(f"  Progressive Hints:")
    for h in pkg.hints:
        print(f"    - L{h.level} ({h.tier}): {h.hint_text[:80]}...")
    print(f"  Solution:         {pkg.solution[:80]}...")
    print(f"  Diagram:          {pkg.diagram.kind if pkg.diagram else 'None'} ({pkg.diagram.title if pkg.diagram else ''})")
    if pkg.diagram and pkg.diagram.rows:
        print(f"                    Headers: {pkg.diagram.headers}")
        print(f"                    Rows ({len(pkg.diagram.rows)}): {pkg.diagram.rows[0]}")
    print(f"  Sources:          {[s.resource_id for s in pkg.sources]}")
    print(f"  Provenance:       origin={pkg.provenance.origin}, status={pkg.provenance.validation_status}")

    print("\n--- 2. Testing In-Memory LRU Cache Hit ---")
    start_time = time.time()
    cached_pkg = service.get_or_generate_study_package(context, SupportMode.normal)
    cache_elapsed = round(time.time() - start_time, 4)
    print(f"Retrieved in {cache_elapsed}s!")
    print(f"  Origin:           {cached_pkg.provenance.origin}")
    assert cached_pkg.provenance.origin == "cache", "Expected cached origin"
    stats = service.get_cache_stats()
    print(f"  Cache Stats:      {stats}")

    print("\n--- 3. Testing Shared Planning Contract (enrich) ---")
    results = service.enrich([context])
    res = results[0]
    print(f"  ActivityResult Title:    {res.title}")
    print(f"  Steps Count:             {len(res.steps)}")
    print(f"  Origin:                  {res.origin}")
    print(f"  Context Hash:            {res.context_hash[:16]}...")
    print(f"  Validation Status:       {res.validation_status}")

    print("\n--- 4. Testing Fallback Package Generation ---")
    from app.features.activities.fallback import generate_fallback_package
    fallback_pkg = generate_fallback_package(context, "hash-test", SupportMode.simpler, "Simulated model outage")
    print(f"  Fallback Title:   {fallback_pkg.title}")
    print(f"  Fallback Origin:  {fallback_pkg.provenance.origin}")
    print(f"  Fallback Status:  {fallback_pkg.provenance.validation_status}")
    print(f"  Fallback Hints:   {len(fallback_pkg.hints)} progressive tiers")

    print("\n" + "=" * 65)
    print("STAGE 2 SMOKE TEST PASSED: Full learning engine verified!")
    print("=" * 65)
    return 0


if __name__ == "__main__":
    sys.exit(run_smoke())
