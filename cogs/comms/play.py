# Copyright 2026 Pravanjan Roy (kingmon6996)
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

import asyncio
import io
import logging
import os
import re
import requests
from collections import defaultdict
from typing import TYPE_CHECKING, cast

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from PIL import Image

import lavalink
from decorators import debounce_action, ensure_voice
from manage import EnvironmentKeys, LavalinkVoiceClient, Error, Success, get_embed_color
from cogs.functions import load_emojis
from lavalink import LoadType

if TYPE_CHECKING:
    from manage import Bot
load_dotenv()
EMOJIS = load_emojis()
URL_RX = re.compile(r"https?://(?:www\.)?.+")


async def download_artwork(artwork_url: str | None) -> io.BytesIO | None:

    if not artwork_url:
        return None

    try:
        response = requests.get(artwork_url, timeout=5)
        response.raise_for_status()


        img = Image.open(io.BytesIO(response.content))
        img = img.resize((480, 300), Image.Resampling.LANCZOS)


        output = io.BytesIO()
        img.save(output, format="PNG")
        output.seek(0)
        return output
    except Exception as e:
        logging.error(f"Failed to download/resize artwork: {e}")
        return None


class CloseButton(discord.ui.Button):

    def __init__(self, user_id: int, parent_view: "PlayResponseView"):
        super().__init__(
            style=discord.ButtonStyle.secondary,
            emoji=EMOJIS.get("delete"),
            custom_id=f"close_{user_id}",
        )
        self.user_id = user_id
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                f"Only the user who played the song can close this.",
                ephemeral=True
            )
            return

        await interaction.response.defer()
        try:
            if self.parent_view.message:
                await self.parent_view.message.delete()
        except Exception as e:
            logging.error(f"Failed to delete message: {e}")


class PlayResponseView(discord.ui.LayoutView):


    def __init__(self, track: lavalink.AudioTrack, user_id: int, artwork_bytes: io.BytesIO | None = None):
        super().__init__()
        self.message = None


        section = discord.ui.Section(
            discord.ui.TextDisplay(
                content=f"## {EMOJIS.get('success', '')} Added [{track.title}]({track.uri})"
            ),
            discord.ui.TextDisplay(content=f"**Author :** *{track.author}*"),
            accessory=CloseButton(user_id, self),
        )


        container_with_separator = discord.ui.Container(
            section,
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
        )


        if artwork_bytes:
            container_full = discord.ui.Container(
                section,
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                discord.ui.MediaGallery(
                    discord.MediaGalleryItem(
                        media="attachment://artwork.png",
                    ),
                ),
            )
            self.add_item(container_full)
        else:
            self.add_item(container_with_separator)


class ResponseView(discord.ui.LayoutView):

    def __init__(self, message: str, user_id: int):
        super().__init__()
        self.message = None


        close_button = discord.ui.Button(
            style=discord.ButtonStyle.secondary,
            emoji=EMOJIS.get("delete"),
            custom_id=f"close_{user_id}",
        )

        async def close_callback(interaction: discord.Interaction):
            if interaction.user.id != user_id:
                await interaction.response.send_message(
                    f"Only the user who ran this command can close this.",
                    ephemeral=True
                )
                return

            await interaction.response.defer()
            try:
                if self.message:
                    await self.message.delete()
            except Exception as e:
                logging.error(f"Failed to delete message: {e}")

        close_button.callback = close_callback

        container = discord.ui.Container(
            discord.ui.Section(
                discord.ui.TextDisplay(content=message),
                accessory=close_button,
            ),
        )
        self.add_item(container)


