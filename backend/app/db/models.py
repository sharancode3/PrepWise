from typing import Optional

from sqlalchemy import CheckConstraint, Enum, ForeignKey, ForeignKeyConstraint, Index, Integer, REAL, Text, UniqueConstraint, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass


class Curricula(Base):
    __tablename__ = 'curricula'
    __table_args__ = (
        UniqueConstraint('title', 'version'),
    )

    title: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Enum('draft', 'published'), nullable=False)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    id: Mapped[Optional[str]] = mapped_column(Text, primary_key=True)


class Students(Base):
    __tablename__ = 'students'
    __table_args__ = (
        CheckConstraint('input_revision >= 0'),
    )

    timezone: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'Asia/Kolkata'"))
    client_token_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    input_revision: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('0'))
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("strftime('%Y-%m-%dT%H:%M:%fZ','now')"))
    id: Mapped[Optional[str]] = mapped_column(Text, primary_key=True)
    display_name: Mapped[Optional[str]] = mapped_column(Text)


class Goals(Base):
    __tablename__ = 'goals'
    __table_args__ = (
        CheckConstraint('start_date <= deadline'),
        UniqueConstraint('id', 'curriculum_id'),
        UniqueConstraint('id', 'student_id')
    )

    student_id: Mapped[str] = mapped_column(ForeignKey('students.id'), nullable=False)
    curriculum_id: Mapped[str] = mapped_column(ForeignKey('curricula.id'), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    goal_text: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    start_date: Mapped[str] = mapped_column(Text, nullable=False)
    deadline: Mapped[str] = mapped_column(Text, nullable=False)
    id: Mapped[Optional[str]] = mapped_column(Text, primary_key=True)

    curriculum: Mapped['Curricula'] = relationship('Curricula')
    student: Mapped['Students'] = relationship('Students')


class RequestReceipts(Base):
    __tablename__ = 'request_receipts'
    __table_args__ = (
        CheckConstraint('json_valid(response_json)'),
    )

    student_id: Mapped[str] = mapped_column(ForeignKey('students.id'), primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(Text, primary_key=True)
    method: Mapped[str] = mapped_column(Text, nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    request_hash: Mapped[str] = mapped_column(Text, nullable=False)
    response_status: Mapped[int] = mapped_column(Integer, nullable=False)
    response_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("strftime('%Y-%m-%dT%H:%M:%fZ','now')"))

    student: Mapped['Students'] = relationship('Students')


class Topics(Base):
    __tablename__ = 'topics'
    __table_args__ = (
        CheckConstraint('check_minutes >= 0'),
        CheckConstraint('difficulty BETWEEN 1 AND 5'),
        CheckConstraint('importance BETWEEN 0 AND 1'),
        CheckConstraint('learn_minutes > 0'),
        CheckConstraint('practice_minutes >= 0'),
        UniqueConstraint('curriculum_id', 'id')
    )

    curriculum_id: Mapped[str] = mapped_column(ForeignKey('curricula.id'), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    difficulty: Mapped[int] = mapped_column(Integer, nullable=False)
    importance: Mapped[float] = mapped_column(REAL, nullable=False, server_default=text('0.5'))
    learn_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    practice_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    check_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    id: Mapped[Optional[str]] = mapped_column(Text, primary_key=True)

    curriculum: Mapped['Curricula'] = relationship('Curricula')


class Availability(Base):
    __tablename__ = 'availability'
    __table_args__ = (
        CheckConstraint('minutes BETWEEN 0 AND 480'),
    )

    goal_id: Mapped[str] = mapped_column(ForeignKey('goals.id'), primary_key=True)
    study_date: Mapped[str] = mapped_column(Text, primary_key=True)
    minutes: Mapped[int] = mapped_column(Integer, nullable=False)

    goal: Mapped['Goals'] = relationship('Goals')


class GoalTopics(Base):
    __tablename__ = 'goal_topics'
    __table_args__ = (
        ForeignKeyConstraint(['curriculum_id', 'topic_id'], ['topics.curriculum_id', 'topics.id']),
        ForeignKeyConstraint(['goal_id', 'curriculum_id'], ['goals.id', 'goals.curriculum_id'])
    )

    goal_id: Mapped[str] = mapped_column(Text, primary_key=True)
    curriculum_id: Mapped[str] = mapped_column(Text, nullable=False)
    topic_id: Mapped[str] = mapped_column(Text, primary_key=True)
    self_report: Mapped[str] = mapped_column(Enum('unknown', 'low', 'medium', 'high'), nullable=False, server_default=text("'unknown'"))

    topics: Mapped['Topics'] = relationship('Topics')
    goals: Mapped['Goals'] = relationship('Goals')


class PlanVersions(Base):
    __tablename__ = 'plan_versions'
    __table_args__ = (
        CheckConstraint('input_revision >= 0'),
        CheckConstraint('json_valid(assumptions_json)'),
        CheckConstraint('json_valid(config_json)'),
        CheckConstraint('json_valid(deferred_json)'),
        CheckConstraint('json_valid(input_snapshot_json)'),
        CheckConstraint('json_valid(metrics_json)'),
        CheckConstraint('version > 0'),
        ForeignKeyConstraint(['goal_id', 'parent_plan_id'], ['plan_versions.goal_id', 'plan_versions.id']),
        UniqueConstraint('goal_id', 'id'),
        UniqueConstraint('goal_id', 'version'),
        Index('one_active_plan', 'goal_id', unique=True)
    )

    goal_id: Mapped[str] = mapped_column(ForeignKey('goals.id'), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Enum('candidate', 'active', 'superseded'), nullable=False)
    input_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    algorithm_version: Mapped[str] = mapped_column(Text, nullable=False)
    policy_version: Mapped[str] = mapped_column(Text, nullable=False)
    feasibility: Mapped[str] = mapped_column(Enum('full', 'partial', 'no_capacity'), nullable=False)
    generation_status: Mapped[str] = mapped_column(Enum('generated', 'mixed', 'template_only'), nullable=False)
    config_json: Mapped[str] = mapped_column(Text, nullable=False)
    metrics_json: Mapped[str] = mapped_column(Text, nullable=False)
    deferred_json: Mapped[str] = mapped_column(Text, nullable=False)
    assumptions_json: Mapped[str] = mapped_column(Text, nullable=False)
    input_snapshot_json: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("strftime('%Y-%m-%dT%H:%M:%fZ','now')"))
    id: Mapped[Optional[str]] = mapped_column(Text, primary_key=True)
    parent_plan_id: Mapped[Optional[str]] = mapped_column(Text)

    plan_versions: Mapped[Optional['PlanVersions']] = relationship('PlanVersions', remote_side=[id])
    goal: Mapped['Goals'] = relationship('Goals')


class Prerequisites(Base):
    __tablename__ = 'prerequisites'
    __table_args__ = (
        CheckConstraint('topic_id <> prerequisite_topic_id'),
        ForeignKeyConstraint(['curriculum_id', 'prerequisite_topic_id'], ['topics.curriculum_id', 'topics.id']),
        ForeignKeyConstraint(['curriculum_id', 'topic_id'], ['topics.curriculum_id', 'topics.id'])
    )

    curriculum_id: Mapped[str] = mapped_column(ForeignKey('curricula.id'), nullable=False)
    topic_id: Mapped[str] = mapped_column(Text, primary_key=True)
    prerequisite_topic_id: Mapped[str] = mapped_column(Text, primary_key=True)

    topics: Mapped['Topics'] = relationship('Topics', foreign_keys=[curriculum_id, prerequisite_topic_id])
    topics_: Mapped['Topics'] = relationship('Topics', foreign_keys=[curriculum_id, topic_id])
    curriculum: Mapped['Curricula'] = relationship('Curricula')


class Resources(Base):
    __tablename__ = 'resources'
    __table_args__ = (
        ForeignKeyConstraint(['curriculum_id', 'topic_id'], ['topics.curriculum_id', 'topics.id']),
    )

    curriculum_id: Mapped[str] = mapped_column(Text, nullable=False)
    topic_id: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    source_label: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    id: Mapped[Optional[str]] = mapped_column(Text, primary_key=True)

    topics: Mapped['Topics'] = relationship('Topics')


class Skills(Base):
    __tablename__ = 'skills'
    __table_args__ = (
        ForeignKeyConstraint(['curriculum_id', 'topic_id'], ['topics.curriculum_id', 'topics.id']),
        UniqueConstraint('id', 'topic_id')
    )

    curriculum_id: Mapped[str] = mapped_column(Text, nullable=False)
    topic_id: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    id: Mapped[Optional[str]] = mapped_column(Text, primary_key=True)

    topics: Mapped['Topics'] = relationship('Topics')


class Jobs(Base):
    __tablename__ = 'jobs'
    __table_args__ = (
        CheckConstraint('accepted_revision >= 0'),
        CheckConstraint('json_valid(metrics_json)'),
        ForeignKeyConstraint(['goal_id', 'base_plan_id'], ['plan_versions.goal_id', 'plan_versions.id']),
        ForeignKeyConstraint(['goal_id', 'result_plan_id'], ['plan_versions.goal_id', 'plan_versions.id']),
        ForeignKeyConstraint(['goal_id', 'student_id'], ['goals.id', 'goals.student_id']),
        Index('one_live_student_job', 'student_id', unique=True)
    )

    student_id: Mapped[str] = mapped_column(Text, nullable=False)
    goal_id: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[str] = mapped_column(Enum('generate', 'replan'), nullable=False)
    status: Mapped[str] = mapped_column(Enum('queued', 'running', 'completed', 'failed', 'interrupted'), nullable=False)
    stage: Mapped[str] = mapped_column(Text, nullable=False)
    accepted_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    request_id: Mapped[str] = mapped_column(Text, nullable=False)
    metrics_json: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'{}'"))
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("strftime('%Y-%m-%dT%H:%M:%fZ','now')"))
    id: Mapped[Optional[str]] = mapped_column(Text, primary_key=True)
    base_plan_id: Mapped[Optional[str]] = mapped_column(Text)
    result_plan_id: Mapped[Optional[str]] = mapped_column(Text)
    error_code: Mapped[Optional[str]] = mapped_column(Text)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    finished_at: Mapped[Optional[str]] = mapped_column(Text)

    plan_versions: Mapped[Optional['PlanVersions']] = relationship('PlanVersions', foreign_keys=[goal_id, base_plan_id])
    plan_versions_: Mapped[Optional['PlanVersions']] = relationship('PlanVersions', foreign_keys=[goal_id, result_plan_id])
    goals: Mapped['Goals'] = relationship('Goals')


class Questions(Base):
    __tablename__ = 'questions'
    __table_args__ = (
        CheckConstraint('difficulty BETWEEN 1 AND 5'),
        CheckConstraint('json_valid(options_json)'),
        CheckConstraint('reviewed IN (0,1)'),
        UniqueConstraint('id', 'skill_id')
    )

    skill_id: Mapped[str] = mapped_column(ForeignKey('skills.id'), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    options_json: Mapped[str] = mapped_column(Text, nullable=False)
    answer_option: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    difficulty: Mapped[int] = mapped_column(Integer, nullable=False)
    form: Mapped[str] = mapped_column(Enum('baseline', 'followup', 'practice'), nullable=False)
    reviewed: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('0'))
    id: Mapped[Optional[str]] = mapped_column(Text, primary_key=True)

    skill: Mapped['Skills'] = relationship('Skills')


class ResourceEmbeddings(Base):
    __tablename__ = 'resource_embeddings'
    __table_args__ = (
        CheckConstraint('dimension > 0'),
        CheckConstraint('json_valid(vector_json)')
    )

    resource_id: Mapped[str] = mapped_column(ForeignKey('resources.id'), primary_key=True)
    model_fingerprint: Mapped[str] = mapped_column(Text, primary_key=True)
    dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    vector_json: Mapped[str] = mapped_column(Text, nullable=False)

    resource: Mapped['Resources'] = relationship('Resources')


class StudentSkillState(Base):
    __tablename__ = 'student_skill_state'
    __table_args__ = (
        CheckConstraint('alpha >= 1'),
        CheckConstraint('beta >= 1'),
        CheckConstraint('independent_count >= 0'),
        CheckConstraint('projection_revision >= 0'),
        CheckConstraint('supported_count >= 0')
    )

    student_id: Mapped[str] = mapped_column(ForeignKey('students.id'), primary_key=True)
    skill_id: Mapped[str] = mapped_column(ForeignKey('skills.id'), primary_key=True)
    alpha: Mapped[float] = mapped_column(REAL, nullable=False)
    beta: Mapped[float] = mapped_column(REAL, nullable=False)
    independent_count: Mapped[int] = mapped_column(Integer, nullable=False)
    supported_count: Mapped[int] = mapped_column(Integer, nullable=False)
    projection_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    last_independent_at: Mapped[Optional[str]] = mapped_column(Text)

    skill: Mapped['Skills'] = relationship('Skills')
    student: Mapped['Students'] = relationship('Students')


class WorkItems(Base):
    __tablename__ = 'work_items'
    __table_args__ = (
        CheckConstraint('base_minutes BETWEEN 1 AND 480'),
        ForeignKeyConstraint(['curriculum_id', 'topic_id'], ['topics.curriculum_id', 'topics.id']),
        ForeignKeyConstraint(['goal_id', 'curriculum_id'], ['goals.id', 'goals.curriculum_id']),
        ForeignKeyConstraint(['skill_id', 'topic_id'], ['skills.id', 'skills.topic_id']),
        UniqueConstraint('goal_id', 'id'),
        UniqueConstraint('goal_id', 'unit_key')
    )

    goal_id: Mapped[str] = mapped_column(Text, nullable=False)
    curriculum_id: Mapped[str] = mapped_column(Text, nullable=False)
    topic_id: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Enum('learn', 'practice', 'assess', 'review'), nullable=False)
    unit_key: Mapped[str] = mapped_column(Text, nullable=False)
    base_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(Enum('pending', 'missed', 'completed'), nullable=False, server_default=text("'pending'"))
    id: Mapped[Optional[str]] = mapped_column(Text, primary_key=True)
    skill_id: Mapped[Optional[str]] = mapped_column(Text)

    topics: Mapped['Topics'] = relationship('Topics')
    goals: Mapped['Goals'] = relationship('Goals')
    skills: Mapped[Optional['Skills']] = relationship('Skills')


