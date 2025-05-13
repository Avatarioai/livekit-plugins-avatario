import asyncio
import os
from typing import Any, cast

import aiohttp

from livekit.agents import (
    DEFAULT_API_CONNECT_OPTIONS,
    NOT_GIVEN,
    APIConnectionError,
    APIConnectOptions,
    APIStatusError,
    NotGivenOr,
    utils,
)

from .log import logger


class AvatarioException(Exception):
    """Exception for Avatario errors"""


DEFAULT_API_URL = ""


class AvatarioAPI:
    def __init__(
        self,
        api_key: NotGivenOr[str] = NOT_GIVEN,
        *,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        self._api_key = api_key or os.getenv("AVATARIO_API_KEY")
        if self._api_key is None:
            raise AvatarioException("AVATARIO_API_KEY must be set")
        self._api_key = cast(str, self._api_key)

        self._conn_options = conn_options
        self._session = session or aiohttp.ClientSession()

    async def start_session(
        self,
        *,
        avatar_id: NotGivenOr[str] = NOT_GIVEN,
        livekit_agent_identity: NotGivenOr[str] = NOT_GIVEN,
        properties: NotGivenOr[dict[str, Any]] = NOT_GIVEN,
        extra_payload: NotGivenOr[dict[str, Any]] = NOT_GIVEN,
    ) -> None:
        avatar_id = avatar_id or os.getenv("AVATARIO_REPLICA_ID")
        if not avatar_id:
            raise AvatarioException("avatar_id must be set")
        if not livekit_agent_identity:
            raise AvatarioException(
                "the identity of agent needs to be provided "
                "to ensure its proper communication with avatario backend"
            )

        properties = properties or {}
        payload = {
            "avatario_face_id": avatar_id,
            "agent_id": livekit_agent_identity,
            "livekit": properties,
        }

        ##extra payload can include values audio_sample_rate, video_frame_width, video_frame_height
        if utils.is_given(extra_payload):
            payload.update(extra_payload)

        await self._post(payload)

    async def _post(self, payload: dict[str, Any]) -> None:
        """
        Make a POST request to the Tavus API with retry logic.

        Args:
            payload: JSON payload for the request

        Raises:
            APIConnectionError: If the request fails after all retries
        """
        for i in range(self._conn_options.max_retry):
            try:
                async with self._session.post(
                    f"{DEFAULT_API_URL}/start_session",
                    headers={
                        "Content-Type": "application/json",
                        "x-api-key": self._api_key,
                    },
                    json=payload,
                    timeout=self._conn_options.timeout,
                ) as response:
                    if not response.ok:
                        text = await response.text()
                        raise APIStatusError(
                            "Server returned an error",
                            status_code=response.status,
                            body=text,
                        )
                    await response.json()
            except Exception as e:
                if isinstance(e, APIConnectionError):
                    logger.warning(
                        "failed to call avatario api", extra={"error": str(e)}
                    )
                else:
                    logger.exception("failed to call avatario api")

                if i < self._conn_options.max_retry - 1:
                    await asyncio.sleep(self._conn_options.retry_interval)

        raise APIConnectionError("Failed to call Avatario API after all retries")