class PlayCommand(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot: Bot = bot
        self._action_locks: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._last_autocomplete: dict[int, float] = {}  

    async def voice_precheck(self, user: discord.User, guild: discord.Guild) -> str | None:
        if not user.voice or not user.voice.channel:
            return "You must be in a voice channel to use this command."
        return None

    async def _release_lock_after(self, lock: asyncio.Lock, delay: float):
        await asyncio.sleep(delay)
        lock.release()

    async def query_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        if not current or len(current) < 2:
            return []

        user_id = interaction.user.id
        current_time = asyncio.get_event_loop().time()


        if user_id in self._last_autocomplete:
            time_since_last = current_time - self._last_autocomplete[user_id]
            if time_since_last < 2.0:
                return []


        self._last_autocomplete[user_id] = current_time

        try:
            query = current.strip("<>")
            if not URL_RX.match(query):
                query = f"ytsearch:{query}"


            results = await asyncio.wait_for(
                self.bot.lavalink.get_tracks(query), 
                timeout=2.0
            )
            if not results or not results.tracks:
                return []


            choices = []
            for track in results.tracks[:25]:
                choice_name = f"{track.title}"

                if len(choice_name) > 100:
                    choice_name = choice_name[:97] + "..."
                choices.append(app_commands.Choice(name=choice_name, value=track.uri))

            return choices
        except asyncio.TimeoutError:
            logging.warning("Autocomplete search timed out")
            return []
        except Exception as e:
            logging.error(f"Autocomplete search failed: {e}")
            return []

    @app_commands.command(name="play", description="Play a song or a playlist with the name or URL.")
    @app_commands.autocomplete(query=query_autocomplete)
    async def play(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()
        player = self.bot.get_player(interaction.guild.id)
        result = await self.handle_play_action(
            interaction, interaction.guild, interaction.user, player, query
        )


        if isinstance(result, dict) and "track" in result:
            track = result["track"]

            artwork_bytes = await download_artwork(track.artwork_url)
            artwork_file = None

            if artwork_bytes:
                artwork_file = discord.File(artwork_bytes, filename="artwork.png")


            view = PlayResponseView(track, interaction.user.id, artwork_bytes)
            if artwork_file:
                message = await interaction.followup.send(view=view, file=artwork_file, ephemeral=True)
            else:
                message = await interaction.followup.send(view=view, ephemeral=True)


            view.message = message
        else:

            if isinstance(result, str):
                msg = result
            elif isinstance(result, (Error, Success)):
                msg = result.message
            elif isinstance(result, dict):
                msg = result.get("message", str(result))
            else:
                msg = str(result)


            view = ResponseView(msg, interaction.user.id)
            message = await interaction.followup.send(view=view, ephemeral=True)
            view.message = message

    @ensure_voice
    @debounce_action(delay=0.1)
    async def handle_play_action(
        self,
        interaction: discord.Interaction,
        guild: discord.Guild,
        user: discord.User,
        player: lavalink.DefaultPlayer | None,
        query: str,
    ) -> str | dict:
        if not guild.voice_client:
            try:
                await user.voice.channel.connect(cls=LavalinkVoiceClient)
                await asyncio.sleep(0.5)
            except Exception as e:
                logging.error("Voice connection failed: %s", e)
                return Error(f"{EMOJIS.get('failure', '')} Could not join your voice channel.")

        if not self.bot.lavalink:
            return Error("Lavalink client is not initialized.")

        player = self.bot.get_player(guild.id) or cast(
            lavalink.DefaultPlayer, self.bot.lavalink.player_manager.create(guild.id)
        )

        if not hasattr(player, '_volume_initialized'):
            try:
                default_volume = int(os.getenv(EnvironmentKeys.BOT_VOLUME, "50"))
                await player.set_volume(default_volume)
                player._volume_initialized = True
            except (ValueError, Exception) as e:
                logging.error(f"Failed to set default volume: {e}")


        self.bot.player_channels[guild.id] = interaction.channel.id
        self.bot.player_info[guild.id] = {
            "channel_id": interaction.channel.id,
            "user_id": interaction.user.id,
        }

        query = query.strip("<>")

        if query.startswith("http"):
            try:
                results = await self.bot.lavalink.get_tracks(query)
            except Exception as e:
                logging.error("Search failed: %s", e)
                return Error(f"{EMOJIS.get('failure', '')} Could not fetch that track.")
        else:

            if not URL_RX.match(query):
                query = f"ytsearch:{query}"

            try:
                results = await self.bot.lavalink.get_tracks(query)
            except Exception as e:
                logging.error("Search failed: %s", e)
                return Error(f"{EMOJIS.get('failure', '')} Could not search for that track.")

        if not results or not results.tracks:
            return Error(f"{EMOJIS.get('failure', '')} No results found for that query.")


        MAX_QUEUE_SIZE = 100

        if results.load_type == LoadType.PLAYLIST:

            current_queue_size = len(player.queue)
            available_slots = MAX_QUEUE_SIZE - current_queue_size

            if available_slots <= 0:
                return Error(f"{EMOJIS.get('failure', '')} Queue is full (max {MAX_QUEUE_SIZE} tracks). Remove some tracks to add more.")


            tracks_added = 0
            for track in results.tracks:
                if tracks_added >= available_slots:
                    break
                player.add(track, requester=user.id)

                self.bot.track_requesters[guild.id][track.uri].append(user.id)
                tracks_added += 1

            playlist_name = getattr(results.playlist_info, "name", "playlist")
            playlist_url = getattr(results.playlist_info, "selected_track", query)
            total_tracks = len(results.tracks)
            skipped = total_tracks - tracks_added

            msg = f"Added **{tracks_added}/{total_tracks}** tracks from **[{playlist_name}]({query})**"
            if skipped > 0:
                msg += f" (skipped {skipped} - queue limit reached)"
            msg += "."


            if not player.is_playing:
                try:
                    await player.play()
                except Exception as e:
                    logging.error(f"Failed to play playlist: {e}")

            return Success(f"{EMOJIS.get('success', '')} {msg}")
        else:

            if len(player.queue) >= MAX_QUEUE_SIZE:
                return Error(f"{EMOJIS.get('failure', '')} Queue is full (max {MAX_QUEUE_SIZE} tracks). Remove some tracks to add more.")

            track = results.tracks[0]
            player.add(track, requester=user.id)

            self.bot.track_requesters[guild.id][track.uri].append(user.id)

            if not player.is_playing:

                retry_count = 0
                max_retries = 3
                while retry_count < max_retries:
                    try:
                        await player.play()
                        break
                    except lavalink.errors.ClientError as e:
                        if "session ID" in str(e):
                            retry_count += 1
                            if retry_count < max_retries:
                                await asyncio.sleep(0.3)
                            else:
                                logging.error(f"Failed to play track after {max_retries} retries: {e}")
                                return Error(f"{EMOJIS.get('failure', '')} Failed to start playback. Try again.")
                        else:
                            raise

            return {
                "track": track,
                "message": (
                    f"{EMOJIS.get('success', '')} Added **[{track.title}]({track.uri})** "
                    "to the queue."
                ),
            }


async def setup(bot: commands.Bot):
    await bot.add_cog(PlayCommand(bot))