class Attempts(Base):
    __tablename__ = 'attempts'
    __table_args__ = (
        CheckConstraint('correct IN (0,1)'),
        CheckConstraint('hints_used BETWEEN 0 AND 10'),
        CheckConstraint('is_independent_evidence IN (0,1)'),
        CheckConstraint('is_independent_evidence=0 OR hints_used=0'),
        ForeignKeyConstraint(['goal_id', 'student_id'], ['goals.id', 'goals.student_id']),
        ForeignKeyConstraint(['question_id', 'skill_id'], ['questions.id', 'questions.skill_id']),
        Index('attempts_for_skill', 'student_id', 'skill_id', 'submitted_at'),
        Index('independent_item_once', 'student_id', 'question_id', unique=True)
    )

    batch_id: Mapped[str] = mapped_column(Text, nullable=False)
    student_id: Mapped[str] = mapped_column(Text, nullable=False)
    goal_id: Mapped[str] = mapped_column(Text, nullable=False)
    skill_id: Mapped[str] = mapped_column(Text, nullable=False)
    question_id: Mapped[str] = mapped_column(Text, nullable=False)
    selected_option: Mapped[str] = mapped_column(Text, nullable=False)
    correct: Mapped[int] = mapped_column(Integer, nullable=False)
    hints_used: Mapped[int] = mapped_column(Integer, nullable=False)
    is_independent_evidence: Mapped[int] = mapped_column(Integer, nullable=False)
    submitted_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("strftime('%Y-%m-%dT%H:%M:%fZ','now')"))
    id: Mapped[Optional[str]] = mapped_column(Text, primary_key=True)

    goals: Mapped['Goals'] = relationship('Goals')
    questions: Mapped['Questions'] = relationship('Questions')


