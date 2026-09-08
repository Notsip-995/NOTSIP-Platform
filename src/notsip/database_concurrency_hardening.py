from __future__ import annotations
import json,time


def install(store):
    backend=getattr(store,'_backend',None)
    if backend is None or getattr(backend,'_notsip_command_claim_guarded',False):return store
    if backend.__class__.__name__!='PostgreSQLStore':return store

    def pull_commands(device_id,limit=20):
        limit=max(1,min(int(limit),100))
        with backend.conn() as conn:
            rows=conn.execute(
                """WITH claimed AS (
                    SELECT id FROM commands
                    WHERE device_id=%s AND status='PENDING'
                    ORDER BY created
                    LIMIT %s
                    FOR UPDATE SKIP LOCKED
                )
                UPDATE commands AS c
                SET status='DELIVERED',updated=%s
                FROM claimed
                WHERE c.id=claimed.id
                RETURNING c.*""",
                (device_id,limit,time.time()),
            ).fetchall()
            conn.commit()
            return [{**dict(row),'payload':json.loads(row['payload'])} for row in rows]

    backend.pull_commands=pull_commands
    backend._notsip_command_claim_guarded=True
    return store
