import hmac
from collections.abc import Generator

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from backend.core.config import ProviderSettings
from backend.integrations.directory import ClinicDirectory
from backend.schemas.directory import DirectoryBranchInput, DirectoryBranchRecord

router = APIRouter(prefix="/admin/clinic-directory", tags=["admin"])
_directory: ClinicDirectory | None = None


def get_directory() -> Generator[ClinicDirectory, None, None]:
    global _directory
    if _directory is None:
        _directory = ClinicDirectory(ProviderSettings.from_environment().directory_path)
    yield _directory


def require_admin(authorization: str | None = Header(default=None)) -> None:
    expected = ProviderSettings.from_environment().admin_token
    supplied = authorization.removeprefix("Bearer ").strip() if authorization else ""
    if not expected or not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="Administrator authorization required.")


@router.get("", response_model=list[DirectoryBranchRecord], dependencies=[Depends(require_admin)])
def list_directory(
    include_deactivated: bool = Query(default=False),
    directory: ClinicDirectory = Depends(get_directory),
) -> list[DirectoryBranchRecord]:
    return directory.list(include_deactivated=include_deactivated)


@router.post(
    "",
    response_model=DirectoryBranchRecord,
    status_code=201,
    dependencies=[Depends(require_admin)],
)
def add_directory_branch(
    data: DirectoryBranchInput,
    directory: ClinicDirectory = Depends(get_directory),
) -> DirectoryBranchRecord:
    return directory.add(data)


@router.put(
    "/{branch_id}",
    response_model=DirectoryBranchRecord,
    dependencies=[Depends(require_admin)],
)
def update_directory_branch(
    branch_id: str,
    data: DirectoryBranchInput,
    verify: bool = Query(default=False),
    directory: ClinicDirectory = Depends(get_directory),
) -> DirectoryBranchRecord:
    try:
        return directory.update(branch_id, data, verify=verify)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Directory branch was not found.") from exc


@router.post(
    "/{branch_id}/deactivate",
    status_code=204,
    dependencies=[Depends(require_admin)],
)
def deactivate_directory_branch(
    branch_id: str,
    directory: ClinicDirectory = Depends(get_directory),
) -> None:
    try:
        directory.deactivate(branch_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Directory branch was not found.") from exc


@router.get(
    "/{branch_id}/audit",
    response_model=list[dict[str, str]],
    dependencies=[Depends(require_admin)],
)
def get_directory_audit(
    branch_id: str,
    directory: ClinicDirectory = Depends(get_directory),
) -> list[dict[str, str]]:
    return directory.audit(branch_id)
