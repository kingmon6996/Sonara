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

import discord
import logging
from discord.ext import commands
from discord import app_commands

logger = logging.getLogger(__name__)


class PingCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ping", description="Check the bot's latency")
    async def ping(self, interaction: discord.Interaction):
        try:
            latency_ms = round(self.bot.latency * 1000)

            await interaction.response.send_message(f" Pong! Latency: **{latency_ms}ms**")
            logger.info(f"User {interaction.user.id} used ping command (latency: {latency_ms}ms)")
        except Exception as e:
            logger.error(f"Error in ping command: {e}")
            await interaction.response.send_message(f" An error occurred: {str(e)}")


async def setup(bot):
    await bot.add_cog(PingCommand(bot))
