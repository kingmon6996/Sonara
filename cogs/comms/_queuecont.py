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
from discord.ext import commands
from typing import Optional
import logging
import asyncio
from cogs.functions import load_emojis
import time
import json
import os
from datetime import datetime

EMOJIS = load_emojis()
LOG_FILE = os.path.join("data", "log.json")


def save_queue_log(prepared_tracks: list, raw_tracks: list) -> None:
    try:

        log_data = {}


        if os.path.exists(LOG_FILE):
            try:
                with open(LOG_FILE, 'r', encoding='utf-8') as f:
                    log_data = json.load(f)
            except (json.JSONDecodeError, IOError):
                log_data = {}


        timestamp = datetime.now().isoformat()


        decorated_tracks = []
        for track_data in prepared_tracks:
            decorated_tracks.append({
                'index': track_data['index'],
                'title': track_data['title'],
                'uri': track_data['uri'],
                'author': track_data['author'],
                'duration': track_data['duration'],
                'artwork_url': track_data['artwork_url'],
                'requester_id': track_data['requester_id'],
            })


        raw_data = []
        for track in raw_tracks:
            try:
                track_dict = {
                    'encoded': track.encoded if hasattr(track, 'encoded') else None,
                    'info': {
                        'identifier': track.identifier if hasattr(track, 'identifier') else None,
                        'isSeekable': track.is_seekable if hasattr(track, 'is_seekable') else False,
                        'author': track.author if hasattr(track, 'author') else 'Unknown',
                        'length': track.duration if hasattr(track, 'duration') else 0,
                        'isStream': track.is_stream if hasattr(track, 'is_stream') else False,
                        'position': 0,
                        'title': track.title if hasattr(track, 'title') else 'Unknown',
                        'uri': track.uri if hasattr(track, 'uri') else 'Unknown',
                        'sourceName': track.source if hasattr(track, 'source') else 'unknown',
                        'artworkUrl': track.artwork_url if hasattr(track, 'artwork_url') else None,
                        'isrc': track.isrc if hasattr(track, 'isrc') else None,
                        'track': track.track if hasattr(track, 'track') else None,
                        'encoded': track.get('encoded', None) if isinstance(track, dict) else None,
                    },
                    'pluginInfo': {
                        'albumName': getattr(track, 'album', None),
                        'albumUrl': getattr(track, 'album_url', None),
                        'previewUrl': getattr(track, 'preview_url', None),
                        'isPreview': getattr(track, 'is_preview', False),
                        'artistUrl': getattr(track, 'artist_url', None),
                        'artistArtworkUrl': getattr(track, 'artist_artwork_url', None),
                        'isLocal': getattr(track, 'is_local', False),
                    },
                    'userData': track.user_data if hasattr(track, 'user_data') else {},
                }
                raw_data.append(track_dict)
            except Exception as e:
                logging.debug(f"Error serializing raw track: {e}")
                continue


        queue_entry = {
            'timestamp': timestamp,
            'total_tracks': len(prepared_tracks),
            'decorated_data': decorated_tracks,
            'raw_data': raw_data,
        }


        if 'queue_history' not in log_data:
            log_data['queue_history'] = []

        log_data['queue_history'].append(queue_entry)


        if len(log_data['queue_history']) > 100:
            log_data['queue_history'] = log_data['queue_history'][-100:]


        with open(LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)

        logging.debug(f"Queue data saved to log.json with {len(prepared_tracks)} tracks")

    except Exception as e:
        logging.error(f"Failed to save queue log: {e}")


class RemoveTrackButton(discord.ui.Button):
    def __init__(self, parent_view, track_index: int, track_obj, requester_id: int, user_id: int):
        super().__init__(
            style=discord.ButtonStyle.secondary,
            emoji=EMOJIS.get("delete"),
            custom_id=f"remove_track_{track_index}",
        )
        self.parent_view = parent_view
        self.track_index = track_index
        self.track_obj = track_obj
        self.requester_id = requester_id
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                f"Only the user who ran the queue command can manage tracks.",
                ephemeral=True
            )
            return
        await interaction.response.defer()
        try:
            track_data_match = None
            track_title = None
            for track_data in self.parent_view.prepared_tracks:
                if (track_data['index'] == self.track_index and 
                    track_data['track'] == self.track_obj):
                    track_data_match = track_data
                    track_title = track_data['title']
                    break

            if not track_data_match:
                await interaction.followup.send(
                    f"The track you are trying to remove doesn't exist in the queue (data mismatch).",
                    ephemeral=True
                )
                return

            queue_list = list(self.parent_view.player.queue)
            track_to_remove = None

            for track in queue_list:
                if track.track == self.track_obj:
                    track_to_remove = track
                    break

            if track_to_remove:
                self.parent_view.player.queue.remove(track_to_remove)


                guild = interaction.guild
                if guild:

                    player_channel_id = self.parent_view.player.bot.player_channels.get(guild.id)
                    if player_channel_id:
                        text_channel = guild.get_channel(player_channel_id)
                        if text_channel:
                            removal_announcement = (
                                f"**Song Removed**\n"
                                f"**{track_title}** was removed by <@{interaction.user.id}>\n"
                                f"Originally requested by <@{self.requester_id}>"
                            )
                            try:
                                await text_channel.send(removal_announcement)
                            except Exception as e:
                                logging.error(f"Failed to send removal message: {e}")


                await asyncio.sleep(3)

                await self.parent_view.refresh_queue_data()

                removal_msg = f"Track removed from queue."
                await self.parent_view.update_queue_display(interaction, custom_message=removal_msg)
            else:

                await interaction.followup.send(
                    f"Track sync error: Track data mismatch. Please refresh the queue.",
                    ephemeral=True
                )
        except Exception as e:
            logging.error(f"Failed to remove track: {e}")
            await interaction.followup.send(
                f"Failed to remove track: {str(e)}",
                ephemeral=True
            )


