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
import requests
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

import lavalink
from decorators import ensure_voice
from cogs.comms._trackcont import TrackView
from cogs.comms._card import create_card, shorten_title, resize_and_round
from manage import Error, Success, get_embed_color, format_duration
from cogs.functions import load_emojis

if TYPE_CHECKING:
    from manage import Bot


EMOJIS = load_emojis()


class CloseButton(discord.ui.Button):

    def __init__(self, user_id: int, parent_view: "ResponseView"):
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
                f"Only the user who ran this command can close this.",
                ephemeral=True
            )
            return

        await interaction.response.defer()
        try:
            if self.parent_view.message:
                await self.parent_view.message.delete()
        except Exception as e:
            logging.error(f"Failed to delete message: {e}")


class ResponseView(discord.ui.LayoutView):


    def __init__(self, message: str, user_id: int):
        super().__init__()
        self.message = None

        container = discord.ui.Container(
            discord.ui.Section(
                discord.ui.TextDisplay(content=message),
                accessory=CloseButton(user_id, self),
            ),
        )
        self.add_item(container)


class ResetCommand(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot: Bot = bot

    def _create_card_file(self, track, requester_id: int) -> io.BytesIO | None:

        if not hasattr(track, 'artwork_url') or not track.artwork_url:
            return None

        try:

            bytes_content = requests.get(track.artwork_url).content
            if not bytes_content:
                return None


            rounded_bytes = resize_and_round(bytes_content)


            result_bytes = create_card(
                image_bytes=rounded_bytes,
                background_path="data/background.png",
                heading=shorten_title(f"{track.title}"),
                author=track.author,
                player=f"User #{requester_id}" if requester_id else "Unknown",
                time_text=format_duration(int(track.duration)) if track.duration else "LIVE"
            )

            return io.BytesIO(result_bytes)

        except Exception as e:
            logging.error(f"Error creating card file for {track.title}: {e}")
            return None

    @app_commands.command(name="reset", description="Reset the Music Player View.")
    async def reset(self, interaction: discord.Interaction):
        await interaction.response.defer()
        player = self.bot.get_player(interaction.guild.id)
        msg = await self.handle_reset_action(
            interaction, interaction.guild, interaction.user, player
        )


        view = ResponseView(msg.message if isinstance(msg, (Error, Success)) else msg, interaction.user.id)
        message = await interaction.followup.send(view=view, ephemeral=True)
        view.message = message

    async def handle_reset_action(
        self,
        interaction: discord.Interaction | commands.Context,
        guild: discord.Guild,
        user: discord.User | discord.Member,
        player: lavalink.DefaultPlayer | None,
    ) -> str:
        if not guild.voice_client:
            return Error(f"{EMOJIS.get('failure', '')} I'm not connected to any voice channel.")

        if not player or not player.current:
            return Error(f"{EMOJIS.get('alert', '')} No track is currently playing.")

        try:

            channel_id = self.bot.player_channels.get(guild.id)
            if not channel_id:
                return Error(f"{EMOJIS.get('failure', '')} Could not find the original channel.")

            channel = guild.get_channel(channel_id)
            if not channel:
                return Error(f"{EMOJIS.get('failure', '')} The original channel is no longer available.")


            if hasattr(self.bot, 'player_views') and guild.id in self.bot.player_views:
                old_view = self.bot.player_views[guild.id]
                if hasattr(old_view, 'message') and old_view.message:
                    try:
                        await old_view.message.delete()
                    except Exception:
                        pass


            requester_id = self.bot.player_info.get(guild.id, {}).get("user_id", 0)
            track_data = {
                "name": player.current.title,
                "author": player.current.author,
                "uri": player.current.uri,
                "requested_by": f"User #{requester_id}" if requester_id else "Unknown",
                "current_duration": "00:00",
                "total_duration": "00:00",
                "current_volume": getattr(player, 'volume', 100),
                "position_ms": player.position,
                "duration_ms": int(player.current.duration) if player.current.duration else 0,
            }

            image = self._create_card_file(player.current, requester_id)
            card_file = discord.File(image, filename="card.png") if image else None

            view = TrackView(self.bot, player, guild.owner, track_data, image if card_file else None)

            if card_file:
                message = await channel.send(view=view, file=card_file)
            else:
                message = await channel.send(view=view)

            view.message = message


            self.bot.player_views[guild.id] = view
            if view.update_task:
                view.update_task.cancel()
            view.update_task = asyncio.create_task(view.start_update_loop())

            return Success(f"{EMOJIS.get('success', '')} Player container has been reset.")
        except Exception as e:
            logging.error(f"Reset error: {e}")
            return Error(f"{EMOJIS.get('failure', '')} Failed to reset the player container.")


async def setup(bot: commands.Bot):
    await bot.add_cog(ResetCommand(bot))
