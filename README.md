# Fantasy Manager
Advanced automation tool for Fantasy.top featuring quest claims, tactics participation, and account information gathering.

**Telegram:** [@unluck_1l0ck](https://t.me/unluck_1l0ck)

## Features
- Multi-threaded account processing
- Quest automation system
- Tactics mode with customizable decks
- Fragment collection
- Proxy system with automatic rotation
- Detailed logging system
- Rate limit protection
- Account information gathering

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/fantasy-manager.git
cd fantasy-manager
```

2. Create virtual environment:
```bash
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Configuration

### Project Structure
```
fantasy-manager/
├── data/
│   ├── config.json             # Main configuration
│   ├── keys_and_addresses.txt  # Private keys
│   └── proxys.txt             # Proxy list
└── logs/
    ├── app.log                # Operation logs
    ├── success_accounts.txt   # Successful accounts
    ├── failure_accounts.txt   # Failed accounts
    └── result.txt            # Account information
```

### Configuration (config.json)
```json
{
    "app": {
        "threads": 10,                        // Number of parallel threads
        "keys_file": "data/keys_and_addresses.txt",  // Private keys file
        "proxy_file": "data/proxys.txt",     // Proxy file
        "success_file": "logs/success_accounts.txt",
        "failure_file": "logs/failure_accounts.txt",
        "result_file": "logs/result.txt",
        "log_file": "logs/app.log",
        "min_balance": 0.01,                 // Minimum balance requirement
        "max_balance_checks": 30,            // Maximum balance check attempts
        "balance_check_delay": 3             // Delay between balance checks
    },
    "rpc": {
        "url": "https://blastl2-mainnet.public.blastapi.io"
    },
    "tactic": {
        "enabled": false,                    // Enable/disable tactics mode
        "id": "29d389d3-5b76-4d4e-9d2d-86c7d0f681d5",  // Tactic ID
        "max_toggle_attempts": 15,           // Maximum attempts to toggle status
        "delay_between_attempts": 2,         // Delay between attempts
        "old_account": false,               // Use old account mode
        "decks": [                          // Deck configurations
            [7, 6, 5, 3, 2],               // Each array represents a deck
            [7, 6, 5, 3, 2],               // Numbers are hero star ratings
            [6, 6, 5, 4, 2],
            [7, 6, 5, 3, 2],
            [7, 6, 6, 2, 2],
            [6, 6, 5, 4, 2],
            [6, 5, 5, 5, 2],
            [6, 6, 5, 3, 3],
            [7, 6, 4, 3, 3],
            [6, 5, 5, 3, 3]
        ]
    },
    "quest": {
        "enabled": true,                     // Enable quests
        "ids": [                            // Quest IDs
            "ea7c4f8a-0db8-4a9d-a840-5f76cfb1fad5",
            "ba57e629-9aee-4a2b-a02c-14713725f941"
        ]
    },
    "daily": {
        "enabled": false                     // Daily rewards
    },
    "fragments": {
        "enabled": false,                    // Fragment collection
        "id": "69e67d0a-0a08-4085-889f-58df15bdecb8"  // Fragment ID
    },
    "info_check": true                      // Gather account information
}
```

### File Formats

#### keys_and_addresses.txt:
```
private_key1:wallet_address1
private_key2:wallet_address2
```

#### proxys.txt:
```
http://login:pass@ip:port
http://login:pass@ip:port
```

## Operating Modes

### Quest Mode
Automatically claims quests. Currently configured for:
- Quest 1: ea7c4f8a-0db8-4a9d-a840-5f76cfb1fad5
- Quest 2: ba57e629-9aee-4a2b-a02c-14713725f941

### Tactics Mode
When enabled, participates in tactic ID: 29d389d3-5b76-4d4e-9d2d-86c7d0f681d5
Features 10 different deck configurations for optimal performance.

### Fragments Mode
When enabled, collects fragment ID: 69e67d0a-0a08-4085-889f-58df15bdecb8

### Information Collection
When enabled, gathers and stores account data including:
- Gold balance
- Stars count
- Portfolio value
- Number of cards
- Fantasy points
- Rewards status

## Usage

1. Configure config.json according to your needs
2. Add private keys to keys_and_addresses.txt
3. Add proxies to proxys.txt
4. Run the script:
```bash
python run.py
```

## Logging System
- `app.log` - Detailed operation logs
- `success_accounts.txt` - Successfully processed accounts
- `failure_accounts.txt` - Failed accounts
- `result.txt` - Account information (gold, stars, rewards, etc.)

## Support
Telegram: [@unluck_1l0ck](https://t.me/unluck_1l0ck)

## Disclaimer
This tool is for educational purposes only.
