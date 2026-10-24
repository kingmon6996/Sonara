# Sonara

Sonara is a Discord music bot with Lavalink playback, interactive player controls, queue management, and personal playlists backed by PostgreSQL. Its player uses a single Lavalink client/node; Spotify and other supported links are sent through that same connection.

## Features

- Slash commands for playback, queue control, connection management, and help.
- Search for tracks or provide a supported track/playlist URL.
- Interactive playback controls for rewind, forward, pause, skip, shuffle, speed, volume, filters, and stop.
- Create and manage personal playlists stored in PostgreSQL.
- Unicode emoji controls that work without installing custom emojis on your Discord server.

## Requirements

- Python 3.11 or newer.
- A Discord application and bot token.
- A reachable Lavalink server and its password.
- A PostgreSQL database reachable by the bot.

## 1. Create the Discord bot

1. Create an application in the [Discord Developer Portal](https://discord.com/developers/applications).
2. Open **Bot**, create the bot user, and copy its token. Keep the token private.
3. Under **OAuth2 → URL Generator**, select the `bot` and `applications.commands` scopes.
4. Grant the permissions the bot needs to send messages and embeds, view channels, connect to voice, and speak. Open the generated URL to invite the bot to your server.
5. Enable the **Message Content Intent** under **Bot → Privileged Gateway Intents**. The bot enables this intent in code.

Give the bot permission to view and send messages, embed links, attach files (for player artwork), and connect to and speak in voice channels.

Sonara's user-facing commands are slash commands. They are synchronized when the bot starts; allow a short time for globally registered commands to appear in Discord.

## 2. Set up Lavalink

Run a Lavalink server somewhere the bot can reach over the network. Configure its server password and port, then configure Sonara with the same values below. Ensure the server accepts connections from the machine running the bot.

Lavalink does not necessarily resolve every music URL out of the box. Install and configure the source/plugin support required by the services you want to use, and check the Lavalink server logs if a link or search returns no results. Sonara uses one Lavalink connection for all sources; it does not need a separate Spotify connection.

For a remote Lavalink server using TLS, set `LAVALINK_SECURE=True` and use the corresponding secure port. For a local, non-TLS server, set it to `False`.

## 3. Set up PostgreSQL

The ORM uses SQLAlchemy's async PostgreSQL driver. Set `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DATABASE`, `POSTGRES_SSL`, `POSTGRES_USERNAME`, and `POSTGRES_PASSWORD` to the values for your PostgreSQL server. Use `POSTGRES_SSL=require` for a TLS-required provider such as Supabase, or `POSTGRES_SSL=disable` only for a trusted local development database.

On first successful connection, SQLAlchemy creates the `playlists` and `playlist_songs` tables from the ORM models. The database user needs permission to create tables. The connection endpoint and SSL mode are configurable through the environment variables listed below; no code edits are needed when changing providers.

## 4. Configure the environment

From the project directory, copy `.env.example` to `.env`:

```powershell
Copy-Item .env.example .env
```

Or on macOS/Linux:

```sh
cp .env.example .env
```

Edit `.env` and set the real Discord token, Lavalink connection details, and PostgreSQL credentials:

| Variable | Purpose |
| --- | --- |
| `BOT_TOKEN` | Discord bot token. Required. |
| `LOG_LEVEL` | Set to `debug` for verbose logs, otherwise use `info`. |
| `BOT_VOLUME` | Initial player volume (default: `50`). |
| `BOT_PREFIX` | Reserved configuration value; current commands use slash commands and the code's prefix is `!`. |
| `BASE_COLOUR` | Default embed color as a hexadecimal integer (default: `0x5C2A2A`). |
| `SSL_ENABLED` | Reserved setting; Lavalink TLS is controlled by `LAVALINK_SECURE`. |
| `LAVALINK_HOST` | Hostname or IP address of your Lavalink server. Required. |
| `LAVALINK_PORT` | Lavalink port (default: `2333`). |
| `LAVALINK_PASSWORD` | Lavalink server password. Required. |
| `LAVALINK_REGION` | Lavalink node region label (default: `us_central`). |
| `LAVALINK_SECURE` | `True` when connecting to Lavalink over TLS; otherwise `False`. |
| `POSTGRES_HOST` | PostgreSQL server hostname. Required. |
| `POSTGRES_PORT` | PostgreSQL port (default: `5432`; Supabase pooler commonly uses `6543`). |
| `POSTGRES_DATABASE` | Database name (default: `postgres`). |
| `POSTGRES_SSL` | PostgreSQL SSL mode passed to asyncpg (default: `require`). Use `disable` only on trusted local connections. |
| `POSTGRES_USERNAME` | PostgreSQL username. |
| `POSTGRES_PASSWORD` | PostgreSQL password. |

Do not commit `.env` or share its contents. It is excluded by `.gitignore`. Keep `.env.example` filled with placeholders only.

## 5. Install and run

Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

On macOS/Linux:

```sh
python3 -m venv .venv
source .venv/bin/activate
```

Install the dependencies and start the bot:

```sh
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main.py
```

Keep the process running to keep the bot online. Stop it with `Ctrl+C`.

## Commands

| Command | What it does |
| --- | --- |
| `/play <query>` | Search for a song or load a supported URL. |
| `/queue` | View and manage the current queue. |
| `/connect` | Connect to your voice channel. |
| `/disconnect` | Stop playback and disconnect. |
| `/stop` | Stop playback and clear the queue while staying connected. |
| `/reset` | Recreate the player controls in the original text channel. |
| `/ping` | Check bot latency. |
| `/help` | List help topics; optionally select a command for more details. |
| `/playlist create <name> [description]` | Create a personal playlist. Names are limited to 30 characters. |
| `/playlist show` | List your playlists and their song counts. |
| `/playlist view <playlist_name>` | Browse tracks in one of your playlists. |
| `/playlist add <query>` | Add a track or supported playlist URL to one of your playlists. |
| `/playlist delete <playlist_name>` | Delete one of your playlists and its tracks. |

Join a voice channel before using music commands. The player controls and queue buttons are limited to the users or voice channel specified by each interaction.

## Troubleshooting

- **Bot exits because `BOT_TOKEN` is missing:** Confirm `.env` is in the project root and contains a valid token.
- **Lavalink configuration error:** Check `LAVALINK_HOST` and `LAVALINK_PASSWORD`; ensure the port and TLS setting match your server.
- **Lavalink connects but tracks do not load:** Check Lavalink logs and install the source plugins needed for the URL or search source. Confirm the URL is supported by your configured server.
- **Database connection fails:** Check the PostgreSQL credentials and Supabase pooler access. The current database configuration requires SSL.
- **Playlist tables fail to initialize:** Grant the configured database user permission to create tables, then restart the bot.
- **Slash commands do not appear:** Confirm the bot was invited with the `applications.commands` scope and wait for Discord's global command propagation.
- **Voice connection or playback fails:** Check the bot's server permissions, Lavalink availability, and terminal logs. The bot needs access to the target voice channel and permission to connect and speak.
- **Custom emoji markup is shown instead of emoji:** Ensure `data/emoji.json` is valid JSON and contains standard Unicode emoji values. Restart the bot after changing the file.

## Project layout

```text
Sonara/
├── cogs/
│   ├── comms/       # Slash commands and interactive music UI
│   ├── database/    # SQLAlchemy ORM models and connection maintenance
│   ├── events/      # Discord and Lavalink event handlers
│   └── functions/   # Shared loaders
├── data/
│   ├── emoji.json   # Unicode emoji used by controls and feedback
│   └── help.json    # Text shown by /help
├── decorators/      # Command decorators
├── manage/          # Bot, Lavalink voice client, and shared utilities
├── .env.example     # Configuration template
├── main.py          # Application entry point
└── requirements.txt # Python dependencies
```

## License

The Sonara source code is licensed under the Apache License 2.0; see [LICENSE](./LICENSE). The bundled fonts and background artwork have separate redistribution rights. Include them only under terms you are authorized to grant, and preserve any asset-specific license or attribution notices that apply.
