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
import json
import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

import lavalink
from decorators import ensure_voice
from cogs.functions import load_emojis
from manage import Error, Success, get_embed_color

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


class DisconnectCommand(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot: Bot = bot

    @app_commands.command(name="disconnect", description="Disconnect the bot from your voice channel.")
    async def disconnect(self, interaction: discord.Interaction):
        await interaction.response.defer()
        player = self.bot.get_player(interaction.guild.id)
        msg = await self.handle_disconnect_action(
            interaction, interaction.guild, interaction.user, player
        )


        view = ResponseView(msg.message, interaction.user.id)
        message = await interaction.followup.send(view=view, ephemeral=True)
        view.message = message

    async def handle_disconnect_action(
        self,
        interaction: discord.Interaction | commands.Context,
        guild: discord.Guild,
        user: discord.User | discord.Member,
        player: lavalink.DefaultPlayer | None,
    ) -> str:
        if not guild.voice_client:
            return Error(f"{EMOJIS.get('failure', '')} I'm not connected to any voice channel.")
        try:
            self.bot.set_latest_action(f"Disconnected by {user.display_name}")
            active_player = player or self.bot.get_player(guild.id)
            if active_player:
                active_player.queue.clear()
                await active_player.stop()
            await guild.voice_client.disconnect(force=True)

        except Exception as e:
            import logging
            logging.error(f"Disconnect error: {e}")
            return Error(f"{EMOJIS.get('failure', '')} Failed to disconnect the player.")

        return Success(f"{EMOJIS.get('success', '')} Disconnected the player.")


async def setup(bot: commands.Bot):
    await bot.add_cog(DisconnectCommand(bot))
