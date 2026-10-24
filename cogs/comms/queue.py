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
import requests
from typing import TYPE_CHECKING, Optional

import discord
from discord import app_commands
from discord.ext import commands

from cogs.functions import load_emojis
from manage import Error, Success, format_duration, get_embed_color
from ._queuecont import QueueLayoutView

if TYPE_CHECKING:
    from manage import Bot

EMOJIS = load_emojis()


class CloseButton(discord.ui.Button):

    def __init__(self, user_id: int, parent_view: "ErrorResponseView"):
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


class ErrorResponseView(discord.ui.LayoutView):


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


class QueueCommand(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot: Bot = bot

    @app_commands.command(name="queue", description="Display the current queue.")
    async def queue(
        self,
        interaction: discord.Interaction,
    ):
        await interaction.response.defer()


        if not interaction.user.voice or not interaction.user.voice.channel:
            view = ErrorResponseView(
                f"You must be in a voice channel to view the queue.",
                interaction.user.id
            )
            message = await interaction.followup.send(view=view, ephemeral=True)
            view.message = message
            return

        player = self.bot.get_player(interaction.guild.id)


        if not player or not player.channel_id or player.channel_id != interaction.user.voice.channel.id:
            view = ErrorResponseView(
                f"I'm not playing music in your voice channel.",
                interaction.user.id
            )
            message = await interaction.followup.send(view=view, ephemeral=True)
            view.message = message
            return

        if not player.queue:
            view = ErrorResponseView(
                f"The queue is empty.",
                interaction.user.id
            )
            message = await interaction.followup.send(view=view, ephemeral=True)
            view.message = message
            return


        view = QueueLayoutView(self.bot, player, page_size=5, user_id=interaction.user.id)
        message = await interaction.followup.send(view=view, ephemeral=True)
        view.message = message
        view.start_disable_timer()                                           


async def setup(bot: commands.Bot):
    await bot.add_cog(QueueCommand(bot))
