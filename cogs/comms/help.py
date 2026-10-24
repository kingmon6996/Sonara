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

import json
import os
from typing import TYPE_CHECKING, Optional

import discord
from discord import app_commands
from discord.ext import commands

if TYPE_CHECKING:
    from manage import Bot

HELP_FILE = os.path.join("data", "help.json")


def load_help_data() -> dict:
    try:
        with open(HELP_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"topics": {}}


async def autocomplete_topics(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:

    help_data = load_help_data()
    topics = help_data.get("topics", {})

    filtered = [
        topic for topic in topics.keys()
        if current.lower() in topic.lower()
    ]

    return [
        app_commands.Choice(name=topic, value=topic)
        for topic in sorted(filtered)[:25]
    ]


class HelpCommand(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot: Bot = bot

    @app_commands.command(
        name="help",
        description="Get help on music bot commands. Provide a command name for detailed info.",
    )
    @app_commands.autocomplete(command=autocomplete_topics)
    async def help_command(
        self,
        interaction: discord.Interaction,
        command: Optional[str] = None,
    ):
        help_data = load_help_data()
        topics = help_data.get("topics", {})

        if not topics:
            await interaction.response.send_message(
                "Help data not available.",
                ephemeral=True
            )
            return

        if not command:
            embed = discord.Embed(
                title="Music Bot Help",
                description="Use `/help <command>` to get detailed information about a specific command.",
                color=0x5C2A2A
            )

            for topic, data in topics.items():
                short_desc = data.get("short_description", "No description available")
                embed.add_field(
                    name=f"• {topic.title()}",
                    value=short_desc,
                    inline=False
                )

            embed.set_footer(text="Use /help <command> to learn more about a specific command")

            await interaction.response.send_message(embed=embed)
            return


        command_lower = command.lower()


        topic_data = None
        actual_topic = None
        for key, value in topics.items():
            if key.lower() == command_lower:
                topic_data = value
                actual_topic = key
                break

        if not topic_data:
            await interaction.response.send_message(
                f" Command **{command}** not found. Use `/help` to see all available commands.",
                ephemeral=True
            )
            return


        embed = discord.Embed(
            title=f"{actual_topic.title()} Command Help",
            description=topic_data.get("description", "No description available"),
            color=0x5C2A2A
        )


        usage = topic_data.get("usage", "No usage information available")
        embed.add_field(name="Usage", value=f"`{usage}`", inline=False)


        examples = topic_data.get("examples", [])
        if examples:
            examples_text = "\n".join(f"`{ex}`" for ex in examples)
            embed.add_field(name="Examples", value=examples_text, inline=False)


        notes = topic_data.get("notes", [])
        if notes:
            notes_text = "\n".join(f"• {note}" for note in notes)
            embed.add_field(name="Notes", value=notes_text, inline=False)

        embed.set_footer(text=f"Use /help to see other commands")

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(HelpCommand(bot))
