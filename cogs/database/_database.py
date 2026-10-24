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



import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncGenerator

from dotenv import load_dotenv
from sqlalchemy import BigInteger, CHAR, ForeignKey, Integer, Text, func, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.engine import URL

load_dotenv()

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


class Playlist(Base):
    __tablename__ = "playlists"

    id: Mapped[str] = mapped_column(CHAR(16), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    songs: Mapped[list["PlaylistSong"]] = relationship(
        back_populates="playlist",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class PlaylistSong(Base):
    __tablename__ = "playlist_songs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    playlist_id: Mapped[str] = mapped_column(
        CHAR(16), ForeignKey("playlists.id", ondelete="CASCADE"), nullable=False
    )
    track: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[str] = mapped_column(Text, nullable=False)
    artwork: Mapped[str | None] = mapped_column(Text)
    uri: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    playlist: Mapped["Playlist"] = relationship(back_populates="songs")


class Database:


    def __init__(self) -> None:
        self.engine: AsyncEngine | None = None
        self.session_factory: async_sessionmaker[AsyncSession] | None = None
        self._is_connected = False

    def _create_engine(self) -> AsyncEngine:
        url = URL.create(
            drivername="postgresql+asyncpg",
            username=os.getenv("POSTGRES_USERNAME", "postgres"),
            password=os.getenv("POSTGRES_PASSWORD", ""),
            host=os.getenv("POSTGRES_HOST"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            database=os.getenv("POSTGRES_DATABASE", "postgres"),
            query={"prepared_statement_cache_size": "0"},
        )
        return create_async_engine(
            url,
            connect_args={
                "ssl": os.getenv("POSTGRES_SSL", "require"),
                "statement_cache_size": 0,
            },
            pool_pre_ping=True,
            pool_size=20,
            max_overflow=0,
            pool_timeout=10,
        )

    async def connect(self) -> bool:
        if self.engine is not None:
            logger.info("Database engine already exists, reusing it")
            self._is_connected = True
            return True

        try:
            self.engine = self._create_engine()
            self.session_factory = async_sessionmaker(
                self.engine, expire_on_commit=False
            )
            async with self.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            self._is_connected = True
            logger.info("Connected to PostgreSQL database")
            return True
        except Exception as e:
            logger.error("Failed to connect to PostgreSQL database: %s", e)
            self._is_connected = False
            if self.engine is not None:
                await self.engine.dispose()
            self.engine = None
            self.session_factory = None
            return False

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        if self.session_factory is None:
            raise RuntimeError("Database session factory is not initialized")
        async with self.session_factory() as session:
            yield session

    async def check_connection(self) -> bool:
        if self.engine is None:
            logger.warning("Database engine is not initialized")
            return False

        try:
            async with self.engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
            self._is_connected = True
            return True
        except Exception as e:
            logger.error("Database connection check failed: %s", e)
            self._is_connected = False
            return False

    async def refresh_connection(self) -> bool:
        try:
            old_engine = self.engine
            self.engine = None
            self.session_factory = None
            self._is_connected = False

            if old_engine is not None:
                await old_engine.dispose()

            return await self.connect()
        except Exception as e:
            logger.error("Failed to refresh database connection: %s", e)
            self._is_connected = False
            return False

    async def close_connection(self) -> bool:
        try:
            if self.engine is not None:
                await self.engine.dispose()
            self.engine = None
            self.session_factory = None
            self._is_connected = False
            logger.info("Database engine disposed")
            return True
        except Exception as e:
            logger.error("Failed to dispose database engine: %s", e)
            return False

    def is_connected(self) -> bool:
        return self._is_connected and self.engine is not None


db = Database()
