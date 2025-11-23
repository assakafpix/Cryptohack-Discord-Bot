# CryptoHack Discord Bot

A Discord bot that tracks CryptoHack users and announces when they solve new challenges.

## Features

- **Track Users**: Add CryptoHack users to monitor their progress
- **Auto-Announcements**: Automatically announces new challenge solves
- **First Blood Badge**: Special recognition 🩸 for first solver in the server
- **Leaderboard**: Server ranking based on CryptoHack scores
- **Challenge Lookup**: See who in your server solved specific challenges
- **Profile Viewer**: Quick access to user stats

## Commands

| Command | Description |
|---------|-------------|
| `/adduser <username>` | Add a CryptoHack user to track |
| `/removeuser <username>` | Remove a user from tracking |
| `/users` | List all tracked users |
| `/leaderboard` | Show server leaderboard sorted by score |
| `/profile <username>` | Display a user's CryptoHack profile |
| `/challenge <name>` | See who solved a specific challenge |
| `/setchannel <channel>` | Set channel for solve announcements |
| `/refresh` | Manually check for new solves |

## Setup

### 1. Create a Discord Bot

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application" and give it a name
3. Go to the "Bot" section and click "Add Bot"
4. Copy the bot token (you'll need this later)
5. Enable these under "Privileged Gateway Intents":
   - None required (uses default intents)

### 2. Generate Invite Link

1. Go to "OAuth2" → "URL Generator"
2. Select scopes: `bot`, `applications.commands`
3. Select bot permissions:
   - Send Messages
   - Embed Links
   - Read Message History
   - Use Slash Commands
4. Copy the generated URL and use it to invite the bot to your server

### 3. Install Dependencies

```bash
# Clone/download the bot files
cd cryptohack_discord_bot

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 4. Configure the Bot

```bash
# Copy example config
cp .env.example .env

# Edit .env with your bot token
nano .env  # or use your preferred editor
```

Set these values in `.env`:
```
DISCORD_TOKEN=your_bot_token_here
CHECK_INTERVAL_MINUTES=10
```

### 5. Run the Bot

```bash
python bot.py
```

## How It Works

1. **Add Users**: Use `/adduser username` to start tracking a CryptoHack user
2. **Background Checks**: Every 10 minutes (configurable), the bot checks for new solves
3. **Announcements**: When someone solves a new challenge, it's announced in:
   - The channel set via `/setchannel`, or
   - A channel named `#cryptohack`, or
   - The server's system channel
4. **First Blood**: If you're the first in your server to solve a challenge, you get the 🩸 badge!

## File Structure

```
cryptohack_discord_bot/
├── bot.py              # Main bot code with commands
├── database.py         # SQLite database operations
├── cryptohack_api.py   # CryptoHack API client
├── requirements.txt    # Python dependencies
├── .env.example        # Example configuration
├── .env                # Your configuration (create this)
└── README.md           # This file
```

## Database

The bot uses SQLite to store:
- Tracked users per server
- Solved challenges (to detect new ones)
- First blood records
- Server settings

The database file `cryptohack_bot.db` is created automatically.

## Rate Limiting

The bot includes delays between API calls to be respectful to CryptoHack's servers:
- 1 second between user checks during background task
- 0.5 seconds between users when refreshing leaderboard

## Troubleshooting

**Bot doesn't respond to commands?**
- Make sure the bot has the required permissions
- Wait a minute for slash commands to sync after first start

**No announcements appearing?**
- Use `/setchannel` to set an announcement channel
- Or create a channel named `#cryptohack`
- Check bot has permission to send messages in that channel

**User not found?**
- Usernames are case-insensitive but must match exactly
- Check the user exists on cryptohack.org

## Contributing

Feel free to submit issues and pull requests!

## License

MIT License
