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
import discord
from discord import ui
import requests
import random
import io
import json
import time
from manage import format_duration
from ._card import create_card, shorten_title, resize_and_round
from lavalink.filters import Timescale, Equalizer, LowPass, Tremolo, Vibrato, Rotation, Distortion, ChannelMix, Karaoke

def load_emojis():
    try:
        with open('data/emoji.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading emojis: {e}")
        return {}


EMOJIS = load_emojis()


class CooldownManager:

    def __init__(self, cooldown_seconds: float = 5.0):
        self.cooldown_seconds = cooldown_seconds
        self.cooldowns = {}                                   

    def is_on_cooldown(self, guild_id: int, action: str) -> bool:

        if guild_id not in self.cooldowns:
            return False

        last_time = self.cooldowns[guild_id].get(action, 0)
        return (time.time() - last_time) < self.cooldown_seconds

    def get_remaining_time(self, guild_id: int, action: str) -> float:

        if guild_id not in self.cooldowns:
            return 0

        last_time = self.cooldowns[guild_id].get(action, 0)
        remaining = self.cooldown_seconds - (time.time() - last_time)
        return max(0, remaining)

    def apply_cooldown(self, guild_id: int, action: str) -> None:

        if guild_id not in self.cooldowns:
            self.cooldowns[guild_id] = {}
        self.cooldowns[guild_id][action] = time.time()


cooldown_manager = CooldownManager(cooldown_seconds=5.0)


class RewindButton(ui.Button):
    def __init__(self, bot, player, view):
        super().__init__(
            label="Rewind",
            emoji=EMOJIS.get("rewind"),
            style=discord.ButtonStyle.secondary,
            row=1,
        )
        self.bot = bot
        self.player = player
        self.parent_view = view

    async def callback(self, interaction: discord.Interaction):

        if not self.parent_view.can_use_controls(interaction):
            await interaction.response.send_message(
                f"You must be in the voice channel where the bot is playing to use controls.",
                ephemeral=True
            )
            return

        await interaction.response.defer()
        guild_id = interaction.guild_id


        if cooldown_manager.is_on_cooldown(guild_id, "backward"):
            remaining = cooldown_manager.get_remaining_time(guild_id, "backward")
            await interaction.followup.send(
                f"Please wait {remaining:.1f}s before using rewind again.",
                ephemeral=True
            )
            return

        cooldown_manager.apply_cooldown(guild_id, "backward")

        if self.player.current:
            new_pos = max(0, self.player.position - 10000)
            await self.player.seek(new_pos)
            current_time = format_duration(new_pos)
            await interaction.followup.send(
                f"Skipped backward to {current_time}",
                ephemeral=True
            )


            try:
                await interaction.channel.send(f"*{interaction.user.name} rewound the track*")
            except Exception:
                pass
        else:
            await interaction.followup.send(
                f"No track is currently playing.",
                ephemeral=True
            )
        await self.parent_view.update_container()


class SpeedButton(ui.Button):
    def __init__(self, bot, player, view):
        super().__init__(
            label="Speed",
            emoji=EMOJIS.get("speed"),
            style=discord.ButtonStyle.secondary,
            row=1,
        )
        self.bot = bot
        self.player = player
        self.parent_view = view

    async def callback(self, interaction: discord.Interaction):

        if not self.parent_view.can_use_controls(interaction):
            await interaction.response.send_message(
                f"You must be in the voice channel where the bot is playing to use controls.",
                ephemeral=True
            )
            return
        await interaction.response.send_modal(SpeedModal(self.player, self.parent_view))


class ReplayButton(ui.Button):
    def __init__(self, bot, player, view):
        super().__init__(
            label="Replay",
            emoji=EMOJIS.get("replay"),
            style=discord.ButtonStyle.secondary,
            row=1,
        )
        self.bot = bot
        self.player = player
        self.parent_view = view

    async def callback(self, interaction: discord.Interaction):

        if not self.parent_view.can_use_controls(interaction):
            await interaction.response.send_message(
                f"You must be in the voice channel where the bot is playing to use controls.",
                ephemeral=True
            )
            return
        await interaction.response.defer()

        if self.player.current:

            current_track = self.player.current
            self.player.queue.insert(0, current_track)
            await interaction.followup.send(
                f"Added **{current_track.title}** to the next position",
                ephemeral=True
            )


            try:
                await interaction.channel.send(f"*{interaction.user.name} replayed the current track*")
            except Exception:
                pass
        else:
            await interaction.followup.send(
                f"No track is currently playing.",
                ephemeral=True
            )
        await self.parent_view.update_container()


class VolumeUpButton(ui.Button):
    def __init__(self, bot, player, view):
        super().__init__(label="Volume⠀", style=discord.ButtonStyle.secondary, row=1)
        self.bot = bot
        self.player = player
        self.parent_view = view
        self.update_emoji()

    def update_emoji(self):
        current_vol = getattr(self.player, 'volume', 100)
        if current_vol < 50:
            self.emoji = EMOJIS.get("lowvolicon")
        elif 50 <= current_vol <= 100:
            self.emoji = EMOJIS.get("midvolicon")
        else:
            self.emoji = EMOJIS.get("highvolicon")

    async def callback(self, interaction: discord.Interaction):

        if not self.parent_view.can_use_controls(interaction):
            await interaction.response.send_message(
                f"You must be in the voice channel where the bot is playing to use controls.",
                ephemeral=True
            )
            return
        await interaction.response.send_modal(VolumeModal(self.player, self.parent_view))


class SaveButton(ui.Button):
    def __init__(self, bot, player, view):
        super().__init__(
            label="Save",
            emoji=EMOJIS.get("save"),
            style=discord.ButtonStyle.secondary,
            row=2,
        )
        self.bot = bot
        self.player = player
        self.parent_view = view

    async def callback(self, interaction: discord.Interaction):

        if not self.parent_view.can_use_controls(interaction):
            await interaction.response.send_message(
                f"You must be in the voice channel where the bot is playing to use controls.",
                ephemeral=True
            )
            return
        await interaction.response.defer()
        await interaction.followup.send(
            f"Save feature not yet added",
            ephemeral=True
        )
        await self.parent_view.update_container()


class ForwardButton(ui.Button):
    def __init__(self, bot, player, view):
        super().__init__(
            label="Forward",
            emoji=EMOJIS.get("forward"),
            style=discord.ButtonStyle.secondary,
            row=1,
        )
        self.bot = bot
        self.player = player
        self.parent_view = view

    async def callback(self, interaction: discord.Interaction):

        if not self.parent_view.can_use_controls(interaction):
            await interaction.response.send_message(
                f"You must be in the voice channel where the bot is playing to use controls.",
                ephemeral=True
            )
            return
        await interaction.response.defer()
        guild_id = interaction.guild_id

        if cooldown_manager.is_on_cooldown(guild_id, "forward"):
            remaining = cooldown_manager.get_remaining_time(guild_id, "forward")
            await interaction.followup.send(
                f"Please wait {remaining:.1f}s before using forward again.",
                ephemeral=True
            )
            return

        cooldown_manager.apply_cooldown(guild_id, "forward")

        if self.player.current:
            new_pos = min(self.player.current.duration, self.player.position + 10000)
            await self.player.seek(new_pos)
            current_time = format_duration(new_pos)
            await interaction.followup.send(
                f"Skipped forward to {current_time}",
                ephemeral=True
            )


            try:
                await interaction.channel.send(f"*{interaction.user.name} skipped forward*")
            except Exception:
                pass
        else:
            await interaction.followup.send(
                f"No track is currently playing.",
                ephemeral=True
            )
        await self.parent_view.update_container()


class PauseResumeButton(ui.Button):
    def __init__(self, bot, player, view):
        super().__init__(
            label="Pause",
            emoji=EMOJIS.get("pause"),
            style=discord.ButtonStyle.secondary,
            row=2,
        )
        self.bot = bot
        self.player = player
        self.parent_view = view

    async def callback(self, interaction: discord.Interaction):

        if not self.parent_view.can_use_controls(interaction):
            await interaction.response.send_message(
                f"You must be in the voice channel where the bot is playing to use controls.",
                ephemeral=True
            )
            return
        await interaction.response.defer()

        if self.player.paused:
            await self.player.set_pause(False)
            self.emoji = EMOJIS.get("pause")
            self.label = "Pause"
            await interaction.followup.send(
                f"Resumed playback",
                ephemeral=True
            )
            action_text = "resumed playback"
        else:
            await self.player.set_pause(True)
            self.emoji = EMOJIS.get("resume")
            self.label = "Resume⠀"
            await interaction.followup.send(
                f"Paused playback",
                ephemeral=True
            )
            action_text = "paused playback"


        action_text = "resumed playback" if not self.player.paused else "paused playback"
        try:
            await interaction.channel.send(f"*{interaction.user.name} {action_text}*")
        except Exception:
            pass

        await self.parent_view.update_container()

        await self.parent_view.update_container()


class SkipButton(ui.Button):

    def __init__(self, bot, player, view):
        super().__init__(
            label="Next",
            emoji=EMOJIS.get("nexttrack"),
            style=discord.ButtonStyle.secondary,
            row=2,
        )
        self.bot = bot
        self.player = player
        self.parent_view = view

    async def callback(self, interaction: discord.Interaction):

        if not self.parent_view.can_use_controls(interaction):
            await interaction.response.send_message(
                f"You must be in the voice channel where the bot is playing to use controls.",
                ephemeral=True
            )
            return
        await interaction.response.defer()

        if self.player.queue:

            next_track = self.player.queue[0] if self.player.queue else None
            await self.player.skip()


            if self.parent_view.message:
                try:
                    await self.parent_view.message.delete()
                except Exception:
                    pass


            if next_track:
                await interaction.followup.send(
                    f"Skipped to: **{next_track.title}**",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    f"Skipped to next track",
                    ephemeral=True
                )


            try:
                await interaction.channel.send(f"*{interaction.user.name} skipped to the next track*")
            except Exception:
                pass
        else:
            await interaction.followup.send(
                f"Nothing in the queue to skip to.",
                ephemeral=True
            )
        await self.parent_view.update_container()


class ShuffleButton(ui.Button):
    def __init__(self, bot, player, view):
        super().__init__(
            label="Shuffle",
            emoji=EMOJIS.get("shuffle"),
            style=discord.ButtonStyle.secondary,
            row=2,
        )
        self.bot = bot
        self.player = player
        self.parent_view = view

    async def callback(self, interaction: discord.Interaction):

        if not self.parent_view.can_use_controls(interaction):
            await interaction.response.send_message(
                f"You must be in the voice channel where the bot is playing to use controls.",
                ephemeral=True
            )
            return
        await interaction.response.defer()

        if self.player.queue:

            queue_list = list(self.player.queue)
            random.shuffle(queue_list)

            self.player.queue.clear()
            for track in queue_list:
                self.player.queue.append(track)
            await interaction.followup.send(
                f"Shuffled queue ({len(queue_list)} tracks)",
                ephemeral=True
            )


            try:
                await interaction.channel.send(f"*{interaction.user.name} shuffled the queue*")
            except Exception:
                pass
        else:
            await interaction.followup.send(
                f"Queue is empty, nothing to shuffle.",
                ephemeral=True
            )
        await self.parent_view.update_container()


class DisconnectButton(ui.Button):
    def __init__(self, bot, player, view):
        super().__init__(
            label="Stop",
            emoji=EMOJIS.get("stop"),
            style=discord.ButtonStyle.secondary,
            row=2,
        )
        self.bot = bot
        self.player = player
        self.parent_view = view

    async def callback(self, interaction: discord.Interaction):

        if not self.parent_view.can_use_controls(interaction):
            await interaction.response.send_message(
                f"You must be in the voice channel where the bot is playing to use controls.",
                ephemeral=True
            )
            return
        await interaction.response.defer()

        if self.player.queue:
            self.player.queue.clear()
        await self.player.stop()


        if self.parent_view.message:
            try:
                await self.parent_view.message.delete()
            except Exception:
                pass

        await interaction.followup.send(
            f"Stopped playback and cleared queue",
            ephemeral=True
        )


        try:
            await interaction.channel.send(f"*{interaction.user.name} stopped playback*")
        except Exception:
            pass


class VolumeModal(ui.Modal, title="Set Volume"):
    volume_input = ui.TextInput(
        label="Volume (1-200)",
        placeholder="Enter volume between 1 and 200",
        min_length=1,
        max_length=3,
        required=True
    )

    def __init__(self, player, parent_view):
        super().__init__()
        self.player = player
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction):
        try:
            volume = int(self.volume_input.value)
            if not 1 <= volume <= 200:
                await interaction.response.send_message(
                    f"Volume must be between 1 and 200!",
                    ephemeral=True
                )
                return

            await self.player.set_volume(volume)
            await interaction.response.send_message(
                f"Volume set to **{volume}%**",
                ephemeral=True
            )


            try:
                await interaction.channel.send(f"*{interaction.user.name} set volume to {volume}%*")
            except Exception:
                pass

            await self.parent_view.update_container()
        except ValueError:
            await interaction.response.send_message(
                f"Please enter a valid number!",
                ephemeral=True
            )


