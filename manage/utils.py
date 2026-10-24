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
import logging
import os
from dataclasses import dataclass

import discord
from dotenv import load_dotenv
from .variable import EnvironmentKeys

load_dotenv()


def get_embed_color() -> int:
    try:
        color_hex = os.getenv(EnvironmentKeys.BASE_COLOUR, "0x5C2A2A")
        return int(color_hex, 16)
    except (ValueError, TypeError):
        return 0x5C2A2A


def format_duration(ms: int) -> str:
    try:
        if isinstance(ms, str):
            ms = int(ms)

        if ms < 0 or ms > 10**15:
            return "00:00"

        seconds = ms // 1000
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"
    except (ValueError, TypeError):
        return "00:00"


@dataclass
class Error:
    message: str

    def __str__(self):
        return self.message


@dataclass
class Success:
    message: str

    def __str__(self):
        return self.message
