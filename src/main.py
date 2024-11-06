import math
import random
from time import sleep
import requests
from web3 import Web3
from colorama import Fore
from .api import FantasyAPI
from .utils import error_log, info_log, success_log

class FantasyProcessor:
    def __init__(self, config, proxies_cycle):
        self.config = config
        self.proxies_cycle = proxies_cycle
        
    def process_account(self, account_number, private_key, wallet_address, total_accounts):
        session = requests.Session()
        proxy = {
            "http": next(self.proxies_cycle),
            "https": next(self.proxies_cycle)
        }
        
        api = FantasyAPI(
            web3_provider=self.config['rpc']['url'],
            session=session,
            proxies=proxy,
            config=self.config
        )
        
        info_log(f'Processing account {account_number}: {wallet_address}')
        
        try:
            if self.config['app']['old_account']:
                balance = api.check_eth_balance(wallet_address)
                if balance < self.config['app']['min_balance']:
                    error_log(f'Insufficient balance ({balance} ETH) for account {account_number}')
                    return False
            
            sleep(random.uniform(1, 3))
            auth_data = api.login(private_key, wallet_address, account_number)
            
            if not auth_data or not api.check_cookies():
                self._write_failure(private_key, wallet_address)
                return False

            sleep(random.uniform(1, 3))
            token = api.get_token(auth_data, wallet_address, account_number)
            if not token:
                self._write_failure(private_key, wallet_address)
                return False

            sleep(random.uniform(1, 3))
            success = False

            if self.config['tactic']['enabled']:
                if self.config['app']['old_account']:
                    if api.toggle_free_tactics(token, wallet_address, account_number):
                        if api.tactic_claim(token, wallet_address, account_number, total_accounts):
                            success = True
                else:
                    if api.tactic_claim(token, wallet_address, account_number, total_accounts):
                        success = True

            if self.config['daily']['enabled']:
                if api.daily_claim(token, wallet_address, account_number):
                    success = True

            if self.config['quest']['enabled']:
                for quest_id in self.config['quest']['ids']:
                    info_log(f'Processing quest ID: {quest_id} for account {account_number}')
                    if api.quest_claim(token, wallet_address, account_number, quest_id):
                        success = True
                    sleep(random.uniform(1, 3))

            if self.config['app']['old_account']:
                accounts = self._read_accounts()
                current_index = next((i for i, (num, (pk, addr)) in enumerate(accounts) if pk == private_key), None)
                
                if current_index is not None and current_index + 1 < len(accounts):
                    next_private_key, next_address = accounts[current_index + 1][1]
                    if api.transfer_eth(private_key, wallet_address, next_address):
                        success_log(f'Successfully transferred ETH to next account: {next_address}')
                    else:
                        error_log(f'Failed to transfer ETH to next account: {next_address}')

            if self.config['info_check']:
                if api.info(token, wallet_address, account_number):
                    success = True

            if success:
                self._write_success(private_key, wallet_address)
            else:
                self._write_failure(private_key, wallet_address)

        except Exception as e:
            error_log(f'Account processing error {account_number}: {str(e)}')
            self._write_failure(private_key, wallet_address)
            return False
        finally:
            session.close()

    def _write_success(self, private_key, wallet_address):
        with open(self.config['app']['success_file'], 'a') as f:
            f.write(f'{private_key}:{wallet_address}\n')

    def _write_failure(self, private_key, wallet_address):
        with open(self.config['app']['failure_file'], 'a') as f:
            f.write(f'{private_key}:{wallet_address}\n')
