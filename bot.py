"""
CryptoHack Discord Bot
Tracks CryptoHack users and announces new challenge solves.
"""

import os
import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv
import aiohttp
from typing import Optional
import asyncio

import database as db
from cryptohack_api import fetch_user, UserNotFoundError, CryptoHackAPIError
from image_generator import generate_solve_image

load_dotenv()

# Bot configuration
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL_MINUTES", "10"))

# Bot setup with required intents
intents = discord.Intents.default()
intents.guilds = True


class CryptoHackBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.session: Optional[aiohttp.ClientSession] = None

    async def setup_hook(self):
        """Initialize database and start background tasks."""
        await db.init_db()
        self.session = aiohttp.ClientSession()
        self.check_new_solves.start()
        await self.tree.sync()
        print("Commands synced!")

    async def close(self):
        """Cleanup on shutdown."""
        self.check_new_solves.cancel()
        if self.session:
            await self.session.close()
        await super().close()

    async def on_ready(self):
        print(f"Logged in as {self.user} (ID: {self.user.id})")
        print(f"Checking for new solves every {CHECK_INTERVAL} minutes")
        print("------")

    @tasks.loop(minutes=CHECK_INTERVAL)
    async def check_new_solves(self):
        """Background task to check for new challenge solves."""
        await self.wait_until_ready()

        guild_ids = await db.get_guild_ids()

        for guild_id in guild_ids:
            guild = self.get_guild(guild_id)
            if not guild:
                print(f"[SKIP] Guild {guild_id} not found (bot may have been removed)")
                continue

            tracked_users = await db.get_tracked_users(guild_id)

            for user_data in tracked_users:
                username = user_data["username"]
                try:
                    await self._check_user_solves(guild_id, username)
                except Exception as e:
                    print(f"Error checking solves for {username}: {e}")

                # Rate limiting - wait a bit between API calls
                await asyncio.sleep(1)

            # Announce new solves for this guild
            try:
                await self._announce_new_solves(guild)
            except Exception as e:
                print(f"Error announcing solves for {guild.name}: {e}")

    async def _check_user_solves(self, guild_id: int, username: str):
        """Check for new solves by a specific user."""
        try:
            user = await fetch_user(username, self.session)
        except UserNotFoundError:
            return
        except CryptoHackAPIError:
            return

        existing_solves = await db.get_solved_challenges(guild_id, username)

        for challenge in user.solved_challenges:
            if challenge.name not in existing_solves:
                # Check if this is first blood for the guild
                is_first_blood = await db.check_and_set_first_blood(
                    guild_id, challenge.name, username
                )

                await db.add_solved_challenge(
                    guild_id=guild_id,
                    username=username,
                    challenge_name=challenge.name,
                    category=challenge.category,
                    points=challenge.points,
                    solved_date=challenge.date,
                    first_blood=is_first_blood
                )

    async def _announce_new_solves(self, guild: discord.Guild):
        """Announce new solves in the designated channel."""
        unannounced = await db.get_unannounced_solves(guild.id)
        if not unannounced:
            return

        # Get announcement channel - try multiple methods
        channel_id = await db.get_announcement_channel(guild.id)
        channel = None

        if channel_id:
            try:
                channel = await self.fetch_channel(channel_id)
            except Exception:
                channel = guild.get_channel(channel_id)

        if not channel:
            channel = discord.utils.get(guild.text_channels, name="cryptohack")

        if not channel:
            channel = guild.system_channel

        if not channel:
            # Mark all as announced to avoid infinite retries
            for solve in unannounced:
                await db.mark_challenge_announced(guild.id, solve["cryptohack_username"], solve["challenge_name"])
            return

        # Announce each solve with an image
        for solve in unannounced:
            try:
                # Fetch user data for score
                user_data = await fetch_user(solve["cryptohack_username"], self.session)

                # Count server solvers for this challenge
                server_solvers = await db.get_challenge_solvers(guild.id, solve["challenge_name"])
                server_rank = len(server_solvers)  # Current user is the latest

                # Generate the image
                image_bytes = await generate_solve_image(
                    username=solve["cryptohack_username"],
                    score=user_data.score,
                    challenge_name=solve["challenge_name"],
                    category=solve["challenge_category"],
                    points=solve["challenge_points"],
                    server_rank=server_rank,
                    total_solvers=0,  # We don't have this info easily
                    is_first_blood=solve["first_blood"],
                    session=self.session
                )

                # Send the image
                file = discord.File(image_bytes, filename="solve.png")
                await channel.send(file=file)

                await db.mark_challenge_announced(
                    guild.id, solve["cryptohack_username"], solve["challenge_name"]
                )
            except discord.Forbidden:
                print(f"Cannot send to channel {channel.name} in {guild.name} - marking as announced")
                await db.mark_challenge_announced(
                    guild.id, solve["cryptohack_username"], solve["challenge_name"]
                )
                continue
            except Exception as e:
                print(f"Error announcing solve: {e}")
                # Mark as announced anyway to avoid spam on errors
                await db.mark_challenge_announced(
                    guild.id, solve["cryptohack_username"], solve["challenge_name"]
                )


