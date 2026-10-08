import asyncio
import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass


logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class MinecraftLink:
    code: str
    minecraft_nick: str
    cargo: str
    created_at: int
    expires_at: int


class LinkingService:
    def __init__(
        self,
        api_url: str,
        api_key: str
    ):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key

    def _request(
        self,
        method: str,
        path: str
    ) -> dict:

        url = f"{self.api_url}{path}"

        request = urllib.request.Request(
            url,
            method=method,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json",
            }
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=10
            ) as response:

                raw_data = response.read()

                data = json.loads(
                    raw_data.decode("utf-8")
                )

                return data

        except urllib.error.HTTPError as error:

            try:
                raw_data = error.read()

                data = json.loads(
                    raw_data.decode("utf-8")
                )

            except Exception:
                data = {
                    "success": False,
                    "error": (
                        f"HTTP {error.code}"
                    )
                }

            return data

        except urllib.error.URLError as error:

            logger.error(
                "Não foi possível conectar ao "
                "Embrapa BOT: %s",
                error
            )

            raise

    async def get_link(
        self,
        code: str
    ) -> MinecraftLink | None:

        normalized_code = code.strip().upper()

        if not normalized_code:
            return None

        try:
            data = await asyncio.to_thread(
                self._request,
                "GET",
                f"/linking/{normalized_code}"
            )

        except Exception:
            logger.exception(
                "Erro ao consultar código de vinculação."
            )
            raise

        if not data.get("success"):
            return None

        return MinecraftLink(
            code=data["code"],
            minecraft_nick=data["minecraftNick"],
            cargo=data["cargo"],
            created_at=data["createdAt"],
            expires_at=data["expiresAt"],
        )

    async def consume_link(
        self,
        code: str
    ) -> MinecraftLink | None:

        normalized_code = code.strip().upper()

        if not normalized_code:
            return None

        try:
            data = await asyncio.to_thread(
                self._request,
                "POST",
                f"/linking/{normalized_code}/consume"
            )

        except Exception:
            logger.exception(
                "Erro ao consumir código de vinculação."
            )
            raise

        if not data.get("success"):
            return None

        return MinecraftLink(
            code=data["code"],
            minecraft_nick=data["minecraftNick"],
            cargo=data["cargo"],
            created_at=data["createdAt"],
            expires_at=data["expiresAt"],
        )