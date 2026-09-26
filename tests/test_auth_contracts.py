"""Offline Cognito compatibility contracts using the real pycognito AWSSRP.

Only boto3 client creation and unrelated MQTT initialization are substituted.
Synthetic PASSWORD_VERIFIER challenges exercise the installed SRP constructor,
parameter generation, challenge processing and signing, not AWS acceptance.
"""

import base64
import re
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from aiophyn.api import API
from aiophyn.errors import AuthenticationError


@pytest.fixture
def cognito(monkeypatch):
    client = MagicMock(spec=["initiate_auth", "respond_to_auth_challenge"])
    factory = MagicMock(return_value=client)
    monkeypatch.setattr("aiophyn.api.boto3.client", factory)
    monkeypatch.setattr("aiophyn.api.MQTTClient", MagicMock())
    api = API("synthetic@example.invalid", "synthetic-password")
    api._cognito = {
        "app_client_id": "synthetic-client",
        "pool_id": "us-east-1_synthetic",
        "region": "us-east-1",
    }
    return api, client, factory


def password_challenge():
    return {
        "ChallengeName": "PASSWORD_VERIFIER",
        "ChallengeParameters": {
            "USERNAME": "canonical-synthetic-user",
            "USER_ID_FOR_SRP": "synthetic-srp-user",
            "SALT": "deadbeef",
            "SRP_B": "2",
            "SECRET_BLOCK": base64.b64encode(b"synthetic-secret-block").decode("ascii"),
        },
    }


def auth_result(*, refresh=True):
    tokens = {
        "AccessToken": "new-synthetic-access",
        "IdToken": "new-synthetic-id",
        "ExpiresIn": 3600,
    }
    if refresh:
        tokens["RefreshToken"] = "new-synthetic-refresh"
    return {"AuthenticationResult": tokens}


def assert_srp_exchange(client):
    initiation = client.initiate_auth.call_args_list[-1].kwargs
    assert initiation["AuthFlow"] == "USER_SRP_AUTH"
    assert initiation["ClientId"] == "synthetic-client"
    params = initiation["AuthParameters"]
    assert set(params) == {"USERNAME", "SRP_A"}
    assert params["USERNAME"] == "synthetic@example.invalid"
    assert int(params["SRP_A"], 16) > 0

    client.respond_to_auth_challenge.assert_called_once()
    response = client.respond_to_auth_challenge.call_args.kwargs
    assert response["ClientId"] == "synthetic-client"
    assert response["ChallengeName"] == "PASSWORD_VERIFIER"
    claims = response["ChallengeResponses"]
    assert set(claims) == {
        "USERNAME", "TIMESTAMP", "PASSWORD_CLAIM_SECRET_BLOCK", "PASSWORD_CLAIM_SIGNATURE",
    }
    assert claims["USERNAME"] == "canonical-synthetic-user"
    assert re.fullmatch(
        r"\w{3} \w{3} \d{1,2} \d{2}:\d{2}:\d{2} UTC \d{4}", claims["TIMESTAMP"]
    )
    assert base64.b64decode(claims["PASSWORD_CLAIM_SECRET_BLOCK"], validate=True) == (
        b"synthetic-secret-block"
    )
    # A real SRP challenge calculation must produce a SHA-256 HMAC signature.
    assert len(base64.b64decode(claims["PASSWORD_CLAIM_SIGNATURE"], validate=True)) == 32


def assert_applied_tokens(api, before, after, refresh):
    assert api._token == "new-synthetic-access"
    assert api._id_token == "new-synthetic-id"
    assert api._refresh_token == refresh
    assert before + timedelta(seconds=3600) <= api._token_expiration
    assert api._token_expiration <= after + timedelta(seconds=3600)


def test_authenticate_uses_real_srp_challenge(cognito):
    api, client, factory = cognito
    client.initiate_auth.return_value = password_challenge()
    client.respond_to_auth_challenge.return_value = auth_result()

    assert api._authenticate() == auth_result()

    factory.assert_called_once_with("cognito-idp", region_name="us-east-1")
    client.initiate_auth.assert_called_once()
    assert_srp_exchange(client)


