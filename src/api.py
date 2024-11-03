import json
import logging
from time import sleep
import random
import requests
from web3 import Web3
from eth_account.messages import encode_defunct
from datetime import datetime
from dateutil import parser
import pytz
import math
from colorama import Fore
from .utils import error_log, success_log, info_log

class FantasyAPI:
    def __init__(self, web3_provider, session, proxies, config):
        self.web3 = Web3(Web3.HTTPProvider(web3_provider))
        self.session = session
        self.proxies = proxies
        self.config = config
        self.base_url = "https://fantasy.top"
        self.api_url = "https://api-v2.fantasy.top"

    def get_headers(self, token=None):
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
            'Origin': self.base_url,
            'Referer': f'{self.base_url}/'
        }
        if token:
            headers['Authorization'] = f'Bearer {token}'
        return headers

    def login(self, private_key, wallet_address, account_number):
        try:
            init_payload = {'address': wallet_address}
            init_headers = {
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'Privy-App-Id': 'clra3wyj700lslb0frokrj261',
                'Privy-Client': 'react-auth:1.88.1',
                'Origin': self.base_url,
                'Referer': f'{self.base_url}/',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
            }
            
            init_response = self.session.post(
                'https://auth.privy.io/api/v1/siwe/init', 
                json=init_payload, 
                headers=init_headers, 
                proxies=self.proxies
            )

            if init_response.status_code == 429:
                info_log(f'INIT: Too many requests. Waiting before retry for account {account_number}: {wallet_address}')
                sleep(10)
                return self.login(private_key, wallet_address, account_number)

            if init_response.status_code == 524:
                info_log(f"{account_number}: {wallet_address} ERROR 524 init_response, retry LOGIN")
                sleep(10)
                return self.login(private_key, wallet_address, account_number)

            if init_response.status_code != 200:
                error_log(f'Error during nonce request for account {account_number}: {wallet_address}|Status Code: {init_response.status_code}')
                error_log(init_response.text)
                return False

            nonce_data = init_response.json()
            message = self._create_sign_message(wallet_address, nonce_data['nonce'])
            signed_message = self._sign_message(message, private_key)

            auth_payload = {
                'chainId': 'eip155:81457',
                'connectorType': 'injected',
                'message': message,
                'signature': signed_message.signature.hex(),
                'walletClientType': 'metamask'
            }

            auth_response = self.session.post(
                'https://privy.fantasy.top/api/v1/siwe/authenticate',
                json=auth_payload, 
                headers=init_headers, 
                proxies=self.proxies
            )

            if auth_response.status_code == 524:
                info_log(f"{account_number}: {wallet_address} ERROR 524 auth_response, retry LOGIN")
                sleep(10)
                return self.login(private_key, wallet_address, account_number)

            if auth_response.status_code == 429:
                error_log(f'AUTH_INIT: Too many requests. Waiting before retry for account {account_number}: {wallet_address}')
                sleep(10)
                return self.login(private_key, wallet_address, account_number)

            if auth_response.status_code != 200:
                error_log(f'Error during authentication for account {account_number}: {wallet_address}|Status Code: {auth_response.status_code}')
                error_log(auth_response.text)
                return False

            auth_data = auth_response.json()

            for cookie in auth_response.cookies:
                self.session.cookies.set_cookie(cookie)

            info_log(f'Authentication successful for account {account_number}: {wallet_address}')
            return auth_data

        except requests.exceptions.RequestException as ex:
            error_log(f'Error during authentication for account {account_number}: {wallet_address}')
            error_log(str(ex))
            return False

    def get_token(self, auth_data, wallet_address, account_number):
        try:
            headers = {
                'Accept': 'application/json, text/plain, */*',
                'Accept-Encoding': 'gzip, deflate, br, zstd',
                'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
                'Content-Type': 'application/json',
                'Origin': self.base_url,
                'Referer': f'{self.base_url}/onboarding/home',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36'
            }

            payload = {"address": wallet_address}

            response = self.session.post(
                f'{self.base_url}/api/auth/privy',
                json=payload,
                headers=headers,
                proxies=self.proxies,
                timeout=30
            )

            if response.status_code == 200:
                token = response.json().get('token')
                info_log(f'Privy request successful for account {account_number}: {wallet_address}')
                return token
            else:
                error_log(f'Error during Privy request for account {account_number}: {wallet_address}|Status Code: {response.status_code}')
                error_log(response.text)
                return False
        except requests.exceptions.RequestException as ex:
            error_log(f'Error during Privy request for account {account_number}: {wallet_address}')
            error_log(str(ex))
            return False

    def daily_claim(self, token, wallet_address, account_number):
        try:
            headers = {
                'Accept': 'application/json, text/plain, */*',
                'Accept-Encoding': 'gzip, deflate, br, zstd',
                'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
                'Authorization': f'Bearer {token}',
                'Content-Length': '0',
                'Origin': self.base_url,
                'Referer': f'{self.base_url}/',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36'
            }

            response = self.session.post(
                f'{self.api_url}/quest/daily-claim',
                headers=headers,
                data="",
                proxies=self.proxies,
                timeout=30
            )

            if response.status_code == 201:
                data = response.json()
                if data.get("success", False):
                    daily_streak = data.get("dailyQuestStreak", "N/A")
                    current_day = data.get("dailyQuestProgress", "N/A")
                    prize = data.get("selectedPrize", {}).get("id", "No prize selected")
                    
                    success_log(f'№{account_number}:{wallet_address}: '
                              f'{Fore.GREEN}RECORD:{daily_streak}{Fore.LIGHTBLACK_EX}, '
                              f'{Fore.GREEN}CURRENT:{current_day}{Fore.LIGHTBLACK_EX}, '
                              f'{Fore.GREEN}PRIZE:{prize}{Fore.LIGHTBLACK_EX}')
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
                        
                        success_log(f"{account_number}: {wallet_address}: "
                                  f"Next claim: {hours}h {minutes}m")
                    else:
                        success_log(f"{account_number} claim next $$$$$$$$$: {wallet_address}: {response.text}")
                    return True
            else:
                error_log(f'Error during daily claim for account {account_number}: {wallet_address} | Status Code: {response.status_code}')
                error_log(response.text)
                return False
        except requests.exceptions.RequestException as ex:
            error_log(f'Error during daily claim for account {account_number}: {wallet_address}')
            error_log(str(ex))
            return False

    def quest_claim(self, token, wallet_address, account_number):
        try:
            headers = {
                'Accept': '*/*',
                'Accept-Encoding': 'gzip, deflate, br, zstd',
                'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
                'Authorization': f'Bearer {token}',
                'Content-Length': '50',
                'Content-Type': 'application/json',
                'Origin': self.base_url,
                'Referer': f'{self.base_url}/rewards',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
            }

            payload = {
                "playerId": wallet_address,
                "questThresholdId": self.config['quest']['id']
            }

            response = self.session.post(
                f'{self.api_url}/quest/claim',
                json=payload,
                headers=headers,
                proxies=self.proxies
            )

            if response.status_code == 201:
                success_log(f'Successful quest claim for account {account_number}: {wallet_address}')
                return True
            elif response.status_code == 429:
                error_log(f'Too many requests. Waiting before retry for account {account_number}: {wallet_address}')
                sleep(10)
                return self.quest_claim(token, wallet_address, account_number)
            else:
                error_log(f'Quest claim failed for account {account_number}: {wallet_address}!')
                error_log(response.text)
                return False
        except requests.exceptions.RequestException as e:
            error_log(f'Error during quest claim request for account {account_number}: {wallet_address}')
            error_log(str(e))
            return False

    def tactic_claim(self, token, wallet_address, account_number, total_accounts):
        try:
            headers = {
                'Accept': '*/*',
                'Accept-Encoding': 'gzip, deflate, br, zstd',
                'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json',
                'Origin': self.base_url,
                'Referer': f'{self.base_url}/play/tactics',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
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

            if register_response.status_code != 200:
                error_log(f'Error registering tactic for account {account_number}. Status Code: {register_response.status_code}')
                error_log(register_response.text)
                return False

            tactic_id = register_response.json().get('id')
            info_log(f'Register: {account_number}: ID tactic {tactic_id}')

            sleep(random.uniform(2, 5))

            deck_response = self.session.get(
                f'{self.api_url}/tactics/entry/{tactic_id}/choices',
                headers=self.get_headers(token),
                proxies=self.proxies
            )

            if deck_response.status_code != 200:
                error_log(f'Error getting hero choices for account {account_number}. Status Code: {deck_response.status_code}')
                error_log(deck_response.text)
                return False

            deck = deck_response.json()
            if not isinstance(deck, dict) or 'hero_choices' not in deck:
                error_log(f'Invalid deck format for account {account_number}')
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
                    total_stars += card['hero']['stars']
                else:
                    max_allowed_stars = 24 - total_stars
                    card = self._get_alternative_card(cards, used_cards, max_allowed_stars)
                    if card:
                        hero_choices.append(card)
                        total_stars += card['hero']['stars']
                    else:
                        error_log(f'Error selecting card with {stars} stars for account {account_number}')
                        return False

            if len(hero_choices) != len(stars_to_select) or total_stars > 24:
                error_log(f'Failed to select valid cards for account {account_number}. Total stars: {total_stars}')
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
            else:
                error_log(f'Save error {account_number}. Status: {deck_upload_response.status_code}')
                error_log(deck_upload_response.text)
                return False

        except Exception as e:
            error_log(f'Tactic claim error for account {account_number}: {str(e)}')
            return False

    def info(self, token, wallet_address, account_number):
        try:
            response = self.session.get(
                f'{self.base_url}/api/get-player-basic-data',
                params={"playerId": wallet_address},
                headers=self.get_headers(token),
                proxies=self.proxies
            )

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
            else:
                error_log(f'Error getting info for account {account_number}: {wallet_address} | Status Code: {response.status_code}')
                error_log(response.text)
                return False

        except Exception as ex:
            error_log(f"Error in info function for account {account_number}: {wallet_address}")
            error_log(str(ex))
            return False

    def check_cookies(self):
        required_cookies = ['privy-token', 'privy-session', 'privy-access-token']
        return all(cookie in self.session.cookies for cookie in required_cookies)

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

    def _get_deck_for_account(self, account_number, total_accounts):
        accounts_per_deck = math.ceil(total_accounts / len(self.config['tactic']['decks']))
        deck_index = min((account_number - 1) // accounts_per_deck, len(self.config['tactic']['decks']) - 1)
        return self.config['tactic']['decks'][deck_index]