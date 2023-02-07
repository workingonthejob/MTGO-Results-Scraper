import requests
import argparse
import sys
import os
import re
import logging
import json
from PIL import Image
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium import webdriver
from logging.config import fileConfig


fileConfig('logging_config.ini')
log = logging.getLogger()

DESCRIPTION = """
Scrape and/or screenshot the Magic: The Gathering match results.
"""
TIMEOUT = 10
REDDIT_PATTERN = r'(\d+\.|\-)\s(\[.*\]).*\*\*(.*)\*\*'
MTGO_RESULTS_PAGE_DATE_RE = '\\w+\\s\\d{1,2},\\s\\d{4}'
MTGO_RESULTS_PAGE_DATE_SP_RE = '(\\d{1,2}) de (\\w+) de (\\d{4})'
MTGO_RESULTS_PAGE_DATE_GR_RE = '(\\d{1,2}) (\\w+) (\\d{4})'

# Example Matches
# The Chicken Cow (32nd Place)
# Tree_for_all (31st Place)
# UnstableVuDoo (5-0)
WIZARDS_NAME_PATTERN = r'^(.*)(((\s\(\d{0,}\-\d{0,}\)))|(\s\(.*\s(?i)Place\)))$'


class MTGOResultsScraper():

    def __init__(self, url, output_dir, take_screenshots, crop_screenshots):
        self.url = url
        self.output_dir = output_dir
        self.take_screenshots = take_screenshots
        self.crop_screenshots = crop_screenshots
        self.mtgo_output_folder_dir = None
        self.folder_name = None
        self.league = None
        self.date = None
        self.screenshots = []
        self.driver = None
        self.number_of_decks = None
        self.x_header = '//nav[@id="siteNavDesktop"]'
        self.x_deck_container = '//section[@class="decklist"]'
        self.x_player = './/p[@class="decklist-player"]'
        self.x_card_name = './/a[@data-card-title="{card}"]'
        self.x_main_card_names ='.//div[@class="decklist-sort-group decklist-sort-type"]//div[@class="decklist-category-columns"]//li[@class="decklist-category-card"]/a'
        self.x_main_card_counts = './/div[@class="sorted-by-overview-container sortedContainer"]//span[@class="card-count"]'
        self.x_side_card_names = './/div[@class="decklist-sort-group decklist-sort-type"]//ul[@class="decklist-category-list decklist-sideboard decklist-category-columns"]/li/a'
        self.x_side_card_counts = './/div[@class="sorted-by-sideboard-container  clearfix element"]//span[@class="card-count"]'
        self.x_no_thanks_btn = '//button[@class="decline-button eu-cookie-compliance-default-button"]'
        self.x_accept_all_cookies_btn = './/button[@id="tarteaucitronPersonalize2"]'
        self.x_reject_all_cookies_btn = './/button[@id="tarteaucitronAllDenied2"]'
        self.x_cookie_notification = '//div[@id="tarteaucitronAlertBig"]'
        self.x_league_type = './/h1'
        self.x_decklist_actions = './/div[@class="decklist-actions"]'
        self.headers = {'User-Agent':
                        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                        'AppleWebKit/537.36 (KHTML, like Gecko) '
                        'Chrome/102.0.0.0 Safari/537.36',
                        'accept': 'application/json',
                        'Accept-Language': 'en_US'}
        self.session = None
        # self.initialize_web_driver() if not self.driver else None

    def get_output_dir(self):
        return self.output_dir

    def get_mtgo_output_folder_dir(self):
        return self.mtgo_output_folder_dir

    def get_folder_name(self):
        return self.folder_name

    def get_screenshots(self):
        return self.screenshots

    def get_number_of_decks(self):
        return self.number_of_decks

    def start_session(self):
        session = requests.Session()
        retry = Retry(connect=3, backoff_factor=0.5)
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        self.session = session.get(self.url, headers=self.headers)

    def get_decklists(self):

        decks = []
        try:
            self.initialize_web_driver() if not self.driver else None
            wait = WebDriverWait(self.driver, TIMEOUT)
            deck_containers = self.find_elements_with_xpath(self.x_deck_container)
            clickable = ec.element_to_be_clickable((By.XPATH, self.x_accept_all_cookies_btn))
            accept_all_btn = wait.until(clickable)
            accept_all_btn.click()
            for deck in deck_containers:
                mainboard = {}
                sideboard = {}
                container = {"Mainboard": mainboard,
                             "Sideboard": sideboard,
                             "Player": None}
                raw_name = deck.find_element(by=By.XPATH, value=self.x_player).text
                player = re.search(WIZARDS_NAME_PATTERN, raw_name).group(1)
                container["Player"] = player
                main_card_names = deck.find_elements(by=By.XPATH, value=self.x_main_card_names)
                main_card_counts = [re.search(r'^\w{1,}', card.text) for card in main_card_names]
                side_card_names = deck.find_elements(by=By.XPATH, value=self.x_side_card_names)
                side_card_counts = [re.search(r'^\w{1,}', card.text).group() for card in side_card_names]
                total_cards_main = 0
                total_cards_side = 0
                for i in range(len(main_card_counts)):
                    number_of_cards = int(main_card_counts[i].group())
                    card_name = re.search(r'^\w{1,} (.*)$', main_card_names[i].text).group(1)
                    total_cards_main += number_of_cards
                    mainboard[card_name] = number_of_cards

                for i in range(len(side_card_names)):
                    number_of_cards = int(side_card_counts[i])
                    card_name = re.search(r'^\w{1,} (.*)$', side_card_names[i].text).group(1)
                    total_cards_side += number_of_cards
                    sideboard[card_name] = number_of_cards
                decks.append(json.dumps(container))
        except Exception as e:
            log.exception(e)
        finally:
            log.info('Quitting web driver')
            self.driver.quit()
        return decks

    def find_elements_with_xpath(self, xpath):
        return self.driver.find_elements(by=By.XPATH, value=xpath)

    def initialize_web_driver(self):
        log.info("Starting web driver.")
        arguments = ['--headless',
                     '--window-size=1920x1080',
                     '--no-sandbox',
                     '--disable-dev-shm-usage']
        # Define the options we want
        # More options here:
        # https://peter.sh/experiments/chromium-command-line-switches/
        options = Options()
        log.debug(f'Using options: {arguments}')
        for arg in arguments:
            options.add_argument(arg)
        # # Starting maximized headless doesn't work correctly.
        # options.add_argument("--window-size=1920x1080")
        # # Ubuntu chrome will throw errors if these is not included.
        # options.add_argument("--no-sandbox")
        # options.add_argument('--disable-dev-shm-usage')
        # This downloads the correct one.
        self.driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()), options=options)
        # This will use the Chromedriver in the current directory.
        # self.driver = webdriver.Chrome(options=options)
        self.driver.get(self.url)

    def take_decklist_screenshots(self):

        self.initialize_web_driver() if not self.driver else None

        self.league = self.find_elements_with_xpath(
            self.x_league_type)[0].text.title()

        self.create_folder_for_screenshots(self.league)
        hide = self.driver.execute_script
        header = self.find_elements_with_xpath(self.x_header)[0]
        js_display_none = "arguments[0].style.display = 'none'"
        js_visibility_hidden = "arguments[0].style.visibility = 'hidden'"
        wait = WebDriverWait(self.driver, TIMEOUT)

        try:
            hide(js_visibility_hidden, header)
            clickable = ec.element_to_be_clickable((By.XPATH, self.x_accept_all_cookies_btn))
            no_thanks_btn_elm = wait.until(clickable)
            cookie = self.find_elements_with_xpath(self.x_cookie_notification)[0]
            hide(js_display_none, cookie)
            self.highlight_latest_cards()
            decks = self.find_elements_with_xpath(self.x_deck_container)
            names = self.find_elements_with_xpath(self.x_player)
            icons = self.find_elements_with_xpath(self.x_decklist_actions)
            self.number_of_decks = len(decks)
            inner_containers = self.find_elements_with_xpath('.//div[@class="decklist-card-preview hidden-xs"]')

            for i in range(self.number_of_decks):
                screenshot_info = {}
                size = decks[i].size
                screenshot_info['width'] = int(size['width'])
                screenshot_info['height'] = int(size['height'])
                screenshot_info['crop_amount'] = inner_containers[i].size['width']
                raw_name = names[i].get_attribute("textContent")
                player = re.search(WIZARDS_NAME_PATTERN, raw_name).group(1)
                screenshot_format = f'png'
                index = str(i + 1)
                file = f'{index}-{player}.{screenshot_format}'
                output_file = os.path.join(self.mtgo_output_folder_dir, file)
                screenshot_info['file'] = output_file
                log.debug(f"[{i + 1}/{self.number_of_decks}] {player}")
                decks[i].location_once_scrolled_into_view
                hide(js_display_none, icons[i])
                decks[i].screenshot(output_file)
                deck_info = {'player': player, 'screenshot': screenshot_info}
                self.screenshots.append(deck_info)

            def natural_sort(x):
                return int(re.search(r'([0-9]+)\-(.*)$', x['screenshot']['file']).group(1))
            self.screenshots.sort(key=natural_sort)

        except Exception as e:
            log.exception(e)
        finally:
            log.info('Quitting web driver')
            self.driver.quit()
            self.driver = None

    def crop_images(self):
        '''
        Crop the images on disk removing the card preview on the
        right hand side.
        '''
        for root, dirs, files in os.walk(self.mtgo_output_folder_dir, topdown=False):
            for name in files:
                screenshot = [screenshot for screenshot in self.screenshots if name in screenshot['screenshot']['file']][0]
                file = os.path.join(root, name)
                im = Image.open(file)
                width = screenshot['screenshot']['width']
                height = screenshot['screenshot']['height']
                crop_amount = screenshot['screenshot']['crop_amount']
                # Setting the points for cropped image
                left = 0
                top = 0
                right = width - crop_amount
                bottom = height
                im1 = im.crop((left, top, right, bottom))
                im1.save(file)

    def create_folder_for_screenshots(self, league):
        self.folder_name = self.url.split('/')[-1]
        self.mtgo_output_folder_dir = os.path.join(self.output_dir, self.folder_name)
        os.makedirs(self.mtgo_output_folder_dir, exist_ok=True)

    def highlight_card(self, card_name):
        '''
        For every instance of card_name within a decklist
        highlight it.
        '''
        js_highlight = "arguments[0].style.background = 'Yellow'"
        highlight = self.driver.execute_script
        cards = self.find_elements_with_xpath(
            self.x_card_name.format(card=card_name))
        [highlight(js_highlight, card) for card in cards]

    def highlight_latest_cards(self):
        '''
        Go through a pre-defined list of cards from the latest Standard
        released set and highlight them.
        '''
        latest_cards = os.path.join('..', 'resources', 'latest_cards.txt')
        my_path = os.path.abspath(os.path.dirname(__file__))
        path = os.path.join(my_path, latest_cards)
        with open(path, 'r') as f:
            for card in f:
                try:
                    self.highlight_card(card.strip())
                except Exception as e:
                    log.exception(e)

    def run(self):
        self.start_session()
        if self.take_screenshots:
            self.take_decklist_screenshots()
            if self.crop_screenshots:
                self.crop_images()
        # decklists = self.get_decklists()
        # print(decklists)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)
    parser.add_argument("-o","--output-dir", help="The directory to save content to.", default=".")
    parser.add_argument("-c","--crop-screenshots", help="Crop the screenshots of the card preview.", action='store_true')
    parser.add_argument("-s","--take-screenshots", help="Take screenshots of the decks.", action='store_true')
    parser.add_argument("-u","--url", help="The page to start at or create screenshots of.", required=True)
    args = parser.parse_args()

    scraper = MTGOResultsScraper(args.url,
                                 r"{}".format(args.output_dir),
                                 args.take_screenshots,
                                 args.crop_screenshots)
    scraper.run()
