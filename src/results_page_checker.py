import requests
import time
import logging
import string
import urllib.parse
from imgur import Imgur
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from datetime import datetime
from lxml import html
from mtgo_results_scraper import MTGOResultsScraper
from logging.config import fileConfig
from database import Database
from zoneinfo import ZoneInfo
from requests.exceptions import ChunkedEncodingError, HTTPError


fileConfig('logging_config.ini')
log = logging.getLogger()

OUTPUT_DIRECTORY = r'.\screenshots'
TAKE_SCREENSHOTS = True
EXPORT_TO_MARKDOWN = False
CROP_SCREENSHOTS = True

# Wizards is west coast
TIME_ZONE = ZoneInfo('America/Los_Angeles')
DATE_FORMAT = "%Y-%m-%d"
TODAY = None
YESTERDAY = None
BASE_URL = 'https://www.mtgo.com'
QUERY_URL = 'https://www.mtgo.com/en/mtgo/decklists/search?query={query}'
QUERY = QUERY_URL.format(query=urllib.parse.quote('pioneer challenge'))

PIONEER_LEAGUE = 'pioneer league'
PIONEER_CHALLENGE = 'pioneer challenge'
PIONEER_SUPER_QUALIFIER = 'pioneer super qualifier'
PIONEER_SHOWCASE_CHALLENGE = 'pioneer showcase challenge'
LINKS = [PIONEER_LEAGUE,
         PIONEER_CHALLENGE,
         PIONEER_SUPER_QUALIFIER,
         PIONEER_SHOWCASE_CHALLENGE]
# xpath
X_NO_RESULT = './/p[@class="no-result"]'
X_EVENT_RESULTS = '//li[@class="decklists-item"]'
# The maximum amount of events to parse
MAX_EVENTS = 2


class Checker():

    def __init__(self):
        self.session = None
        self.url = None
        self.mtgo_scraper = None
        self.headers = {'User-Agent':
                        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                        'AppleWebKit/537.36 (KHTML, like Gecko) '
                        'Chrome/102.0.0.0 Safari/537.36',
                        'accept': 'application/json'}
        self.db = Database('scraper')

    def start_session(self):
        self.session = requests.Session()
        retry = Retry(connect=3, backoff_factor=0.5)
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)

    def clean_url(self, url):
        '''
            Clean the link of parameters (?oe etc.) before
            committing to the database.
        '''
        return url.split('?')[0]

    def get_event_urls(self):
        urls = []
        self.start_session()
        r = self.session.get(QUERY, headers=self.headers)
        tree = html.fromstring(r.content)
        results = tree.xpath(X_EVENT_RESULTS)
        for result in results:
            href = result.find('./a').attrib['href']
            url = BASE_URL + href
            urls.append(url)
        return urls

    def take_screenshots(self, url):
        in_db = self.db.is_result_link_in_imgur_table(url)
        if not in_db:
            self.mtgo_scraper = MTGOResultsScraper(url,
                                                   OUTPUT_DIRECTORY,
                                                   TAKE_SCREENSHOTS,
                                                   CROP_SCREENSHOTS)
            self.mtgo_scraper.take_decklist_screenshots()
            self.mtgo_scraper.crop_images()
            number_of_decks = self.mtgo_scraper.get_number_of_decks()
            folder_name = self.mtgo_scraper.get_folder_name()
            self.db.add_wizards_row(url, number_of_decks)
        return folder_name

    def upload_screenshots(self, folder, url):
        im = Imgur()
        album_id = im.create_album(
            title=folder)['data']['id']
        for screenshot in self.mtgo_scraper.get_screenshots():
            screenshot_file = screenshot['screenshot']['file']
            player = screenshot['player']
            log.info(f'Uploading {screenshot_file}')
            try:
                response = im.upload_image(image=screenshot_file,
                                           album=album_id,
                                           sleep=True)
                imgur_link = response['data']['link']
                self.db.add_imgur_row(screenshot_file,
                                      album_id,
                                      player,
                                      imgur_link,
                                      url)
            except HTTPError as e:
                log.exception(e)

    def run(self):
        log.info('Starting...')
        urls = self.get_event_urls()
        counter = 0
        for url in urls:
            if counter == MAX_EVENTS:
                break
            log.debug(url)
            folder = self.take_screenshots(url)
            self.upload_screenshots(folder, url)
            counter += 1


c = Checker()
c.run()
