import json
import logging
from time import sleep
import random
import requests
from web3 import Web3
from eth_account.messages import encode_defunct
from datetime import datetime, timedelta
from dateutil import parser
import pytz
import math
import os
import jwt
from typing import Dict, Optional, Tuple
from colorama import Fore
from .utils import error_log, success_log, info_log, rate_limit_log

class TokenManager:
    def __init__(self, account_storage, api_instance):
        self.account_storage = account_storage
        self.api = api_instance
        self.max_retries = 2
        self.rate_limit_delay = 3
        self.stored_credentials_failed = set()

    def validate_token(self, token: str) -> bool:
        try:
            decoded = jwt.decode(token, options={"verify_signature": False})
            exp_timestamp = decoded.get('exp')
            if not exp_timestamp:
                return False
            
            expiration = datetime.fromtimestamp(exp_timestamp, pytz.UTC)
            current_time = datetime.now(pytz.UTC)
            
            return current_time < (expiration - timedelta(minutes=5))
        except jwt.InvalidTokenError:
            return False

    def validate_cookies(self, cookies: dict) -> bool:
        required_cookies = {
            'privy-token',
            'privy-session',
            'privy-access-token',
            'privy-refresh-token'
        }
        return all(cookie in cookies for cookie in required_cookies)

    def check_stored_credentials(self, wallet_address: str) -> tuple[bool, Optional[str], Optional[dict]]:
        account_data = self.account_storage.get_account_data(wallet_address)
        if not account_data:
            return False, None, None

        token = account_data.get('token')
        cookies = account_data.get('cookies')

        if not token or not cookies:
            return False, None, None

        if not self.validate_token(token):
            return False, None, None

        if wallet_address in self.stored_credentials_failed:
            return False, None, None

        last_claim = account_data.get('last_daily_claim')
        if last_claim:
            try:
                last_claim_time = datetime.fromisoformat(last_claim)
                next_claim = last_claim_time + timedelta(hours=24)
                if datetime.now(pytz.UTC) < next_claim:
                    info_log(f"Account {wallet_address} cannot claim daily yet. Next claim at {next_claim}")
                    return False, None, None
            except ValueError:
                return False, None, None

        return True, token, cookies

    def _test_token(self, token: str, wallet_address: str, account_number: int) -> bool:
        headers = {
            'Accept': 'application/json, text/plain, */*',
            'Authorization': f'Bearer {token}',
            'Origin': 'https://fantasy.top',
            'Referer': 'https://fantasy.top/',
        }
        
        for attempt in range(2):
            try:
                response = self.api.session.get(
                    'https://fantasy.top/api/get-player-basic-data',
                    params={"playerId": wallet_address},
                    headers=headers,
                    proxies=self.api.proxies,
                    timeout=10
                )
                
                if response.status_code == 429:
                    rate_limit_log(f'Rate limit hit while testing token for account {account_number}')
                    sleep(self.rate_limit_delay)
                    continue
                    
                return response.status_code == 200
                
            except requests.exceptions.RequestException:
                sleep(1)
                continue
                
        return False

    def try_stored_credentials(self, wallet_address: str, account_number: int) -> Tuple[bool, Optional[str]]:
        is_valid, token, cookies = self.check_stored_credentials(wallet_address)
        if not is_valid:
            return False, None

        if cookies:
            for cookie_name, cookie_value in cookies.items():
                self.api.session.cookies.set(cookie_name, cookie_value)

        token_valid = self._test_token(token, wallet_address, account_number)
        if not token_valid:
            return False, None
            
        return True, token

    def mark_stored_credentials_failed(self, wallet_address: str):
        self.stored_credentials_failed.add(wallet_address)

    def should_try_stored_credentials(self, wallet_address: str) -> bool:
        return wallet_address not in self.stored_credentials_failed

    def update_credentials(self, wallet_address: str, token: str, cookies: dict):
        self.account_storage.update_account(
            wallet_address,
            self.account_storage.get_account_data(wallet_address)["private_key"],
            token=token,
            cookies=cookies
        )

    def invalidate_credentials(self, wallet_address: str):
        account_data = self.account_storage.get_account_data(wallet_address)
        if account_data:
            self.account_storage.update_account(
                wallet_address,
                account_data["private_key"],
                token=None,
                cookies=None
            )

