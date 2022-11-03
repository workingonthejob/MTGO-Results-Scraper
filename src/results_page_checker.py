import requests
import logging
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
from requests.exceptions import HTTPError
import os


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
BASE_URL = 'https://www.mtgo.com'
QUERY_URL = BASE_URL + '/en/mtgo/decklists/search?query={query}'
QUERY = QUERY_URL.format(query=urllib.parse.quote('pioneer challenge'))

FORMATS = ['standard', 'pioneer', 'modern', 'legacy', 'vintage']
EVENTS = ['league', 'challenge', 'super qualifier', 'showcase challenge']

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
# The maximum amount of events to capture screenshots
MAX_EVENTS = 1


class Checker():

    def __init__(self):
        self.session = None
        self.url = None
        self.mtgo_scraper = None
        self.folder = None
        self.screenshots = None
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

    def get_event_urls(self):
        """
        Parses the MTGO decklist page and go through the different magic
        events and return a list of urls for the results.

        """
        urls = []
        self.start_session()
        for event in LINKS:
            counter = 0
            query = QUERY_URL.format(query=urllib.parse.quote(event))
            # Make query for each type of event
            r = self.session.get(query, headers=self.headers)
            tree = html.fromstring(r.content)
            results = tree.xpath(X_EVENT_RESULTS)
            for result in results:
                if counter == MAX_EVENTS:
                    break
                href = result.find('./a').attrib['href']
                url = BASE_URL + href
                urls.append(url)
                counter += 1
        return urls

    def take_screenshots(self, url):
        """
        Take screenshots of the decklists for the given url.
        """
        log.debug(url)
        in_db = self.db.is_result_link_in_imgur_table(url)
        if not in_db:
            try:
                self.mtgo_scraper = MTGOResultsScraper(url,
                                                       OUTPUT_DIRECTORY,
                                                       TAKE_SCREENSHOTS,
                                                       CROP_SCREENSHOTS)
                self.mtgo_scraper.take_decklist_screenshots()
                self.mtgo_scraper.crop_images()
                self.screenshots = self.mtgo_scraper.get_screenshots()
                total_decks = self.mtgo_scraper.get_number_of_decks()
                self.folder = self.mtgo_scraper.get_folder_name()
                self.db.add_wizards_row(url, total_decks)
            except Exception as e:
                log.exception(e)

    def upload_screenshots(self, url):
        """
        Upload the screenshots to an imgur album.
        """
        im = None
        album_id = None

        # Initialize only if there are screenshots.
        if self.screenshots:
            im = Imgur()
            album_id = im.create_album(
                title=self.folder)['data']['id']
            for screenshot in self.screenshots:
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
                    # log.exception(f'Adding {screenshot_file} '
                    #               f'to the retry queue!')
                    # self.db.add_image_to_queue(screenshot_file, album_id, url)

    def process_retry_queue(self):
        log.info('Processing retry queue...')
        im = Imgur()
        images = self.db.get_all_retry_images()
        for image in images:
            file = image['file']
            album = image['imgur_album']
            url = image['url']
            player = image['player']
            log.info(f'Retrying {file}')
            try:
                response = im.upload_image(image=file,
                                           album=album,
                                           sleep=True)
                imgur_link = response['data']['link']
                self.db.add_imgur_row(file,
                                      album,
                                      player,
                                      imgur_link,
                                      url)
                # self.db.remove_image_from_queue()
            except Exception as e:
                log.exception(e)

    def run(self):
        this_file = os.path.basename(__file__)
        log.info(f'Starting {this_file}...')
        # self.process_retry_queue()
        urls = self.get_event_urls()
        for url in urls:
            ignore = self.db.url_in_ignore(url)
            if ignore:
                log.debug(f'{url} being ignored')
            else:
                log.info(url)
                self.take_screenshots(url)
                self.upload_screenshots(url)


c = Checker()
c.run()
