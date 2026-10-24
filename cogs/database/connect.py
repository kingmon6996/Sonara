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
from typing import TYPE_CHECKING

from discord.ext import commands

from ._database import db

if TYPE_CHECKING:
    from manage import Bot

logger = logging.getLogger(__name__)


async def initialize_database(bot: "Bot") -> bool:


    try:

        logger.info("Initializing database connection...")
        connected = await db.connect()

        if not connected:
            logger.error("Failed to initialize database connection")
            return False


        if not await db.check_connection():
            logger.error("Database connection verification failed")
            return False

        logger.info("Database initialized successfully")
        return True

    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        return False


async def connection_maintenance_loop(bot: "Bot", check_interval: int = 30) -> None:


    logger.info(f"Starting connection maintenance loop (check every {check_interval}s)")

    while True:
        try:
            await asyncio.sleep(check_interval)


            is_healthy = await db.check_connection()

            if not is_healthy:
                logger.warning("Database connection unhealthy, attempting to refresh...")
                refresh_success = await db.refresh_connection()

                if refresh_success:
                    logger.info("Database connection refreshed successfully")
                else:
                    logger.error("Failed to refresh database connection")
            else:
                logger.debug("Database connection is healthy")

        except asyncio.CancelledError:
            logger.info("Connection maintenance loop cancelled")
            break

        except Exception as e:
            logger.error(f"Error in connection maintenance loop: {e}")


class DatabaseCog(commands.Cog):


    def __init__(self, bot: "Bot"):
        self.bot: "Bot" = bot
        self.maintenance_task = None

    @commands.Cog.listener()
    async def on_ready(self):

        logger.info("Bot is ready, initializing database connection...")

        try:

            initialized = await initialize_database(self.bot)

            if not initialized:
                logger.error("Database initialization failed on bot ready")
                return


            if self.maintenance_task is None or self.maintenance_task.done():
                self.maintenance_task = self.bot.loop.create_task(
                    connection_maintenance_loop(self.bot, check_interval=30)
                )
                logger.info("Database maintenance loop started")

        except Exception as e:
            logger.error(f"Error during bot ready database setup: {e}")


async def setup(bot: "Bot"):


    await bot.add_cog(DatabaseCog(bot))