class SpeedModal(ui.Modal, title="Set Speed"):
    speed_input = ui.TextInput(
        label="Speed (0.5-2.0)",
        placeholder="Enter speed between 0.5 and 2.0",
        min_length=1,
        max_length=3,
        required=True
    )

    def __init__(self, player, parent_view):
        super().__init__()
        self.player = player
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction):
        try:
            speed = float(self.speed_input.value)
            if not 0.5 <= speed <= 2.0:
                await interaction.response.send_message(
                    f"Speed must be between 0.5 and 2.0!",
                    ephemeral=True
                )
                return


            timescale = Timescale(speed=speed, pitch=1.0)
            await self.player.set_filters(timescale)

            await interaction.response.send_message(
                f"Speed set to **{speed}x**",
                ephemeral=True
            )


            try:
                await interaction.channel.send(f"*{interaction.user.name} set speed to {speed}x*")
            except Exception:
                pass

            await self.parent_view.update_container()
        except ValueError:
            await interaction.response.send_message(
                f"Please enter a valid number!",
                ephemeral=True
            )


async def apply_lofi_filter(player):
    await player.clear_filters()
    timescale = Timescale(speed=0.9, pitch=0.9)
    lowpass = LowPass(smoothing=20.0)
    eq = Equalizer()
    eq.update(bands=[
        (0, 0.15),   
        (1, 0.10),
        (2, 0.05),
        (13, -0.10), 
        (14, -0.15)
    ])
    await player.set_filters(timescale, lowpass, eq)

