#!/usr/bin/env python3
"""UA Arena Discord bot.

Creates welcome, announcements, title roles, and one discussion
thread per anime or manga title. Consensus 50s are pulled from
unionarenadecklists.com/discord/board.json (or a local board.json).

  pip install -r requirements-bot.txt
  export DISCORD_TOKEN=...
  python3 scripts/discord_bot.py

Dry run without a token:

  python3 scripts/discord_bot.py --dump --theme yyh
  python3 scripts/discord_bot.py --dump --live
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

import discord_board  # noqa: E402
import uadb  # noqa: E402

INFO_CATEGORY = "Information"
DECK_CATEGORY = "Deck Discussion"
WELCOME_CHANNEL = "welcome"
ANNOUNCE_CHANNEL = "announcements"
ROLES_CHANNEL = "roles"
GENERAL_CHANNEL = "general"
TITLE_CHANNEL = "title-threads"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="UA Arena Discord bot")
    parser.add_argument("--dump", action="store_true", help="Print consensus text and exit")
    parser.add_argument("--theme", default="", help="Limit dump/post to one theme (yyh, solo leveling, ...)")
    parser.add_argument("--live", action="store_true", help="Pull board.json from the live website")
    parser.add_argument("--source", default="", help="Board JSON path or URL")
    parser.add_argument("--token", default="", help="Bot token (else DISCORD_TOKEN)")
    parser.add_argument("--guild", default="", help="Guild id (else DISCORD_GUILD_ID)")
    return parser.parse_args(argv)


def load_board(args: argparse.Namespace) -> dict:
    prefer = "live" if args.live else "local"
    if not args.source and not args.dump:
        prefer = "live"
    return discord_board.fetch_board(args.source or None, prefer=prefer)


def channel_name(slug: str) -> str:
    name = uadb.slugify(slug)[:100]
    return name or "title"


def embed_from_payload(payload: dict):
    import discord

    embed = discord.Embed(
        title=payload.get("title") or "Deck",
        url=payload.get("url") or None,
        description=payload.get("description") or None,
        color=payload.get("color") or 0x5865F2,
    )
    thumb = (payload.get("thumbnail") or {}).get("url")
    if thumb:
        embed.set_thumbnail(url=thumb)
    for field in payload.get("fields") or []:
        embed.add_field(name=field.get("name") or "Cards", value=field.get("value") or "-", inline=False)
    footer = (payload.get("footer") or {}).get("text")
    if footer:
        embed.set_footer(text=footer)
    return embed


def marker_of(deck: dict) -> str:
    return f"{discord_board.MARKER_PREFIX}{deck.get('key') or ''}"


async def get_or_create_category(guild, name: str):
    for cat in guild.categories:
        if cat.name.lower() == name.lower():
            return cat
    return await guild.create_category(name)


async def get_or_create_text(guild, name: str, category, topic: str = ""):
    want = channel_name(name)
    for ch in guild.text_channels:
        if ch.name == want:
            if category and ch.category_id != category.id:
                await ch.edit(category=category, topic=topic or ch.topic)
            elif topic and ch.topic != topic:
                await ch.edit(topic=topic)
            return ch
    return await guild.create_text_channel(want, category=category, topic=topic or None)


async def find_marked_message(channel, marker: str):
    async for message in channel.history(limit=200):
        if message.author != channel.guild.me:
            continue
        if marker in (message.content or ""):
            return message
        for embed in message.embeds:
            footer = (embed.footer.text or "") if embed.footer else ""
            if marker in footer:
                return message
    return None


async def upsert_text(channel, marker: str, content: str):
    existing = await find_marked_message(channel, marker)
    body = content if marker in content else f"{content}\n\n`{marker}`"
    if len(body) > discord_board.MESSAGE_LIMIT:
        body = body[: discord_board.MESSAGE_LIMIT - 20] + "\n…"
    if existing:
        if existing.content != body:
            await existing.edit(content=body)
        return existing
    return await channel.send(content=body)


async def upsert_embed(channel, deck: dict, board: dict):
    import discord

    marker = marker_of(deck)
    payload = discord_board.format_consensus_embed(deck, board.get("site"))
    embed = embed_from_payload(payload)
    existing = await find_marked_message(channel, marker)
    if existing:
        await existing.edit(content=None, embed=embed)
        return existing
    return await channel.send(embed=embed)


async def sync_title_roles(guild, board: dict) -> None:
    import discord

    existing = {role.name: role for role in guild.roles}
    for row in discord_board.title_roles(board):
        name = (row.get("name") or "")[:100]
        if not name:
            continue
        color_name = (row.get("color") or "").split(";")[0].split("/")[0].strip().lower()
        color = discord.Color(discord_board.COLOR_INT.get(color_name, 0x5865F2))
        current = existing.get(name)
        if current is None:
            created = await guild.create_role(
                name=name,
                colour=color,
                mentionable=True,
                reason="UA Arena title role",
            )
            existing[name] = created
            await asyncio.sleep(0.3)
            continue
        kwargs = {}
        if not current.mentionable:
            kwargs["mentionable"] = True
        if current.colour.value != color.value and current.is_assignable():
            kwargs["colour"] = color
        if kwargs and current.is_assignable():
            await current.edit(**kwargs, reason="UA Arena title role")


async def setup_guild(guild, board: dict, theme_query: str = "") -> None:
    info = await get_or_create_category(guild, INFO_CATEGORY)
    decks_cat = await get_or_create_category(guild, DECK_CATEGORY)
    welcome = await get_or_create_text(guild, WELCOME_CHANNEL, info, "Start here")
    announce = await get_or_create_text(guild, ANNOUNCE_CHANNEL, info, "Format notes and consensus updates")
    roles = await get_or_create_text(guild, ROLES_CHANNEL, info, "One role per anime or manga title")
    await get_or_create_text(guild, GENERAL_CHANNEL, info, "Table talk")
    titles = await get_or_create_text(
        guild, TITLE_CHANNEL, decks_cat, "One thread per anime or manga title"
    )

    await upsert_text(welcome, "ua-welcome", discord_board.format_welcome_text(board))
    await upsert_text(announce, "ua-announcements", discord_board.format_announcements_text(board))
    await upsert_text(roles, "ua-roles", discord_board.format_roles_text(board))
    await sync_title_roles(guild, board)

    themes = board.get("themes") or []
    if theme_query:
        matched = discord_board.resolve_theme(theme_query, themes)
        themes = [matched] if matched else []
        if not themes:
            raise SystemExit(f"No theme matched {theme_query!r}")

    index_lines = ["**Title threads**", "One thread per anime or manga. Consensus 50s from the website.", ""]
    for theme in board.get("themes") or []:
        index_lines.append(f"• **{theme.get('name')}** — {int(theme.get('deck_count') or 0)} lists")
    await upsert_text(titles, "ua-title-index", "\n".join(index_lines))

    for theme in themes:
        intro = discord_board.format_theme_intro(theme, board)
        seed = await upsert_text(titles, f"ua-theme:{theme['slug']}", intro)
        thread = seed.thread
        want_name = (theme.get("name") or theme.get("slug") or "title")[:100]
        if thread is None:
            try:
                thread = await seed.create_thread(name=want_name, auto_archive_duration=10080)
            except Exception:
                thread = None
        elif thread.name != want_name:
            try:
                await thread.edit(name=want_name)
            except Exception:
                pass
        if thread is not None:
            if getattr(thread, "archived", False):
                try:
                    await thread.edit(archived=False)
                except Exception:
                    pass
            for deck in theme.get("decks") or []:
                await upsert_embed(thread, deck, board)
                await asyncio.sleep(0.4)


def run_bot(args: argparse.Namespace, board: dict) -> None:
    try:
        import discord
        from discord import app_commands
    except ImportError as exc:
        raise SystemExit("Install Discord.py first: pip install -r requirements-bot.txt") from exc

    token = args.token or os.environ.get("DISCORD_TOKEN") or ""
    if not token:
        raise SystemExit("Set DISCORD_TOKEN or pass --token")
    guild_id = args.guild or os.environ.get("DISCORD_GUILD_ID") or ""

    intents = discord.Intents.default()
    intents.guilds = True
    intents.members = True

    client = discord.Client(intents=intents)
    tree = app_commands.CommandTree(client)

    def current_board() -> dict:
        return load_board(args)

    @tree.command(name="setup", description="Create welcome, roles, and one thread per anime title")
    @app_commands.default_permissions(manage_guild=True)
    async def setup_cmd(interaction: discord.Interaction, theme: str = ""):
        await interaction.response.defer(ephemeral=True)
        live = current_board()
        await setup_guild(interaction.guild, live, theme)
        await interaction.followup.send("UA Arena rooms are up. Title threads and roles posted.", ephemeral=True)

    @tree.command(name="refresh", description="Pull latest consensus 50s from the website")
    @app_commands.default_permissions(manage_guild=True)
    async def refresh_cmd(interaction: discord.Interaction, theme: str = ""):
        await interaction.response.defer(ephemeral=True)
        live = discord_board.fetch_board(prefer="live")
        await setup_guild(interaction.guild, live, theme)
        await interaction.followup.send("Pulled consensus lists from the website.", ephemeral=True)

    @tree.command(name="consensus", description="Post the consensus 50s for a title (yyh, solo leveling, ...)")
    async def consensus_cmd(interaction: discord.Interaction, theme: str):
        live = current_board()
        matched = discord_board.resolve_theme(theme, live.get("themes") or [])
        if not matched:
            await interaction.response.send_message(f"No title matched `{theme}`.", ephemeral=True)
            return
        await interaction.response.defer()
        await interaction.followup.send(discord_board.format_theme_intro(matched, live)[:1900])
        for deck in matched.get("decks") or []:
            payload = discord_board.format_consensus_embed(deck, live.get("site"))
            await interaction.followup.send(embed=embed_from_payload(payload))

    @tree.command(name="themes", description="List anime and manga title threads")
    async def themes_cmd(interaction: discord.Interaction):
        live = current_board()
        lines = [
            f"{t['name']} — {t['deck_count']} lists (#{t['slug']})"
            for t in live.get("themes") or []
        ]
        text = "\n".join(lines) or "No titles on the board yet."
        await interaction.response.send_message(text[:1900], ephemeral=True)

    @tree.command(name="roles", description="List title roles (one per anime or manga)")
    async def roles_cmd(interaction: discord.Interaction):
        live = current_board()
        await interaction.response.send_message(discord_board.format_roles_text(live)[:1900], ephemeral=True)

    @client.event
    async def on_ready():
        uadb.log("discord bot", client.user)
        if guild_id:
            guild = discord.Object(id=int(guild_id))
            tree.copy_global_to(guild=guild)
            await tree.sync(guild=guild)
        else:
            await tree.sync()
        if os.environ.get("DISCORD_AUTO_SETUP") == "1":
            live = current_board()
            for guild in client.guilds:
                if guild_id and str(guild.id) != str(guild_id):
                    continue
                await setup_guild(guild, live, args.theme)

    @client.event
    async def on_member_join(member: discord.Member):
        channel = discord.utils.get(member.guild.text_channels, name=WELCOME_CHANNEL)
        if channel is None:
            return
        await channel.send(
            f"Welcome {member.mention}. Read #announcements, grab a title role in #roles, then hop that title thread."
        )

    client.run(token)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    board = load_board(args)
    if args.dump:
        print(discord_board.dump_theme(board, args.theme or None))
        return
    run_bot(args, board)


if __name__ == "__main__":
    main()
