#!/usr/bin/env python3
"""UA Arena Discord bot.

Creates welcome, announcements, title roles, and one discussion
channel per anime or manga title. Consensus 50s are pulled from
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
ROLE_SELECT_ID = "ua-title-role-select"


def _title_role_options(roles: list) -> list:
    import discord

    options = []
    for role in roles[:25]:
        if role is None:
            continue
        options.append(
            discord.SelectOption(
                label=(role.name or "Title")[:100],
                value=str(role.id),
                description="Flair next to your name",
            )
        )
    if not options:
        options.append(discord.SelectOption(label="Title flair", value="0"))
    return options


def make_title_role_view(roles: list | None = None):
    import discord

    class TitleRoleSelect(discord.ui.Select):
        def __init__(self, role_list: list):
            opts = _title_role_options(role_list)
            super().__init__(
                custom_id=ROLE_SELECT_ID,
                placeholder="Pick your title flair",
                min_values=0,
                max_values=min(25, len(opts)),
                options=opts,
            )

        async def callback(self, interaction: discord.Interaction):
            await apply_title_flair(interaction)

    class TitleRoleView(discord.ui.View):
        def __init__(self, role_list: list | None = None):
            super().__init__(timeout=None)
            self.add_item(TitleRoleSelect(role_list or []))

    return TitleRoleView(roles or [])


async def apply_title_flair(interaction) -> None:
    import discord

    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message("Use this in the server.", ephemeral=True)
        return
    member = interaction.user
    if not isinstance(member, discord.Member):
        member = await guild.fetch_member(interaction.user.id)
    try:
        live = discord_board.fetch_board(prefer="live")
    except Exception:
        live = discord_board.fetch_board(prefer="local")
    names = {(row.get("name") or "")[:100] for row in discord_board.title_roles(live)}
    names.discard("")
    title_roles = [role for role in guild.roles if role.name in names]
    raw = []
    if interaction.data:
        raw = interaction.data.get("values") or []
    wanted = {int(v) for v in raw if str(v).isdigit() and str(v) != "0"}
    add = []
    remove = []
    for role in title_roles:
        has = role in member.roles
        want = role.id in wanted
        if want and not has:
            add.append(role)
        elif has and not want:
            remove.append(role)
    try:
        if add:
            await member.add_roles(*add, reason="UA Arena title flair")
        if remove:
            await member.remove_roles(*remove, reason="UA Arena title flair")
    except discord.Forbidden:
        await interaction.response.send_message(
            "I cannot assign those roles. Server Settings → Roles: drag the bot role **above** Solo Leveling, Yu Yu Hakusho, and the other title roles.",
            ephemeral=True,
        )
        return
    picked = [role.name for role in title_roles if role.id in wanted] or ["none"]
    await interaction.response.send_message("Title flair: " + ", ".join(picked), ephemeral=True)


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


def _markers_in_text(blob: str) -> list[str]:
    found = []
    for part in (blob or "").replace("`", " ").split():
        if part.startswith("ua-"):
            found.append(part)
    return found


def _markers_in_message(message) -> list[str]:
    found = _markers_in_text(message.content or "")
    for embed in message.embeds:
        footer = (embed.footer.text or "") if embed.footer else ""
        found.extend(_markers_in_text(footer))
        found.extend(_markers_in_text(embed.description or ""))
    return found


async def load_marked_messages(channel) -> dict:
    found = {}
    try:
        async for message in channel.history(limit=100):
            if message.author != channel.guild.me:
                continue
            for marker in _markers_in_message(message):
                found[marker] = message
    except Exception as exc:
        uadb.log("history skip", getattr(channel, "name", channel), exc)
    return found


async def upsert_text(channel, marker: str, content: str, marked: dict | None = None):
    cache = marked if marked is not None else await load_marked_messages(channel)
    existing = cache.get(marker)
    body = content if marker in content else f"{content}\n\n`{marker}`"
    if len(body) > discord_board.MESSAGE_LIMIT:
        body = body[: discord_board.MESSAGE_LIMIT - 20] + "\n…"
    if existing:
        if existing.content != body:
            await existing.edit(content=body)
        return existing
    sent = await channel.send(content=body)
    cache[marker] = sent
    return sent


async def upsert_embed(channel, deck: dict, board: dict, marked: dict | None = None):
    cache = marked if marked is not None else await load_marked_messages(channel)
    marker = marker_of(deck)
    payload = discord_board.format_consensus_embed(deck, board.get("site"))
    embed = embed_from_payload(payload)
    existing = cache.get(marker)
    if existing:
        await existing.edit(content=None, embed=embed)
        return existing
    sent = await channel.send(embed=embed)
    cache[marker] = sent
    return sent


async def sync_title_roles(guild, board: dict) -> list:
    import discord

    existing = {role.name: role for role in guild.roles}
    out = []
    for row in discord_board.title_roles(board):
        name = (row.get("name") or "")[:100]
        if not name:
            continue
        color_name = (row.get("color") or "").split(";")[0].split("/")[0].strip().lower()
        color = discord.Color(discord_board.COLOR_INT.get(color_name, 0x5865F2))
        current = existing.get(name)
        if current is None:
            current = await guild.create_role(
                name=name,
                colour=color,
                mentionable=True,
                hoist=False,
                reason="UA Arena title flair",
            )
            existing[name] = current
            await asyncio.sleep(0.15)
        else:
            kwargs = {}
            if not current.mentionable:
                kwargs["mentionable"] = True
            if current.hoist:
                kwargs["hoist"] = False
            if current.colour.value != color.value and current.is_assignable():
                kwargs["colour"] = color
            if kwargs and current.is_assignable():
                await current.edit(**kwargs, reason="UA Arena title flair")
        out.append(current)
    return out


async def post_role_picker(channel, guild, board: dict, view) -> None:
    body = discord_board.format_roles_text(board)
    if "ua-roles" not in body:
        body = f"{body}\n\n`ua-roles`"
    marked = await load_marked_messages(channel)
    existing = marked.get("ua-roles")
    if existing:
        await existing.edit(content=body, view=view)
        return
    await channel.send(content=body, view=view)


async def setup_guild(guild, board: dict, theme_query: str = "") -> None:
    info = await get_or_create_category(guild, INFO_CATEGORY)
    decks_cat = await get_or_create_category(guild, DECK_CATEGORY)
    welcome = await get_or_create_text(guild, WELCOME_CHANNEL, info, "Start here")
    announce = await get_or_create_text(guild, ANNOUNCE_CHANNEL, info, "Format notes and consensus updates")
    roles = await get_or_create_text(guild, ROLES_CHANNEL, info, "One role per anime or manga title")
    await get_or_create_text(guild, GENERAL_CHANNEL, info, "Table talk")

    role_objs = await sync_title_roles(guild, board)
    await upsert_text(welcome, "ua-welcome", discord_board.format_welcome_text(board))
    await upsert_text(announce, "ua-announcements", discord_board.format_announcements_text(board))
    picker = make_title_role_view(role_objs)
    await post_role_picker(roles, guild, board, picker)

    themes = board.get("themes") or []
    if theme_query:
        matched = discord_board.resolve_theme(theme_query, themes)
        themes = [matched] if matched else []
        if not themes:
            raise ValueError(f"No title matched {theme_query!r}")

    total = len(themes)
    for i, theme in enumerate(themes, start=1):
        name = theme.get("name") or theme.get("slug") or "title"
        slug = theme.get("slug") or channel_name(name)
        uadb.log("setup channel", f"{i}/{total}", f"#{slug}")
        channel = await get_or_create_text(guild, slug, decks_cat, f"{name} lists and talk")
        intro = discord_board.format_theme_intro(theme, board)
        marks = await load_marked_messages(channel)
        await upsert_text(channel, f"ua-theme:{slug}", intro, marks)
        for deck in theme.get("decks") or []:
            await upsert_embed(channel, deck, board, marks)
            await asyncio.sleep(0.12)
        await asyncio.sleep(0.15)


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

    async def _run_setup(interaction: discord.Interaction, live: dict, theme: str, done: str) -> None:
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send(
            "Setup started. It creates a channel per anime title, so give it a few minutes. "
            "Watch the left sidebar under **Deck Discussion** for #solo-leveling, #yu-yu-hakusho, and the rest.",
            ephemeral=True,
        )
        try:
            await setup_guild(interaction.guild, live, theme)
        except Exception as exc:
            uadb.log("setup failed", exc)
            await interaction.followup.send(f"Setup hit an error: {exc}", ephemeral=True)
            return
        await interaction.followup.send(done, ephemeral=True)

    @tree.command(name="setup", description="Create welcome, roles, and one channel per anime title")
    @app_commands.default_permissions(manage_guild=True)
    async def setup_cmd(interaction: discord.Interaction, theme: str = ""):
        await _run_setup(
            interaction,
            current_board(),
            theme,
            "Done. Check #roles and pick your title flair from the menu. Title channels are under Deck Discussion.",
        )

    @tree.command(name="refresh", description="Pull latest consensus 50s from the website")
    @app_commands.default_permissions(manage_guild=True)
    async def refresh_cmd(interaction: discord.Interaction, theme: str = ""):
        await _run_setup(
            interaction,
            discord_board.fetch_board(prefer="live"),
            theme,
            "Pulled consensus lists from the website.",
        )

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

    @tree.command(name="themes", description="List anime and manga title channels")
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
        client.add_view(make_title_role_view())
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
            f"Welcome {member.mention}. Read #announcements, pick title flair in #roles, then hop that title channel."
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