class PlanChanges(Base):
    __tablename__ = 'plan_changes'
    __table_args__ = (
        CheckConstraint('after_json IS NULL OR json_valid(after_json)'),
        CheckConstraint('before_json IS NULL OR json_valid(before_json)'),
        CheckConstraint('json_valid(evidence_json)')
    )

    plan_id: Mapped[str] = mapped_column(ForeignKey('plan_versions.id'), nullable=False)
    work_item_id: Mapped[str] = mapped_column(ForeignKey('work_items.id'), nullable=False)
    change_type: Mapped[str] = mapped_column(Enum('added', 'moved', 'resized', 'deferred', 'removed'), nullable=False)
    reason_code: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_json: Mapped[str] = mapped_column(Text, nullable=False)
    id: Mapped[Optional[str]] = mapped_column(Text, primary_key=True)
    before_json: Mapped[Optional[str]] = mapped_column(Text)
    after_json: Mapped[Optional[str]] = mapped_column(Text)

    plan: Mapped['PlanVersions'] = relationship('PlanVersions')
    work_item: Mapped['WorkItems'] = relationship('WorkItems')


class PlanEntries(Base):
    __tablename__ = 'plan_entries'
    __table_args__ = (
        CheckConstraint('duration_minutes > 0'),
        CheckConstraint('json_valid(activity_json)'),
        CheckConstraint('json_valid(reason_details_json)'),
        CheckConstraint('sequence > 0'),
        ForeignKeyConstraint(['goal_id', 'plan_id'], ['plan_versions.goal_id', 'plan_versions.id']),
        ForeignKeyConstraint(['goal_id', 'work_item_id'], ['work_items.goal_id', 'work_items.id']),
        UniqueConstraint('plan_id', 'study_date', 'sequence'),
        UniqueConstraint('plan_id', 'work_item_id', 'id'),
        UniqueConstraint('plan_id', 'work_item_id')
    )

    goal_id: Mapped[str] = mapped_column(Text, nullable=False)
    plan_id: Mapped[str] = mapped_column(Text, nullable=False)
    work_item_id: Mapped[str] = mapped_column(Text, nullable=False)
    study_date: Mapped[str] = mapped_column(Text, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    reason_code: Mapped[str] = mapped_column(Text, nullable=False)
    reason_details_json: Mapped[str] = mapped_column(Text, nullable=False)
    activity_json: Mapped[str] = mapped_column(Text, nullable=False)
    id: Mapped[Optional[str]] = mapped_column(Text, primary_key=True)

    plan_versions: Mapped['PlanVersions'] = relationship('PlanVersions')
    work_items: Mapped['WorkItems'] = relationship('WorkItems')


class ProgressEvents(Base):
    __tablename__ = 'progress_events'
    __table_args__ = (
        CheckConstraint('actual_minutes BETWEEN 0 AND 480'),
        ForeignKeyConstraint(['goal_id', 'plan_id'], ['plan_versions.goal_id', 'plan_versions.id']),
        ForeignKeyConstraint(['goal_id', 'student_id'], ['goals.id', 'goals.student_id']),
        ForeignKeyConstraint(['goal_id', 'work_item_id'], ['work_items.goal_id', 'work_items.id']),
        UniqueConstraint('plan_id', 'work_item_id', 'event_type')
    )

    student_id: Mapped[str] = mapped_column(Text, nullable=False)
    goal_id: Mapped[str] = mapped_column(Text, nullable=False)
    plan_id: Mapped[str] = mapped_column(Text, nullable=False)
    work_item_id: Mapped[str] = mapped_column(Text, nullable=False)
    event_type: Mapped[str] = mapped_column(Enum('completed', 'missed'), nullable=False)
    occurred_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("strftime('%Y-%m-%dT%H:%M:%fZ','now')"))
    id: Mapped[Optional[str]] = mapped_column(Text, primary_key=True)
    actual_minutes: Mapped[Optional[int]] = mapped_column(Integer)

    plan_versions: Mapped['PlanVersions'] = relationship('PlanVersions')
    goals: Mapped['Goals'] = relationship('Goals')
    work_items: Mapped['WorkItems'] = relationship('WorkItems')


