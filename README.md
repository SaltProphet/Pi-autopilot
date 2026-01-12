# Pi-Autopilot

**Raspberry Pi AI-Orchestrated Reddit-to-Gumroad Digital Product Pipeline**

An automated system that scrapes Reddit for trending topics, generates product specifications using OpenAI, and creates digital products on Gumroad — all running on a Raspberry Pi.

## Features

- 🤖 **Automated Reddit Scraping**: Uses PRAW to scrape top posts from specified subreddits
- 🧠 **AI Product Generation**: OpenAI GPT-4 generates detailed product specifications
- 🛍️ **Gumroad Integration**: Automatically creates products on Gumroad
- 📊 **SQLite Database**: Lightweight database perfect for Raspberry Pi
- 🕒 **Scheduled Jobs**: Automated scraping and generation at configurable intervals
- 📈 **Metrics & Monitoring**: Track system performance and operations
- 🔄 **CI/CD**: GitHub Actions workflow for automated deployment

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Reddit    │────▶│  Pi-Autopilot │────▶│   Gumroad   │
│    API      │     │   (FastAPI)   │     │     API     │
└─────────────┘     └──────────────┘     └─────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │   OpenAI     │
                    │     API      │
                    └──────────────┘
```

## Project Structure

```
Pi-autopilot/
├── agents/
│   ├── db.py                    # SQLite database operations
│   ├── reddit_scraper.py        # Reddit scraping logic
│   ├── product_generator.py    # OpenAI product generation
│   ├── gumroad_uploader.py     # Gumroad API integration
│   └── metrics.py               # System metrics tracking
├── .github/
│   └── workflows/
│       └── deploy-to-pi.yml    # GitHub Actions deployment
├── main.py                      # FastAPI application
├── scheduler.py                 # Scheduled jobs (scrape & generate)
├── start.sh                     # Server start script
├── requirements.txt             # Python dependencies
├── Dockerfile                   # Docker configuration
├── saltprophet.service         # Systemd service file
├── .env.example                # Environment variables template
└── README.md                   # This file
```

## Prerequisites

- Raspberry Pi (3B+ or newer recommended)
- Python 3.9+
- Reddit API credentials
- OpenAI API key
- Gumroad account and API token

## Installation

### On Raspberry Pi

1. **Clone the repository**
   ```bash
   cd ~
   git clone https://github.com/SaltProphet/Pi-autopilot.git
   cd Pi-autopilot
   ```

2. **Create and activate virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   ```bash
   cp .env.example .env
   nano .env
   ```

   Fill in your API credentials:
   ```env
   # Reddit API
   REDDIT_CLIENT_ID=your_reddit_client_id
   REDDIT_CLIENT_SECRET=your_reddit_client_secret
   REDDIT_USER_AGENT=Pi-Autopilot/1.0
   
   # OpenAI API
   OPENAI_API_KEY=your_openai_api_key
   
   # Gumroad API
   GUMROAD_ACCESS_TOKEN=your_gumroad_access_token
   
   # App Configuration
   APP_HOST=0.0.0.0
   APP_PORT=8000
   LOG_LEVEL=INFO
   
   # Database
   DATABASE_PATH=./pi_autopilot.db
   
   # Scheduling (in hours)
   SCRAPE_INTERVAL_HOURS=24
   GENERATION_INTERVAL_HOURS=6
   ```

5. **Initialize database**
   ```bash
   python3 -c "from agents.db import init_database; init_database()"
   ```

## Getting API Keys

### Reddit API
1. Go to https://www.reddit.com/prefs/apps
2. Click "Create App" or "Create Another App"
3. Select "script" as the app type
4. Fill in the required fields
5. Copy the client ID (under the app name) and secret

### OpenAI API
1. Visit https://platform.openai.com/api-keys
2. Click "Create new secret key"
3. Copy and save the key securely

### Gumroad API
1. Log into Gumroad
2. Go to Settings → Advanced → Applications
3. Create a new application
4. Generate an access token
5. Copy the token

## Running the Application

### Manual Start

**Start the API server:**
```bash
./start.sh
# Or directly:
uvicorn main:app --host 0.0.0.0 --port 8000
```

**Start the scheduler (in a separate terminal):**
```bash
python3 scheduler.py
```

### Using Docker

```bash
# Build the image
docker build -t pi-autopilot .

# Run the container
docker run -d \
  --name pi-autopilot \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  --env-file .env \
  pi-autopilot
```

### As a Systemd Service

1. **Copy the service file**
   ```bash
   sudo cp saltprophet.service /etc/systemd/system/
   ```

2. **Edit paths if necessary**
   ```bash
   sudo nano /etc/systemd/system/saltprophet.service
   ```
   
   Update `User`, `WorkingDirectory`, and paths to match your setup.

3. **Enable and start the service**
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable saltprophet.service
   sudo systemctl start saltprophet.service
   ```

