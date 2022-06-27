import requests
import time
import logging
from imgur import Imgur
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from datetime import datetime
from lxml import html
from mtgo_results_scraper import MTGOResultsScraper
from logging.config import fileConfig


fileConfig('logging_config.ini')
log = logging.getLogger()

OUTPUT_DIRECTORY = r'.'
TAKE_SCREENSHOTS = True
UPLOAD_TO_IMGUR = False
EXPORT_TO_MARKDOWN = False
CROP_SCREENSHOTS = True

DATE_FORMAT = "%Y-%m-%d"
TODAY = datetime.today().strftime(DATE_FORMAT)
BASE_URL = "https://magic.wizards.com/en/articles/archive/mtgo-standings/"
PIONEER_LEAGUE_LINK = BASE_URL + "pioneer-league-{}".format(TODAY)
PIONEER_CHALLENGE_LINK = BASE_URL + "pioneer-challenge-{}".format(TODAY)
MODERN_LEAGUE_LINK = BASE_URL + "modern-league-{}".format(TODAY)
MODERN_CHALLENGE_LINK = BASE_URL + "modern-challenge-{}".format(TODAY)
TEST_LINK = BASE_URL + "modern-league-{}".format('2022-06-17')
LINKS = [PIONEER_LEAGUE_LINK,
         PIONEER_CHALLENGE_LINK, TEST_LINK]
# xpath
X_NO_RESULT = './/p[@class="no-result"]'
ALREADY_PROCESSED_LINKS = []
LAST_CHECKED_DATE = {
    'pioneer_league': None,
    'pioneer_challenge': None,
    'modern_league': None,
    'modern_challenge': None
}


class Checker():

    def __init__(self):
        self.session = None
        self.url = None
        self.headers = {'User-Agent':
                        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                        'AppleWebKit/537.36 (KHTML, like Gecko) '
                        'Chrome/102.0.0.0 Safari/537.36',
                        'accept': 'application/json'}

    def start_session(self):
        self.session = requests.Session()
        retry = Retry(connect=3, backoff_factor=0.5)
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)

    def record_date(self, link):
        if link == PIONEER_LEAGUE_LINK:
            print('Pioneer League')
            LAST_CHECKED_DATE['pioneer_league'] = TODAY
        elif link == PIONEER_CHALLENGE_LINK:
            print('Pioneer Challenge')
            LAST_CHECKED_DATE['pioneer_challenge'] = TODAY
        elif link == MODERN_LEAGUE_LINK:
            print('Modern League')
            LAST_CHECKED_DATE['modern_league'] = TODAY
        elif link == MODERN_CHALLENGE_LINK:
            print('Modern Challenge')
            LAST_CHECKED_DATE['modern_challenge'] = TODAY

    def run(self):
        self.start_session()

        while True:
            for link in LINKS:
                try:
                    log.info(link)
                    screenshot_count = 0
                    s = self.session.get(link, headers=self.headers)
                    tree = html.fromstring(s.content)
                    results = tree.find(X_NO_RESULT)
                    if results is None and link not in ALREADY_PROCESSED_LINKS:
                        self.record_date(link)
                        mrs = MTGOResultsScraper(link,
                                                 OUTPUT_DIRECTORY,
                                                 TAKE_SCREENSHOTS,
                                                 UPLOAD_TO_IMGUR,
                                                 CROP_SCREENSHOTS)
                        # folder_path = mrs.get_mtgo_output_folder_dir()
                        mrs.take_decklist_screenshots()
                        mrs.crop_images()
                        folder_name = mrs.get_folder_name()
                        im = Imgur()
                        for screenshot in mrs.get_screenshots():
                            log.info("Uploading screenshot {}".format(
                                screenshot))
                            # For every 50 screenshot uploads sleep for an hour
                            if not screenshot_count % 50:
                                time_elapsed = 0
                                log.info('Imgur API upload limit reached.')
                                # Update user every minute
                                while time_elapsed <= 3660:
                                    time_elapsed_min = int(time_elapsed)/60
                                    log.info('Slept for {} minutes so far.'.format(time_elapsed_min))
                                    time.sleep(60)
                                    time_elapsed += 60
                            album_id = im.create_album(title=folder_name)
                            im.upload_image(image=screenshot, album=album_id)
                            screenshot_count += 1
                        ALREADY_PROCESSED_LINKS.append(link)
                except KeyboardInterrupt as e:
                    log.exception(e)
            # 10 minutes
            time.sleep(600)


c = Checker()
c.run()
