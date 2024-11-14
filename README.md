# Fantasy-Manager
Advanced automation tool for Fantasy.top daily claims and interactions.

**Telegram:** [1LOCK](https://t.me/unluck_1l0ck)
**X:** https://x.com/1l0ck

## Features
- Multi-account support with parallel processing
- Support for both new and legacy accounts
- Smart token and session management system
- Proxy support with automatic rotation and error handling
- Daily claims automation with cooldown tracking
- Tactic registration and deck building
- Multi-quest support
- Detailed logging system
- Automatic retry system for failed requests
- Rate limiting protection

## Important Setup Notes

### Account Data Storage System
The script maintains account data in `data/accounts_data.json`:
- Bearer tokens and session data
- Cookies and authentication information
- Last claim timestamps
- Account creation dates

Example account data structure:
```json
{
    "0xWALLET_ADDRESS": {
        "private_key": "PRIVATE_KEY",
        "created_at": "2024-11-12T10:00:00.000000Z",
        "token": "BEARER_TOKEN",
        "token_updated_at": "2024-11-12T10:00:00.000000Z",
        "cookies": {
            "privy-token": "COOKIE_VALUE",
            "privy-session": "COOKIE_VALUE",
            "privy-access-token": "COOKIE_VALUE"
        },
        "cookies_updated_at": "2024-11-12T10:00:00.000000Z",
        "last_daily_claim": "2024-11-12T10:00:00.000000Z"
    }
}
```

### Smart Token Management
- Automatically reuses valid tokens and sessions
- Handles token expiration and renewal
- Maintains session persistence between runs
- Reduces unnecessary authentication requests

### Rate Limit Protection
- Smart delay system between requests
- Automatic proxy rotation on errors
- Exponential backoff for failed attempts
- Request distribution across multiple proxies

### Configuration Example
```json
{
    "app": {
        "threads": 10,
        "keys_file": "data/keys_and_addresses.txt",
        "proxy_file": "data/proxys.txt",
        "success_file": "logs/success_accounts.txt",
        "failure_file": "logs/failure_accounts.txt",
        "result_file": "logs/result.txt",
        "log_file": "logs/app.log",
        "old_account": false,
        "min_balance": 0.01,
        "max_balance_checks": 30,
        "balance_check_delay": 3
    },
    "rpc": {
        "url": "https://blastl2-mainnet.public.blastapi.io"
    },
    "tactic": {
        "enabled": false,
        "id": "your_id",
        "max_toggle_attempts": 15,
        "delay_between_attempts": 5,
        "decks": [
            [7, 6, 5, 3, 2],
            [7, 6, 5, 3, 2],
            [6, 6, 5, 4, 2],
        ]
    },
    "quest": {
        "enabled": false,
        "ids": [
            "ea7c4f8a-0db8-4a9d-a840-5f76cfb1fad5",
            "ba57e629-9aee-4a2b-a02c-14713725f941"
        ]
    },
    "daily": {
        "enabled": true
    },
    "info_check": false
}
```

## Setup Process
1. Clone repository:
```bash
git clone https://github.com/onel0ck/fantasy-manager.git
cd fantasy-manager
```

2. Create virtual environment:
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

3. Configure files:
- `data/config.json`: Your settings
- `data/keys_and_addresses.txt`: Account credentials
- `data/proxys.txt`: Proxy list

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

## Operation Flow
1. Load and validate stored account data
2. Smart authentication using stored tokens
3. Execute enabled operations:
   - Tactic operations
   - Daily claims
   - Quest claims
4. Update account data storage
5. Handle any failures with automatic retries

## Advanced Features
- Proxy error handling with automatic switching
- Smart delay system to prevent rate limits
- Session persistence for efficiency
- Automatic token refresh when needed
- Detailed success/failure tracking

## Logs
Generated log files:
- `app.log`: Detailed operation logs
- `success_accounts.txt`: Successful accounts
- `failure_accounts.txt`: Failed accounts
- `result.txt`: Account information
- `accounts_data.json`: Session and claim data

## Usage
Run the script:
```bash
python run.py
```

## Support
Telegram: [@unluck_1l0ck](https://t.me/unluck_1l0ck)

## Disclaimer
Educational purposes only. Use according to Fantasy.top's terms of service.
