import json
import os
from datetime import datetime
from typing import Dict, Optional
import pytz

class AccountStorage:
    def __init__(self, storage_file: str = "data/accounts_data.json"):
        self.storage_file = storage_file
        self.data = self._load_data()

    def _load_data(self) -> Dict:
        if os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {}
        return {}

    def _save_data(self):
        os.makedirs(os.path.dirname(self.storage_file), exist_ok=True)
        with open(self.storage_file, 'w') as f:
            json.dump(self.data, f, indent=4)

    def update_account(self, address: str, private_key: str, token: Optional[str] = None,
                      cookies: Optional[Dict] = None):
        if address not in self.data:
            self.data[address] = {
                "private_key": private_key,
                "created_at": datetime.now(pytz.UTC).isoformat()
            }
        
        account_data = self.data[address]
        
        if token is not None:
            account_data["token"] = token
            account_data["token_updated_at"] = datetime.now(pytz.UTC).isoformat()
        
        if cookies is not None:
            account_data["cookies"] = cookies
            account_data["cookies_updated_at"] = datetime.now(pytz.UTC).isoformat()
        
        self._save_data()

    def get_account_data(self, address: str) -> Optional[Dict]:
        return self.data.get(address)

    def is_token_valid(self, address: str) -> bool:
        account_data = self.get_account_data(address)
        if not account_data or "token" not in account_data:
            return False
        return True
