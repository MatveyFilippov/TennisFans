# Architecture and data model

FastAPI validates request contracts. Services check actor membership, permissions, and state transitions before changing normalized SQLAlchemy records. Alembic owns schema DDL. Vite produces a static React SPA. Node runs the reference frontend server and supplies runtime API origin configuration. The API runs its own scheduler in the backend process.

```mermaid
erDiagram
    USERS ||--o{ SESSIONS : owns
    USERS ||--o{ TOURNAMENT_PARTICIPANTS : joins
    USERS ||--o{ TOURNAMENT_APPLICATIONS : applies
    USERS ||--o{ TOURNAMENT_ORGANIZERS : manages
    TOURNAMENTS ||--o{ TOURNAMENT_PARTICIPANTS : accepts
    TOURNAMENTS ||--o{ TOURNAMENT_APPLICATIONS : receives
    TOURNAMENTS ||--o{ TOURNAMENT_ORGANIZERS : assigns
    TOURNAMENTS ||--o{ TOURNAMENT_ENTRIES : seeds
    TOURNAMENT_ENTRIES ||--|{ TOURNAMENT_ENTRY_MEMBERS : contains
    TOURNAMENT_PARTICIPANTS ||--o| TOURNAMENT_ENTRY_MEMBERS : fills
    TOURNAMENTS ||--o{ TOURNAMENT_STAGES : schedules
    TOURNAMENT_STAGES ||--o{ TOURNAMENT_GROUPS : partitions
    TOURNAMENT_GROUPS ||--o{ TOURNAMENT_GROUP_ENTRIES : groups
    TOURNAMENT_STAGES ||--o{ FIXTURES : defines
    FIXTURES ||--o| MATCHES : instantiates
    MATCHES ||--|{ MATCH_SIDES : has
    MATCH_SIDES ||--|{ MATCH_SIDE_PLAYERS : contains
    USERS ||--o{ MATCH_SIDE_PLAYERS : plays
    MATCHES ||--o{ MATCH_SETS : scores
    MATCHES ||--o{ MATCH_RESULT_REVISIONS : revises
    MATCHES ||--o{ DISPUTES : reviews
    MATCHES ||--o{ RATING_EVENTS : projects
    USERS ||--o{ RATING_EVENTS : earns
    MATCHES ||--o{ MEDIA_FILES : depicts
    TOURNAMENTS ||--o{ MEDIA_FILES : depicts
    USERS ||--o| MEDIA_FILES : has_avatar
    USERS ||--o{ AUDIT_EVENTS : acts
```

A registered user supplies the player identity everywhere. Accepted roster positions and seed positions are distinct. Fixed teams contain exactly two roster members at startup. Fixture edges reference upstream fixture IDs, and schedule labels are separate from actual playing times. The rotation uses independent structural slots so deletion of a played match can reconstruct the scheduled fixture without restoring the deleted facts.

```mermaid
stateDiagram-v2
    [*] --> Scheduled
    Scheduled --> ActionRequired: due with incomplete roster
    ActionRequired --> Scheduled: administrator changes start time
    Scheduled --> Active: due with valid full roster
    Active --> Completed: all required outcomes resolved
    Completed --> Active: dispute or missing valid outcome
    Scheduled --> [*]: administrator deletes
    ActionRequired --> [*]: administrator deletes
    Active --> [*]: administrator deletes
    Completed --> [*]: administrator deletes
```

```mermaid
stateDiagram-v2
    [*] --> Scheduled: known fixture sides
    [*] --> Completed: friendly result
    Scheduled --> Completed: participant records result
    Completed --> Disputed: opponent challenges
    Disputed --> Completed: uphold or replacement
    Completed --> Blocked: upstream dispute prevents progression
    Blocked --> Completed: upstream result supports same participants
    Blocked --> [*]: confirmed cascade
    Completed --> [*]: confirmed deletion
    Disputed --> [*]: confirmed annulment
```

All writes share a PostgreSQL transaction advisory lock. The due-date reconciler selects candidates and rereads each candidate under both the advisory lock and a row lock. Writes, fixture changes, media metadata, and full Elo replay commit together. Public reads use PostgreSQL repeatable-read snapshots. Operations use match versions and client-generated idempotency keys to protect retries. Multiple backend processes must share the same database, rating configuration, and persistent media.

The filesystem adapter writes sanitized images and thumbnail siblings outside PostgreSQL. Delete transactions enqueue idempotent file removal. Startup and periodic maintenance retry removals and sweep old unreferenced objects. A future S3-compatible implementation can replace the storage interface and provide its own streaming/deletion semantics.
