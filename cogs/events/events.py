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
import io
import requests

import discord
from discord.ext import commands

import lavalink
from cogs.comms._trackcont import TrackView
from cogs.comms._card import create_card, shorten_title, resize_and_round
from lavalink.events import (
    NodeReadyEvent,
    PlayerErrorEvent,
    QueueEndEvent,
    TrackStartEvent,
    TrackStuckEvent,
)
from manage import Error, format_duration

if TYPE_CHECKING:
    from manage import Bot


class EventHandlers(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot: Bot = bot
        if self.bot.lavalink:
            self.bot.lavalink.add_event_hooks(self)

    async def _create_card_file(self, track, requester_id: int) -> discord.File | None:
        if not hasattr(track, 'artwork_url') or not track.artwork_url:
            logging.debug(f"No artwork URL for track: {track.title if track else 'Unknown'}")
            return None

        try:
            requester_name = "Unknown"
            if requester_id:
                try:
                    user = self.bot.get_user(int(requester_id))
                    if user:
                        requester_name = user.name
                    else:
                        user = await self.bot.fetch_user(int(requester_id))
                        requester_name = user.name
                except Exception as e:
                    logging.warning(f"Failed to fetch user {requester_id}: {e}")
                    requester_name = f"User #{requester_id}"

            bytes_content = requests.get(track.artwork_url).content
            if not bytes_content:
                logging.warning(f"Empty artwork content for: {track.title}")
                return None

            rounded_bytes = resize_and_round(bytes_content)

            result_bytes = create_card(
                image_bytes=rounded_bytes,
                background_path="data/background.png",
                heading=shorten_title(f"{track.title}"),
                author=track.author,
                player=requester_name,
                time_text=format_duration(int(track.duration)) if track.duration else "LIVE"
            )
            logging.debug(f"Card file created successfully for: {track.title}")
            return io.BytesIO(result_bytes)

        except Exception as e:
            logging.error(f"Error creating card file for {track.title}: {e}")
            return None

    async def _get_track_data(self, track, requester_id: int) -> dict:
        if not track:
            return {}

        requester_name = "Unknown"
        if requester_id:
            try:
                user = await self.bot.fetch_user(int(requester_id))
                requester_name = user.name
            except Exception as e:
                logging.warning(f"Failed to fetch user {requester_id}: {e}")
                requester_name = f"User #{requester_id}"

        current_pos = format_duration(0)
        total_duration = format_duration(int(track.duration)) if track.duration else "00:00"
        is_stream = bool(getattr(track, "stream", False))
        mode = track.info.get("sourceName", "Youtube") if hasattr(track, 'info') else "Youtube"

        return {
            "name": track.title,
            "author": track.author,
            "requested_by": requester_name,
            "current_duration": current_pos,
            "total_duration": total_duration if not is_stream else "LIVE",
            "current_volume": 100,
            "mode": mode.title(),
            "uri": track.uri
        }

    @commands.Cog.listener()
    async def on_connect(self):
        logging.info("Connecting to Discord...")
        await self.bot.wait_until_ready()
        logging.info("Connected to Discord.")

    @commands.Cog.listener()
    async def on_ready(self):
        logging.info("Logged in: %s | %s", self.bot.user, self.bot.user.id)
        activity = discord.Game(name=f"Serving {len(self.bot.guilds)} servers")
        await self.bot.change_presence(status=discord.Status.online, activity=activity)
        logging.info("Bot is online & can be used ")

    @lavalink.listener(NodeReadyEvent)
    async def on_lavalink_node_ready(self, event: NodeReadyEvent):
        logging.info(
            "Lavalink node ready: %s | Session: %s | Resumed: %s",
            event.node,
            event.session_id,
            event.resumed,
        )

    @lavalink.listener(TrackStartEvent)
    async def on_lavalink_track_start(self, event: TrackStartEvent):
        player = event.player
        guild = self.bot.get_guild(player.guild_id)
        if not guild:
            return

        if player.guild_id not in self.bot.player_channels:
            return

        channel = guild.get_channel(self.bot.player_channels[player.guild_id])
        if not channel:
            return

        if player.guild_id in self.bot.player_views:
            old_view = self.bot.player_views[player.guild_id]
            if hasattr(old_view, 'delete_old_container'):
                try:
                    await old_view.delete_old_container()
                except Exception:
                    pass
            if hasattr(old_view, 'update_task') and old_view.update_task:
                old_view.update_task.cancel()

        requester_id = 0
        if player.guild_id in self.bot.track_requesters and player.current:
            requesters_queue = self.bot.track_requesters[player.guild_id].get(player.current.uri, [])
            if requesters_queue:
                requester_id = requesters_queue.pop(0)

        try:
            track_data = await self._get_track_data(player.current, requester_id)

            image = await self._create_card_file(player.current, requester_id)

            card_file = discord.File(image, filename="card.png") if image else None

            view = TrackView(self.bot, player, guild.owner, track_data, image if card_file else None)

            if card_file:
                message = await channel.send(view=view, file=card_file)
            else:
                message = await channel.send(view=view)

            view.message = message

            self.bot.player_views[player.guild_id] = view
            view.update_task = asyncio.create_task(view.start_update_loop())

        except Exception as e:
            import traceback
            print(traceback.format_exc())
            logging.error(f"Error handling track start for guild {guild.id}: {e}")


    @lavalink.listener(QueueEndEvent)
    async def on_lavalink_queue_end(self, event: QueueEndEvent):
        pass

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        pass

    @lavalink.listener(PlayerErrorEvent)
    async def on_lavalink_player_error(self, event: PlayerErrorEvent):
        logging.warning(
            "Track exception on guild %s: %r",
            event.player.guild_id,
            event,
        )
        await event.player.skip()

    @lavalink.listener(TrackStuckEvent)
    async def on_lavalink_track_stuck(self, event: TrackStuckEvent):
        logging.warning(
            "Track stuck on guild %s at position %sms",
            event.player.guild_id,
            event.threshold,
        )
        await event.player.skip()


async def setup(bot: commands.Bot):
    await bot.add_cog(EventHandlers(bot))
