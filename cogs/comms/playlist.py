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
import re
import secrets
import string
from collections import defaultdict
from typing import TYPE_CHECKING, Optional

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import func, select

from cogs.database import db
from cogs.database._database import Playlist, PlaylistSong
from cogs.functions import load_emojis
from ._viewcont import PlaylistLayoutView

if TYPE_CHECKING:
    from manage import Bot

logger = logging.getLogger(__name__)
EMOJIS = load_emojis()

URL_RX = re.compile(r"https?://(?:www\.)?.+")


def generate_playlist_id() -> str:

    characters = string.ascii_letters + string.digits
    return ''.join(secrets.choice(characters) for _ in range(16))


class ShowPlaylistFirstButton(discord.ui.Button):

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
                f"Only the user who ran the command can use this.",
                ephemeral=True
            )
            return
        await interaction.response.defer()
        self.parent_view.current_page = 0
        await self.parent_view.update_playlist_display(interaction)


class ShowPlaylistPreviousButton(discord.ui.Button):

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
                f"Only the user who ran the command can use this.",
                ephemeral=True
            )
            return
        await interaction.response.defer()
        if self.parent_view.current_page > 0:
            self.parent_view.current_page -= 1
            await self.parent_view.update_playlist_display(interaction)


class ShowPlaylistNextButton(discord.ui.Button):

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
                f"Only the user who ran the command can use this.",
                ephemeral=True
            )
            return
        await interaction.response.defer()
        if self.parent_view.current_page < self.parent_view.total_pages - 1:
            self.parent_view.current_page += 1
            await self.parent_view.update_playlist_display(interaction)


class ShowPlaylistLastButton(discord.ui.Button):

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
                f"Only the user who ran the command can use this.",
                ephemeral=True
            )
            return
        await interaction.response.defer()
        self.parent_view.current_page = self.parent_view.total_pages - 1
        await self.parent_view.update_playlist_display(interaction)