class LearningProjects(Base):
    __tablename__ = 'learning_projects'
    __table_args__ = (
        ForeignKeyConstraint(['student_id'], ['students.id']),
        ForeignKeyConstraint(['curriculum_id'], ['curricula.id']),
        ForeignKeyConstraint(['goal_id'], ['goals.id']),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    student_id: Mapped[str] = mapped_column(Text, nullable=False)
    curriculum_id: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    goal_id: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("strftime('%Y-%m-%dT%H:%M:%fZ','now')"))
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("strftime('%Y-%m-%dT%H:%M:%fZ','now')"))


class StudyScopes(Base):
    __tablename__ = 'study_scopes'
    __table_args__ = (
        CheckConstraint('json_valid(selected_topics_json)'),
        CheckConstraint('json_valid(selected_resources_json)'),
        ForeignKeyConstraint(['project_id'], ['learning_projects.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['student_id'], ['students.id']),
        UniqueConstraint('project_id'),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    project_id: Mapped[str] = mapped_column(Text, nullable=False)
    student_id: Mapped[str] = mapped_column(Text, nullable=False)
    selected_topics_json: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'[]'"))
    selected_resources_json: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'[]'"))
    free_text_request: Mapped[Optional[str]] = mapped_column(Text)
    confirmed_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("strftime('%Y-%m-%dT%H:%M:%fZ','now')"))


class ResourceUploads(Base):
    __tablename__ = 'resource_uploads'
    __table_args__ = (
        ForeignKeyConstraint(['student_id'], ['students.id']),
        ForeignKeyConstraint(['project_id'], ['learning_projects.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['curriculum_id'], ['curricula.id']),
        UniqueConstraint('student_id', 'content_hash'),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    student_id: Mapped[str] = mapped_column(Text, nullable=False)
    project_id: Mapped[Optional[str]] = mapped_column(Text)
    curriculum_id: Mapped[Optional[str]] = mapped_column(Text)
    topic_id: Mapped[Optional[str]] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    original_filename: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(Text, nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    extracted_text: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    processing_status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'indexed'"))
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("strftime('%Y-%m-%dT%H:%M:%fZ','now')"))