async def apply_karoake_filter(player):
    await player.clear_filters()
    karoake = Karaoke(level=1.0, mono_level=1.0, filter_band=220.0, filter_width=100.0)
    await player.set_filters(karoake)

async def apply_nightcore_filter(player):
    await player.clear_filters()
    timescale = Timescale(speed=1.25, pitch=1.2)
    await player.set_filters(timescale)

async def apply_slowed_reverb_filter(player):
    await player.clear_filters()
    timescale = Timescale(speed=0.8, pitch=0.8)
    await player.set_filters(timescale)

async def apply_treble_filter(player):
    await player.clear_filters()
    eq = Equalizer()
    eq.update(bands=[
        (12, 0.15),
        (13, 0.2),
        (14, 0.25)
    ])
    await player.set_filters(eq)

[
                {
                    "band": 0,
                    "gain": 0.3
                },
                {
                    "band": 1,
                    "gain": 0.25
                },
                {
                    "band": 2,
                    "gain": 0.2
                }
            ]

async def apply_bassboost_filter(player):
    await player.clear_filters()
    eq = Equalizer()
    eq.update(bands=[
        (0, 0.3),
        (1, 0.25),
        (2, 0.2)
    ])
    await player.set_filters(eq)

async def apply_8d_filter(player):
    await player.clear_filters()
    rotation = Rotation(rotation_hz=0.2)
    await player.set_filters(rotation)

