# Fantasy-Manager
Advanced automation tool for Fantasy.top daily claims and interactions.

**Telegram:** [1LOCK](https://t.me/unluck_1l0ck)
**X:** https://x.com/1l0ck

## Features
- Multi-account support with parallel processing
- Static proxy support with account binding
- Automatic proxy rotation on errors
- Smart token management system
- Daily claims automation with cooldown tracking
- Detailed logging system
- Rate limit protection with proxy switching

## Important Setup Notes

### Account Data Storage System
The script maintains account data in `data/accounts_data.json`:
- Bearer tokens and session data
- Cookies and authentication information
- Last claim timestamps and next claim times
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
        "last_daily_claim": "2024-11-12T10:00:00.000000Z",
        "next_daily_claim": "2024-11-13T10:00:00.000000Z"
    }
}
```

### Smart Proxy Management
- Each account has its dedicated static proxy
- Automatic proxy rotation on rate limits or errors
- Proxy validation and error handling
- Random proxy selection from pool for retries

### Configuration Example
```json
{
    "app": {
        "threads": 5,
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
Each line corresponds to the account with the same line number:
```
http://login:password@ip:port
http://login:password@ip:port
```

## Operation Flow
1. Account and proxy binding
2. Smart authentication with retry system
3. Execute daily claims
4. Handle failures with proxy rotation
5. Track success and failures

## Advanced Features
- Static proxy binding for consistent account usage
- Automatic proxy rotation on rate limits
- Smart retry system with proxy switching
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

## License
See [LICENSE](LICENSE) file for rights and limitations.

## Support
Telegram: [@unluck_1l0ck](https://t.me/unluck_1l0ck)

## Disclaimer
Educational purposes only. Use according to Fantasy.top's terms of service.
