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
import jwt
from typing import Dict, Optional, Tuple
from colorama import Fore
from .utils import error_log, success_log, info_log, rate_limit_log

class TokenManager:
    def __init__(self, account_storage, api_instance):
        self.account_storage = account_storage
        self.api = api_instance
        self.max_retries = 2

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
        last_claim = account_data.get('last_daily_claim')

        if not token or not cookies:
            return False, None, None

        if not self.validate_token(token) or not self.validate_cookies(cookies):
            return False, None, None

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

    def try_stored_credentials(self, wallet_address: str, account_number: int) -> Tuple[bool, Optional[str]]:
        is_valid, token, cookies = self.check_stored_credentials(wallet_address)
        if not is_valid:
            return False, None

        for cookie_name, cookie_value in cookies.items():
            self.api.session.cookies.set(cookie_name, cookie_value)

        for attempt in range(self.max_retries):
            try:
                success = self._test_token(token, wallet_address, account_number)
                if success:
                    return True, token
            except Exception as e:
                rate_limit_log(f"Error testing stored credentials (attempt {attempt + 1}): {str(e)}")
                sleep(1)

        return False, None

    def _test_token(self, token: str, wallet_address: str, account_number: int) -> bool:
        headers = {
            'Accept': 'application/json, text/plain, */*',
            'Authorization': f'Bearer {token}',
            'Origin': 'https://fantasy.top',
            'Referer': 'https://fantasy.top/',
        }
        
        try:
            response = self.api.session.get(
                'https://fantasy.top/api/get-player-basic-data',
                params={"playerId": wallet_address},
                headers=headers,
                proxies=self.api.proxies
            )
            if response.status_code == 429:
                rate_limit_log(f'Rate limit hit while testing token for account {account_number}')
                return False
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False

    def update_credentials(self, wallet_address: str, token: str, cookies: dict):
        account_data = self.account_storage.get_account_data(wallet_address)
        if account_data:
            self.account_storage.update_account(
                wallet_address,
                account_data["private_key"],
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
    def __init__(self, web3_provider, session, proxies, config, user_agent, account_storage):
        self.web3 = Web3(Web3.HTTPProvider(web3_provider))
        self.session = session
        self.proxies = proxies
        self.config = config
        self.user_agent = user_agent
        self.base_url = "https://fantasy.top"
        self.api_url = "https://api-v2.fantasy.top"
        self.account_storage = account_storage
        self.token_manager = TokenManager(account_storage, self)
        
    def _init_session(self):
        max_retries = 3
        
        self.session.headers.update({
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            'Origin': self.base_url,
            'Referer': f'{self.base_url}/',
            'User-Agent': self.user_agent,
            'Privy-App-Id': 'clra3wyj700lslb0frokrj261',
            'Privy-Client': 'react-auth:1.92.8',
            'Privy-Client-Id': 'client-WY2gt82Pt8inAqcq7bpeCwm6Y42kx96jX6hVeVwF8K1qQ',
            'Privy-Ca-Id': '315a64ce-afe9-4e58-87ea-3abd2d9a9484'
        })
        
        for attempt in range(max_retries):
            try:
                response = self.session.get(
                    'https://fantasy.top/cdn-cgi/rum',
                    proxies=self.proxies,
                    timeout=10
                )
                self.session.cookies.update(response.cookies)

                response = self.session.get(
                    'https://auth.privy.io/api/v1/apps/clra3wyj700lslb0frokrj261',
                    proxies=self.proxies,
                    timeout=10
                )
                self.session.cookies.update(response.cookies)

                maintenance_response = self.session.get(
                    'https://api-v2.fantasy.top/common/maintenance',
                    headers=self.get_headers(),
                    proxies=self.proxies
                )
                
                if all([
                    response.status_code == 200,
                    maintenance_response.status_code in [200, 401]
                ]):
                    return True
                    
                if attempt < max_retries - 1:
                    info_log(f'Session initialization retry {attempt + 1}/{max_retries} - status codes: {response.status_code}, {maintenance_response.status_code}')
                    sleep(1)
                    continue
                    
            except requests.exceptions.ReadTimeout:
                if attempt < max_retries - 1:
                    info_log(f'Session initialization timeout, retrying ({attempt + 1}/{max_retries})...')
                    sleep(1)
                    continue
                info_log(f'Session initialization timeout after {max_retries} attempts - need proxy change')
                return False
            except requests.exceptions.ProxyError:
                if attempt < max_retries - 1:
                    info_log(f'Proxy connection error, retrying ({attempt + 1}/{max_retries})...')
                    sleep(1)
                    continue
                info_log(f'Proxy connection failed after {max_retries} attempts - need proxy change')
                return False
            except Exception as e:
                if attempt < max_retries - 1:
                    info_log(f'Session initialization error, retrying ({attempt + 1}/{max_retries}): {str(e)}')
                    sleep(1)
                    continue
                info_log(f'Session initialization failed after {max_retries} attempts: {str(e)}')
                return False
        
        return False

    def login(self, private_key, wallet_address, account_number):
        max_retries = 5
        
        for attempt in range(max_retries):
            try:
                if not self._init_session():
                    if attempt < max_retries - 1:
                        sleep(1)
                        continue
                    return False

                init_payload = {'address': wallet_address}
                init_headers = {
                    'Accept': 'application/json',
                    'Content-Type': 'application/json',
                    'Privy-App-Id': 'clra3wyj700lslb0frokrj261',
                    'Privy-Client': 'react-auth:1.92.8',
                    'Privy-Ca-Id': '315a64ce-afe9-4e58-87ea-3abd2d9a9484'
                }
                
                init_response = self.session.post(
                    'https://privy.fantasy.top/api/v1/siwe/init', 
                    json=init_payload,
                    headers=init_headers,
                    proxies=self.proxies
                )

                if init_response.status_code == 429:
                    rate_limit_log(f'Rate limit hit for account {account_number}')
                    if attempt < max_retries - 1:
                        sleep(2)
                        continue
                    return False

                if init_response.status_code != 200:
                    error_log(f'SIWE init failed for account {account_number}: Status {init_response.status_code}')
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
                    headers=init_headers,
                    proxies=self.proxies
                )

                if auth_response.status_code == 429:
                    rate_limit_log(f'Rate limit hit for account {account_number}')
                    if attempt < max_retries - 1:
                        sleep(2)
                        continue
                    return False

                if auth_response.status_code != 200:
                    error_log(f'Authentication failed for account {account_number}: {auth_response.status_code}')
                    return False

                auth_data = auth_response.json()
                cookies_dict = {cookie.name: cookie.value for cookie in self.session.cookies}
                
                if 'token' in auth_data:
                    self.session.cookies.set('privy-token', auth_data['token'])
                if 'privy_access_token' in auth_data:
                    self.session.cookies.set('privy-access-token', auth_data['privy_access_token'])

                self.account_storage.update_account(
                    wallet_address,
                    private_key,
                    token=auth_data.get('token'),
                    cookies=cookies_dict
                )
                
                info_log(f'Authentication successful for account {account_number}: {wallet_address}')
                return auth_data

            except Exception as e:
                if attempt < max_retries - 1:
                    sleep(1)
                    continue
                error_log(f'Login error for account {account_number}: {str(e)}')
                return False

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
        try:
            headers = {
                'Accept': 'application/json, text/plain, */*',
                'Authorization': f'Bearer {token}',
                'Origin': self.base_url,
                'Referer': f'{self.base_url}/',
                'Content-Length': '0'
            }

            response = self.session.post(
                f'{self.api_url}/quest/daily-claim',
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
                            return self.daily_claim(new_token, wallet_address, account_number)

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
                    prize = data.get("selectedPrize", {}).get("id", "No prize selected")
                    success_log(f'№{account_number}:{wallet_address}: {Fore.GREEN}RECORD:{daily_streak}{Fore.LIGHTBLACK_EX}, {Fore.GREEN}CURRENT:{current_day}{Fore.LIGHTBLACK_EX}, {Fore.GREEN}PRIZE:{prize}{Fore.LIGHTBLACK_EX}')
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
                        success_log(f"{account_number}: {wallet_address}: Next claim: {hours}h {minutes}m")
                    return True

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
        private_key = self.account_storage.get_account_data(wallet_address)["private_key"]
        
        try:
            headers = {
                'Accept': '*/*',
                'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json',
                'Origin': self.base_url,
                'Referer': f'{self.base_url}/rewards'
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

            if response.status_code == 401:
                auth_data = self.login(private_key, wallet_address, account_number)
                if auth_data:
                    new_token = self.get_token(auth_data, wallet_address, account_number)
                    if new_token:
                        return self.quest_claim(new_token, wallet_address, account_number, quest_id)

            if response.status_code == 201:
                success_log(f'Successfully claimed quest {quest_id} for account {account_number}: {wallet_address}')
                return True

            error_log(f'Quest claim failed for account {account_number}: {wallet_address}!')
            return False

        except Exception as e:
            error_log(f'Quest claim error for account {account_number}: {str(e)}')
            return False

    def info(self, token, wallet_address, account_number):
        try:
            headers = self.get_headers(token)
            response = self.session.get(
                f'{self.base_url}/api/get-player-basic-data',
                params={"playerId": wallet_address},
                headers=headers,
                proxies=self.proxies
            )

            if response.status_code == 401:
                account_data = self.account_storage.get_account_data(wallet_address)
                if account_data:
                    auth_data = self.login(account_data["private_key"], wallet_address, account_number)
                    if auth_data:
                        new_token = self.get_token(auth_data, wallet_address, account_number)
                        if new_token:
                            return self.info(new_token, wallet_address, account_number)

            if response.status_code == 200:
                data = response.json()
                player_data = data.get('players_by_pk', {})
                
                fantasy_points = player_data.get('fantasy_points', 0)
                stars = player_data.get('stars', 0)
                is_onboarding_done = player_data.get('is_onboarding_done', False)
                gold = player_data.get('gold', '0')
                portfolio_value = player_data.get('portfolio_value', 0)
                number_of_cards = player_data.get('number_of_cards', '0')
                rewards = data.get('rewards', [])

                result_line = (f"{wallet_address}:"
                            f"stars={stars}:"
                            f"is_onboarding_done={is_onboarding_done}:"
                            f"gold={gold}:"
                            f"portfolio_value={portfolio_value}:"
                            f"number_of_cards={number_of_cards}:"
                            f"rewards={'Yes' if rewards else 'No'}:"
                            f"fantasy_points={fantasy_points}")

                with open(self.config['app']['result_file'], 'a') as f:
                    f.write(result_line + '\n')

                success_log(f"Info collected for account {account_number}: {wallet_address}")
                return True

            error_log(f'Error getting info for account {account_number}: {wallet_address} | Status Code: {response.status_code}')
            return False

        except Exception as e:
            error_log(f"Error in info function for account {account_number}: {wallet_address}: {str(e)}")
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

    def transfer_eth(self, from_private_key, from_address, to_address):
        try:
            balance_wei = self.web3.eth.get_balance(from_address)
            balance_eth = float(self.web3.from_wei(balance_wei, 'ether'))
            
            initial_gas_reserve = 0.000001
            
            transfer_amount = balance_eth - initial_gas_reserve
            
            if transfer_amount <= 0:
                error_log(f'Insufficient balance for transfer from {from_address}')
                return False

            if transfer_amount < self.config['app']['min_balance']:
                error_log(f'Transfer amount too small: {transfer_amount} ETH')
                return False

            try:
                transaction = {
                    'nonce': self.web3.eth.get_transaction_count(from_address),
                    'to': self.web3.to_checksum_address(to_address),
                    'value': self.web3.to_wei(transfer_amount, 'ether'),
                    'gas': 21000,
                    'maxFeePerGas': self.web3.eth.gas_price * 2,
                    'maxPriorityFeePerGas': self.web3.to_wei(0.000000001, 'gwei'),
                    'type': 2,
                    'chainId': 81457
                }

                signed_txn = self.web3.eth.account.sign_transaction(transaction, from_private_key)
                tx_hash = self.web3.eth.send_raw_transaction(signed_txn.rawTransaction)
                
                success_log(f'Sending {transfer_amount} ETH from {from_address} to {to_address}')
                success_log(f'TX Hash: {tx_hash.hex()}')
                
                receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
                return receipt['status'] == 1

            except Exception as e:
                error_log(f'Transfer error: {str(e)}')
                return False

        except Exception as e:
            error_log(f'Critical error in transfer_eth: {str(e)}')
            return False

    def tactic_claim(self, token, wallet_address, account_number, total_accounts):
        private_key = self.account_storage.get_account_data(wallet_address)["private_key"]
        
        try:
            headers = {
                'Accept': '*/*',
                'Authorization': f'Bearer {token}',
                'Origin': self.base_url,
                'Referer': f'{self.base_url}/play/tactics'
            }

            register_response = self.session.post(
                f'{self.base_url}/api/tactics/register',
                json={"tacticId": self.config['tactic']['id']},
                headers=headers,
                proxies=self.proxies
            )

            if register_response.status_code == 400:
                success_log(f'DECK REGISTER {account_number}')
                return True

            if register_response.status_code == 401:
                auth_data = self.login(private_key, wallet_address, account_number)
                if auth_data:
                    new_token = self.get_token(auth_data, wallet_address, account_number)
                    if new_token:
                        return self.tactic_claim(new_token, wallet_address, account_number, total_accounts)

            if register_response.status_code != 200:
                error_log(f'Error registering tactic for account {account_number}')
                return False

            tactic_id = register_response.json().get('id')
            info_log(f'Register: {account_number}: ID tactic {tactic_id}')

            deck_response = self.session.get(
                f'{self.api_url}/tactics/entry/{tactic_id}/choices',
                headers=self.get_headers(token),
                proxies=self.proxies
            )
                
            if deck_response.status_code != 200:
                error_log(f'Failed to get deck choices: {deck_response.status_code}')
                return False

            deck = deck_response.json()
            if not isinstance(deck, dict) or 'hero_choices' not in deck:
                error_log('Invalid deck response format')
                return False

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
                    else:
                        error_log(f'Error selecting alternative card with {stars} stars for account {account_number}')
                        return False

            if len(hero_choices) != len(stars_to_select) or total_stars > 24:
                error_log(f'Invalid card selection for account {account_number}. Total stars: {total_stars}')
                return False

            hero_choices_json = json.dumps(hero_choices)
            payload_card = {
                "tacticPlayerId": tactic_id,
                "heroChoices": hero_choices_json
            }

            deck_upload_response = self.session.post(
                f'{self.base_url}/api/tactics/deck/save',
                json=payload_card,
                headers=headers,
                proxies=self.proxies
            )

            if deck_upload_response.status_code == 200:
                success_log(f'Deck saved for account {account_number}')
                return True
            
            error_log(f'Save error {account_number}. Status: {deck_upload_response.status_code}')
            return False

        except Exception as e:
            error_log(f'Tactic claim error for account {account_number}: {str(e)}')
            return False

    def _get_deck_for_account(self, account_number, total_accounts):
        accounts_per_deck = math.ceil(total_accounts / len(self.config['tactic']['decks']))
        deck_index = min((account_number - 1) // accounts_per_deck, len(self.config['tactic']['decks']) - 1)
        return self.config['tactic']['decks'][deck_index]

    def _select_card_by_stars(self, stars, deck, used_cards):
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
