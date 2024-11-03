# Fantasy-Manager

Advanced automation tool for Fantasy.top daily claims and interactions.

**Telegram:** [1LOCK](https://t.me/unluck_1l0ck)
**X:** https://x.com/1l0ck

## Features

- Multi-account support with parallel processing
- Proxy support with automatic rotation
- Daily claims automation
- Tactic registration and deck building
- Quest claiming
- Detailed success/failure logging
- Colorized console output
- Failed accounts auto-retry system

## Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/onel0ck/fantasy-manager.git
   cd fantasy-manager
   ```

2. Create and activate virtual environment:
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```

3. Install required packages:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up configuration files:
   - Create `data/config.json` with your settings
   - Add accounts in `data/keys_and_addresses.txt`
   - Add proxies in `data/proxys.txt`

## Configuration

### Account Format (keys_and_addresses.txt)
```
private_key1:address1
private_key2:address2
```

### Proxy Format (proxys.txt)
```
http://login:password@ip:port
http://login:password@ip:port
```

## Usage

1. Configure your settings in config.json
2. Add your accounts and proxies
3. Run the script:
   ```bash
   python run.py
   ```
4. Enter delay time when prompted
5. Monitor the console output for progress
6. Check logs folder for detailed results

## Features Details

- **Daily Claims**: Automatically claims daily rewards
- **Tactic System**: Handles tactic registration and deck building
- **Quest Claims**: Processes available quests
- **Account Info**: Collects and saves account statistics
- **Proxy Support**: Rotates proxies for each account
- **Error Handling**: Auto-retries failed accounts
- **Logging System**: Detailed logs with timestamps and status

## Logs

The script creates several log files:
- `app.log`: General application logs
- `success_accounts.txt`: Successfully processed accounts
- `failure_accounts.txt`: Failed accounts
- `result.txt`: Detailed account information

## Controls

- Use CTRL+C to gracefully stop the script
- The script will finish current operations before stopping

## Disclaimer

This tool is for educational purposes only. Use at your own risk and in accordance with Fantasy.top's terms of service.

## Support

- Telegram Channel: [@unluck_1l0ck](https://t.me/unluck_1l0ck)
