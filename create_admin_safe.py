import asyncio
import asyncpg
from app.core.security import get_password_hash

async def create_admin_user():
    """
    Create admin user with proper parameterized query
    (no shell interpolation, no $ escaping issues)
    """
    # Connection to database inside Docker network
    conn = await asyncpg.connect(
        user='postgres',
        password='SecureP@ssw0rd2024!',
        database='autoservice',
        host='db'  # Docker service name
    )
    
    try:
        # Generate proper password hash
        password_hash = get_password_hash('admin')
        print(f"Generated hash: {password_hash}")
        
        # Check if admin already exists
        existing = await conn.fetchval(
            'SELECT id FROM users WHERE username = $1',
            'admin'
        )
        
        if existing:
            print(f"Admin user already exists (id={existing})")
            # Update password instead
            await conn.execute(
                'UPDATE users SET hashed_password = $1 WHERE username = $2',
                password_hash,
                'admin'
            )
            print("Admin password updated!")
        else:
            # Insert new admin user
            # Using parameterized query - PostgreSQL handles escaping
            result = await conn.execute(
                '''INSERT INTO users 
                   (username, hashed_password, is_active, role, tenant_id) 
                   VALUES ($1, $2, $3, $4, $5)''',
                'admin',           # $1 - username
                password_hash,     # $2 - hashed_password (WITH $ symbols safe!)
                True,              # $3 - is_active
                'ADMIN',           # $4 - role
                1                  # $5 - tenant_id
            )
            print(f"Admin user created successfully!")
        
        # Verify
        user = await conn.fetchrow(
            'SELECT id, username, hashed_password, is_active, role FROM users WHERE username = $1',
            'admin'
        )
        
        if user:
            print(f"\n✓ User in database:")
            print(f"  ID: {user['id']}")
            print(f"  Username: {user['username']}")
            print(f"  Hash length: {len(user['hashed_password'])} chars")
            print(f"  Is active: {user['is_active']}")
            print(f"  Role: {user['role']}")
            
            # Verify hash is not corrupted
            if user['hashed_password'].startswith('$2b$'):
                print(f"  ✓ Hash format valid (starts with $2b$)")
            else:
                print(f"  ✗ Hash format INVALID!")
                
    finally:
        await conn.close()
        print("\nDatabase connection closed.")

if __name__ == '__main__':
    asyncio.run(create_admin_user())
