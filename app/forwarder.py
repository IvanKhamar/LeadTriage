"""Hands a lead to the n8n webhook, adding the webhook token on the server side (it never reaches a browser)."""

import logging

import httpx
from pydantic import SecretStr

log = logging.getLogger("leadtriage")


class ForwardError(Exception):
    """n8n could not take the lead. The caller answers 503 and the source retries later."""


class N8nForwarder:
    def __init__(self, client: httpx.AsyncClient, url: str, token: SecretStr) -> None:
        self.client = client
        self.url = url
        self.token = token

    async def forward(self, payload: dict) -> dict:
        """POSTs the lead; returns n8n's JSON answer (the triage result), or {} when it is not JSON.

        One retry, and only when the request surely did not reach n8n (connection refused or connect timeout).
        A read timeout is not retried: n8n may still be working on the lead, and a second copy would be processed
        twice. It becomes a 503 instead, and the source's own retry is the second chance.
        """
        headers = {"X-Webhook-Token": self.token.get_secret_value()}
        for attempt in (1, 2):
            try:
                response = await self.client.post(self.url, json=payload, headers=headers)
            except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
                log.warning("n8n not reachable (attempt %d): %s", attempt, type(exc).__name__)
                if attempt == 2:
                    raise ForwardError("n8n not reachable") from exc
                continue
            except httpx.HTTPError as exc:
                log.warning("forwarding failed: %s", type(exc).__name__)
                raise ForwardError(type(exc).__name__) from exc

            if response.is_success:
                try:
                    answer = response.json()
                except ValueError:
                    return {}
                return answer if isinstance(answer, dict) else {}
            log.warning("n8n answered %d", response.status_code)
            raise ForwardError(f"n8n answered {response.status_code}")
        raise ForwardError("unreachable")  # the loop always returns or raises; this keeps type checkers calm
