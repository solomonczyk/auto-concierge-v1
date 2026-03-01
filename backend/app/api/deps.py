from typing import Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.db.session import get_db
from app.models.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/login/access-token")
optional_bearer = HTTPBearer(auto_error=False)

async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: AsyncSession = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    stmt = select(User).where(User.username == username)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)]
) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

async def get_current_user_optional(
    auth: Annotated[HTTPAuthorizationCredentials | None, Depends(optional_bearer)] = None,
    db: AsyncSession = Depends(get_db)
) -> User | None:
    if not auth or not auth.credentials:
        return None
    token = auth.credentials
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
        
        stmt = select(User).where(User.username == username)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()
    except JWTError:
        return None

async def get_current_tenant_id(
    current_user: Annotated[User | None, Depends(get_current_user_optional)] = None
) -> int:
    # 1. Check context (set by middleware, includes production fallback)
    from app.core.context import tenant_id_context
    ctx_tenant_id = tenant_id_context.get()
    if ctx_tenant_id:
        return ctx_tenant_id
        
    # 2. Check user as backup
    if current_user:
        return current_user.tenant_id

    # 3. Last resort production fallback (if for some reason middleware didn't set it)
    if settings.ENVIRONMENT == "production":
        return 3

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated and no tenant context",
    )

from app.models.models import UserRole

def require_role(allowed_roles: list[UserRole]):
    def role_checker(current_user: User = Depends(get_current_active_user)):
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="Not enough permissions"
            )
        return current_user
    return role_checker