async def apply_distorted_filter(player):
    await player.clear_filters()
    distortion = Distortion(
        sin_scale=0.8,
        cos_scale=0.8,
        tan_scale=0.5,
        scale=1.2
    )
    await player.set_filters(distortion)

async def apply_vibrato_filter(player):
    await player.clear_filters()
    vibrato = Vibrato(
        frequency=4.0,
        depth=0.75
    )
    await player.set_filters(vibrato)

async def apply_tremolo_filter(player):
    await player.clear_filters()
    tremolo = Tremolo(
        frequency=5.0,
        depth=0.7
    )
    await player.set_filters(tremolo)

async def apply_vaporwave_filter(player):
    await player.clear_filters()

    timescale = Timescale(speed=0.85, pitch=0.8)

    eq = Equalizer()
    eq.update(bands=[
        (0, 0.2),
        (1, 0.15),
        (13, -0.2),
        (14, -0.25)
    ])

    await player.set_filters(timescale, eq)

FILTER_FUNCTIONS = {
    "Lofi": apply_lofi_filter,
    "Karaoke": apply_karoake_filter,
    "Nightcore": apply_nightcore_filter,
    "Slowed/Reverb": apply_slowed_reverb_filter,
    "Treble": apply_treble_filter,
    "Bass Boost": apply_bassboost_filter,
    "8D": apply_8d_filter,
    "Distorted": apply_distorted_filter,
    "Vibrato": apply_vibrato_filter,
    "Tremolo": apply_tremolo_filter,
    "Vaporwave": apply_vaporwave_filter,
}