class PaginatedPlaylistShowView(discord.ui.View):

    def __init__(self, playlists: list, user_id: int, page_size: int = 10):
        super().__init__(timeout=300)                     
        self.playlists = playlists
        self.user_id = user_id
        self.page_size = page_size
        self.current_page = 0
        self.message = None

        self.total_pages = max(1, (len(playlists) + page_size - 1) // page_size)

        self.add_buttons()

    def add_buttons(self):
        self.clear_items()
        self.add_item(ShowPlaylistFirstButton(self, self.user_id))
        self.add_item(ShowPlaylistPreviousButton(self, self.user_id))
        self.add_item(ShowPlaylistNextButton(self, self.user_id))
        self.add_item(ShowPlaylistLastButton(self, self.user_id))

    def get_page_embed(self) -> discord.Embed:
        start_idx = self.current_page * self.page_size
        end_idx = min(start_idx + self.page_size, len(self.playlists))
        page_playlists = self.playlists[start_idx:end_idx]

        playlists_text = "\n".join(
            f"• **{p[1]}** - `{p[4]} songs`{f' - {p[2]}' if p[2] else ''}"
            for p in page_playlists
        )

        embed = discord.Embed(
            title="Your Playlists",
            description=playlists_text if playlists_text else "No playlists on this page",
            color=0x5C2A2A
        )
        embed.set_footer(text=f"Page {self.current_page + 1}/{self.total_pages} | Total: {len(self.playlists)} playlist(s)")

        return embed

    async def update_playlist_display(self, interaction: discord.Interaction):

        if not self.message:
            return

        try:
            self.add_buttons()
            embed = self.get_page_embed()
            await self.message.edit(embed=embed, view=self)
            await interaction.response.defer()
        except Exception as e:
            logger.error(f"Error updating playlist display: {e}")

    async def on_timeout(self):

        try:
            if self.message:
                self.clear_items()
                await self.message.edit(view=self)
        except Exception as e:
            logger.debug(f"Error disabling buttons on timeout: {e}")


class PlaylistSelectView(discord.ui.View):
    def __init__(self, user_id: int, playlists: list, page: int = 0):
        super().__init__()
        self.user_id = user_id
        self.playlists = playlists
        self.page = page
        self.total_pages = (len(playlists) + 23) // 24  
        self.message = None  

        self.update_select()

    def update_select(self):
        for item in self.children[:]:
            if isinstance(item, discord.ui.Select):
                self.remove_item(item)

        options = []

        if self.page > 0:
            options.append(
                discord.SelectOption(
                    label="Previous",
                    value="__previous__",
                    emoji=EMOJIS.get("prevtrack"),
                    description=f"Go to page {self.page}"
                )
            )

        if self.page == 0:
            playlist_count = 24
        else:
            playlist_count = 23

        start = self.page * 24
        end = start + playlist_count
        page_playlists = self.playlists[start:end]


        for p in page_playlists:
            options.append(
                discord.SelectOption(
                    label=p[1][:100],  
                    value=p[0],  
                    emoji=EMOJIS.get("plus"),
                    description=f"{p[3]} songs"                   
                )
            )

        has_next = (self.page * 24 + playlist_count) < len(self.playlists)

        if has_next:
            options.append(
                discord.SelectOption(
                    label="Next ",
                    value="__next__",
                    emoji=EMOJIS.get("next"),
                    description=f"Go to page {self.page + 2}"
                )
            )

        options.append(
            discord.SelectOption(
                label="Cancel",
                value="__cancel__",
                emoji=EMOJIS.get("delete"),
                description="Cancel this operation"
            )
        )

        select = discord.ui.Select(
            placeholder="Select a playlist or navigate pages",
            options=options,
            min_values=1,
            max_values=1
        )
        select.callback = self.select_playlist
        self.add_item(select)

    async def select_playlist(self, interaction: discord.Interaction):
        selected_value = interaction.data['values'][0]

        if selected_value == "__previous__":
            if self.page > 0:
                self.page -= 1
                self.clear_items()
                self.update_select()
                await interaction.response.edit_message(view=self)
            else:
                await interaction.response.defer()
        elif selected_value == "__next__":
            if (self.page * 24 + (24 if self.page == 0 else 23)) < len(self.playlists):
                self.page += 1
                self.clear_items()
                self.update_select()
                await interaction.response.edit_message(view=self)
            else:
                await interaction.response.defer()
        elif selected_value == "__cancel__":
            await interaction.response.defer()
        else:

            await interaction.response.defer()
            self.selected_playlist_id = selected_value


            for p in self.playlists:
                if p[0] == selected_value:
                    self.selected_playlist_name = p[1]
                    self.selected_playlist_count = p[3]
                    break

            self.message = interaction.message


class PlaylistCommand(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot: Bot = bot
        self._last_autocomplete: dict[int, float] = {}

    async def playlist_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        try:
            user_id = interaction.user.id
            if not db.is_connected():
                return []

            async with db.session() as session:
                playlist_names = (
                    await session.scalars(
                        select(Playlist.name)
                        .where(Playlist.user_id == user_id)
                        .order_by(Playlist.created_at.desc())
                    )
                ).all()


            filtered = [
                name for name in playlist_names if current.lower() in name.lower()
            ]
            choices = [
                app_commands.Choice(name=name[:100], value=name)
                for name in filtered[:25]
            ]
            return choices
        except Exception as e:
            logger.error(f"Playlist autocomplete error: {e}")
            return []

    async def song_search_autocomplete(
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
            logger.warning("Autocomplete search timed out")
            return []
        except Exception as e:
            logger.error(f"Autocomplete search failed: {e}")
            return []

    playlist_group = app_commands.Group(
        name="playlist",
        description="Manage your playlists",
    )

    @playlist_group.command(
        name="create",
        description="Create a new playlist",
    )
    async def playlist_create(
        self,
        interaction: discord.Interaction,
        name: str,
        description: Optional[str] = None,
    ):
        try:
            user_id = interaction.user.id


            if len(name) > 30:
                await interaction.response.send_message(
                    f"{EMOJIS.get('failure', '')} Playlist name must be 30 characters or less. "
                    f"(Current: {len(name)} characters)",
                    ephemeral=True
                )
                return


            if not db.is_connected():
                await interaction.response.send_message(
                    f"{EMOJIS.get('failure', '')} Database connection not available.",
                    ephemeral=True
                )
                return


            playlist_id = generate_playlist_id()


            async with db.session() as session:
                session.add(
                    Playlist(
                        id=playlist_id,
                        user_id=user_id,
                        name=name,
                        description=description or "",
                    )
                )
                await session.commit()

            embed = discord.Embed(
                title=f"{EMOJIS.get('success', '')} Playlist Created",
                description=f"{EMOJIS.get('success', '')} Successfully created playlist **{name}**",
                color=0x5C2A2A
            )
            if description:
                embed.add_field(name="Description", value=description, inline=False)

            await interaction.response.send_message(embed=embed, ephemeral=True)
            logger.info(f"Playlist '{name}' (ID: {playlist_id}) created by user {user_id}")

        except Exception as e:
            logger.error(f"Error creating playlist: {e}")
            await interaction.response.send_message(
                f"{EMOJIS.get('failure', '')} Failed to create playlist: {str(e)}",
                ephemeral=True
            )

    @playlist_group.command(
        name="show",
        description="View your playlists with song count",
    )
    async def playlist_show(
        self,
        interaction: discord.Interaction,
    ):
        try:
            user_id = interaction.user.id
            if not db.is_connected():
                await interaction.response.send_message(
                    f"{EMOJIS.get('failure', '')} Database connection not available.",
                    ephemeral=True
                )
                return

            async with db.session() as session:
                playlists = (
                    await session.execute(
                        select(
                            Playlist.id,
                            Playlist.name,
                            Playlist.description,
                            Playlist.created_at,
                            func.count(PlaylistSong.id).label("song_count"),
                        )
                        .outerjoin(PlaylistSong, PlaylistSong.playlist_id == Playlist.id)
                        .where(Playlist.user_id == user_id)
                        .group_by(
                            Playlist.id,
                            Playlist.name,
                            Playlist.description,
                            Playlist.created_at,
                        )
                        .order_by(Playlist.created_at.desc())
                    )
                ).all()

            if not playlists:
                embed = discord.Embed(
                    title="Your Playlists",
                    description="You don't have any playlists yet. Create one with `/playlist create`",
                    color=0x5C2A2A
                )
                await interaction.response.send_message(embed=embed, ephemeral=False)
                return


            view = PaginatedPlaylistShowView(playlists, user_id, page_size=10)
            embed = view.get_page_embed()

            message = await interaction.response.send_message(embed=embed, view=view, ephemeral=False)
            view.message = message

        except Exception as e:
            logger.error(f"Error viewing playlists: {e}")
            await interaction.response.send_message(
                f"{EMOJIS.get('failure', '')} Failed to view playlists: {str(e)}",
                ephemeral=True
            )

    @playlist_group.command(
        name="view",
        description="View songs in a specific playlist",
    )
    @app_commands.autocomplete(playlist_name=playlist_autocomplete)
    async def playlist_view(
        self,
        interaction: discord.Interaction,
        playlist_name: str,
    ):
        try:
            await interaction.response.defer()
            user_id = interaction.user.id

            if not db.is_connected():
                await interaction.followup.send(
                    f"{EMOJIS.get('failure', '')} Database connection not available.",
                    ephemeral=True
                )
                return

            async with db.session() as session:
                playlist = await session.scalar(
                    select(Playlist).where(
                        Playlist.user_id == user_id,
                        Playlist.name == playlist_name,
                    )
                )

                if not playlist:
                    await interaction.followup.send(
                        f"{EMOJIS.get('failure', '')} Playlist **{playlist_name}** not found.",
                        ephemeral=True
                    )
                    return

                playlist_id = playlist.id


                songs = (
                    await session.scalars(
                        select(PlaylistSong)
                        .where(PlaylistSong.playlist_id == playlist_id)
                        .order_by(PlaylistSong.created_at.asc())
                    )
                ).all()

            if not songs:
                embed = discord.Embed(
                    title=playlist.name,
                    description="No songs in this playlist",
                    color=0x5C2A2A
                )
                embed.add_field(name="Created", value=str(playlist.created_at), inline=False)
                await interaction.followup.send(embed=embed, ephemeral=False)
                return


            formatted_songs = []
            for song in songs:
                formatted_songs.append({
                    'song_id': song.id,
                    'playlist_id': song.playlist_id,
                    'track': song.track,
                    'title': song.title,
                    'author': song.author,
                    'artwork': song.artwork,
                    'uri': song.uri,
                    'created_at': song.created_at
                })


            view = PlaylistLayoutView(
                self.bot,
                formatted_songs,
                playlist.name,
                playlist_id,
                page_size=5,
                user_id=user_id,
            )

            message = await interaction.followup.send(view=view, ephemeral=False)
            view.message = message
            logger.info(f"User {user_id} viewed playlist '{playlist_name}' with {len(songs)} songs")

        except Exception as e:
            logger.error(f"Error viewing playlist: {e}")
            await interaction.followup.send(
                f"{EMOJIS.get('failure', '')} Failed to view playlist: {str(e)}",
                ephemeral=True
            )

    @playlist_group.command(
        name="delete",
        description="Delete a playlist",
    )
    @app_commands.autocomplete(playlist_name=playlist_autocomplete)
    async def playlist_delete(
        self,
        interaction: discord.Interaction,
        playlist_name: str,
    ):
        try:
            user_id = interaction.user.id
            if not db.is_connected():
                await interaction.response.send_message(
                    f"{EMOJIS.get('failure', '')} Database connection not available.",
                    ephemeral=True
                )
                return

            async with db.session() as session:

                playlist = await session.scalar(
                    select(Playlist).where(
                        Playlist.user_id == user_id,
                        Playlist.name == playlist_name,
                    )
                )

                if not playlist:
                    await interaction.response.send_message(
                        f"{EMOJIS.get('failure', '')} Playlist **{playlist_name}** not found.",
                        ephemeral=True
                    )
                    return

                playlist_id = playlist.id
                await session.delete(playlist)
                await session.commit()

            embed = discord.Embed(
                title=f"{EMOJIS.get('delete', '')} Playlist Deleted",
                description=f"{EMOJIS.get('success', '')} Successfully deleted playlist **{playlist_name}**",
                color=0x5C2A2A
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)
            logger.info(f"Playlist '{playlist_name}' (ID: {playlist_id}) deleted by user {user_id}")

        except Exception as e:
            logger.error(f"Error deleting playlist: {e}")
            await interaction.response.send_message(
                f"{EMOJIS.get('failure', '')} Failed to delete playlist: {str(e)}",
                ephemeral=True
            )

    @playlist_group.command(
        name="add",
        description="Add a song or playlist to your playlist",
    )
    @app_commands.autocomplete(query=song_search_autocomplete)
    async def playlist_add(
        self,
        interaction: discord.Interaction,
        query: str,
    ):


        try:
            user_id = interaction.user.id


            await interaction.response.send_message(
                f"{EMOJIS.get('alert', '')} Fetching your song details..."
            )

            if not db.is_connected():
                await interaction.followup.send(
                    f"{EMOJIS.get('failure', '')} Database connection not available.",
                    ephemeral=True
                )
                return


            try:
                results = await self.bot.lavalink.get_tracks(query)

                if not results or not results.tracks:
                    await interaction.followup.send(
                        f"{EMOJIS.get('failure', '')} Song/Playlist not found.",
                        ephemeral=True
                    )
                    return


                tracks = results.tracks
                is_playlist = results.load_type.name == 'PLAYLIST'


                if is_playlist:
                    tracks_to_add = tracks
                else:
                    tracks_to_add = [tracks[0]]

            except Exception as e:
                logger.error(f"Failed to get track(s): {e}")
                await interaction.followup.send(
                    f"{EMOJIS.get('failure', '')} Failed to retrieve song/playlist.",
                    ephemeral=True
                )
                return


            prepared_track_data = []
            for track in tracks_to_add:
                track_dict = {
                    'title': track.title,
                    'author': track.author,
                    'uri': track.uri,
                    'track': track.track if hasattr(track, 'track') else track.uri,
                    'artwork_url': getattr(track, 'artwork_url', None) or ""
                }
                prepared_track_data.append(track_dict)


            async with db.session() as session:
                playlists = (
                    await session.execute(
                        select(
                            Playlist.id,
                            Playlist.name,
                            Playlist.description,
                            func.count(PlaylistSong.id).label("song_count"),
                        )
                        .outerjoin(PlaylistSong, PlaylistSong.playlist_id == Playlist.id)
                        .where(Playlist.user_id == user_id)
                        .group_by(
                            Playlist.id,
                            Playlist.name,
                            Playlist.description,
                            Playlist.created_at,
                        )
                        .order_by(Playlist.created_at.desc())
                    )
                ).all()

            if not playlists:
                await interaction.followup.send(
                    f"{EMOJIS.get('alert', '')} You don't have any playlists. "
                    "Create one with `/playlist create`",
                    ephemeral=True
                )
                return


            view = PlaylistSelectView(user_id, playlists, page=0)
            view.prepared_track_data = prepared_track_data                             

            description = f"Add {len(prepared_track_data)} song(s)" if len(prepared_track_data) > 1 else f"Add **{prepared_track_data[0]['title']}**"
            embed = discord.Embed(
                title="Select Playlist",
                description=description + " to a playlist",
                color=0x5C2A2A
            )
            if len(prepared_track_data) == 1:
                embed.add_field(name="Song", value=f"[{prepared_track_data[0]['title']}]({prepared_track_data[0]['uri']})", inline=False)
                embed.add_field(name="Artist", value=prepared_track_data[0]['author'], inline=True)
            else:
                embed.add_field(name="Playlist", value=f"{len(prepared_track_data)} songs", inline=False)
            embed.set_footer(text=f"Total playlists: {len(playlists)}")


            msg = await interaction.channel.send(content=interaction.user.mention, embed=embed, view=view)
            view.message = msg


            await view.wait()

            if not hasattr(view, 'selected_playlist_id'):
                return

            playlist_id = view.selected_playlist_id
            playlist_name = view.selected_playlist_name
            current_count = view.selected_playlist_count


            try:
                await msg.delete()
            except:
                pass


            available_slots = 250 - current_count

            if available_slots <= 0:
                await interaction.followup.send(
                    f"{EMOJIS.get('alert', '')} Playlist is full! Maximum 250 songs allowed.",
                    ephemeral=True
                )
                return


            tracks_to_insert = prepared_track_data[:available_slots]


            processing_count = len(tracks_to_insert)
            processing_msg = await interaction.channel.send(
                f"{EMOJIS.get('alert', '')} Processing {processing_count} song(s) to the database..."
            )


            added_count = 0
            if tracks_to_insert:
                async with db.session() as session:
                    session.add_all(
                        [
                            PlaylistSong(
                                playlist_id=playlist_id,
                                track=track_dict["track"],
                                title=track_dict["title"],
                                author=track_dict["author"],
                                artwork=track_dict["artwork_url"],
                                uri=track_dict["uri"],
                            )
                            for track_dict in tracks_to_insert
                        ]
                    )
                    await session.commit()

                added_count = len(tracks_to_insert)


            try:
                await processing_msg.delete()
            except:
                pass

            if added_count == 0:
                await interaction.channel.send(
                    f"{EMOJIS.get('failure', '')} Could not add songs to playlist."
                )
                return


            if added_count == 1:
                result_text = (
                    f"{EMOJIS.get('success', '')} Successfully saved "
                    f"**{prepared_track_data[0]['title']}** to **{playlist_name}**"
                )
            else:
                result_text = (
                    f"{EMOJIS.get('success', '')} Successfully saved "
                    f"**{added_count} songs** to **{playlist_name}**"
                )

            embed = discord.Embed(
                title=f"{EMOJIS.get('success', '')} Songs Added to Playlist",
                description=result_text,
                color=0x5C2A2A
            )
            embed.set_footer(text=f"Playlist: {playlist_name}")

            await interaction.channel.send(embed=embed)

            logger.info(f"User {user_id} added {added_count} song(s) to playlist {playlist_id}")

        except Exception as e:
            logger.error(f"Error adding to playlist: {e}")
            await interaction.followup.send(
                f"{EMOJIS.get('failure', '')} Failed to add song(s): {str(e)}",
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(PlaylistCommand(bot))