bot = CryptoHackBot()


# ============= Embed Creators =============

def create_solve_embed(solve: dict, guild_id: int) -> discord.Embed:
    """Create an embed for a new solve announcement."""
    username = solve["cryptohack_username"]
    challenge = solve["challenge_name"]
    category = solve["challenge_category"]
    points = solve["challenge_points"]
    is_first_blood = solve["first_blood"]

    if is_first_blood:
        title = "🩸 First Blood!"
        color = discord.Color.red()
        description = f"**{username}** is the first in the server to solve **{challenge}**!"
    else:
        title = "🎉 Challenge Solved!"
        color = discord.Color.green()
        description = f"**{username}** solved **{challenge}**!"

    embed = discord.Embed(title=title, description=description, color=color)
    embed.add_field(name="Category", value=category, inline=True)
    embed.add_field(name="Points", value=str(points), inline=True)
    embed.set_footer(text="CryptoHack", icon_url="https://cryptohack.org/static/img/favicon.ico")

    return embed


def create_user_embed(user, tracked_users: list[dict]) -> discord.Embed:
    """Create an embed for user profile display."""
    embed = discord.Embed(
        title=f"🔐 {user.username}",
        url=user.profile_url,
        color=discord.Color.blue()
    )

    # Add country flag if available
    if user.country:
        embed.description = f":flag_{user.country}:"

    embed.add_field(name="🏆 Score", value=str(user.score), inline=True)
    embed.add_field(name="📊 Rank", value=f"#{user.rank}", inline=True)
    embed.add_field(name="⭐ Level", value=str(user.level), inline=True)
    embed.add_field(name="🩸 First Bloods", value=str(user.first_bloods), inline=True)
    embed.add_field(name="✅ Challenges Solved", value=str(len(user.solved_challenges)), inline=True)
    embed.add_field(name="📅 Joined", value=user.joined, inline=True)

    embed.set_footer(text="CryptoHack", icon_url="https://cryptohack.org/static/img/favicon.ico")

    return embed


def create_leaderboard_embed(users_data: list[tuple], guild_name: str) -> discord.Embed:
    """Create a leaderboard embed."""
    embed = discord.Embed(
        title=f"🏆 {guild_name} CryptoHack Leaderboard",
        color=discord.Color.gold()
    )

    if not users_data:
        embed.description = "No tracked users yet. Use `/adduser` to add users!"
        return embed

    leaderboard_text = ""
    medals = ["🥇", "🥈", "🥉"]

    for i, (username, score, rank, level, solved_count) in enumerate(users_data):
        medal = medals[i] if i < 3 else f"**{i + 1}.**"
        leaderboard_text += f"{medal} **{username}** - {score} pts (#{rank}, Lvl {level}, {solved_count} solved)\n"

    embed.description = leaderboard_text
    embed.set_footer(text="CryptoHack", icon_url="https://cryptohack.org/static/img/favicon.ico")

    return embed


def create_challenge_embed(challenge_name: str, solvers: list[dict], category: str = None, points: int = None) -> discord.Embed:
    """Create an embed showing who solved a challenge."""
    embed = discord.Embed(
        title=f"📝 {challenge_name}",
        color=discord.Color.purple()
    )

    if category:
        embed.add_field(name="Category", value=category, inline=True)
    if points:
        embed.add_field(name="Points", value=str(points), inline=True)

    if not solvers:
        embed.description = "No one from this server has solved this challenge yet."
    else:
        solver_text = ""
        for i, solver in enumerate(solvers):
            username = solver["cryptohack_username"]
            is_first = solver.get("first_blood", False)
            badge = " 🩸" if is_first else ""
            solver_text += f"**{i + 1}.** {username}{badge} - {solver['solved_date']}\n"

        embed.add_field(name=f"Solvers ({len(solvers)})", value=solver_text, inline=False)

    embed.set_footer(text="CryptoHack", icon_url="https://cryptohack.org/static/img/favicon.ico")

    return embed


# ============= Slash Commands =============