4. **Check status**
   ```bash
   sudo systemctl status saltprophet.service
   ```

5. **View logs**
   ```bash
   sudo journalctl -u saltprophet.service -f
   ```

## API Endpoints

### Health Check
```bash
GET /health
```
Returns system status and metrics.

### Scrape Subreddit
```bash
POST /run/scrape/{subreddit}?limit=10
```
Scrape posts from a specific subreddit.

**Example:**
```bash
curl -X POST "http://localhost:8000/run/scrape/python?limit=10"
```

### Generate Product Spec
```bash
POST /gen/product/{post_id}
```
Generate a product specification from a Reddit post.

**Example:**
```bash
curl -X POST "http://localhost:8000/gen/product/abc123"
```

### Push to Gumroad
```bash
POST /products/push/{product_spec_id}
```
Create a product on Gumroad from a product spec.

**Example:**
```bash
curl -X POST "http://localhost:8000/products/push/1"
```

### Get Metrics
```bash
GET /metrics
```
View system metrics and statistics.

## Automated Deployment with GitHub Actions

### Setup

1. **Add secrets to GitHub repository:**
   - `PI_HOST`: IP address or hostname of your Raspberry Pi
   - `PI_USERNAME`: SSH username (usually `pi`)
   - `PI_SSH_KEY`: Private SSH key for authentication

2. **Generate SSH key on your computer:**
   ```bash
   ssh-keygen -t rsa -b 4096 -C "pi-autopilot"
   ```

3. **Copy public key to Raspberry Pi:**
   ```bash
   ssh-copy-id pi@your-pi-ip-address
   ```

4. **Add private key to GitHub:**
   - Go to Settings → Secrets and variables → Actions
   - Click "New repository secret"
   - Add `PI_SSH_KEY` with the contents of your private key

### Deployment Process

Once configured, every push to the `main` branch will:
1. SSH into your Raspberry Pi
2. Pull the latest code
3. Upgrade dependencies
4. Restart the systemd service

## Scheduled Jobs

The scheduler runs two automated jobs:

1. **Scrape Job** (default: every 24 hours)
   - Scrapes configured subreddits
   - Saves new posts to database

2. **Generation Job** (default: every 6 hours)
   - Finds posts without product specs
   - Generates specs using OpenAI
   - Saves to database

Configure intervals in `.env`:
```env
SCRAPE_INTERVAL_HOURS=24
GENERATION_INTERVAL_HOURS=6
```

## Database Schema

### reddit_posts
```sql
CREATE TABLE reddit_posts (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    body TEXT,
    timestamp INTEGER NOT NULL,
    subreddit TEXT,
    author TEXT,
    score INTEGER DEFAULT 0,
    url TEXT,
    created_at INTEGER DEFAULT (strftime('%s', 'now'))
)
```

### product_specs
```sql
CREATE TABLE product_specs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_post_id TEXT NOT NULL,
    json_spec TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    created_at INTEGER DEFAULT (strftime('%s', 'now')),
    gumroad_product_id TEXT,
    FOREIGN KEY (source_post_id) REFERENCES reddit_posts(id)
)
```

## Troubleshooting

### Service won't start
```bash
# Check service status
sudo systemctl status saltprophet.service

# Check logs
sudo journalctl -u saltprophet.service -n 50
```

### Database issues
```bash
# Reinitialize database
python3 -c "from agents.db import init_database; init_database()"
```

### API errors
```bash
# Check if all environment variables are set
cat .env | grep -v '^#'

# Test API connectivity
curl http://localhost:8000/health
```

### Reddit API rate limiting
Reddit has rate limits. The scraper includes delays between requests. If you hit limits:
- Reduce scrape frequency
- Decrease post limit per subreddit
- Check your Reddit app's rate limit status

## Development

### Running Tests
```bash
pytest
```

### Code Style
This project follows PEP 8 guidelines with clear inline comments.

## Security Notes

- **Never commit `.env` file** - Contains sensitive API keys
- **Use environment variables** for all secrets
- **Restrict Pi SSH access** - Use key-based authentication only
- **Keep dependencies updated** - Regularly run `pip install --upgrade`
- **Monitor API usage** - Watch for unusual patterns

## Performance Tips

### For Raspberry Pi 3B+
- Use limit=5-10 for scraping to avoid memory issues
- Increase job intervals to reduce CPU load
- Consider using a cooling fan

### For Raspberry Pi 4+
- Default settings should work well
- Can increase scrape limits and decrease intervals

## License

See LICENSE file for details.

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## Support

For issues and questions:
- Open an issue on GitHub
- Check existing issues for solutions

## Acknowledgments

- Built with FastAPI, PRAW, OpenAI, and Gumroad APIs
- Designed for Raspberry Pi enthusiasts and indie makers

---

**Made with ❤️ for the maker community**