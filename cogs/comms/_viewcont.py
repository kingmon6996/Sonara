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
from typing import Optional
import logging
from sqlalchemy import delete

from cogs.functions import load_emojis
from cogs.database import db
from cogs.database._database import PlaylistSong

EMOJIS = load_emojis()
logger = logging.getLogger(__name__)


class ManageTrackButton(discord.ui.Button):
    def __init__(self, parent_view, song_data: dict, user_id: int, playlist_id: Optional[str] = None):
        super().__init__(
            style=discord.ButtonStyle.secondary,
            emoji=EMOJIS.get("settings"),
            custom_id=f"manage_song_{song_data['song_id']}",
        )
        self.parent_view = parent_view
        self.song_data = song_data
        self.user_id = user_id
        self.playlist_id = playlist_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                f"Only the user who ran the playlist command can use this.",
                ephemeral=True
            )
            return

        select = discord.ui.Select(
            placeholder="Choose an action",
            options=[
                discord.SelectOption(
                    label="Add to Queue/Play",
                    value="add_to_queue",
                    emoji=EMOJIS.get("plus")
                ),
                discord.SelectOption(
                    label="Delete from Playlist",
                    value="delete_from_playlist",
                    emoji=EMOJIS.get("delete")
                ),
            ]
        )

        async def select_callback(select_interaction: discord.Interaction):
            if select_interaction.user.id != self.user_id:
                await select_interaction.response.send_message(
                    f"Only the user who ran the playlist command can use this.",
                    ephemeral=True
                )
                return

            action = select_interaction.data['values'][0]

            if action == "add_to_queue":
                await self._handle_add_to_queue(select_interaction, view)
            elif action == "delete_from_playlist":
                await self._handle_delete_from_playlist(select_interaction, view)

        select.callback = select_callback
        view = discord.ui.View(timeout=None)
        view.add_item(select)

        await interaction.response.send_message(
            content=f"**{self.song_data['title']}** - Choose an action:",
            view=view,
            ephemeral=True
        )

    async def _handle_add_to_queue(self, interaction: discord.Interaction, view: discord.ui.View):
        await interaction.response.defer()
        try:
            if not interaction.user.voice or not interaction.user.voice.channel:
                await interaction.followup.send(
                    f"You must be in a voice channel to add songs.",
                    ephemeral=True
                )
                return


            play_cog = self.parent_view.bot.get_cog("PlayCommand")
            if not play_cog:
                await interaction.followup.send(
                    f"Play command not available.",
                    ephemeral=True
                )
                return


            player = self.parent_view.bot.get_player(interaction.guild.id)


            result = await play_cog.handle_play_action(
                interaction,
                interaction.guild,
                interaction.user,
                player,
                self.song_data['uri']
            )


            if isinstance(result, dict) and 'track' in result:
                await interaction.followup.send(
                    f"Added **{self.song_data['title']}** to the queue.",
                    ephemeral=True
                )
                logging.info(f"User {interaction.user.id} queued '{self.song_data['title']}'")
            elif isinstance(result, str):

                await interaction.followup.send(result, ephemeral=True)
            else:

                message = getattr(result, 'message', str(result))
                await interaction.followup.send(message, ephemeral=True)
        except Exception as e:
            logging.error(f"Error adding track to queue: {e}")
            await interaction.followup.send(
                f"An error occurred: {str(e)}",
                ephemeral=True
            )
        finally:

            for item in view.children:
                item.disabled = True
            try:
                await interaction.message.edit(view=view)
            except:
                pass

    async def _handle_delete_from_playlist(self, interaction: discord.Interaction, view: discord.ui.View):
        await interaction.response.defer()
        try:
            if not db.is_connected():
                await interaction.followup.send(
                    f"Database connection not available.",
                    ephemeral=True
                )
                return

            async with db.session() as session:
                await session.execute(
                    delete(PlaylistSong).where(
                        PlaylistSong.id == self.song_data["song_id"],
                        PlaylistSong.playlist_id == self.playlist_id,
                    )
                )
                await session.commit()

            self.parent_view.songs = [s for s in self.parent_view.songs if s['song_id'] != self.song_data['song_id']]

            self.parent_view.total_pages = max(1, (len(self.parent_view.songs) + self.parent_view.page_size - 1) // self.parent_view.page_size)

            if self.parent_view.current_page >= self.parent_view.total_pages:
                self.parent_view.current_page = max(0, self.parent_view.total_pages - 1)

            await self.parent_view.update_playlist_display(interaction)

            await interaction.followup.send(
                f"Deleted **{self.song_data['title']}** from playlist!",
                ephemeral=True
            )

            logger.info(f"User {interaction.user.id} deleted '{self.song_data['title']}' from playlist {self.playlist_id}")
        except Exception as e:
            logger.error(f"Failed to delete track: {e}")
            await interaction.followup.send(
                f"Failed to delete song: {str(e)}",
                ephemeral=True
            )
        finally:

            for item in view.children:
                item.disabled = True
            try:
                await interaction.message.edit(view=view)
            except:
                pass


class ClosePlaylistButton(discord.ui.Button):
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
                f"Only the user who ran the playlist command can close this.",
                ephemeral=True
            )
            return
        await interaction.response.defer()
        if self.parent_view.message:
            try:
                await self.parent_view.message.delete()
            except Exception:
                pass