class FilterSelect(ui.Select):
    def __init__(self, bot, player, view):
        options = [
            discord.SelectOption(
                label="Reset Filters",
                value="reset",
                emoji=EMOJIS.get("delete"),
            )
        ]
        for filter_name in FILTER_FUNCTIONS.keys():
            options.append(
                discord.SelectOption(
                    label=filter_name.capitalize(),
                    value=filter_name,
                    emoji=EMOJIS.get("settings"),
                )
            )

        super().__init__(
            placeholder="Select Filter",
            options=options,
            min_values=1,
            max_values=1,
            row=0,
        )
        self.bot = bot
        self.player = player
        self.parent_view = view

    async def callback(self, interaction: discord.Interaction):

        if not self.parent_view.can_use_controls(interaction):
            await interaction.response.send_message(
                f"You must be in the voice channel where the bot is playing to use controls.",
                ephemeral=True
            )
            return
        await interaction.response.defer()
        guild_id = interaction.guild_id


        if cooldown_manager.is_on_cooldown(guild_id, "filter"):
            remaining = cooldown_manager.get_remaining_time(guild_id, "filter")
            await interaction.followup.send(
                f"Please wait {remaining:.1f}s before changing filter again.",
                ephemeral=True
            )
            return

        cooldown_manager.apply_cooldown(guild_id, "filter")

        selected_filter = self.values[0]
        if selected_filter != "reset" and selected_filter in FILTER_FUNCTIONS:
            await FILTER_FUNCTIONS[selected_filter](self.player)
            await interaction.followup.send(
                f"Applied **{selected_filter}** filter",
                ephemeral=True
            )


            try:
                await interaction.channel.send(f"*{interaction.user.name} applied {selected_filter} filter*")
            except Exception:
                pass
        else:
            await self.player.clear_filters()
            await interaction.followup.send(
                f"Filters cleared",
                ephemeral=True
            )


            try:
                await interaction.channel.send(f"*{interaction.user.name} cleared filters*")
            except Exception:
                pass
        await self.parent_view.update_container()


