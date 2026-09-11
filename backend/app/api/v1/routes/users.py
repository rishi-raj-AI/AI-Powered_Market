from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.core.capabilities import capabilities_for
from app.models.user import User
from app.schemas.user import CapabilityResponse, UserResponse

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserResponse)
def read_current_user(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.get("/me/capabilities", response_model=CapabilityResponse)
def read_current_user_capabilities(current_user: User = Depends(get_current_user)) -> CapabilityResponse:
    """Return only capabilities the backend will actually enforce."""
    return CapabilityResponse(
        is_super_admin=current_user.is_super_admin,
        capabilities=sorted(capability.value for capability in capabilities_for(current_user)),
    )
