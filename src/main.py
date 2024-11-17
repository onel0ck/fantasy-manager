import math
import random
import time
import threading
import concurrent.futures
from time import sleep
import requests
from web3 import Web3
from colorama import Fore
from src.api import FantasyAPI
from src.utils import error_log, info_log, success_log, rate_limit_log
from src.account_storage import AccountStorage

class RetryManager:
    def __init__(self, max_retries=5, success_threshold=0.9):
        self.failed_accounts = set()
        self.success_accounts = set()
        self.attempt_counter = {}
        self.failed_with_stored = set()
        self.max_retries = max_retries
        self.success_threshold = success_threshold
        self.lock = threading.Lock()

    def add_failed_account(self, account_data):
        with self.lock:
            self.failed_accounts.add(account_data)
            if account_data not in self.attempt_counter:
                self.attempt_counter[account_data] = 1
            else:
                self.attempt_counter[account_data] += 1

    def add_success_account(self, account_data):
        with self.lock:
            if account_data in self.failed_accounts:
                self.failed_accounts.remove(account_data)
            if account_data in self.failed_with_stored:
                self.failed_with_stored.remove(account_data)
            self.success_accounts.add(account_data)

    def mark_stored_credentials_failed(self, account_data):
        with self.lock:
            self.failed_with_stored.add(account_data)

    def should_try_stored_credentials(self, account_data):
        return account_data not in self.failed_with_stored

    def get_retry_accounts(self):
        with self.lock:
            return [acc for acc in self.failed_accounts 
                   if self.attempt_counter[acc] < self.max_retries]

    def get_current_attempt(self, account_data):
        with self.lock:
            return self.attempt_counter.get(account_data, 0)

    def get_success_rate(self):
        total = len(self.success_accounts) + len(self.failed_accounts)
        return len(self.success_accounts) / total if total > 0 else 0

    def should_continue_retrying(self):
        return (self.get_success_rate() < self.success_threshold and 
                bool(self.get_retry_accounts()))

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
        self.retry_manager = RetryManager()
        self.retry_delay = 5

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

    def _try_with_different_proxy(self, account_number):
        new_proxy = self._get_random_proxy()
        info_log(f'Switching proxy for account {account_number} to: {new_proxy}')
        proxy_dict = {
            "http": new_proxy,
            "https": new_proxy
        }
        return proxy_dict

    def process_account_with_retry(self, account_number, private_key, wallet_address, total_accounts):
        account_data = (account_number, private_key, wallet_address)
        
        try:
            success = self.process_account(account_number, private_key, wallet_address, total_accounts)
            if success:
                self.retry_manager.add_success_account(account_data)
            else:
                self.retry_manager.add_failed_account(account_data)
        except Exception as e:
            error_log(f"Error processing account {account_number}: {str(e)}")
            self.retry_manager.add_failed_account(account_data)

    def process_account(self, account_number, private_key, wallet_address, total_accounts):
        max_attempts = 7
        account_data = (account_number, private_key, wallet_address)
        current_attempt = self.retry_manager.get_current_attempt(account_data)
        
        while current_attempt < max_attempts:
            thread_id = threading.get_ident()
            self._wait_rate_limit(thread_id)
            
            session = requests.Session()
            proxy_dict = self._try_with_different_proxy(account_number)
            
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
            
            if current_attempt == 0:
                info_log(f'Processing account {account_number}: {wallet_address}')
            else:
                info_log(f'Retrying account {account_number}: {wallet_address} (Attempt {current_attempt + 1}/{max_attempts})')
            
            try:
                # Проверяем stored credentials только если ещё не было неудачных попыток с ними
                if self.retry_manager.should_try_stored_credentials(account_data):
                    stored_success, stored_token = api.token_manager.try_stored_credentials(wallet_address, account_number)
                    if stored_success:
                        info_log(f'Using stored credentials for account {account_number}')
                        token = stored_token
                    else:
                        self.retry_manager.mark_stored_credentials_failed(account_data)
                        token = None
                else:
                    token = None

                if not token:
                    auth_data = api.login(private_key, wallet_address, account_number)
                    if not auth_data:
                        current_attempt += 1
                        self.retry_manager.add_failed_account(account_data)
                        session.close()
                        sleep(2)
                        continue

                    token = api.get_token(auth_data, wallet_address, account_number)
                    if not token:
                        current_attempt += 1
                        self.retry_manager.add_failed_account(account_data)
                        session.close()
                        sleep(2)
                        continue

                try:
                    if self.config['daily']['enabled']:
                        daily_result = api.daily_claim(token, wallet_address, account_number)
                        if daily_result is True:
                            self._write_success(private_key, wallet_address)
                            self.retry_manager.add_success_account(account_data)
                            session.close()
                            return True
                        else:
                            current_attempt += 1
                            self.retry_manager.add_failed_account(account_data)
                            if not self.retry_manager.should_try_stored_credentials(account_data):
                                self.retry_manager.mark_stored_credentials_failed(account_data)
                                
                except (requests.exceptions.ProxyError, requests.exceptions.ConnectionError):
                    current_attempt += 1
                    self.retry_manager.add_failed_account(account_data)
                    session.close()
                    sleep(2)
                    continue

            except Exception as e:
                current_attempt += 1
                self.retry_manager.add_failed_account(account_data)
                error_log(f'Processing error for account {account_number}: {str(e)}')
                session.close()
                sleep(2)
                continue

        self._write_failure(private_key, wallet_address)
        return False

    def retry_failed_accounts(self):
        while self.retry_manager.should_continue_retrying():
            retry_accounts = self.retry_manager.get_retry_accounts()
            info_log(f"Retrying {len(retry_accounts)} accounts. Current success rate: "
                    f"{self.retry_manager.get_success_rate()*100:.2f}%")
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.config['app']['threads']) as executor:
                futures = []
                for account_number, private_key, wallet_address in retry_accounts:
                    sleep(self.retry_delay)
                    future = executor.submit(
                        self.process_account_with_retry,
                        account_number,
                        private_key,
                        wallet_address,
                        len(retry_accounts)
                    )
                    futures.append(future)

                concurrent.futures.wait(futures)

            success_rate = self.retry_manager.get_success_rate() * 100
            info_log(f"Current success rate after retry: {success_rate:.2f}%")

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