class TrackView(ui.LayoutView):
    def __init__(self, bot, player, author, track_data=None, card_file=None):
        super().__init__(timeout=14.5 * 60)
        self.bot = bot
        self.player = player
        self.category = None
        self.duration = None
        self.author = author
        self.confirmed = None
        self.track_data = track_data or {}
        self.card_file = card_file
        self.message = None
        self.update_task = None
        self.current_track_id = player.current.uri if player.current else None


        self.previous_button_states = {
            "skip_disabled": True,
            "shuffle_disabled": True,
        }

        self.main_container = self.MainContainer(self.category, self.duration, self.author, self, self.track_data, self.card_file, self.player)
        self.add_item(self.main_container)

    def can_use_controls(self, interaction: discord.Interaction) -> bool:

        if not interaction.user.voice or not interaction.user.voice.channel:
            return False
        if self.player.channel_id != interaction.user.voice.channel.id:
            return False
        return True

    async def update_container(self):
        if not self.message or not self.main_container:
            return

        try:
            if self.player.current:
                current_pos = format_duration(self.player.position)
                total_duration = format_duration(int(self.player.current.duration)) if self.player.current.duration else "00:00"
                current_vol = getattr(self.player, 'volume', 100)


                self.track_data.update({
                    "current_duration": current_pos,
                    "total_duration": total_duration,
                    "current_volume": current_vol,
                    "position_ms": self.player.position,
                    "duration_ms": int(self.player.current.duration) if self.player.current.duration else 0,
                })


                for item in self.main_container.children:
                    if isinstance(item, self.MainContainer.DurationData):
                        item.update_data(self.track_data)
                    elif isinstance(item, self.MainContainer.VolumeData):
                        item.update_data(self.track_data)


                self.update_button_states()

                await self.message.edit(view=self)
        except discord.NotFound:
            pass
        except Exception:
            pass

    def update_button_states(self):

        has_queue = bool(self.player.queue)


        new_states = {
            "skip_disabled": not has_queue,
            "shuffle_disabled": not has_queue,
        }


        if new_states == self.previous_button_states:
            return


        for item in self.children:
            if isinstance(item, discord.ui.ActionRow):
                for button in item.children:
                    if isinstance(button, SkipButton):
                        button.disabled = new_states["skip_disabled"]
                    elif isinstance(button, ShuffleButton):
                        button.disabled = new_states["shuffle_disabled"]


        self.previous_button_states = new_states

    async def start_update_loop(self):

        try:
            while self.message:

                if self.player.current:
                    if self.player.current.uri != self.current_track_id:
                        self.current_track_id = self.player.current.uri if self.player.current else None

                        if self.message:
                            try:
                                await self.message.delete()
                            except Exception:
                                pass
                        return
                else:

                    if self.message:
                        try:
                            await self.message.delete()
                        except Exception:
                            pass
                    return

                try:
                    await self.update_container()
                except discord.NotFound:
                    return
                except Exception:
                    pass

                await asyncio.sleep(5)
        except asyncio.CancelledError:
            pass

    async def on_timeout(self):

        if self.player.current:

            self.timeout = 14.5 * 60
        else:

            if self.message:
                try:
                    await self.message.delete()
                except Exception:
                    pass

            if self.update_task:
                self.update_task.cancel()

    async def delete_old_container(self):
        if self.message:
            try:
                await self.message.delete()
            except Exception:
                pass


    class MainContainer(ui.Container):
        def __init__(self, category, duration, author, view, track_data, card_file, player):
            super().__init__()
            self.category = category
            self.duration = duration
            self.author = author
            self.root_view = view
            self.track_data = track_data
            self.card_file = card_file
            self.player = player

            self.add_item(self.SongDetails(self.root_view, self.track_data))
            if self.card_file:
                self.add_item(discord.ui.MediaGallery(
                    discord.MediaGalleryItem(
                        media="attachment://card.png",
                        ),
                ))
                self.add_item(discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small))


            self.add_item(self.DurationData(self.root_view, self.track_data))
            self.add_item(ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small))
            self.add_item(self.VolumeData(self.root_view, self.track_data))
            self.add_item(ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small))
            self.add_item(discord.ui.ActionRow(FilterSelect(self.player, self.player, self.root_view)))
            self.add_item(ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small))
            self.add_item(discord.ui.ActionRow(
                RewindButton(self.player, self.player, self.root_view),
                SpeedButton(self.player, self.player, self.root_view),
                VolumeUpButton(self.player, self.player, self.root_view),
                ReplayButton(self.player, self.player, self.root_view),
                ForwardButton(self.player, self.player, self.root_view),
            ))
            self.add_item(ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small))
            self.add_item(discord.ui.ActionRow(
                PauseResumeButton(self.player, self.player, self.root_view),
                DisconnectButton(self.player, self.player, self.root_view),
                SkipButton(self.player, self.player, self.root_view),
                ShuffleButton(self.player, self.player, self.root_view),
                SaveButton(self.player, self.player, self.root_view),
            ))
        def recreate_sections(self, track_data):
            self.song_details.update_data(track_data)
            self.song_data.update_data(track_data)

        class DurationData(ui.TextDisplay):
            def __init__(self, root_view, track_data):
                super().__init__(content="")
                self.root_view = root_view
                self.track_data = track_data
                self.update_display()

            def update_display(self):
                current_duration = self.track_data.get("current_duration", "00:00")
                total_duration = self.track_data.get("total_duration", "00:00")
                position_ms = self.track_data.get("position_ms", 0)
                duration_ms = self.track_data.get("duration_ms", 0)


                if duration_ms > 0:
                    progress = (position_ms / duration_ms) * 100
                    filled_bars = int((progress / 100) * 20)
                else:
                    filled_bars = 0


                fill_bar = EMOJIS.get("barfill", "█")
                knob = EMOJIS.get("barknob", "")
                empty_bar = EMOJIS.get("barempty", "░")


                if filled_bars > 0:
                    bars = (fill_bar * (filled_bars - 1)) + knob + (empty_bar * (20 - filled_bars))
                else:
                    bars = knob + (empty_bar * 19)

                self.content = f"{current_duration} ⠀⠀ {bars} ⠀⠀ {total_duration}"

            def update_data(self, track_data):
                self.track_data = track_data
                self.update_display()

        class VolumeData(ui.TextDisplay):
            def __init__(self, root_view, track_data):
                super().__init__(content="")
                self.root_view = root_view
                self.track_data = track_data
                self.update_display()

            def update_display(self):
                current_volume = self.track_data.get("current_volume", 100)

                full_bars = current_volume // 10
                remainder = current_volume % 10
                has_half_bar = remainder >= 5
                empty_bars = 20 - full_bars - (1 if has_half_bar else 0)

                low_icon = EMOJIS.get("lowvolicon", "")
                high_icon = EMOJIS.get("highvolicon", "")
                full_bar = EMOJIS.get("volbarhigh", "█")
                half_bar = EMOJIS.get("volbarmid", "▌")
                empty_bar = EMOJIS.get("volbarlow", "░")

                bars = (full_bar * full_bars) + (half_bar if has_half_bar else "") + (empty_bar * empty_bars)

                self.content = f"{low_icon} ⠀⠀⠀ {bars} ⠀⠀ {high_icon} `{current_volume}%`"

            def update_data(self, track_data):
                self.track_data = track_data
                self.update_display()

        class SongDetails(ui.TextDisplay):
            def __init__(self, root_view, track_data):
                super().__init__(content="")
                self.root_view = root_view
                self.track_data = track_data
                self.update_display()

            def update_display(self):
                song_name = self.track_data.get("name", "Unknown")
                self.content = (
                    f"## {EMOJIS.get('nowplaying', '')} Now Playing: "
                    f"[{song_name}]({self.track_data.get('uri', '')})"
                )

            def update_data(self, track_data):
                self.track_data = track_data
                self.update_display()