@pytest.mark.asyncio
async def test_async_srp_auth_applies_result(cognito):
    api, client, factory = cognito
    client.initiate_auth.return_value = password_challenge()
    client.respond_to_auth_challenge.return_value = auth_result()
    before = datetime.now()

    await api.async_authenticate()

    assert_applied_tokens(api, before, datetime.now(), "new-synthetic-refresh")
    factory.assert_called_once_with("cognito-idp", region_name="us-east-1")
    assert_srp_exchange(client)


@pytest.mark.asyncio
async def test_refresh_uses_cognito_flow_and_preserves_refresh_token(cognito):
    api, client, factory = cognito
    api._refresh_token = "existing-synthetic-refresh"
    client.initiate_auth.return_value = auth_result(refresh=False)
    before = datetime.now()

    await api.async_authenticate()

    client.initiate_auth.assert_called_once_with(
        ClientId="synthetic-client",
        AuthFlow="REFRESH_TOKEN_AUTH",
        AuthParameters={"REFRESH_TOKEN": "existing-synthetic-refresh"},
    )
    client.respond_to_auth_challenge.assert_not_called()
    factory.assert_called_once_with("cognito-idp", region_name="us-east-1")
    assert_applied_tokens(api, before, datetime.now(), "existing-synthetic-refresh")


@pytest.mark.asyncio
async def test_rejected_refresh_falls_back_to_real_srp(cognito):
    api, client, factory = cognito
    api._refresh_token = "expired-synthetic-refresh"
    client.initiate_auth.side_effect = [
        ClientError(
            {"Error": {"Code": "NotAuthorizedException", "Message": "Synthetic expiry"}},
            "InitiateAuth",
        ),
        password_challenge(),
    ]
    client.respond_to_auth_challenge.return_value = auth_result()
    before = datetime.now()

    await api.async_authenticate()

    assert client.initiate_auth.call_count == 2
    assert client.initiate_auth.call_args_list[0].kwargs == {
        "ClientId": "synthetic-client",
        "AuthFlow": "REFRESH_TOKEN_AUTH",
        "AuthParameters": {"REFRESH_TOKEN": "expired-synthetic-refresh"},
    }
    assert factory.call_count == 2
    assert_srp_exchange(client)
    assert_applied_tokens(api, before, datetime.now(), "new-synthetic-refresh")


@pytest.mark.asyncio
async def test_allow_refresh_false_forces_real_srp(cognito):
    api, client, _ = cognito
    api._refresh_token = "existing-synthetic-refresh"
    client.initiate_auth.return_value = password_challenge()
    client.respond_to_auth_challenge.return_value = auth_result()

    await api.async_authenticate(allow_refresh=False)

    client.initiate_auth.assert_called_once()
    assert_srp_exchange(client)
    assert api._refresh_token == "new-synthetic-refresh"


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["initiate", "challenge", "refresh-then-srp"])
async def test_srp_client_errors_become_authentication_errors(cognito, stage):
    api, client, _ = cognito
    failure = ClientError(
        {"Error": {"Code": "NotAuthorizedException", "Message": "Synthetic rejection"}},
        "RespondToAuthChallenge" if stage == "challenge" else "InitiateAuth",
    )
    if stage == "challenge":
        client.initiate_auth.return_value = password_challenge()
        client.respond_to_auth_challenge.side_effect = failure
    elif stage == "refresh-then-srp":
        api._refresh_token = "expired-synthetic-refresh"
        client.initiate_auth.side_effect = failure
    else:
        client.initiate_auth.side_effect = failure

    with pytest.raises(AuthenticationError, match="Unable to authenticate with Phyn") as caught:
        await api.async_authenticate()

    assert caught.value.__cause__ is failure
    assert client.initiate_auth.call_count == (2 if stage == "refresh-then-srp" else 1)
    assert api._token is None
    assert api._id_token is None
    assert api._token_expiration is None
    assert api._refresh_token is None
