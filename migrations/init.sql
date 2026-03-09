CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS users (
    id         BIGSERIAL    PRIMARY KEY,
    telegram_id BIGINT      UNIQUE NOT NULL,
    username   VARCHAR(255),
    created_at TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS topics (
    id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS questions (
    id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    topic_id UUID NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    text     TEXT NOT NULL,
    answer   TEXT NOT NULL,
    cost     INTEGER NOT NULL CHECK (cost > 0)
);

CREATE TABLE IF NOT EXISTS games (
    id                UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    chat_id           BIGINT      NOT NULL,
    status            VARCHAR(20) NOT NULL DEFAULT 'waiting',
    current_player_id UUID,
    host_id           BIGINT      REFERENCES users(id),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at       TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS participants (
    id        UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id   BIGINT      NOT NULL REFERENCES users(id),
    game_id   UUID        NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    role      VARCHAR(20) NOT NULL DEFAULT 'player',
    score     INTEGER     NOT NULL DEFAULT 0,
    joined_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_active BOOLEAN     NOT NULL DEFAULT TRUE,
    UNIQUE(game_id, user_id)
);

ALTER TABLE games
    ADD CONSTRAINT fk_games_current_player
    FOREIGN KEY (current_player_id) REFERENCES participants(id);

CREATE TABLE IF NOT EXISTS questions_in_game (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    game_id     UUID        NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    question_id UUID        NOT NULL REFERENCES questions(id),
    status      VARCHAR(20) NOT NULL DEFAULT 'pending',
    asked_by    UUID        REFERENCES participants(id),
    answered_by UUID        REFERENCES participants(id),
    asked_at    TIMESTAMPTZ,
    answered_at TIMESTAMPTZ,
    UNIQUE(game_id, question_id)
);

CREATE TABLE IF NOT EXISTS game_states (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    game_id             UUID        UNIQUE NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    status              VARCHAR(20) NOT NULL,
    current_question_id UUID        REFERENCES questions_in_game(id),
    buzzer_pressed_by   UUID        REFERENCES participants(id),
    buzzer_pressed_at   TIMESTAMPTZ,
    timer_ends_at       TIMESTAMPTZ,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