class FantasyAPI:
    def __init__(self, web3_provider, session, proxies, all_proxies, config, user_agent, account_storage):
        self.web3 = Web3(Web3.HTTPProvider(web3_provider))
        self.session = session
        self.proxies = proxies
        self.all_proxies = all_proxies
        self.config = config
        self.user_agent = user_agent
        self.base_url = "https://fantasy.top"
        self.api_url = "https://api-v2.fantasy.top"
        self.account_storage = account_storage
        self.token_manager = TokenManager(account_storage, self)
        
    
    def login(self, private_key, wallet_address, account_number):
        max_retries = 15
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                self.session.headers.update({
                    'Accept': 'application/json',
                    'Content-Type': 'application/json',
                    'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
                    'Origin': self.base_url,
                    'Referer': f'{self.base_url}/',
                    'User-Agent': self.user_agent,
                    'Privy-App-Id': 'clra3wyj700lslb0frokrj261',
                    'Privy-Client': 'react-auth:1.92.8',
                    'Privy-Client-Id': 'client-WY2gt82Pt8inAqcq7bpeCwm6Y42kx96jX6hVeVwF8K1qQ',
                    'Privy-Ca-Id': '315a64ce-afe9-4e58-87ea-3abd2d9a9484'
                })

                init_payload = {'address': wallet_address}
                
                init_response = self.session.post(
                    'https://privy.fantasy.top/api/v1/siwe/init', 
                    json=init_payload,
                    proxies=self.proxies
                )

                if init_response.status_code != 200:
                    if attempt < max_retries - 1:
                        proxy = random.choice(self.all_proxies)
                        self.proxies = {"http": proxy, "https": proxy}
                        info_log(f'Switching proxy for account {account_number} to: {proxy}')
                        sleep(retry_delay)
                        continue
                    info_log(f'SIWE init failed for account {account_number}: Status {init_response.status_code}')
                    return False

                nonce_data = init_response.json()
                message = self._create_sign_message(wallet_address, nonce_data['nonce'])
                signed_message = self._sign_message(message, private_key)

                auth_payload = {
                    'chainId': 'eip155:81457',
                    'connectorType': 'injected',
                    'message': message,
                    'signature': signed_message.signature.hex(),
                    'walletClientType': 'metamask',
                    'mode': 'login-or-sign-up'
                }

                auth_response = self.session.post(
                    'https://privy.fantasy.top/api/v1/siwe/authenticate',
                    json=auth_payload,
                    proxies=self.proxies
                )

                if auth_response.status_code != 200:
                    if attempt < max_retries - 1:
                        proxy = random.choice(self.all_proxies)
                        self.proxies = {"http": proxy, "https": proxy}
                        info_log(f'Switching proxy for account {account_number} to: {proxy}')
                        sleep(retry_delay)
                        continue
                    info_log(f'Authentication failed for account {account_number}: {auth_response.status_code}')
                    return False

                auth_data = auth_response.json()
                
                if 'token' in auth_data:
                    self.session.cookies.set('privy-token', auth_data['token'])
                if auth_data.get('identity_token'):
                    self.session.cookies.set('privy-id-token', auth_data['identity_token'])
                
                final_auth_headers = {
                    'Accept': 'application/json, text/plain, */*',
                    'Content-Type': 'application/json',
                    'Origin': self.base_url,
                    'Referer': f'{self.base_url}/onboarding/home'
                }
                
                final_auth_payload = {"address": wallet_address}
                
                final_auth_response = self.session.post(
                    f'{self.base_url}/api/auth/privy',
                    json=final_auth_payload,
                    headers=final_auth_headers,
                    proxies=self.proxies
                )
                
                if final_auth_response.status_code != 200:
                    if attempt < max_retries - 1:
                        proxy = random.choice(self.all_proxies)
                        self.proxies = {"http": proxy, "https": proxy}
                        info_log(f'Switching proxy for account {account_number} to: {proxy}')
                        sleep(retry_delay)
                        continue
                    error_log(f'Final auth failed for account {account_number}: {final_auth_response.status_code}')
                    return False

                final_auth_data = final_auth_response.json()
                cookies_dict = {cookie.name: cookie.value for cookie in self.session.cookies}

                self.account_storage.update_account(
                    wallet_address,
                    private_key,
                    token=final_auth_data.get('token'),
                    cookies=cookies_dict
                )
                
                info_log(f'Authentication successful for account {account_number}: {wallet_address}')
                return final_auth_data

            except Exception as e:
                info_log(f'Login error for account {account_number}: {str(e)}')
                if attempt < max_retries - 1:
                    proxy = random.choice(self.all_proxies)
                    self.proxies = {"http": proxy, "https": proxy}
                    info_log(f'Switching proxy for account {account_number} to: {proxy}')
                    sleep(retry_delay)
                    continue

        return False
        
    def get_token(self, auth_data, wallet_address, account_number):
        try:
            headers = {
                'Accept': 'application/json, text/plain, */*',
                'Content-Type': 'application/json',
                'Origin': self.base_url,
                'Referer': f'{self.base_url}/onboarding/home'
            }

            payload = {"address": wallet_address}

            response = self.session.post(
                f'{self.base_url}/api/auth/privy',
                json=payload,
                headers=headers,
                proxies=self.proxies,
                timeout=10
            )

            if response.status_code == 200:
                token = response.json().get('token')
                if token:
                    self.account_storage.update_account(
                        wallet_address,
                        self.account_storage.get_account_data(wallet_address)["private_key"],
                        token=token
                    )
                info_log(f'Token obtained for account {account_number}: {wallet_address}')
                return token
            
            error_log(f'Token request failed for account {account_number}: {response.status_code}')
            return False

        except Exception as e:
            error_log(f'Token error for account {account_number}: {str(e)}')
            return False

    def daily_claim(self, token, wallet_address, account_number):
        max_retries = 5
        retry_delay = 1
        
        headers = {
            'Accept': 'application/json, text/plain, */*',
            'Authorization': f'Bearer {token}',
            'Origin': self.base_url,
            'Referer': f'{self.base_url}/',
            'Content-Length': '0'
        }

        while True:
            try:
                response = self.session.post(
                    f'{self.api_url}/quest/daily-claim',
                    headers=headers,
                    data="",
                    proxies=self.proxies,
                    timeout=10
                )

                if response.status_code == 500:
                    info_log(f'Daily claim returned 500 for account {account_number}, retrying same request...')
                    sleep(retry_delay)
                    continue

                if response.status_code == 201:
                    data = response.json()
                    if data.get("success", False):
                        self.account_storage.update_account(
                            wallet_address,
                            self.account_storage.get_account_data(wallet_address)["private_key"],
                            last_daily_claim=datetime.now(pytz.UTC).isoformat()
                        )
                        daily_streak = data.get("dailyQuestStreak", "N/A")
                        current_day = data.get("dailyQuestProgress", "N/A")
                        prize = data.get("selectedPrize", {})
                        prize_type = prize.get("type", "Unknown")
                        prize_amount = prize.get("text", "Unknown")
                        
                        success_log(f'Account {account_number} ({wallet_address}): '
                                  f'{Fore.GREEN}STREAK:{daily_streak}{Fore.RESET}, '
                                  f'{Fore.GREEN}DAY:{current_day}{Fore.RESET}, '
                                  f'{Fore.GREEN}PRIZE:{prize_type}({prize_amount}){Fore.RESET}')
                        return True
                    else:
                        next_due_time = data.get("nextDueTime")
                        if next_due_time:
                            next_due_datetime = parser.parse(next_due_time)
                            moscow_tz = pytz.timezone('Europe/Moscow')
                            current_time = datetime.now(moscow_tz)
                            time_difference = next_due_datetime.replace(tzinfo=pytz.UTC) - current_time.replace(tzinfo=moscow_tz)
                            hours, remainder = divmod(time_difference.seconds, 3600)
                            minutes, _ = divmod(remainder, 60)
                            success_log(f"Account {account_number}: {wallet_address}: Next claim available in {hours}h {minutes}m")
                        return True

                if response.status_code == 401:
                    account_data = self.account_storage.get_account_data(wallet_address)
                    if account_data:
                        auth_data = self.login(account_data["private_key"], wallet_address, account_number)
                        if auth_data:
                            new_token = self.get_token(auth_data, wallet_address, account_number)
                            if new_token:
                                return self.daily_claim(new_token, wallet_address, account_number)
                    return False

                error_log(f'Daily claim failed for account {account_number}: {response.status_code}')
                return False

            except Exception as e:
                error_log(f'Daily claim error for account {account_number}: {str(e)}')
                return False

    def _create_sign_message(self, wallet_address, nonce):
        return f"""fantasy.top wants you to sign in with your Ethereum account:
{wallet_address}

By signing, you are proving you own this wallet and logging in. This does not initiate a transaction or cost any fees.

URI: https://fantasy.top
Version: 1
Chain ID: 81457
Nonce: {nonce}
Issued At: {datetime.utcnow().isoformat()}Z
Resources:
- https://privy.io"""

    def _sign_message(self, message, private_key):
        return self.web3.eth.account.sign_message(
            encode_defunct(message.encode('utf-8')),
            private_key
        )

    def quest_claim(self, token, wallet_address, account_number, quest_id):
        try:
            headers = {
                'Accept': 'application/json, text/plain, */*',
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json',
                'Origin': self.base_url,
                'Referer': f'{self.base_url}/',
                'User-Agent': self.user_agent
            }

            payload = {
                "playerId": wallet_address,
                "questThresholdId": quest_id
            }

            response = self.session.post(
                f'{self.api_url}/quest/claim',
                json=payload,
                headers=headers,
                proxies=self.proxies
            )

            if response.status_code == 201 or response.status_code == 200:
                success_log(f'Successfully claimed quest {quest_id} for account {account_number}: {wallet_address}')
                return True

            elif response.status_code == 429:
                info_log(f'Rate limit on quest claim for account {account_number}, retrying...')
                return "429"

            elif response.status_code == 401:
                account_data = self.account_storage.get_account_data(wallet_address)
                if account_data:
                    auth_data = self.login(account_data["private_key"], wallet_address, account_number)
                    if auth_data:
                        new_token = self.get_token(auth_data, wallet_address, account_number)
                        if new_token:
                            return self.quest_claim(new_token, wallet_address, account_number, quest_id)

            error_log(f'Quest claim failed for account {account_number}: {response.status_code}')
            return False

        except Exception as e:
            error_log(f'Quest claim error for account {account_number}: {str(e)}')
            return False

    def fragments_claim(self, token, wallet_address, account_number, fragment_id):
        try:
            headers = {
                'Accept': 'application/json, text/plain, */*',
                'Authorization': f'Bearer {token}',
                'Origin': self.base_url,
                'Referer': f'{self.base_url}/',
                'Content-Length': '0'
            }

            response = self.session.post(
                f'{self.api_url}/quest/onboarding/complete/{fragment_id}',
                headers=headers,
                data="",
                proxies=self.proxies,
                timeout=10
            )

            if response.status_code == 401:
                account_data = self.account_storage.get_account_data(wallet_address)
                if account_data:
                    auth_data = self.login(account_data["private_key"], wallet_address, account_number)
                    if auth_data:
                        new_token = self.get_token(auth_data, wallet_address, account_number)
                        if new_token:
                            return self.fragments_claim(new_token, wallet_address, account_number, fragment_id)

            if response.status_code == 201:
                success_log(f'Successfully claimed fragment {fragment_id} for account {account_number}: {wallet_address}')
                return True

            error_log(f'Fragment claim failed for account {account_number}: {response.status_code}')
            return False

        except Exception as e:
            error_log(f'Fragment claim error for account {account_number}: {str(e)}')
            return False

    def info(self, token, wallet_address, account_number):
        try:
            headers = {
                'Accept': 'application/json, text/plain, */*',
                'Authorization': f'Bearer {token}',
                'Origin': self.base_url,
                'Referer': f'{self.base_url}/',
                'User-Agent': self.user_agent
            }

            response = self.session.get(
                f'{self.api_url}/player/basic-data/{wallet_address}',
                headers=headers,
                proxies=self.proxies
            )

            if response.status_code == 200:
                data = response.json()
                player_data = data.get('players_by_pk', {})
                rewards_status = "true" if data.get('rewards', []) else "false"
                
                result_file = self.config['app']['result_file']
                existing_addresses = set()
                if os.path.exists(result_file):
                    with open(result_file, 'r', encoding='utf-8') as f:
                        for line in f:
                            addr = line.split(':')[0]
                            existing_addresses.add(addr)
                
                gold_value = player_data.get('gold', '0')
                
                result_line = (
                    f"{wallet_address}:"
                    f"stars={player_data.get('stars', 0)}:"
                    f'gold="{gold_value}":'
                    f"portfolio_value={player_data.get('portfolio_value', 'None')}:"
                    f"number_of_cards={player_data.get('number_of_cards', '0')}:"
                    f"fantasy_points={player_data.get('fantasy_points', 0)}:"
                    f"rewards={rewards_status}"
                )

                if wallet_address not in existing_addresses:
                    with open(result_file, 'a', encoding='utf-8') as f:
                        f.write(result_line + '\n')

                success_log(f"Info collected for account {account_number}: {wallet_address}")
                return True
                
            elif response.status_code == 429:
                info_log(f'Rate limit on info check for account {account_number}, retrying...')
                return "429"

            error_log(f'Error getting info for account {account_number}: {response.status_code}')
            return False

        except Exception as e:
            error_log(f"Error in info function for account {account_number}: {str(e)}")
            return False
            
    def get_headers(self, token=None):
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'User-Agent': self.user_agent,
            'Origin': self.base_url,
            'Referer': f'{self.base_url}/'
        }
        if token:
            headers['Authorization'] = f'Bearer {token}'
        return headers

    def check_cookies(self):
        required_cookies = ['privy-token', 'privy-session', 'privy-access-token']
        return all(cookie in self.session.cookies for cookie in required_cookies)

    def check_eth_balance(self, address):
        try:
            balance_wei = self.web3.eth.get_balance(address)
            balance_eth = float(self.web3.from_wei(balance_wei, 'ether'))
            return balance_eth
        except Exception as e:
            error_log(f'Error checking balance for {address}: {str(e)}')
            return 0

    def toggle_free_tactics(self, token, wallet_address, account_number):
        headers = {
            'Accept': 'application/json, text/plain, */*',
            'Authorization': f'Bearer {token}',
            'Origin': self.base_url,
            'Referer': f'{self.base_url}/',
            'User-Agent': self.user_agent
        }

        max_attempts = 15
        delay_between_attempts = 5

        for attempt in range(max_attempts):
            try:
                info_log(f'Toggle attempt {attempt + 1}/{max_attempts} for account {account_number}')
                response = self.session.post(
                    'https://api-v2.fantasy.top/tactics/toggle-can-play-free-tactics', 
                    headers=headers, 
                    proxies=self.proxies
                )
                
                if response.status_code == 201:
                    data = response.json()
                    if data.get('can_play_free_tactics', False):
                        success_log(f'Got TRUE status for account {account_number}: {wallet_address}')
                        return True
                    else:
                        info_log(f'Attempt {attempt + 1}: Status still FALSE for account {account_number}')
                        sleep(delay_between_attempts)
                else:
                    error_log(f'Toggle request failed: {response.status_code}')
                    sleep(delay_between_attempts)

            except Exception as e:
                error_log(f'Toggle attempt {attempt + 1} error: {str(e)}')
                sleep(delay_between_attempts)

        return False

    def wait_for_balance(self, address, required_balance, max_attempts=30, check_delay=3):
        for attempt in range(max_attempts):
            current_balance = self.check_eth_balance(address)
            info_log(f'Balance check attempt {attempt + 1}/{max_attempts} for {address}: {current_balance} ETH')
            
            if current_balance >= required_balance:
                success_log(f'Required balance reached for {address}: {current_balance} ETH')
                return True
                
            info_log(f'Waiting for balance... Current: {current_balance} ETH, Required: {required_balance} ETH')
            sleep(check_delay)
        
        error_log(f'Balance never reached required amount for {address}')
        return False

    def transfer_eth(self, from_private_key, from_address, to_address):
        max_retries = 3
        base_gas_reserve = 0.000003
        
        for attempt in range(max_retries):
            try:
                balance_wei = self.web3.eth.get_balance(from_address)
                balance_eth = float(self.web3.from_wei(balance_wei, 'ether'))
                
                current_gas_reserve = base_gas_reserve * (attempt + 1)
                
                transfer_amount = balance_eth - current_gas_reserve
                
                if transfer_amount <= 0:
                    error_log(f'Insufficient balance for transfer from {from_address} (attempt {attempt + 1})')
                    continue

                if transfer_amount < self.config['app']['min_balance']:
                    error_log(f'Transfer amount too small: {transfer_amount} ETH (attempt {attempt + 1})')
                    continue

                transaction = {
                    'nonce': self.web3.eth.get_transaction_count(from_address),
                    'to': self.web3.to_checksum_address(to_address),
                    'value': self.web3.to_wei(transfer_amount, 'ether'),
                    'gas': 21000,
                    'maxFeePerGas': self.web3.eth.gas_price * (2 + attempt),
                    'maxPriorityFeePerGas': self.web3.to_wei(0.00000005 * (1 + attempt), 'gwei'),
                    'type': 2,
                    'chainId': 81457
                }

                signed_txn = self.web3.eth.account.sign_transaction(transaction, from_private_key)
                tx_hash = self.web3.eth.send_raw_transaction(signed_txn.rawTransaction)
                
                success_log(f'Sending {transfer_amount} ETH from {from_address} to {to_address} (attempt {attempt + 1})')
                success_log(f'TX Hash: {tx_hash.hex()}')
                
                receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
                if receipt['status'] == 1:
                    success_log(f'Transfer confirmed: {tx_hash.hex()}')
                    return True
                else:
                    error_log(f'Transfer failed: {tx_hash.hex()} (attempt {attempt + 1})')
                    continue

            except Exception as e:
                error_log(f'Transfer error (attempt {attempt + 1}): {str(e)}')
                if attempt < max_retries - 1:
                    sleep(2)
                continue
        
        return False

    def _make_transfer_to_next(self, account_number: int, total_accounts: int, wallet_address: str, private_key: str):
        max_transfer_attempts = 5
        transfer_delay = 3
        
        next_account = (account_number % total_accounts) + 1
        
        with open(self.config['app']['keys_file'], 'r') as f:
            lines = f.readlines()
            if next_account <= len(lines):
                _, target_address = lines[next_account - 1].strip().split(':')
                
                for attempt in range(max_transfer_attempts):
                    try:
                        transfer_success = self.transfer_eth(private_key, wallet_address, target_address)
                        if transfer_success:
                            success_log(f'Successfully transferred from account {account_number} to {next_account}')
                            return True
                        
                        error_log(f'Transfer attempt {attempt + 1} failed, retrying...')
                        sleep(transfer_delay)
                        
                    except Exception as e:
                        error_log(f'Transfer attempt {attempt + 1} error: {str(e)}')
                        if attempt < max_transfer_attempts - 1:
                            sleep(transfer_delay)
                        continue
                
                error_log(f'All transfer attempts failed for account {account_number} to {next_account}')
        return False

    def tactic_claim(self, token, wallet_address, account_number, total_accounts, old_account_flag):
        success = False
        try:
            if old_account_flag:
                private_key = self.account_storage.get_account_data(wallet_address)["private_key"]
                balance = self.check_eth_balance(wallet_address)
                
                if balance < self.config['app']['min_balance']:
                    info_log(f'Insufficient balance ({balance} ETH) for account {account_number}: {wallet_address}')
                    
                    prev_account = account_number - 1 if account_number > 1 else 1
                    with open(self.config['app']['keys_file'], 'r') as f:
                        lines = f.readlines()
                        if prev_account <= len(lines):
                            prev_private_key, prev_address = lines[prev_account - 1].strip().split(':')
                            prev_balance = self.check_eth_balance(prev_address)
                            
                            if prev_balance >= self.config['app']['min_balance']:
                                transfer_success = self.transfer_eth(prev_private_key, prev_address, wallet_address)
                                if not transfer_success or not self.wait_for_balance(wallet_address, self.config['app']['min_balance']):
                                    info_log(f'Failed to transfer or reach required balance for account {account_number}')
                            else:
                                info_log(f'Previous account {prev_account} has insufficient balance: {prev_balance} ETH')

                if not self.toggle_free_tactics(token, wallet_address, account_number):
                    info_log(f'Failed to get TRUE status for account {account_number}')

            headers = {
                'Accept': 'application/json, text/plain, */*',
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {token}',
                'Origin': self.base_url,
                'Referer': f'{self.base_url}/play/tactics'
            }

            register_payload = {"tactic_id": self.config['tactic']['id']}
            register_response = self.session.post(
                f'{self.api_url}/tactics/register',
                json=register_payload,
                headers=headers,
                proxies=self.proxies,
                timeout=15
            )

            if register_response.status_code == 400:
                success_log(f'Already registered in tactic {account_number}')
                success = True
            else:
                try:
                    response_data = register_response.json()
                    if "id" in response_data:
                        success_log(f'Successfully registered in tactic {account_number} with ID: {response_data["id"]}')
                        success = True

                        entry_id = response_data["id"]
                        deck_response = self.session.get(
                            f'{self.api_url}/tactics/entry/{entry_id}/choices',
                            headers=self.get_headers(token),
                            proxies=self.proxies
                        )
                                
                        if deck_response.status_code == 200:
                            deck = deck_response.json()
                            if isinstance(deck, dict) and 'hero_choices' in deck:
                                cards = deck['hero_choices']
                                stars_to_select = self._get_deck_for_account(account_number, total_accounts)

                                used_cards = []
                                hero_choices = []
                                total_stars = 0

                                for stars in stars_to_select:
                                    card = self._select_card_by_stars(stars, cards, used_cards)
                                    if card:
                                        hero_choices.append(card)
                                        total_stars += card['hero_score']['stars']
                                    else:
                                        max_allowed_stars = 24 - total_stars
                                        card = self._get_alternative_card(cards, used_cards, max_allowed_stars)
                                        if card:
                                            hero_choices.append(card)
                                            total_stars += card['hero_score']['stars']

                                if len(hero_choices) == len(stars_to_select) and total_stars <= 24:
                                    save_payload = {
                                        "tacticPlayerId": entry_id,
                                        "heroChoices": hero_choices
                                    }

                                    save_response = self.session.post(
                                        f'{self.api_url}/tactics/save-deck',
                                        json=save_payload,
                                        headers=headers,
                                        proxies=self.proxies
                                    )

                                    if save_response.status_code == 200:
                                        success_log(f'Deck saved for account {account_number}')
                                    else:
                                        info_log(f'Save error {account_number}. Status: {save_response.status_code}')
                except Exception as e:
                    error_log(f'Error processing deck for account {account_number}: {str(e)}')

        except Exception as e:
            error_log(f'Tactic claim error for account {account_number}: {str(e)}')
            success = False
        
        finally:
            if old_account_flag:
                try:
                    self._make_transfer_to_next(account_number, total_accounts, wallet_address, private_key)
                except Exception as e:
                    error_log(f'Transfer error after tactic for account {account_number}: {str(e)}')
            
            return success

    def _get_deck_for_account(self, account_number: int, total_accounts: int):
        accounts_per_deck = math.ceil(total_accounts / len(self.config['tactic']['decks']))
        deck_index = min((account_number - 1) // accounts_per_deck, len(self.config['tactic']['decks']) - 1)
        return self.config['tactic']['decks'][deck_index]

    def _select_card_by_stars(self, stars: int, deck: list, used_cards: list):
        for card in deck:
            if isinstance(card, dict) and 'hero' in card and 'stars' in card['hero']:
                if card['hero']['stars'] == stars and card not in used_cards:
                    used_cards.append(card)
                    return card
        return None

    def _get_alternative_card(self, deck, used_cards, max_stars):
        for card in deck:
            if card not in used_cards and card['hero']['stars'] <= max_stars:
                used_cards.append(card)
                return card
        return None
