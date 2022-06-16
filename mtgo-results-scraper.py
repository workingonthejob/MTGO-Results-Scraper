import requests
import argparse
import sys
import os
import re
import time
from lxml import html
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait
from selenium import webdriver
from pprint import pprint
from imgur import Imgur
from imgur import MAX_UPLOADS_PER_HOUR
from IniParser import IniParser
from logging.config import fileConfig
import logging


fileConfig('logging_config.ini')
log = logging.getLogger()

DESCRIPTION = """
Scrape and/or screenshot the Magic: The Gathering match results.
"""
TIMEOUT = 10
REDDIT_PATTERN = r'(\d+\.|\-)\s(\[.*\]).*\*\*(.*)\*\*'


class MTGOResultsScraper():

    def __init__(self, url, output_dir, take_screenshots,
        upload_to_imgur, export_to_markdown):
        self.url = url
        self.output_dir = output_dir
        self.take_screenshots = take_screenshots
        self.upload_to_imgur = upload_to_imgur
        self.export_to_markdown = export_to_markdown
        self.imgur_album_name = None
        self.screenshots = []
        self.imgur = None
        self.x_deck_container = '//div[@class="deck-group"]'
        self.x_player = './/h4'
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
            player = deck.find(self.x_player).text.split(" ")[0]
            container["Player"] = player
            # print("[{}]".format(player))
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

            # print("{} total cards main deck.".format(total_cards_main))
            # print("----------------")
            for i in range(len(side_card_counts)):
                number_of_cards = int(side_card_counts[i].text)
                card_name = side_card_names[i].text
                total_cards_side += number_of_cards
                sideboard[card_name] = number_of_cards
            # print("{} total cards in sideboard.".format(total_cards_side))
            # print("----------------")
            pprint(container)

    def initialize_web_driver(self):
        # Define the options we want
        # More options here:
        # https://peter.sh/experiments/chromium-command-line-switches/
        options = Options()
        options.add_argument("--headless")
        # Starting maximized headless doesn't work correctly.
        options.add_argument("--window-size=1920x1080")
        self.driver = webdriver.Chrome(options=options)

    def take_decklist_screenshots(self):
        # Define the options we want
        # More options here:
        # https://peter.sh/experiments/chromium-command-line-switches/
        options = Options()
        options.add_argument("--headless")
        # Starting maximized headless doesn't work correctly.
        options.add_argument("--window-size=1920x1080")
        driver = webdriver.Chrome(options=options)

        try:
            self.create_folder_for_screenshots()
            driver.get(self.url)
            driver.execute_script(
                'document.querySelector("header").style.display = "none"')
            wait = WebDriverWait(driver, TIMEOUT)
            clickable = ec.element_to_be_clickable((By.XPATH, self.x_no_thanks_btn))
            no_thanks_btn_elm = wait.until(clickable)
            no_thanks_btn_elm.click()
            decks = driver.find_elements(by=By.XPATH, value=self.x_deck_container)
            names = driver.find_elements(by=By.XPATH, value=self.x_player)
            number_of_decks = len(decks)

            for i in range(number_of_decks):
                player_name = names[i].text.split(" ")[0]
                output_file = r"{}\{}-{}.png".format(self.output_dir, i + 1, player_name)
                log.debug("{}[{}/{}]".format(player_name, i + 1, number_of_decks))
                decks[i].location_once_scrolled_into_view
                driver.execute_script(
                    'document.querySelectorAll("span.decklist-icons")[{}].style.display = "none"'.format(i))
                decks[i].screenshot(output_file)
                deck_info = {'player': player_name, 'screenshot': output_file}
                self.screenshots.append(deck_info)

            def natural_sort(x):
                return int(re.search(r'([0-9]+)\-(.*)$', x['screenshot']).group(1))
            self.screenshots.sort(key=natural_sort)

        except Exception as e:
            log.exception(e)
        finally:
            driver.quit()

    def create_folder_for_screenshots(self):
        tree = html.fromstring(self.session.content)
        league = tree.find(self.x_league_type).text_content()
        posted_in = tree.find(self.x_posted_in)
        text = posted_in.text_content().strip()
        date = re.search('\\w+\\s\\d{,2},\\s\\d{4}', text).group()
        folder_name = "MTGO {} Results ({})".format(league, date)
        new_output_dir = "\\".join([self.output_dir, folder_name])
        os.makedirs(new_output_dir, exist_ok=True)
        self.output_dir = new_output_dir
        self.imgur_album_name = folder_name

    def load_imgur_credentials(self):
        log.debug("Loading imgur credentials...")
        ip = IniParser('imgur-config.ini')
        client_id = ip.get_imgur_properties('CLIENT_ID')
        client_secret = ip.get_imgur_properties('CLIENT_SECRET')
        refresh_token = ip.get_imgur_properties('REFRESH_TOKEN')
        access_token = ip.get_imgur_properties('ACCESS_TOKEN')
        username = ip.get_imgur_properties('USERNAME')
        self.imgur = Imgur(username,
                           client_id,
                           client_secret,
                           refresh_token,
                           access_token)
        self.imgur.start_session()
        self.imgur.test_and_update_access_token()

    def upload(self):
        self.load_imgur_credentials()
        album = self.imgur.create_album(title=self.imgur_album_name)
        album_id = album['data']['id']
        for screenshot in self.screenshots:
            name = screenshot['screenshot'].split('\\')[-1]
            log.debug("Uploading {}".format(name))
            result = MAX_UPLOADS_PER_HOUR - self.screenshots.index(screenshot)

            if result == 0:
                log.warning("Reached {} upload limit on Imgur."
                            .format(MAX_UPLOADS_PER_HOUR))
                log.warning("Sleeping for an hour until resuming.")
                time.sleep(3660)
            r = self.imgur.upload_image(image=screenshot['screenshot'], album=album_id)
            screenshot['imgur'] = r['data']['link']
            if self.export_to_markdown:
                log.debug("* [DECK_NAME]({}): **{}**\n"
                          .format(screenshot['imgur'], screenshot['player'].lower()))
            time.sleep(1)

    def highlight_card(self, driver, card):
        x_card_name = ".//span[@class='card-name']/a[text()='{}}']"
        cards = driver.find_elements(
            by=By.XPATH, value=x_card_name.format(x_card_name))
        for card in cards:
            driver.execute_script(
                "arguments[0].style.background = 'Yellow'", card)

    def make_markdown(self):
        tree = html.fromstring(self.session.content)
        deck_containers = tree.xpath(self.x_deck_container)
        for deck in deck_containers:
            mainboard = {}
            sideboard = {}
            container = {"Mainboard": mainboard,
                         "Sideboard": sideboard}
            player = deck.find(self.x_player).text.split(" ")[0]
            container["Player"] = player

    def run(self):
        self.start_session()
        if self.take_screenshots:
            self.take_decklist_screenshots()
        if self.take_screenshots and self.upload_to_imgur:
            self.upload()
        if self.export_to_markdown:
            self.make_markdown()
        self.print_decklists()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)
    parser.add_argument("-o","--output-dir", help="The directory to save content to.", default=".")
    parser.add_argument("-s","--take-screenshots", help="Take screenshots of the decks.", action='store_true')
    parser.add_argument("-u","--url", help="The page to start at or create screenshots of.", required=True)
    parser.add_argument("-i","--upload-to-imgur", help="Create an Imgur album and upload deck images to it.", action='store_true')
    parser.add_argument("-e","--export-to-markdown", help="Export the deck images to markdown for reddit.", action='store_true')
    parser.add_argument("-r","--post-to-reddit", help="Post decklist to reddit.", action='store_true')
    args = parser.parse_args()

    scraper = MTGOResultsScraper(args.url,
                                 r"{}".format(args.output_dir),
                                 args.take_screenshots,
                                 args.upload_to_imgur,
                                 args.export_to_markdown)
    scraper.run()