class PlaylistPaginationFirstButton(discord.ui.Button):
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
                f"Only the user who ran the playlist command can navigate.",
                ephemeral=True
            )
            return
        await interaction.response.defer()
        self.parent_view.current_page = 0
        await self.parent_view.update_playlist_display(interaction)


class PlaylistPaginationPreviousButton(discord.ui.Button):
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
                f"Only the user who ran the playlist command can navigate.",
                ephemeral=True
            )
            return
        await interaction.response.defer()
        if self.parent_view.current_page > 0:
            self.parent_view.current_page -= 1
            await self.parent_view.update_playlist_display(interaction)


class PlaylistPaginationNextButton(discord.ui.Button):
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
                f"Only the user who ran the playlist command can navigate.",
                ephemeral=True
            )
            return
        await interaction.response.defer()
        if self.parent_view.current_page < self.parent_view.total_pages - 1:
            self.parent_view.current_page += 1
            await self.parent_view.update_playlist_display(interaction)


class PlaylistPaginationLastButton(discord.ui.Button):

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
                f"Only the user who ran the playlist command can navigate.",
                ephemeral=True
            )
            return
        await interaction.response.defer()
        self.parent_view.current_page = self.parent_view.total_pages - 1
        await self.parent_view.update_playlist_display(interaction)


class PlaylistContainer(discord.ui.Container):
    def __init__(self, songs: list, page_size: int, current_page: int, total_pages: int, playlist_name: str, playlist_id: str, parent_view, user_id: int):
        super().__init__()

        self.add_item(discord.ui.Section(
            discord.ui.TextDisplay(content=f"##  {playlist_name} - Page {current_page + 1}/{total_pages}"),
            accessory=ClosePlaylistButton(parent_view, user_id)
        ))
        self.add_item(discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small))

        start_idx = current_page * page_size
        end_idx = min(start_idx + page_size, len(songs))

        if start_idx < len(songs):
            for i in range(start_idx, end_idx):
                song_data = songs[i]

                title_text = f"### {i + 1}. {song_data['title']}"
                info_text = f"- **Artist:** {song_data['author']}"

                self.add_item(discord.ui.Section(
                    discord.ui.TextDisplay(content=title_text),
                    discord.ui.TextDisplay(content=info_text),
                    accessory=ManageTrackButton(parent_view, song_data, user_id, playlist_id)
                ))

                if i < end_idx - 1:
                    self.add_item(discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small))
        else:
            self.add_item(discord.ui.TextDisplay(content="No songs on this page."))

        self.add_item(discord.ui.ActionRow(
            PlaylistPaginationFirstButton(parent_view, user_id),
            PlaylistPaginationPreviousButton(parent_view, user_id),
            PlaylistPaginationNextButton(parent_view, user_id),
            PlaylistPaginationLastButton(parent_view, user_id),
        ))


class PlaylistLayoutView(discord.ui.LayoutView):

    def __init__(self, bot, songs: list, playlist_name: str, playlist_id: str, page_size: int = 5, user_id: int = None):
        super().__init__(timeout=None)
        self.bot = bot
        self.songs = songs
        self.playlist_name = playlist_name
        self.playlist_id = playlist_id
        self.page_size = page_size
        self.current_page = 0
        self.message = None
        self.user_id = user_id

        self.total_pages = max(1, (len(self.songs) + page_size - 1) // page_size)


        self._container = None
        self._build_container()

    def _build_container(self):

        self.clear_items()

        self._container = PlaylistContainer(
            self.songs,
            self.page_size,
            self.current_page,
            self.total_pages,
            self.playlist_name,
            self.playlist_id,
            self,
            self.user_id
        )
        self.add_item(self._container)

    async def update_playlist_display(self, interaction: discord.Interaction):
        if not self.message:
            return

        try:
            self._build_container()
            await self.message.edit(view=self)
        except Exception as e:
            logging.error(f"Error updating playlist display: {e}")

    async def on_timeout(self):
        pass
