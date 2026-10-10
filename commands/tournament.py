"""Slash command /torneio integrado à API do Embrapa BOT."""

from __future__ import annotations

import asyncio
import logging
import re
import urllib.error
import urllib.request
import json
import unicodedata
from typing import Any

import discord
from discord import app_commands

from config.settings import Settings

logger = logging.getLogger(__name__)

# Chaves comuns para localizar as tabelas/rankings no snapshot do Minecraft.
RANKING_KEYS = (
    "players",
    "topPlayers",
    "top_players",
    "top",
    "ranking",
    "rankings",
    "leaderboard",
    "entries",
    "participants",
    "scores",
    "results",
    "jogadores",
    "classificacao",
    "classificação",
)

NAME_KEYS = (
    "name",
    "player",
    "username",
    "nick",
    "nickname",
    "ign",
    "minecraftNick",
    "minecraft_nick",
    "displayName",
    "display_name",
    "playerName",
    "player_name",
    "jogador",
)

POSITION_KEYS = (
    "position",
    "rank",
    "place",
    "pos",
    "placement",
    "positionIndex",
    "colocacao",
    "colocação",
    "posicao",
    "posição",
)

SCORE_KEYS = (
    "points",
    "score",
    "pontuacao",
    "pontuação",
    "totalPoints",
    "total_points",
    "value",
    "amount",
    "pontos",
)

EPA_TAG_KEYS = (
    "tag",
    "prefix",
    "clanTag",
    "clan_tag",
    "clan",
    "team",
    "guild",
    "grupo",
)

EPA_PRIZES = {1: 100_000, 2: 75_000, 3: 50_000}
SERVER_PRIZES = {1: 200_000, 2: 150_000, 3: 100_000}


def _normalize(value: Any) -> str:
    text = str(value or "").strip().casefold()
    return "".join(
        char
        for char in unicodedata.normalize("NFD", text)
        if unicodedata.category(char) != "Mn"
    )


def _first_value(row: dict[str, Any], keys: tuple[str, ...]) -> Any:
    """Busca uma chave ignorando maiúsculas/minúsculas e underscores."""
    normalized = {
        re.sub(r"[_\-\s]", "", str(key)).casefold(): value
        for key, value in row.items()
    }

    for key in keys:
        lookup = re.sub(r"[_\-\s]", "", key).casefold()
        if lookup in normalized and normalized[lookup] not in (None, ""):
            return normalized[lookup]

    return None


def _to_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)

    match = re.search(r"-?\d+", str(value).replace(",", ""))
    return int(match.group(0)) if match else None


def _is_player_row(value: Any) -> bool:
    return isinstance(value, dict) and _first_value(value, NAME_KEYS) is not None


def _rows_from_candidate(value: Any) -> list[dict[str, Any]]:
    """Converte uma lista ou um mapa de posições em linhas de ranking."""
    if isinstance(value, list):
        return [item for item in value if _is_player_row(item)]

    if isinstance(value, dict):
        if _is_player_row(value):
            return [value]

        # Alguns coletores podem representar TOPs como {"1": {...}, "2": {...}}.
        numeric_items: list[tuple[int, Any]] = []
        for key, item in value.items():
            rank_match = re.search(r"\d+", str(key))
            if rank_match and _is_player_row(item):
                numeric_items.append((int(rank_match.group(0)), item))

        if numeric_items:
            numeric_items.sort(key=lambda pair: pair[0])
            rows: list[dict[str, Any]] = []
            for rank, item in numeric_items:
                copied = dict(item)
                if _first_value(copied, POSITION_KEYS) is None:
                    copied["position"] = rank
                rows.append(copied)
            return rows

    return []


def _extract_ranking(tournament: dict[str, Any]) -> list[dict[str, Any]]:
    for key in RANKING_KEYS:
        if key in tournament:
            rows = _rows_from_candidate(tournament[key])
            if rows:
                return rows

    # Segunda tentativa: procura os campos de ranking em objetos aninhados.
    for value in tournament.values():
        if isinstance(value, dict):
            for key in RANKING_KEYS:
                if key in value:
                    rows = _rows_from_candidate(value[key])
                    if rows:
                        return rows

    return []


def _is_epa_player(row: dict[str, Any], player_name: str) -> bool:
    if re.search(r"\[\s*EPA\s*\]", player_name, flags=re.IGNORECASE):
        return True

    explicit_flag = _first_value(
        row,
        ("isEPA", "is_epa", "epaMember", "epa_member", "isClanMember"),
    )
    if explicit_flag is True or str(explicit_flag).strip().casefold() in {
        "true", "1", "yes", "sim"
    }:
        return True

    for key in EPA_TAG_KEYS:
        value = _first_value(row, (key,))
        if value is None:
            continue
        normalized = _normalize(value).replace("[", "").replace("]", "")
        if normalized in {"epa", "embrapa"} or "[epa]" in str(value).casefold():
            return True

    return False


def _clean_player_name(name: str) -> str:
    name = re.sub(r"^\s*\[\s*EPA\s*\]\s*", "", name, flags=re.IGNORECASE)
    return name.strip() or "Jogador desconhecido"


def _format_number(value: Any) -> str:
    numeric = _to_int(value)
    if numeric is None:
        return str(value) if value not in (None, "") else "pontuação indisponível"
    return f"{numeric:,}".replace(",", ".")


def _tournament_name(tournament: dict[str, Any], index: int) -> str:
    value = _first_value(
        tournament,
        ("name", "title", "tournamentName", "tournament_name", "displayName", "nome"),
    )
    return str(value).strip() if value else f"Torneio {index + 1}"


