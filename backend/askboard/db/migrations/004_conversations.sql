-- Conversations: questions are grouped into chat threads, like a chat assistant.
-- Earlier questions are given to the LLM so follow-ups ("and per month?") make sense.

CREATE TABLE IF NOT EXISTS askboard.conversations (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES askboard.workspaces(id) ON DELETE CASCADE,
    title        text NOT NULL CHECK (length(trim(title)) > 0),
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS conversations_workspace_updated_idx
    ON askboard.conversations (workspace_id, updated_at DESC);

ALTER TABLE askboard.questions
    ADD COLUMN IF NOT EXISTS conversation_id uuid
        REFERENCES askboard.conversations(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS questions_conversation_created_idx
    ON askboard.questions (conversation_id, created_at);

-- Questions asked before conversations existed: one thread per workspace.
DO $$
DECLARE
    ws record;
    conv uuid;
BEGIN
    FOR ws IN
        SELECT workspace_id, min(created_at) AS first_at, max(created_at) AS last_at
        FROM askboard.questions WHERE conversation_id IS NULL GROUP BY workspace_id
    LOOP
        INSERT INTO askboard.conversations (workspace_id, title, created_at, updated_at)
        VALUES (ws.workspace_id, 'Earlier questions', ws.first_at, ws.last_at)
        RETURNING id INTO conv;
        UPDATE askboard.questions SET conversation_id = conv
        WHERE workspace_id = ws.workspace_id AND conversation_id IS NULL;
    END LOOP;
END
$$;

ALTER TABLE askboard.questions ALTER COLUMN conversation_id SET NOT NULL;

REVOKE ALL ON askboard.conversations FROM PUBLIC;
