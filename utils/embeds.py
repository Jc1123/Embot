import discord


def giveaway_embed(
    title: str,
    description: str,
    organizer_id: int,
    participants: int,
    footer: str,
    color: discord.Color,
) -> discord.Embed:

    embed = discord.Embed(
        title=title,
        description=description,
        color=color
    )

    embed.add_field(
        name="",
        value=(
            f"Organizado por: "
            f"<@{organizer_id}>\n"
            f"Número de participantes: "
            f"{participants}\n"
            "Terminará em breve..."
        ),
        inline=False
    )

    embed.set_footer(
        text=footer
    )

    return embed