def _epa_top_five(tournament: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []

    for index, row in enumerate(_extract_ranking(tournament), start=1):
        raw_name = _first_value(row, NAME_KEYS)
        if raw_name is None:
            continue

        raw_name = str(raw_name).strip()
        if not _is_epa_player(row, raw_name):
            continue

        raw_position = _first_value(row, POSITION_KEYS)
        position = _to_int(raw_position) or index
        if position < 1 or position > 5:
            continue

        score = _first_value(row, SCORE_KEYS)
        result.append({
            "name": _clean_player_name(raw_name),
            "position": position,
            "score": score,
        })

    result.sort(key=lambda player: player["position"])
    return result


class TournamentCommands:
    def __init__(self, settings: Settings):
        self.api_url = settings.linking_api_url.rstrip("/")
        self.api_key = settings.linking_api_key

    def _fetch_tournaments_sync(self) -> list[dict[str, Any]]:
        request = urllib.request.Request(
            f"{self.api_url}/tournaments",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json",
                "User-Agent": "Embot-Tournaments/1.0",
            },
            method="GET",
        )

        try:
            with urllib.request.urlopen(request, timeout=12) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            if error.code == 401:
                raise RuntimeError(
                    "A API recusou a chave de acesso. Confira se LINKING_API_KEY "
                    "está igual no Embrapa BOT e no Embot."
                ) from error
            raise RuntimeError(f"A API retornou HTTP {error.code}.") from error
        except urllib.error.URLError as error:
            raise RuntimeError(
                "Não foi possível conectar à API do Embrapa BOT. "
                "Confira LINKING_API_URL e se o serviço está online."
            ) from error
        except (TimeoutError, json.JSONDecodeError) as error:
            raise RuntimeError(
                "A API demorou demais para responder ou retornou JSON inválido."
            ) from error

        if not isinstance(payload, dict) or payload.get("success") is not True:
            raise RuntimeError("A API respondeu em um formato inesperado.")

        tournaments = payload.get("tournaments", [])
        if not isinstance(tournaments, list):
            raise RuntimeError("A lista de torneios recebida da API é inválida.")

        return [item for item in tournaments if isinstance(item, dict)]

    async def _fetch_tournaments(self) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._fetch_tournaments_sync)

    def register(self, tree: app_commands.CommandTree) -> None:
        @tree.command(
            name="torneio",
            description="Mostra as posições da EPA nos torneios do Minecraft.",
        )
        @app_commands.guild_only()
        @app_commands.describe(
            resetado=(
                "Ative para formatar a mensagem como anúncio de reset, incluindo premiações."
            )
        )
        async def torneio(
            interaction: discord.Interaction,
            resetado: bool = False,
        ) -> None:
            await interaction.response.defer(thinking=True)

            try:
                tournaments = await self._fetch_tournaments()
            except RuntimeError as error:
                logger.warning("Não foi possível obter os torneios: %s", error)
                await interaction.followup.send(
                    f"❌ {error}",
                    ephemeral=True,
                    allowed_mentions=discord.AllowedMentions.none(),
                )
                return
            except Exception:
                logger.exception("Erro inesperado ao consultar os torneios.")
                await interaction.followup.send(
                    "❌ Ocorreu um erro ao consultar os torneios do Minecraft.",
                    ephemeral=True,
                )
                return

            if not tournaments:
                await interaction.followup.send(
                    "ℹ️ O Embrapa BOT ainda não disponibilizou dados de torneios. "
                    "Verifique se ele já abriu `/torneio` no Minecraft e coletou os rankings.",
                    ephemeral=True,
                )
                return

            embeds: list[discord.Embed] = []
            for index, tournament in enumerate(tournaments):
                name = _tournament_name(tournament, index)
                players = _epa_top_five(tournament)

                if resetado:
                    embed = discord.Embed(
                        title=f"🔄 TORNEIO RESETADO — {name}",
                        color=discord.Color.orange(),
                    )
                    lines = []
                    for player in players:
                        position = player["position"]
                        score = _format_number(player["score"])
                        prize_epa = EPA_PRIZES.get(position)
                        prize_server = SERVER_PRIZES.get(position)
                        line = (
                            f"**{position}º lugar — {player['name']}**\n"
                            f"{score} pontos"
                        )
                        if prize_epa is not None and prize_server is not None:
                            line += (
                                f" · Prêmio EPA: **{_format_number(prize_epa)}**"
                                f" · Prêmio servidor: **{_format_number(prize_server)}**"
                            )
                        lines.append(line)

                    if not lines:
                        lines.append("Nenhum membro da EPA aparece no TOP 5 deste torneio.")
                    embed.description = "\n\n".join(lines)
                    embed.set_footer(text="Valores de premiação configurados para a EPA")
                else:
                    embed = discord.Embed(
                        title=f"🏆 Posições da EPA — {name}",
                        color=discord.Color.blurple(),
                    )
                    if players:
                        embed.description = "\n".join(
                            f"**{player['position']}º lugar** — {player['name']} · "
                            f"{_format_number(player['score'])} pontos"
                            for player in players
                        )
                    else:
                        embed.description = "Nenhum membro da EPA aparece no TOP 5 deste torneio."

                embeds.append(embed)

            # Discord permite no máximo 10 embeds por mensagem.
            for start in range(0, len(embeds), 10):
                chunk = embeds[start:start + 10]
                if start == 0:
                    await interaction.followup.send(
                        embeds=chunk,
                        allowed_mentions=discord.AllowedMentions.none(),
                    )
                else:
                    await interaction.channel.send(
                        embeds=chunk,
                        allowed_mentions=discord.AllowedMentions.none(),
                    )