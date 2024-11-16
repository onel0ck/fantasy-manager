import math
import random
import time
import threading
from time import sleep
import requests
from web3 import Web3
from colorama import Fore
from src.api import FantasyAPI
from src.utils import error_log, info_log, success_log
from src.account_storage import AccountStorage

class FantasyProcessor:
    def __init__(self, config, proxies_dict, all_proxies, user_agents_cycle):
        self.config = config
        self.proxies = proxies_dict
        self.all_proxies = all_proxies
        self.user_agents_cycle = user_agents_cycle
        self.account_storage = AccountStorage()
        self.last_request_time = {}
        self.min_request_interval = 2
        self.lock = threading.Lock()

    def _wait_rate_limit(self, thread_id):
        current_time = time.time()
        with self.lock:
            last_time = self.last_request_time.get(thread_id, 0)
            time_since_last = current_time - last_time
            if time_since_last < self.min_request_interval:
                sleep_time = self.min_request_interval - time_since_last
                sleep(sleep_time)
            self.last_request_time[thread_id] = time.time()

    def _get_random_proxy(self):
        with self.lock:
            return random.choice(self.all_proxies)

    def _try_with_different_proxy(self, api, account_number):
        new_proxy = self._get_random_proxy()
        info_log(f'Switching proxy for account {account_number} to: {new_proxy}')
        proxy_dict = {
            "http": new_proxy,
            "https": new_proxy
        }
        api.proxies = proxy_dict
        api.session.proxies = proxy_dict
        return True

    def process_account(self, account_number, private_key, wallet_address, total_accounts):
        thread_id = threading.get_ident()
        self._wait_rate_limit(thread_id)
        
        session = requests.Session()
        
        initial_proxy = self.proxies.get(account_number)
        if not initial_proxy:
            error_log(f'No proxy found for account {account_number}')
            self._write_failure(private_key, wallet_address)
            return False
            
        proxy_dict = {
            "http": initial_proxy,
            "https": initial_proxy
        }
        
        with self.lock:
            user_agent = next(self.user_agents_cycle)
        
        api = FantasyAPI(
            web3_provider=self.config['rpc']['url'],
            session=session,
            proxies=proxy_dict,
            config=self.config,
            user_agent=user_agent,
            account_storage=self.account_storage
        )
        
        info_log(f'Processing account {account_number}: {wallet_address}')
        
        try:
            auth_data = api.login(private_key, wallet_address, account_number)
            if not auth_data:
                if self._try_with_different_proxy(api, account_number):
                    auth_data = api.login(private_key, wallet_address, account_number)
                    if not auth_data:
                        error_log(f'Failed to login account {account_number}: {wallet_address}')
                        self._write_failure(private_key, wallet_address)
                        return False

            token = api.get_token(auth_data, wallet_address, account_number)
            if not token:
                error_log(f'Failed to get token for account {account_number}: {wallet_address}')
                self._write_failure(private_key, wallet_address)
                return False

            task_success = False
                
            try:
                if self.config['daily']['enabled']:
                    daily_result = api.daily_claim(token, wallet_address, account_number)
                    if daily_result is True:
                        task_success = True
                    else:
                        self._write_failure(private_key, wallet_address)
                        
            except (requests.exceptions.ProxyError, requests.exceptions.ConnectionError):
                if self._try_with_different_proxy(api, account_number):
                    daily_result = api.daily_claim(token, wallet_address, account_number)
                    if daily_result is True:
                        task_success = True
                    else:
                        self._write_failure(private_key, wallet_address)
                        return False
                else:
                    error_log(f'Proxy error during task for account {account_number}')
                    self._write_failure(private_key, wallet_address)
                    return False

            if task_success:
                self._write_success(private_key, wallet_address)
                return True

        except Exception as e:
            error_log(f'Processing error for account {account_number}: {str(e)}')
            self._write_failure(private_key, wallet_address)
            return False
        finally:
            session.close()

    def _write_success(self, private_key, wallet_address):
        with self.lock:
            try:
                with open(self.config['app']['success_file'], 'a') as f:
                    f.write(f'{private_key}:{wallet_address}\n')
            except Exception as e:
                error_log(f'Error writing to success file: {str(e)}')

    def _write_failure(self, private_key, wallet_address):
        with self.lock:
            try:
                with open(self.config['app']['failure_file'], 'a') as f:
                    f.write(f'{private_key}:{wallet_address}\n')
            except Exception as e:
                error_log(f'Error writing to failure file: {str(e)}')
