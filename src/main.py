import math
import random
import time
from time import sleep
import requests
from web3 import Web3
from colorama import Fore
from .api import FantasyAPI
from .utils import error_log, info_log, success_log
from .account_storage import AccountStorage

class FantasyProcessor:
    def __init__(self, config, proxies_cycle, user_agents_cycle):
        self.config = config
        self.proxies_cycle = proxies_cycle
        self.user_agents_cycle = user_agents_cycle
        self.account_storage = AccountStorage()
        self.last_request_time = 0
        self.min_request_interval = 3

    def _wait_rate_limit(self):
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last
            sleep(sleep_time)
        self.last_request_time = time.time()

    def _refresh_proxy(self, api):
        new_proxy = {
            "http": next(self.proxies_cycle),
            "https": next(self.proxies_cycle)
        }
        api.proxies = new_proxy
        api.session.proxies = new_proxy
        return new_proxy

    def process_account(self, account_number, private_key, wallet_address, total_accounts):
        self._wait_rate_limit()
        
        session = requests.Session()
        proxy = {
            "http": next(self.proxies_cycle),
            "https": next(self.proxies_cycle)
        }
        
        user_agent = next(self.user_agents_cycle)
        
        api = FantasyAPI(
            web3_provider=self.config['rpc']['url'],
            session=session,
            proxies=proxy,
            config=self.config,
            user_agent=user_agent,
            account_storage=self.account_storage
        )
        
        info_log(f'Processing account {account_number}: {wallet_address}')
        
        try:
            token = None
            account_data = self.account_storage.get_account_data(wallet_address)
            
            if account_data:
                stored_token = account_data.get('token')
                stored_cookies = account_data.get('cookies')
                
                if stored_token and stored_cookies:
                    for cookie_name, cookie_value in stored_cookies.items():
                        session.cookies.set(cookie_name, cookie_value)
                    
                    if api.token_manager.validate_token(stored_token):
                        token = stored_token

            task_success = False
            task_attempted = False
            
            while not task_attempted or (not task_success and token):
                task_attempted = True
                
                if not token:
                    success, new_token = self._perform_login(api, private_key, wallet_address, account_number)
                    if not success:
                        sleep(random.uniform(3, 5))
                        continue
                    token = new_token

                try:
                    if self.config['daily']['enabled']:
                        daily_result = api.daily_claim(token, wallet_address, account_number)
                        if daily_result is True:
                            task_success = True
                            break
                        elif isinstance(daily_result, str) and "Unauthorized" in daily_result:
                            info_log(f'Token expired, refreshing login for account {account_number}')
                            sleep(5)
                            token = None
                            continue
                        
                except (requests.exceptions.ProxyError, requests.exceptions.ConnectionError):
                    info_log(f'Proxy error during task for account {account_number}, refreshing proxy')
                    self._refresh_proxy(api)
                    sleep(5)
                    continue

            if task_success:
                self._write_success(private_key, wallet_address)
                sleep(random.uniform(2, 4))

        except Exception as e:
            info_log(f'Processing error for account {account_number}: {str(e)}')
            sleep(random.uniform(3, 5))
            return False
        finally:
            session.close()

    def _perform_login(self, api, private_key, wallet_address, account_number):
        base_delay = 15
        max_attempts = 3
        max_proxy_retries = 2
        
        for attempt in range(max_attempts):
            proxy_retries = 0
            while proxy_retries <= max_proxy_retries:
                try:
                    self._wait_rate_limit()
                    auth_data = api.login(private_key, wallet_address, account_number)
                    
                    if auth_data and api.check_cookies():
                        self._wait_rate_limit()
                        token = api.get_token(auth_data, wallet_address, account_number)
                        if token:
                            return True, token
                        elif "Invalid Privy token" in str(auth_data):
                            break  # Переходим к следующей основной попытке
                    
                    break  # Если нет ошибки прокси, выходим из внутреннего цикла
                    
                except (requests.exceptions.ProxyError, requests.exceptions.ConnectionError) as e:
                    proxy_retries += 1
                    if proxy_retries <= max_proxy_retries:
                        info_log(f'Proxy error for account {account_number}, switching proxy and retrying')
                        new_proxy = self._refresh_proxy(api)
                        info_log(f'New proxy assigned for account {account_number}')
                        sleep(5)
                        continue
                    break
                
                except Exception as e:
                    info_log(f'Unexpected error during login attempt for account {account_number}: {str(e)}')
                    break
            
            if attempt < max_attempts - 1:
                delay = base_delay * (attempt + 1) + random.uniform(1, 5)
                info_log(f'Login attempt {attempt + 1} failed for account {account_number}, waiting {int(delay)} seconds')
                sleep(delay)
            else:
                info_log(f'All login attempts failed for account {account_number}')
        
        return False, None

    def _write_success(self, private_key, wallet_address):
        with open(self.config['app']['success_file'], 'a') as f:
            f.write(f'{private_key}:{wallet_address}\n')