@bot.tree.command(name="adduser", description="Add a CryptoHack user to track")
@app_commands.describe(username="The CryptoHack username to track")
async def add_user(interaction: discord.Interaction, username: str):
    """Add a CryptoHack user to the tracking list."""
    await interaction.response.defer()

    # Verify user exists on CryptoHack
    try:
        user = await fetch_user(username, bot.session)
    except UserNotFoundError:
        await interaction.followup.send(
            f"❌ User `{username}` not found on CryptoHack.",
            ephemeral=True
        )
        return
    except CryptoHackAPIError as e:
        await interaction.followup.send(
            f"❌ Error connecting to CryptoHack: {e}",
            ephemeral=True
        )
        return

    # Add to database
    added = await db.add_user(interaction.guild_id, user.username)

    if added:
        # Fetch and store existing solves (don't announce them)
        for challenge in user.solved_challenges:
            is_first = await db.check_and_set_first_blood(
                interaction.guild_id, challenge.name, user.username
            )
            await db.add_solved_challenge(
                guild_id=interaction.guild_id,
                username=user.username,
                challenge_name=challenge.name,
                category=challenge.category,
                points=challenge.points,
                solved_date=challenge.date,
                first_blood=is_first
            )
            # Mark as announced so we don't spam existing solves
            await db.mark_challenge_announced(
                interaction.guild_id, user.username, challenge.name
            )

        embed = create_user_embed(user, [])
        await interaction.followup.send(
            f"✅ Now tracking **{user.username}**!",
            embed=embed
        )
    else:
        await interaction.followup.send(
            f"ℹ️ User `{user.username}` is already being tracked.",
            ephemeral=True
        )


@bot.tree.command(name="removeuser", description="Remove a CryptoHack user from tracking")
@app_commands.describe(username="The CryptoHack username to stop tracking")
async def remove_user(interaction: discord.Interaction, username: str):
    """Remove a user from the tracking list."""
    removed = await db.remove_user(interaction.guild_id, username)

    if removed:
        await interaction.response.send_message(f"✅ Stopped tracking `{username}`.")
    else:
        await interaction.response.send_message(
            f"❌ User `{username}` is not being tracked.",
            ephemeral=True
        )


@bot.tree.command(name="users", description="List all tracked CryptoHack users")
async def list_users(interaction: discord.Interaction):
    """List all tracked users in the server."""
    await interaction.response.defer()

    tracked = await db.get_tracked_users(interaction.guild_id)

    if not tracked:
        await interaction.followup.send("No users are being tracked. Use `/adduser` to add someone!")
        return

    embed = discord.Embed(
        title="📋 Tracked CryptoHack Users",
        color=discord.Color.blue()
    )

    user_list = "\n".join([f"• {u['username']}" for u in tracked])
    embed.description = user_list
    embed.set_footer(text=f"{len(tracked)} users tracked")

    await interaction.followup.send(embed=embed)


@bot.tree.command(name="leaderboard", description="Show the server's CryptoHack leaderboard")
async def leaderboard(interaction: discord.Interaction):
    """Display the server leaderboard."""
    await interaction.response.defer()

    tracked = await db.get_tracked_users(interaction.guild_id)

    if not tracked:
        await interaction.followup.send("No users are being tracked. Use `/adduser` to add someone!")
        return

    # Fetch current data for all users
    users_data = []
    for user_info in tracked:
        try:
            user = await fetch_user(user_info["username"], bot.session)
            users_data.append((
                user.username,
                user.score,
                user.rank,
                user.level,
                len(user.solved_challenges)
            ))
        except Exception:
            continue
        await asyncio.sleep(0.5)  # Rate limiting

    # Sort by score descending
    users_data.sort(key=lambda x: x[1], reverse=True)

    embed = create_leaderboard_embed(users_data, interaction.guild.name)
    await interaction.followup.send(embed=embed)


@bot.tree.command(name="profile", description="Show a CryptoHack user's profile")
@app_commands.describe(username="The CryptoHack username to look up")
async def profile(interaction: discord.Interaction, username: str):
    """Display a user's CryptoHack profile."""
    await interaction.response.defer()

    try:
        user = await fetch_user(username, bot.session)
    except UserNotFoundError:
        await interaction.followup.send(f"❌ User `{username}` not found on CryptoHack.", ephemeral=True)
        return
    except CryptoHackAPIError as e:
        await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)
        return

    tracked = await db.get_tracked_users(interaction.guild_id)
    embed = create_user_embed(user, tracked)
    await interaction.followup.send(embed=embed)


