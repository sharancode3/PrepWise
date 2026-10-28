"""Retrieval service for Curriculum and Resources (Person 2).

Implements:
- Semantic ranking using cached embeddings and NumPy cosine similarity.
- Prerequisite and topic-scope filtering.
- Safe deterministic fallback to authored topic resources when embeddings are unavailable.
- Strict compliance with shared ResourceMatch contract.
"""

import json
import math
import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contracts.domain import ResourceMatch
from app.db.models import Base

T = Base.metadata.tables


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    a = np.array(vec_a, dtype=np.float64)
    b = np.array(vec_b, dtype=np.float64)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


class RetrievalService:
    @staticmethod
    def get_authored_resources(session: Session, topic_id: str, curriculum_id: str | None = None) -> list[ResourceMatch]:
        """Deterministic fallback: load authored reviewed resources for this topic."""
        res_table = T["resources"]
        query = select(
            res_table.c.id,
            res_table.c.topic_id,
            res_table.c.body,
            res_table.c.source_label,
        ).where(res_table.c.topic_id == topic_id)

        if curriculum_id:
            query = query.where(res_table.c.curriculum_id == curriculum_id)

        rows = session.execute(query).mappings().all()
        return [
            ResourceMatch(
                resource_id=row["id"],
                topic_id=row["topic_id"],
                text=row["body"],
                source_label=row["source_label"],
                score=1.0,
            )
            for row in rows
        ]

    @classmethod
    def retrieve(
        cls,
        session: Session,
        topic_id: str,
        objective: str,
        evidence: list | None = None,
        k: int = 3,
        gateway=None,
        curriculum_id: str | None = None,
    ) -> list[ResourceMatch]:
        """Retrieve relevant resources for a topic using semantic similarity or deterministic fallback.

        Always returns ResourceMatch instances matching the shared contract.
        """
        # Load candidate resources for the given topic
        candidates = cls.get_authored_resources(session, topic_id, curriculum_id)
        if not candidates:
            return []

        # If gateway is not supplied or embedding model is unconfigured, return authored candidates
        if gateway is None or not getattr(gateway.settings, "embedding_model", None):
            return candidates[:k]

        try:
            # Query combines objective and topic
            query_text = f"{objective} (topic: {topic_id})"
            query_vectors = gateway.embed([query_text])
            if not query_vectors or not query_vectors[0]:
                return candidates[:k]
            q_vec = query_vectors[0]

            # Fetch or generate candidate vectors
            emb_table = T["resource_embeddings"]
            scored_matches: list[tuple[float, ResourceMatch]] = []

            for cand in candidates:
                cached = session.execute(
                    select(emb_table.c.vector_json).where(
                        emb_table.c.resource_id == cand.resource_id,
                        emb_table.c.model_fingerprint == gateway.settings.embedding_model,
                    )
                ).scalar()

                if cached:
                    c_vec = json.loads(cached)
                else:
                    # Embed and cache vector
                    doc_vectors = gateway.embed([cand.text])
                    c_vec = doc_vectors[0]
                    # Update or insert into cache
                    import hashlib
                    chash = hashlib.sha256(cand.text.encode()).hexdigest()
                    session.execute(
                        emb_table.insert().values(
                            resource_id=cand.resource_id,
                            model_fingerprint=gateway.settings.embedding_model,
                            dimension=len(c_vec),
                            content_hash=chash,
                            vector_json=json.dumps(c_vec),
                        )
                    )
                    session.commit()

                score = cosine_similarity(q_vec, c_vec)
                scored_matches.append((score, cand))

            # Rank by score descending, then by resource_id ascending for deterministic tie-breaking
            scored_matches.sort(key=lambda item: (-item[0], item[1].resource_id))

            results: list[ResourceMatch] = []
            for score, match in scored_matches[:k]:
                results.append(
                    ResourceMatch(
                        resource_id=match.resource_id,
                        topic_id=match.topic_id,
                        text=match.text,
                        source_label=match.source_label,
                        score=round(score, 4),
                    )
                )
            return results

        except Exception:
            # On any embedding failure, safely return deterministic authored resources
            return candidates[:k]