class CloseButton(discord.ui.Button):
    def __init__(self, parent_view, user_id: int):
        super().__init__(
            style=discord.ButtonStyle.secondary,
            emoji=EMOJIS.get("delete"),
        )
        self.parent_view = parent_view
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                f"Only the user who ran the queue command can close this.",
                ephemeral=True
            )
            return
        await interaction.response.defer()
        if self.parent_view.message:
            try:
                await self.parent_view.message.delete()
            except Exception:
                pass


class PaginationFirstButton(discord.ui.Button):
    def __init__(self, parent_view, user_id: int):
        super().__init__(
            style=discord.ButtonStyle.secondary,
            emoji=EMOJIS.get("first"),
            label="First",
        )
        self.parent_view = parent_view
        self.user_id = user_id
        self.disabled = parent_view.current_page == 0

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                f"Only the user who ran the queue command can navigate.",
                ephemeral=True
            )
            return
        await interaction.response.defer()
        self.parent_view.current_page = 0
        await self.parent_view.update_queue_display(interaction)


class PaginationPreviousButton(discord.ui.Button):
    def __init__(self, parent_view, user_id: int):
        super().__init__(
            style=discord.ButtonStyle.secondary,
            emoji=EMOJIS.get("prevtrack"),
            label="Previous",
        )
        self.parent_view = parent_view
        self.user_id = user_id
        self.disabled = parent_view.current_page == 0

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                f"Only the user who ran the queue command can navigate.",
                ephemeral=True
            )
            return
        await interaction.response.defer()
        if self.parent_view.current_page > 0:
            self.parent_view.current_page -= 1
            await self.parent_view.update_queue_display(interaction)


class PaginationNextButton(discord.ui.Button):
    def __init__(self, parent_view, user_id: int):
        super().__init__(
            style=discord.ButtonStyle.secondary,
            emoji=EMOJIS.get("next"),
            label="Next",
        )
        self.parent_view = parent_view
        self.user_id = user_id
        self.disabled = parent_view.current_page >= parent_view.total_pages - 1

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                f"Only the user who ran the queue command can navigate.",
                ephemeral=True
            )
            return
        await interaction.response.defer()
        if self.parent_view.current_page < self.parent_view.total_pages - 1:
            self.parent_view.current_page += 1
            await self.parent_view.update_queue_display(interaction)


class PaginationLastButton(discord.ui.Button):

    def __init__(self, parent_view, user_id: int):
        super().__init__(
            style=discord.ButtonStyle.secondary,
            emoji=EMOJIS.get("last"),
            label="Last",
        )
        self.parent_view = parent_view
        self.user_id = user_id
        self.disabled = parent_view.current_page >= parent_view.total_pages - 1

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                f"Only the user who ran the queue command can navigate.",
                ephemeral=True
            )
            return
        await interaction.response.defer()
        self.parent_view.current_page = self.parent_view.total_pages - 1
        await self.parent_view.update_queue_display(interaction)