@bot.tree.command(name="challenge", description="See who solved a specific challenge")
@app_commands.describe(challenge_name="The name of the challenge")
async def challenge(interaction: discord.Interaction, challenge_name: str):
    """Show who in the server solved a specific challenge."""
    await interaction.response.defer()

    solvers = await db.get_challenge_solvers(interaction.guild_id, challenge_name)

    # Try to get challenge details from first solver's data
    category = None
    points = None
    if solvers:
        # Get from database
        async with db.aiosqlite.connect(db.DATABASE_PATH) as conn:
            cursor = await conn.execute(
                "SELECT challenge_category, challenge_points FROM solved_challenges WHERE challenge_name = ? LIMIT 1",
                (challenge_name,)
            )
            row = await cursor.fetchone()
            if row:
                category, points = row

    embed = create_challenge_embed(challenge_name, solvers, category, points)
    await interaction.followup.send(embed=embed)


@bot.tree.command(name="setchannel", description="Set the channel for solve announcements")
@app_commands.describe(channel="The channel for announcements")
@app_commands.default_permissions(manage_channels=True)
async def set_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    """Set the announcement channel."""
    await db.set_announcement_channel(interaction.guild_id, channel.id)
    await interaction.response.send_message(
        f"✅ Solve announcements will now be posted in {channel.mention}"
    )


@bot.tree.command(name="test", description="Test image generation")
async def test_image(interaction: discord.Interaction):
    """Test image generation with assakaf user."""
    await interaction.response.defer()

    try:
        user_data = await fetch_user("assakaf", bot.session)

        image_bytes = await generate_solve_image(
            username="assakaf",
            score=user_data.score,
            challenge_name="Test Challenge",
            category="Introduction",
            points=10,
            server_rank=1,
            total_solvers=0,
            is_first_blood=True,
            session=bot.session
        )

        file = discord.File(image_bytes, filename="test_solve.png")
        await interaction.followup.send("Test image:", file=file)
    except Exception as e:
        await interaction.followup.send(f"Error: {e}")


@bot.tree.command(name="refresh", description="Manually check for new solves")
@app_commands.default_permissions(manage_guild=True)
async def refresh(interaction: discord.Interaction):
    """Manually trigger a check for new solves and post images here."""
    await interaction.response.defer()

    tracked = await db.get_tracked_users(interaction.guild_id)

    if not tracked:
        await interaction.followup.send("No users are being tracked.")
        return

    # Collect new solves
    new_solves_data = []
    for user_data in tracked:
        try:
            user = await fetch_user(user_data["username"], bot.session)
            existing = await db.get_solved_challenges(interaction.guild_id, user_data["username"])

            for challenge in user.solved_challenges:
                if challenge.name not in existing:
                    is_first = await db.check_and_set_first_blood(
                        interaction.guild_id, challenge.name, user_data["username"]
                    )
                    await db.add_solved_challenge(
                        guild_id=interaction.guild_id,
                        username=user_data["username"],
                        challenge_name=challenge.name,
                        category=challenge.category,
                        points=challenge.points,
                        solved_date=challenge.date,
                        first_blood=is_first
                    )
                    new_solves_data.append({
                        "username": user_data["username"],
                        "challenge_name": challenge.name,
                        "category": challenge.category,
                        "points": challenge.points,
                        "first_blood": is_first,
                        "score": user.score
                    })
        except Exception as e:
            print(f"Error checking {user_data['username']}: {e}")
            continue
        await asyncio.sleep(0.5)

    if not new_solves_data:
        await interaction.followup.send("No new solves found.")
        return

    # Send images directly in this channel
    await interaction.followup.send(f"Found {len(new_solves_data)} new solve(s):")

    for solve in new_solves_data:
        try:
            server_solvers = await db.get_challenge_solvers(interaction.guild_id, solve["challenge_name"])
            server_rank = len(server_solvers)

            image_bytes = await generate_solve_image(
                username=solve["username"],
                score=solve["score"],
                challenge_name=solve["challenge_name"],
                category=solve["category"],
                points=solve["points"],
                server_rank=server_rank,
                total_solvers=0,
                is_first_blood=solve["first_blood"],
                session=bot.session
            )

            file = discord.File(image_bytes, filename="solve.png")
            await interaction.channel.send(file=file)

            # Mark as announced
            await db.mark_challenge_announced(
                interaction.guild_id, solve["username"], solve["challenge_name"]
            )
        except Exception as e:
            print(f"Error generating image for {solve['challenge_name']}: {e}")
            await interaction.channel.send(f"Error generating image for {solve['challenge_name']}: {e}")


# ============= Run Bot =============

def main():
    if not DISCORD_TOKEN:
        print("Error: DISCORD_TOKEN not set in .env file")
        print("Please copy .env.example to .env and add your bot token")
        return

    bot.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()
