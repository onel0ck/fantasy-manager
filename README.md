# Fantasy-Manager
Advanced automation tool for Fantasy.top daily claims and interactions.

**Telegram:** [1LOCK](https://t.me/unluck_1l0ck)
**X:** https://x.com/1l0ck

## Features
- Multi-account support with parallel processing
- Support for both new and legacy accounts
- ETH balance management and transfer system
- Proxy support with automatic rotation
- Daily claims automation
- Tactic registration and deck building with multiple deck strategies
- Multi-quest support with sequential processing
- Detailed success/failure logging
- Colorized console output
- Failed accounts auto-retry system

## Important Setup Notes

### Legacy Account Mode Setup
When using `old_account: true` mode:
- The first account in `keys_and_addresses.txt` must have sufficient ETH balance
- Balance will be automatically transferred from first to subsequent accounts
- Minimum recommended balance for first account: `0.01 ETH * (number_of_accounts)`
- All accounts after the first one can have zero balance

Example wallet sequence:
```
wallet1 (with balance) -> wallet2 -> wallet3 -> wallet4
```

The script will:
1. Process the first wallet's tasks
2. Transfer ETH to the second wallet
3. Wait for balance confirmation
4. Process second wallet's tasks
5. Continue this chain for all accounts

### Configuration Example for Legacy Mode
```json
{
    "app": {
        "threads": 1,
        "old_account": true,
        "min_balance": 0.01,
        "max_balance_checks": 30,
        "balance_check_delay": 3
    },
    "tactic": {
        "enabled": true,
        "id": "your_id",
        "max_toggle_attempts": 15,
        "delay_between_attempts": 5
    }
}
```

### Important Notes
- Legacy mode automatically sets thread count to 1 for safe balance transfers
- Each account must complete its tasks before ETH is transferred to the next account
- If a transfer fails, the script will retry before moving to the next account
- Monitor the first account's balance to ensure sufficient funds for all transfers

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

### Enhanced Configuration Options (config.json)
```json
{
    "app": {
        "threads": 5,
        "old_account": false,
        "min_balance": 0.01,
        "max_balance_checks": 30,
        "balance_check_delay": 3
    },
    "tactic": {
        "enabled": false,
        "id": "your_id",
        "max_toggle_attempts": 15,
        "delay_between_attempts": 5
    },
    "quest": {
        "enabled": false,
        "ids": [
            "quest_id_1",
            "quest_id_2",
            "quest_id_3"
        ]
    }
}
```

## New Features Details

### Legacy Account Support
- Set `old_account: true` for legacy account processing
- Automated ETH balance checks and transfers between accounts
- Single-threaded processing for secure balance transfers
- Automatic free tactics toggling system

### Enhanced Quest System
- Support for multiple quest IDs
- Sequential processing of all configured quests
- Automatic retry on rate limits
- Configurable delays between quest claims

### Operation Order
1. Tactic operations (if enabled)
2. Daily claims (if enabled)
3. Quest claims (processes all configured quest IDs)
4. ETH transfers (for legacy accounts)
5. Account info collection (if enabled)

### Balance Management
- Configurable minimum balance requirements
- Automatic balance checking system
- Smart ETH transfer with gas estimation
- Retry mechanism for failed transfers

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
- **Multi-Quest System**: Processes multiple quests sequentially
- **Legacy Support**: Special handling for old accounts with balance management
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
