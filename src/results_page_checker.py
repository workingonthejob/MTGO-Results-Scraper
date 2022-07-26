import requests
import time
import logging
import string
from imgur import Imgur
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from datetime import datetime
from lxml import html
from mtgo_results_scraper import MTGOResultsScraper
from logging.config import fileConfig
from database import Database
from zoneinfo import ZoneInfo
from requests.exceptions import ChunkedEncodingError


fileConfig('logging_config.ini')
log = logging.getLogger()

OUTPUT_DIRECTORY = r'.'
TAKE_SCREENSHOTS = True
UPLOAD_TO_IMGUR = False
EXPORT_TO_MARKDOWN = False
CROP_SCREENSHOTS = True

# Wizards is west coast
TIME_ZONE = ZoneInfo('America/Los_Angeles')
DATE_FORMAT = "%Y-%m-%d"
TODAY = None
BASE_URL = 'https://magic.wizards.com/en/articles/archive/mtgo-standings/'
PIONEER_LEAGUE_LINK = BASE_URL + 'pioneer-league-{}'
PIONEER_CHALLENGE_LINK = BASE_URL + 'pioneer-challenge-{}'
PIONEER_SUPER_QUALIFIER = BASE_URL + 'pioneer-super-qualifier-{}'
PIONEER_SHOWCASE_CHALLENGE = BASE_URL + 'pioneer-showcase-challenge-{}'
MODERN_LEAGUE_LINK = BASE_URL + 'modern-league-{}'
MODERN_CHALLENGE_LINK = BASE_URL + 'modern-challenge-{}'
TEST_LINK = BASE_URL + 'modern-league-{}'.format('2022-06-17')
LINKS = [PIONEER_LEAGUE_LINK,
         PIONEER_CHALLENGE_LINK,
         PIONEER_SUPER_QUALIFIER,
         PIONEER_SHOWCASE_CHALLENGE]
# xpath
X_NO_RESULT = './/p[@class="no-result"]'
ALREADY_PROCESSED_LINKS = []


class Checker():

    def __init__(self):
        self.session = None
        self.url = None
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

    def run(self):
        log.info('Starting...')
        while True:
            for link in LINKS:
                try:
                    # TODAY = datetime.today().strftime(DATE_FORMAT)
                    TODAY = datetime.now(TIME_ZONE).strftime(DATE_FORMAT)
                    today_link = link.format(TODAY)
                    secret_link = None
                    screenshot_count = 0
                    letters = list(string.ascii_lowercase)
                    # Always seems to be a page with no results
                    letters.remove('q')

                    for letter in letters:
                        secret_link = today_link + f'?{letter}'
                        self.start_session()
                        s = self.session.get(secret_link, headers=self.headers)
                        tree = html.fromstring(s.content)
                        results = tree.find(X_NO_RESULT)
                        result_link_in_imgur_table = self.db.is_result_link_in_imgur_table(today_link)

                        if results is None and not result_link_in_imgur_table:
                            try:
                                log.info(secret_link)
                                mrs = MTGOResultsScraper(secret_link,
                                                         OUTPUT_DIRECTORY,
                                                         TAKE_SCREENSHOTS,
                                                         UPLOAD_TO_IMGUR,
                                                         CROP_SCREENSHOTS)
                                mrs.take_decklist_screenshots()
                                mrs.crop_images()
                                folder_name = mrs.get_folder_name()
                                im = Imgur()
                                album_id = im.create_album(
                                    title=folder_name)['data']['id']
                                for screenshot in mrs.get_screenshots():
                                    screenshot_file = screenshot['screenshot']['file']
                                    player = screenshot['player']
                                    log.info(f'Uploading {screenshot_file}')
                                    response = im.upload_image(image=screenshot_file,
                                                               album=album_id,
                                                               sleep=True)
                                    imgur_link = response['data']['link']
                                    self.db.add_imgur_row(screenshot_file,
                                                          album_id,
                                                          player,
                                                          imgur_link,
                                                          today_link)
                                    screenshot_count += 1
                            except IndexError as e:
                                log.exception(e)
                except KeyboardInterrupt as e:
                    log.exception(e)
                except ChunkedEncodingError as e:
                    log.exception(e)
            # 10 minutes
            log.debug('Sleeping for 10 minutes.')
            time.sleep(600)


c = Checker()
c.run()
