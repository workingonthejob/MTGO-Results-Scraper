import requests
import argparse
import sys
import os
import re
import logging
import json
from PIL import Image
from lxml import html
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
MTGO_RESULTS_PAGE_DATE_RE = '\\w+\\s\\d{,2},\\s\\d{4}'
WIZARDS_NAME_PATTERN = r'^(.*)(((\s\(\d{0,}\-\d{0,}\)))|(\s\(.*\sPlace\)))$'


class MTGOResultsScraper():

    def __init__(self, url, output_dir, take_screenshots, crop_screenshots):
        self.url = url
        self.output_dir = output_dir
        self.take_screenshots = take_screenshots
        self.crop_screenshots = crop_screenshots
        self.mtgo_output_folder_dir = None
        self.folder_name = None
        self.folder_name_template = "MTGO {} Results ({})"
        self.league = None
        self.date = None
        self.screenshots = []
        self.driver = None
        self.number_of_decks = None
        self.x_header = '//header'
        self.x_deck_container = '//div[@class="deck-group"]'
        self.x_player = './/h4'
        self.x_card_name = './/span[@class="card-name"]/a[text()="{card}"] | .//span[@class="card-name" and text()="{card}"]'
        self.x_main_card_names ='.//div[@class="sorted-by-overview-container sortedContainer"]//span[@class="card-name"]/a'
        self.x_main_card_counts = './/div[@class="sorted-by-overview-container sortedContainer"]//span[@class="card-count"]'
        self.x_side_card_names = './/div[@class="sorted-by-sideboard-container  clearfix element"]//span[@class="card-name"]/a'
        self.x_side_card_counts = './/div[@class="sorted-by-sideboard-container  clearfix element"]//span[@class="card-count"]'
        self.x_no_thanks_btn = '//button[@class="decline-button eu-cookie-compliance-default-button"]'
        self.x_league_type = './/h1'
        self.x_posted_in = './/div[@id="main-content"]//p[@class="posted-in"]'
        self.x_decklist_icons = './/span[@class="decklist-icons"]'
        self.headers = {'User-Agent':
                        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                        'AppleWebKit/537.36 (KHTML, like Gecko) '
                        'Chrome/102.0.0.0 Safari/537.36',
                        'accept': 'application/json'}
        self.session = None

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

    def print_decklists(self):
        tree = html.fromstring(self.session.content)
        deck_containers = tree.xpath(self.x_deck_container)
        for deck in deck_containers:
            mainboard = {}
            sideboard = {}
            container = {"Mainboard": mainboard,
                         "Sideboard": sideboard}
            raw_name = deck.find(self.x_player).text
            player = re.search(WIZARDS_NAME_PATTERN, raw_name).group(1)
            container["Player"] = player
            main_card_names = deck.findall(self.x_main_card_names)
            main_card_counts = deck.findall(self.x_main_card_counts)
            side_card_names = deck.findall(self.x_side_card_names)
            side_card_counts = deck.findall(self.x_side_card_counts)
            total_cards_main = 0
            total_cards_side = 0
            for i in range(len(main_card_counts)):
                number_of_cards = int(main_card_counts[i].text)
                card_name = main_card_names[i].text
                total_cards_main += number_of_cards
                mainboard[card_name] = number_of_cards

            for i in range(len(side_card_counts)):
                number_of_cards = int(side_card_counts[i].text)
                card_name = side_card_names[i].text
                total_cards_side += number_of_cards
                sideboard[card_name] = number_of_cards
            print(json.dumps(container))

    def find_elements_with_xpath(self, xpath):
        return self.driver.find_elements(by=By.XPATH, value=xpath)

    def initialize_web_driver(self):
        log.debug("Starting web driver.")
        # Define the options we want
        # More options here:
        # https://peter.sh/experiments/chromium-command-line-switches/
        options = Options()
        options.add_argument("--headless")
        # Starting maximized headless doesn't work correctly.
        options.add_argument("--window-size=1920x1080")
        # Ubuntu chrome will throw errors if these is not included.
        options.add_argument("--no-sandbox")
        options.add_argument('--disable-dev-shm-usage')
        # This downloads the correct one.
        self.driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()), options=options)
        # This will use the Chromedriver in the current directory.
        # self.driver = webdriver.Chrome(options=options)
        self.driver.get(self.url)

    def take_decklist_screenshots(self):

        self.initialize_web_driver() if not self.driver else None

        # Get the League type and the date to create the folder.
        posted_in = self.find_elements_with_xpath(self.x_posted_in)[0]
        self.league = self.find_elements_with_xpath(
            self.x_league_type)[0].text.title()
        text = posted_in.text.strip()
        self.date = re.search(MTGO_RESULTS_PAGE_DATE_RE, text).group()

        self.create_folder_for_screenshots(self.league, self.date)
        hide = self.driver.execute_script
        header = self.find_elements_with_xpath(self.x_header)[0]
        js_display_none = "arguments[0].style.display = 'none'"
        wait = WebDriverWait(self.driver, TIMEOUT)

        try:
            hide(js_display_none, header)
            clickable = ec.element_to_be_clickable((By.XPATH, self.x_no_thanks_btn))
            no_thanks_btn_elm = wait.until(clickable)
            no_thanks_btn_elm.click()
            self.highlight_latest_cards()

            decks = self.find_elements_with_xpath(self.x_deck_container)
            names = self.find_elements_with_xpath(self.x_player)
            icons = self.find_elements_with_xpath(self.x_decklist_icons)
            self.number_of_decks = len(decks)
            inner_containers = self.find_elements_with_xpath('.//div[@class="deck-list-text"]')

            for i in range(self.number_of_decks):
                screenshot_info = {}
                size = decks[i].size
                # screenshot_info['location'] = decks[i].location
                screenshot_info['width'] = int(size['width'])
                screenshot_info['height'] = int(size['height'])
                screenshot_info['crop_amount'] = int(inner_containers[i].value_of_css_property("margin-right").split("px")[0])
                player = re.search(WIZARDS_NAME_PATTERN, names[i].get_attribute("textContent")).group(1)
                output_file = os.path.join(self.mtgo_output_folder_dir, str(i + 1) + '-' + player) + '.png'
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
            self.driver.quit()

    def crop_images(self):
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

    def create_folder_for_screenshots(self, league, date):
        self.folder_name = self.folder_name_template.format(league, date)
        self.mtgo_output_folder_dir = os.path.join(self.output_dir, self.folder_name)
        os.makedirs(self.mtgo_output_folder_dir, exist_ok=True)

    def highlight_card(self, card_name):
        js_highlight = "arguments[0].style.background = 'Yellow'"
        highlight = self.driver.execute_script
        cards = self.find_elements_with_xpath(
            self.x_card_name.format(card=card_name))
        [highlight(js_highlight, card) for card in cards]

    def highlight_latest_cards(self):
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
        self.print_decklists()


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