class QueueContainer(discord.ui.Container):
    def __init__(self, prepared_tracks: list, page_size: int, current_page: int, total_pages: int, parent_view, user_id: int):
        super().__init__()

        self.add_item(discord.ui.Section(
            discord.ui.TextDisplay(content=f"## Queue - Page {current_page + 1}/{total_pages}"),
            accessory=CloseButton(parent_view, user_id)
        ))
        self.add_item(discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small))

        start_idx = current_page * page_size
        end_idx = min(start_idx + page_size, len(prepared_tracks))

        if start_idx < len(prepared_tracks):
            for i in range(start_idx, end_idx):
                track_data = prepared_tracks[i]

                title_text = f"### {track_data['index']}. [{track_data['title']}]({track_data['uri']})"
                info_text = (
                    f"- **Author:** {track_data['author']}\n"
                    f"- **Duration:** {self._format_duration(track_data['duration'])}\n"
                    f"- **Requested by:** <@{track_data['requester_id']}>"
                )

                self.add_item(discord.ui.Section(
                    discord.ui.TextDisplay(content=title_text),
                    discord.ui.TextDisplay(content=info_text),
                    accessory=RemoveTrackButton(parent_view, track_data['index'], track_data['track'], track_data['requester_id'], user_id)
                ))

                if i < end_idx - 1:
                    self.add_item(discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small))
        else:
            self.add_item(discord.ui.TextDisplay(content="No tracks on this page."))

        self.add_item(discord.ui.ActionRow(
            PaginationFirstButton(parent_view, user_id),
            PaginationPreviousButton(parent_view, user_id),
            PaginationNextButton(parent_view, user_id),
            PaginationLastButton(parent_view, user_id),
        ))

    @staticmethod
    def _format_duration(ms: int) -> str:
        try:
            seconds = ms // 1000
            minutes, seconds = divmod(seconds, 60)
            return f"{minutes}:{seconds:02d}"
        except:
            return "00:00"


class QueueLayoutView(discord.ui.LayoutView):
    def __init__(self, bot, player, page_size: int = 5, user_id: int = None):
        super().__init__(timeout=None)                                          
        self.bot = bot
        self.player = player
        self.page_size = page_size
        self.current_page = 0
        self.message = None
        self.user_id = user_id
        self._disable_task = None
        self._message_created_time = None


        self.prepared_tracks = self._prepare_track_data()
        self.total_pages = max(1, (len(self.prepared_tracks) + page_size - 1) // page_size)


        raw_tracks = list(self.player.queue)
        save_queue_log(self.prepared_tracks, raw_tracks)


        self._container = None
        self._build_container()

    def _prepare_track_data(self) -> list:


        prepared = []
        for idx, track in enumerate(self.player.queue, 1):

            requester_info = self.bot.track_requesters.get(self.player.guild_id, {}).get(track.uri, [])
            requester_id = requester_info[0] if requester_info else 0

            prepared.append({
                'index': idx,
                'title': track.title,
                'uri': track.uri,
                'author': track.author,
                'duration': track.duration,
                'artwork_url': track.artwork_url,
                'requester_id': requester_id,
                'track': track.track,                         
            })

        return prepared

    async def refresh_queue_data(self):

        self.prepared_tracks = self._prepare_track_data()
        self.total_pages = max(1, (len(self.prepared_tracks) + self.page_size - 1) // self.page_size)


        if self.current_page >= self.total_pages:
            self.current_page = max(0, self.total_pages - 1)

    def _build_container(self):

        self.clear_items()

        self._container = QueueContainer(
            self.prepared_tracks,
            self.page_size,
            self.current_page,
            self.total_pages,
            self,                              
            self.user_id
        )
        self.add_item(self._container)

    async def update_queue_display(self, interaction: discord.Interaction, custom_message: str = None):

        if not self.message:
            return

        try:

            self._build_container()
            await self.message.edit(view=self)


            if custom_message:
                await interaction.followup.send(custom_message, ephemeral=True)
            else:
                await interaction.followup.send(
                    f"Switched to page **{self.current_page + 1}/{self.total_pages}**",
                    ephemeral=True
                )
        except Exception as e:
            print(f"Error updating queue display: {e}")

    def _disable_all_buttons(self):

        for item in self.children:
            if isinstance(item, discord.ui.Container):
                for child in item.children:
                    if isinstance(child, discord.ui.ActionRow):
                        for button in child.children:
                            if isinstance(button, discord.ui.Button):
                                button.disabled = True
                    elif isinstance(child, discord.ui.Button):
                        child.disabled = True
            elif isinstance(item, discord.ui.ActionRow):
                for button in item.children:
                    if isinstance(button, discord.ui.Button):
                        button.disabled = True
            elif isinstance(item, discord.ui.Button):
                item.disabled = True

    async def _disable_buttons_after_delay(self):

        try:
            await asyncio.sleep(300)                  
            self._disable_all_buttons()


            if self.message:
                try:
                    await self.message.edit(view=self)
                except Exception as e:
                    logging.debug(f"Failed to update message with disabled buttons: {e}")
        except asyncio.CancelledError:
            pass                              
        except Exception as e:
            logging.error(f"Error in disable buttons task: {e}")

    def start_disable_timer(self):

        if self._disable_task:
            self._disable_task.cancel()
        self._disable_task = asyncio.create_task(self._disable_buttons_after_delay())

    async def on_timeout(self):

        pass
