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
import logging
from typing import TYPE_CHECKING

import discord
from discord.ext import commands, tasks

if TYPE_CHECKING:
    from manage import Bot

logger = logging.getLogger(__name__)


class AutoDisconnect(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot: Bot = bot
        self.idle_timers: dict[int, float] = {}  
        self.auto_disconnect_task.start()

    def cog_unload(self):
        self.auto_disconnect_task.cancel()

    @tasks.loop(minutes=1)
    async def auto_disconnect_task(self):
        try:
            if not self.bot.lavalink:
                return

            for guild in self.bot.guilds:
                try:
                    voice_client = guild.voice_client

                    if not voice_client:
                        self.idle_timers.pop(guild.id, None)
                        continue

                    channel = voice_client.channel
                    if not channel:
                        continue

                    user_count = sum(1 for member in channel.members if not member.bot)

                    player = self.bot.get_player(guild.id)

                    if user_count == 0:
                        if player and player.is_playing:
                            if guild.id not in self.idle_timers:
                                self.idle_timers[guild.id] = asyncio.get_event_loop().time()
                            else:
                                elapsed_time = asyncio.get_event_loop().time() - self.idle_timers[guild.id]

                                if elapsed_time >= 300:  

                                    try:
                                        if player and player.queue:
                                            player.queue.clear()

                                        await voice_client.disconnect()
                                        self.idle_timers.pop(guild.id, None)
                                    except Exception as e:
                                        logger.error(f"[{guild.name}] Error disconnecting: {e}")
                        else:
                            try:
                                if player and player.queue:
                                    player.queue.clear()

                                await voice_client.disconnect()
                                self.idle_timers.pop(guild.id, None)
                            except Exception as e:
                                logger.error(f"[{guild.name}] Error disconnecting: {e}")

                    else:
                        if guild.id in self.idle_timers:
                            self.idle_timers.pop(guild.id)

                except Exception as e:
                    logger.error(f"[{guild.name}] Error checking voice channel: {e}")

        except Exception as e:
            logger.error(f"Error in auto_disconnect_task: {e}", exc_info=True)

    @auto_disconnect_task.before_loop
    async def before_auto_disconnect(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(AutoDisconnect(bot))
