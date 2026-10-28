import json
from typing import Any
from sqlalchemy.orm import Session

from app.api.deps import owned_goal
from app.features.progress.fixtures import seed_dev_fixture_questions
from app.features.progress.repository import ProgressRepository
from app.features.progress.schemas import QuestionPublic, QuizRecommendationResponse
from app.features.progress.scoring import compute_skill_evidence


class RecommendationService:
    """
    Deterministic evidence-based quiz recommendation service (Stage 6).
    Reuses Policy v1 SkillEvidence projections and connects directly to the quiz player.
    """

    @staticmethod
    def get_recommendation(
        session: Session,
        goal_id: str,
        student_id: str,
    ) -> QuizRecommendationResponse:
        goal = owned_goal(session, goal_id, student_id)
        curriculum_id = goal["curriculum_id"]

        # Ensure seed fixture exists if no reviewed questions are loaded
        if ProgressRepository.count_reviewed_questions(session, curriculum_id) == 0:
            seed_dev_fixture_questions(session)

        # Get all skills in curriculum
        curriculum_skills = ProgressRepository.get_curriculum_skills(session, curriculum_id)
        if not curriculum_skills:
            return QuizRecommendationResponse(
                goal_id=goal_id,
                action="fresh_check",
                effective_difficulty=3,
                difficulty_label="practice",
                question_count=5,
                reason_code="no_evidence",
                factual_explanation="No skills found for this goal's curriculum.",
                availability_status="exhausted",
                available_count=0,
            )

        # Compute evidence per skill
        skill_assessments: list[dict[str, Any]] = []
        for s in curriculum_skills:
            attempts = ProgressRepository.get_student_skill_attempts(session, student_id, s["id"])
            evidence = compute_skill_evidence(s["id"], attempts)

            # Count eligible independent correct answers
            indep_attempts = [a for a in attempts if a.get("is_independent_evidence") == 1]
            window = indep_attempts[-8:] if len(indep_attempts) > 8 else indep_attempts
            correct_indep = sum(1 for a in window if int(a.get("correct", 0)) == 1)

            skill_assessments.append(
                {
                    "skill_id": s["id"],
                    "title": s["title"],
                    "topic_id": s["topic_id"],
                    "evidence": evidence,
                    "status": evidence["evidence_status"],
                    "estimate": evidence["performance_estimate"],
                    "independent_count": evidence["independent_count"],
                    "correct_count": correct_indep,
                    "attempt_ids": evidence["attempt_ids"],
                }
            )

        # Determine priority skill according to Stage 6 policy rules:
        # 1. needs_attention (highest priority)
        # 2. unknown or limited (fresh questions needed before diagnosing weakness)
        # 3. ordinary (mixed practice)
        # 4. strong (harder application questions)
        needs_attention_skills = [s for s in skill_assessments if s["status"] == "needs_attention"]
        limited_skills = [s for s in skill_assessments if s["status"] in ("unknown", "limited")]
        ordinary_skills = [s for s in skill_assessments if s["status"] == "ordinary"]
        strong_skills = [s for s in skill_assessments if s["status"] == "strong"]

        if needs_attention_skills:
            # Sort by lowest estimate, then highest independent count, then stable skill_id
            needs_attention_skills.sort(key=lambda s: (s["estimate"] if s["estimate"] is not None else 1.0, -s["independent_count"], s["skill_id"]))
            priority = needs_attention_skills[0]
            action = "targeted_quiz"
            reason_code = "needs_attention"
            effective_difficulty = 2  # One-lower / foundation difficulty
            diff_label = "introductory"
            explanation = (
                f"Recommended because {priority['title']} had {priority['correct_count']} correct answers across "
                f"{priority['independent_count']} independent questions."
            )
        elif limited_skills:
            # Prioritize unknown first, then limited with fewest attempts
            limited_skills.sort(key=lambda s: (0 if s["status"] == "unknown" else 1, s["independent_count"], s["skill_id"]))
            priority = limited_skills[0]
            action = "fresh_check"
            reason_code = "limited_evidence" if priority["independent_count"] > 0 else "no_evidence"
            effective_difficulty = 3  # Neutral difficulty
            diff_label = "practice"
            if priority["independent_count"] == 0:
                explanation = (
                    f"Recommended because {priority['title']} has no independent assessment evidence yet; "
                    f"more fresh questions are needed before diagnosing performance."
                )
            else:
                explanation = (
                    f"Recommended because {priority['title']} has limited independent evidence "
                    f"({priority['independent_count']} answers recorded); more fresh questions are needed before diagnosing performance."
                )
        elif ordinary_skills:
            ordinary_skills.sort(key=lambda s: (s["estimate"] if s["estimate"] is not None else 0.5, s["skill_id"]))
            priority = ordinary_skills[0]
            action = "mixed_practice"
            reason_code = "ordinary_practice"
            effective_difficulty = 3  # Current difficulty
            diff_label = "practice"
            explanation = (
                f"Recommended for mixed practice across assessed skills to maintain retention and active recall."
            )
        else:
            # All skills are strong
            priority = strong_skills[0]
            action = "challenge_quiz"
            reason_code = "strong_mastery"
            effective_difficulty = 4  # Harder application questions
            diff_label = "challenge"
            pct = int((priority["estimate"] or 0.8) * 100)
            explanation = (
                f"Recommended harder application questions because {priority['title']} demonstrated "
                f"strong performance ({pct}% across {priority['independent_count']} independent questions)."
            )

        priority_skill_id = priority["skill_id"]
        priority_skill_title = priority["title"]
        priority_topic_id = priority["topic_id"]
        supporting_attempt_ids = priority["attempt_ids"]

        # Question Selection:
        # Aim for: 3 on priority skill, 1 prerequisite question where mapping exists, 1 mixed review
        prereq_topics = ProgressRepository.get_prerequisite_topic_ids(session, curriculum_id, priority_topic_id)
        prereq_skills = ProgressRepository.get_skills_for_topics(session, curriculum_id, prereq_topics)
        prereq_skill_ids = [ps["id"] for ps in prereq_skills if ps["id"] != priority_skill_id]
        other_curriculum_skill_ids = [s["id"] for s in curriculum_skills if s["id"] != priority_skill_id]

        selected_question_dicts: list[dict[str, Any]] = []
        selected_qids: set[str] = set()

        def add_unseen(q_list: list[dict[str, Any]], max_add: int):
            added = 0
            for q in q_list:
                if q["question_id"] not in selected_qids and added < max_add:
                    selected_question_dicts.append(q)
                    selected_qids.add(q["question_id"])
                    added += 1

        # 1. Up to 3 questions on priority skill (prefer unseen)
        priority_unseen = ProgressRepository.get_unseen_questions(
            session=session,
            curriculum_id=curriculum_id,
            student_id=student_id,
            skill_ids=[priority_skill_id],
            difficulty=effective_difficulty,
            limit=5,
        )
        if len(priority_unseen) < 3:
            # Try any difficulty for priority skill
            priority_unseen_any_diff = ProgressRepository.get_unseen_questions(
                session=session,
                curriculum_id=curriculum_id,
                student_id=student_id,
                skill_ids=[priority_skill_id],
                difficulty=None,
                limit=5,
            )
            for q in priority_unseen_any_diff:
                if q not in priority_unseen:
                    priority_unseen.append(q)
        add_unseen(priority_unseen, 3)

        # 2. Up to 1 prerequisite question if mapping exists
        if prereq_skill_ids:
            prereq_unseen = ProgressRepository.get_unseen_questions(
                session=session,
                curriculum_id=curriculum_id,
                student_id=student_id,
                skill_ids=prereq_skill_ids,
                difficulty=None,
                limit=3,
            )
            add_unseen(prereq_unseen, 1)

        # 3. Up to 1 mixed review question
        if other_curriculum_skill_ids:
            review_unseen = ProgressRepository.get_unseen_questions(
                session=session,
                curriculum_id=curriculum_id,
                student_id=student_id,
                skill_ids=other_curriculum_skill_ids,
                difficulty=None,
                limit=3,
            )
            add_unseen(review_unseen, 1)

        # 4. Fill remaining deficit up to 5 questions with any unseen questions in curriculum
        if len(selected_question_dicts) < 5:
            remaining_deficit = 5 - len(selected_question_dicts)
            general_unseen = ProgressRepository.get_unseen_questions(
                session=session,
                curriculum_id=curriculum_id,
                student_id=student_id,
                skill_ids=None,
                difficulty=None,
                limit=remaining_deficit + 3,
            )
            add_unseen(general_unseen, remaining_deficit)

        is_supported_practice_only = False
        # If no unseen questions exist at all, offer reviewed bank as supported practice
        if len(selected_question_dicts) == 0:
            reviewed_pool = ProgressRepository.get_reviewed_questions_any(
                session=session,
                curriculum_id=curriculum_id,
                skill_ids=[priority_skill_id] if priority_skill_id else None,
                limit=5,
            )
            if not reviewed_pool:
                reviewed_pool = ProgressRepository.get_reviewed_questions_any(
                    session=session,
                    curriculum_id=curriculum_id,
                    skill_ids=None,
                    limit=5,
                )

            if reviewed_pool:
                is_supported_practice_only = True
                add_unseen(reviewed_pool, 5)
                explanation += " Fresh independent questions are currently exhausted; available questions are offered as supported practice."
                availability_status = "supported_only"
            else:
                availability_status = "exhausted"
                explanation = f"No questions are currently available in the reviewed bank for {priority_skill_title}."
        else:
            availability_status = "available" if len(selected_question_dicts) >= 5 else "limited"

        # Transform to QuestionPublic (hiding private grading keys)
        public_questions: list[QuestionPublic] = []
        for q in selected_question_dicts:
            options_dict = json.loads(q["options_json"]) if isinstance(q["options_json"], str) else q["options_json"]
            public_questions.append(
                QuestionPublic(
                    question_id=q["question_id"],
                    skill_id=q["skill_id"],
                    prompt=q["prompt"],
                    options=options_dict,
                    difficulty=q["difficulty"],
                    form=q["form"],
                )
            )

        all_target_skills = list({priority_skill_id} | {q.skill_id for q in public_questions})

        return QuizRecommendationResponse(
            goal_id=goal_id,
            action=action,
            priority_skill_id=priority_skill_id,
            priority_skill_title=priority_skill_title,
            skill_ids=all_target_skills,
            effective_difficulty=effective_difficulty,
            difficulty_label=diff_label,
            question_count=len(public_questions),
            reason_code=reason_code,
            supporting_attempt_ids=supporting_attempt_ids,
            factual_explanation=explanation,
            availability_status=availability_status,
            available_count=len(public_questions),
            is_supported_practice_only=is_supported_practice_only,
            questions=public_questions,
        )
