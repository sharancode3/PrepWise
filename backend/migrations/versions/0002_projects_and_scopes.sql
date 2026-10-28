CREATE TABLE learning_projects (
  id TEXT PRIMARY KEY,
  student_id TEXT NOT NULL REFERENCES students(id),
  curriculum_id TEXT NOT NULL REFERENCES curricula(id),
  title TEXT NOT NULL,
  description TEXT,
  goal_id TEXT REFERENCES goals(id),
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  FOREIGN KEY(student_id) REFERENCES students(id),
  FOREIGN KEY(curriculum_id) REFERENCES curricula(id),
  FOREIGN KEY(goal_id) REFERENCES goals(id)
);

CREATE TABLE study_scopes (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES learning_projects(id) ON DELETE CASCADE,
  student_id TEXT NOT NULL REFERENCES students(id),
  selected_topics_json TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(selected_topics_json)),
  selected_resources_json TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(selected_resources_json)),
  free_text_request TEXT,
  confirmed_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  UNIQUE(project_id),
  FOREIGN KEY(project_id) REFERENCES learning_projects(id) ON DELETE CASCADE,
  FOREIGN KEY(student_id) REFERENCES students(id)
);

CREATE TABLE resource_uploads (
  id TEXT PRIMARY KEY,
  student_id TEXT NOT NULL REFERENCES students(id),
  project_id TEXT REFERENCES learning_projects(id) ON DELETE CASCADE,
  curriculum_id TEXT REFERENCES curricula(id),
  topic_id TEXT,
  title TEXT NOT NULL,
  original_filename TEXT NOT NULL,
  mime_type TEXT NOT NULL,
  byte_size INTEGER NOT NULL,
  content_hash TEXT NOT NULL,
  extracted_text TEXT NOT NULL DEFAULT '',
  processing_status TEXT NOT NULL DEFAULT 'indexed',
  error_message TEXT,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  UNIQUE(student_id, content_hash),
  FOREIGN KEY(student_id) REFERENCES students(id),
  FOREIGN KEY(project_id) REFERENCES learning_projects(id) ON DELETE CASCADE,
  FOREIGN KEY(curriculum_id) REFERENCES curricula(id)
);
