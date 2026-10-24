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

import asyncio
import json
import logging
import os
import re
from collections import defaultdict
from typing import cast

import discord
from discord.ext import commands
from dotenv import load_dotenv

import lavalink
from .variable import EnvironmentKeys, LatestActionKeys

load_dotenv()
URL_RX = re.compile(r"https?://(?:www\.)?.+")

original_stats_init = lavalink.stats.Stats.__init__

def patched_stats_init(self, node, data):
    try:
        original_stats_init(self, node, data)
    except (KeyError, AttributeError):
        object.__setattr__(self, 'node', node)

        if 'cpu' in data:
            cpu = data['cpu']
            object.__setattr__(self, 'system_load', cpu.get('systemLoad', 0.0))
            object.__setattr__(self, 'process_load', cpu.get('processLoad', 0.0))
            object.__setattr__(self, 'cores', cpu.get('cores', 1))
            object.__setattr__(self, 'lavalink_load', cpu.get('lavalinkLoad', 0.0))
        else:
            object.__setattr__(self, 'system_load', 0.0)
            object.__setattr__(self, 'process_load', 0.0)
            object.__setattr__(self, 'cores', 1)
            object.__setattr__(self, 'lavalink_load', 0.0)

        if 'memory' in data:
            mem = data['memory']
            object.__setattr__(self, 'allocated', mem.get('allocated', 0))
            object.__setattr__(self, 'used', mem.get('used', 0))
            object.__setattr__(self, 'free', mem.get('free', 0))
            object.__setattr__(self, 'reservable', mem.get('reservable', 0))
        else:
            object.__setattr__(self, 'allocated', 0)
            object.__setattr__(self, 'used', 0)
            object.__setattr__(self, 'free', 0)
            object.__setattr__(self, 'reservable', 0)

        object.__setattr__(self, 'uptime', data.get('uptime', 0))

lavalink.stats.Stats.__init__ = patched_stats_init


class Bot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        logging_level = (
            logging.DEBUG
            if os.getenv(EnvironmentKeys.LOG_LEVEL).lower() == "debug"
            else logging.INFO
        )
        discord.utils.setup_logging(level=logging_level)

        super().__init__(
            command_prefix="!",
            intents=intents,
            partials=["MESSAGE", "REACTION", "USER"],
        )

        self.latest_action: dict | None = None
        self._action_locks: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)
        self.lavalink: lavalink.Client | None = None
        self.player_views: dict[int, any] = {}  
        self.player_channels: dict[int, int] = {}  
        self.player_info: dict[int, dict] = {}  
        self.track_requesters: dict[int, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))

    def set_latest_action(self, action: str, persist: bool = False):
        self.latest_action = {
            LatestActionKeys.TEXT: action,
            LatestActionKeys.PERSIST: persist,
        }

    async def setup_hook(self):
        if self.user is None:
            raise RuntimeError("Bot user unavailable during setup_hook.")

        self.lavalink = lavalink.Client(self.user.id)

        try:
            host = os.getenv(EnvironmentKeys.LAVALINK_HOST)
            port = int(os.getenv(EnvironmentKeys.LAVALINK_PORT, "2333"))
            password = os.getenv(EnvironmentKeys.LAVALINK_PASSWORD)
            region = os.getenv(EnvironmentKeys.LAVALINK_REGION, "us_central")
            secure = os.getenv(EnvironmentKeys.LAVALINK_SECURE, "False").lower() == "true"

            if not host or not password:
                raise RuntimeError("LAVALINK_HOST and LAVALINK_PASSWORD must be set in .env")

            self.lavalink.add_node(
                host=host,
                port=port,
                password=password,
                region=region,
                name="lavalink-node",
                ssl=secure,
            )
            logging.info(f"Added Lavalink node: {host}:{port}")
        except (ValueError, TypeError) as e:
            raise RuntimeError(f"Invalid Lavalink configuration in .env: {e}")
        except Exception as e:
            raise RuntimeError(f"Failed to add Lavalink node: {e}")

        await self.load_cogs()
        await self.tree.sync()

    async def load_cogs(self):
        base_path = "cogs"

        for folder in ["comms", "events", "database"]:
            folder_path = os.path.join(base_path, folder)

            if not os.path.isdir(folder_path):
                continue

            for file in os.listdir(folder_path):
                if file.startswith("_") or not file.endswith(".py"):
                    continue

                module = f"{base_path}.{folder}.{file[:-3]}"

                try:
                    await self.load_extension(module)
                except Exception as e:
                    print(f"Failed to load {module}: {e}")

    def get_player(self, guild_id: int) -> lavalink.DefaultPlayer | None:
        if not self.lavalink:
            return None
        return cast(
            lavalink.DefaultPlayer | None, self.lavalink.player_manager.get(guild_id)
        )

    async def voice_precheck(
        self,
        user: discord.abc.Snowflake,
        guild: discord.Guild,
    ) -> str | None:
        member = guild.get_member(user.id)
        if not member or not member.voice or not member.voice.channel:
            return "You must join a voice channel first."

        vc = guild.voice_client
        if vc and vc.channel != member.voice.channel:
            return f" You must be in the same voice channel as the bot ({vc.channel.mention})."

        return None
