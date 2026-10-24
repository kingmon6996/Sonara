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
from functools import wraps

from manage import Error


def debounce_action(delay: float = 0.5):
    def decorator(fn):
        @wraps(fn)
        async def wrapper(self, interaction, guild, user, *args, **kwargs):
            lock = self._action_locks[guild.id]
            if lock.locked():
                return Error("Too many button presses at once—please wait a moment.")
            await lock.acquire()

            logging.debug(f"[{guild.id}] lock acquired by {user.display_name}")
            asyncio.create_task(self._release_lock_after(lock, delay))
            return await fn(self, interaction, guild, user, *args, **kwargs)

        return wrapper

    return decorator


def ensure_voice(fn):
    @wraps(fn)
    async def wrapper(self, interaction, guild, user, *args, **kwargs):
        err = await self.voice_precheck(user, guild)
        if err:
            return Error(err)
        return await fn(self, interaction, guild, user, *args, **kwargs)

    return wrapper
