from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api.admin import get_directory
from backend.core.config import ProviderSettings
from backend.main import app
from backend.integrations.directory import ClinicDirectory


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("CLINIC_ADMIN_TOKEN", "test-token")
    monkeypatch.setenv("CLINIC_DIRECTORY_PATH", str(tmp_path / "directory.sqlite3"))
    directory = ClinicDirectory(tmp_path / "directory.sqlite3")
    app.dependency_overrides[get_directory] = lambda: directory
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_directory, None)


def payload() -> dict[str, object]:
    return {
        "facility_name": "Suraksha Clinic",
        "branch_name": "Barrackpore",
        "facility_type": "clinic",
        "address": "1 Station Road",
        "latitude": 22.76,
        "longitude": 88.37,
        "field_sources": {"address": "official branch confirmation"},
        "field_evidence": {"address": "https://clinic.example/branch"},
        "verification_method": "official branch directory review",
    }


def test_admin_directory_requires_authentication(client: TestClient) -> None:
    response = client.post("/admin/clinic-directory", json=payload())
    assert response.status_code == 401


def test_admin_can_add_then_verify_branch(client: TestClient) -> None:
    headers = {"Authorization": "Bearer test-token"}
    created = client.post("/admin/clinic-directory", json=payload(), headers=headers)
    assert created.status_code == 201
    assert created.json()["verification_status"] == "pending"

    branch_id = created.json()["id"]
    verified = client.put(
        f"/admin/clinic-directory/{branch_id}?verify=true",
        json=payload(),
        headers=headers,
    )
    assert verified.status_code == 200
    assert verified.json()["verification_status"] == "verified"

    audit = client.get(
        f"/admin/clinic-directory/{branch_id}/audit",
        headers=headers,
    )
    assert audit.status_code == 200
    assert [entry["action"] for entry in audit.json()] == ["created", "updated"]


def test_admin_cannot_verify_without_evidence(client: TestClient) -> None:
    headers = {"Authorization": "Bearer test-token"}
    created = client.post("/admin/clinic-directory", json=payload(), headers=headers)
    branch_id = created.json()["id"]
    invalid_payload = {**payload(), "field_evidence": {}}

    response = client.put(
        f"/admin/clinic-directory/{branch_id}?verify=true",
        json=invalid_payload,
        headers=headers,
    )

    assert response.status_code == 422
