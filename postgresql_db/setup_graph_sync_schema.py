import asyncio
import os
from dotenv import load_dotenv
from postgresql_db.database import create_pool, close_pool, get_pool

# Load .env
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))


async def setup():
    await create_pool()
    pool = get_pool()
    conn = await pool.acquire()

    try:
        print("Adding Microsoft Graph sync columns to users...")
        await conn.execute("""
            ALTER TABLE users ADD COLUMN IF NOT EXISTS department TEXT;
            ALTER TABLE users ADD COLUMN IF NOT EXISTS job_title TEXT;
            ALTER TABLE users ADD COLUMN IF NOT EXISTS graph_account_enabled BOOLEAN;
            ALTER TABLE users ADD COLUMN IF NOT EXISTS last_graph_sync TIMESTAMP WITH TIME ZONE;
        """)

        print("Seeding PENDING_USER and USER roles...")
        await conn.execute(
            "INSERT INTO roles (code, name, description, is_system_role) VALUES ('USER', 'Standard User', 'Standard user with view access', false) ON CONFLICT (code) DO NOTHING"
        )
        await conn.execute(
            "INSERT INTO roles (code, name, description, is_system_role) VALUES ('PENDING_USER', 'Pending User', 'Pending activation', true) ON CONFLICT (code) DO NOTHING"
        )

        print("Backfilling USER role for active users with no roles assigned...")
        backfilled = await conn.fetch("""
            INSERT INTO user_roles (user_id, role_id, is_active, assigned_at)
            SELECT u.id, r.id, true, now()
            FROM users u
            CROSS JOIN (SELECT id FROM roles WHERE code = 'USER') r
            WHERE u.is_active = true
              AND NOT EXISTS (
                  SELECT 1 FROM user_roles ur WHERE ur.user_id = u.id AND ur.is_active = true
              )
            RETURNING user_id
        """)
        print(f"Backfilled USER role for {len(backfilled)} existing user(s).")

        print("Graph sync schema setup complete!")
    finally:
        await pool.release(conn)
        await close_pool()


if __name__ == "__main__":
    asyncio.run(setup())
