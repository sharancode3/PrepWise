import hashlib
import json
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
    if norm_a == 0 or norm_b == 0 or not np.isfinite(norm_a) or not np.isfinite(norm_b):
        return 0.0
    val = float(np.dot(a, b) / (norm_a * norm_b))
    return val if np.isfinite(val) else 0.0


def lexical_score(query: str, text: str) -> float:
    q_tokens = set(query.lower().replace("?", "").replace(",", "").replace(".", "").split())
    if not q_tokens:
        return 0.0
    text_tokens = set(text.lower().split())
    overlap = len(q_tokens.intersection(text_tokens))
    return overlap / max(len(q_tokens), 1)


class RetrievalService:
    @staticmethod
    def get_candidate_resources(
        session: Session,
        topic_id: str | None = None,
        curriculum_id: str | None = None,
        resource_ids: list[str] | None = None,
        student_id: str | None = None,
    ) -> list[ResourceMatch]:
        res_table = T["resources"]
        query = select(
            res_table.c.id,
            res_table.c.topic_id,
            res_table.c.body,
            res_table.c.source_label,
            res_table.c.content_hash,
        )

        if resource_ids:
            query = query.where(res_table.c.id.in_(resource_ids))
        elif topic_id:
            query = query.where(res_table.c.topic_id == topic_id)

        if curriculum_id:
            query = query.where(res_table.c.curriculum_id == curriculum_id)

        rows = session.execute(query).mappings().all()
        candidates = [
            ResourceMatch(
                resource_id=row["id"],
                topic_id=row["topic_id"],
                text=row["body"],
                source_label=row["source_label"],
                score=1.0,
            )
            for row in rows
        ]

        # Also search resource_uploads if student_id is known or resource_ids given
        if resource_ids or student_id:
            up_table = T["resource_uploads"]
            up_query = select(
                up_table.c.id,
                up_table.c.topic_id,
                up_table.c.extracted_text,
                up_table.c.original_filename,
            ).where(up_table.c.processing_status == "indexed")

            if student_id:
                up_query = up_query.where(up_table.c.student_id == student_id)
            if resource_ids:
                up_query = up_query.where(up_table.c.id.in_(resource_ids))
            elif topic_id:
                up_query = up_query.where(up_table.c.topic_id == topic_id)

            up_rows = session.execute(up_query).mappings().all()
            for r in up_rows:
                candidates.append(
                    ResourceMatch(
                        resource_id=r["id"],
                        topic_id=r["topic_id"] or "general",
                        text=r["extracted_text"],
                        source_label=f"Uploaded note: {r['original_filename']}",
                        score=1.0,
                    )
                )

        return candidates

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
        resource_ids: list[str] | None = None,
        student_id: str | None = None,
    ) -> list[ResourceMatch]:
        candidates = cls.get_candidate_resources(
            session=session,
            topic_id=topic_id,
            curriculum_id=curriculum_id,
            resource_ids=resource_ids,
            student_id=student_id,
        )
        if not candidates:
            return []

        # If gateway is not supplied or embedding model is unconfigured, use deterministic lexical ranking
        if gateway is None or not getattr(getattr(gateway, "settings", None), "embedding_model", None):
            return cls._rank_lexically(candidates, objective, topic_id, k)

        try:
            model_name = gateway.settings.embedding_model
            query_text = f"{objective} (topic: {topic_id})"

            emb_table = T["resource_embeddings"]
            cached_vectors = {}
            missing_candidates = []

            for cand in candidates:
                cand_hash = hashlib.sha256(cand.text.encode()).hexdigest()
                cached = session.execute(
                    select(emb_table.c.vector_json, emb_table.c.content_hash, emb_table.c.dimension).where(
                        emb_table.c.resource_id == cand.resource_id,
                        emb_table.c.model_fingerprint == model_name,
                    )
                ).mappings().first()

                if cached and cached["content_hash"] == cand_hash:
                    cached_vectors[cand.resource_id] = json.loads(cached["vector_json"])
                else:
                    missing_candidates.append(cand)

            # Batch missing embeddings
            if missing_candidates:
                texts_to_embed = [c.text[:2000] for c in missing_candidates]
                vectors = gateway.embed(texts_to_embed)
                for cand, vec in zip(missing_candidates, vectors):
                    cached_vectors[cand.resource_id] = vec
                    c_hash = hashlib.sha256(cand.text.encode()).hexdigest()
                    try:
                        session.execute(
                            emb_table.insert().prefix_with("OR REPLACE").values(
                                resource_id=cand.resource_id,
                                model_fingerprint=model_name,
                                dimension=len(vec),
                                content_hash=c_hash,
                                vector_json=json.dumps(vec),
                            )
                        )
                        session.commit()
                    except Exception:
                        session.rollback()

            # Embed query
            query_vectors = gateway.embed([query_text])
            if not query_vectors or not query_vectors[0]:
                return cls._rank_lexically(candidates, objective, topic_id, k)
            q_vec = query_vectors[0]

            scored_matches = []
            for cand in candidates:
                c_vec = cached_vectors.get(cand.resource_id)
                if c_vec:
                    score = cosine_similarity(q_vec, c_vec)
                else:
                    score = lexical_score(query_text, cand.text)
                scored_matches.append((score, cand))

            # Sort descending by score, deterministic tie-breaking by resource_id ascending
            scored_matches.sort(key=lambda item: (-item[0], item[1].resource_id))

            results = []
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
            return cls._rank_lexically(candidates, objective, topic_id, k)

    @classmethod
    def _rank_lexically(cls, candidates: list[ResourceMatch], objective: str, topic_id: str, k: int) -> list[ResourceMatch]:
        query = f"{objective} {topic_id}"
        scored = []
        for c in candidates:
            score = lexical_score(query, c.text)
            scored.append((score, c))
        # Sort descending by score, tie-break by resource_id
        scored.sort(key=lambda item: (-item[0], item[1].resource_id))

        results = []
        for score, match in scored[:k]:
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
