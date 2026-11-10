"""Cognito identity and workspace boundary checks for foundation issues 91/92."""

from datetime import datetime, timedelta, timezone
import uuid

import pytest
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import select

from app.api import deps
from app.core import cognito
from app.core.config import settings
from app.db.session import get_db
from app.main import app
from app.models.membership import Membership, MembershipRole
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceType


def test_cognito_rejects_wrong_audience_and_token_type(monkeypatch):
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization

    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                        serialization.NoEncryption())
    public_pem = private.public_key().public_bytes(serialization.Encoding.PEM,
                                                    serialization.PublicFormat.SubjectPublicKeyInfo)
    monkeypatch.setattr(settings, "cognito_user_pool_id", "ap-southeast-1_test")
    monkeypatch.setattr(settings, "cognito_client_id", "web-client")
    monkeypatch.setattr(cognito, "_keys", {"test-key": public_pem})
    monkeypatch.setattr(cognito, "_keys_expires_at", float("inf"))
    claims = {"sub": "subject-1", "aud": "web-client", "token_use": "id",
              "iss": "https://cognito-idp.ap-southeast-1.amazonaws.com/ap-southeast-1_test",
              "iat": datetime.now(timezone.utc),
              "exp": datetime.now(timezone.utc) + timedelta(minutes=5)}

    def token(**changes):
        return jwt.encode({**claims, **changes}, private_pem, algorithm="RS256",
                          headers={"kid": "test-key"})

    assert cognito.verify_id_token(token())["sub"] == "subject-1"
    for change in ({"aud": "other-client"}, {"token_use": "access"},
                   {"iss": "https://wrong.example"},
                   {"exp": datetime.now(timezone.utc) - timedelta(minutes=1)}):
        with pytest.raises(Exception):
            cognito.verify_id_token(token(**change))


def test_first_sign_in_creates_personal_workspace_and_checks_selection(db, monkeypatch):
    monkeypatch.setattr(deps, "verify_id_token", lambda _: {"sub": "new-sub"})

    class CognitoClient:
        def admin_get_user(self, **kwargs):
            assert kwargs["Username"] == "new-sub"
            return {"UserAttributes": [
                {"Name": "sub", "Value": "new-sub"},
                {"Name": "email", "Value": "new@example.com"},
            ]}

    monkeypatch.setattr(deps.boto3, "client", lambda *args, **kwargs: CognitoClient())
    app.dependency_overrides[get_db] = lambda: db
    try:
        client = TestClient(app)
        assert client.get("/me").status_code == 401
        headers = {"Authorization": "Bearer signed-token"}
        me = client.get("/me", headers=headers)
        assert me.status_code == 200
        assert me.json()["user"]["email"] == "new@example.com"
        personal_id = me.json()["memberships"][0]["workspace"]["id"]
        assert me.json()["memberships"][0]["role"] == "owner"
        assert client.get("/notifications", headers=headers).status_code == 400
        assert client.get("/notifications", headers={**headers, "X-Workspace-Id": personal_id}).status_code == 200
        foreign_user = User(cognito_sub="other-sub", email="other@example.com")
        foreign = Workspace(name="Other Organization", type=WorkspaceType.organization)
        db.add_all([foreign_user, foreign])
        db.flush()
        db.add(Membership(user_id=foreign_user.id, workspace_id=foreign.id, role=MembershipRole.owner))
        db.flush()
        assert client.get("/notifications", headers={**headers, "X-Workspace-Id": str(foreign.id)}).status_code == 404
        assert client.get("/me", headers=headers).json()["memberships"][0]["workspace"]["id"] == personal_id
    finally:
        app.dependency_overrides.clear()


def test_create_organization_owner_and_reject_invalid_type(api, db, user):
    response = api.post("/workspaces", json={"name": "  Acme  ", "type": "organization"})
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Acme" and body["role"] == "owner"
    org = db.get(Workspace, uuid.UUID(body["id"]))
    assert org.type is WorkspaceType.organization
    member = db.scalar(select(Membership).where(
        Membership.user_id == user.id, Membership.workspace_id == org.id))
    assert member.role is MembershipRole.owner
    assert any(item["workspace"]["id"] == body["id"] for item in api.get("/me").json()["memberships"])
    assert api.post("/workspaces", json={"name": "  ", "type": "organization"}).status_code == 422
    assert api.post("/workspaces", json={"name": "No", "type": "personal"}).status_code == 422
