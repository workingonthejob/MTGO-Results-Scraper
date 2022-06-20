import requests
import time
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from datetime import datetime
from lxml import html


DATE_FORMAT = "%Y-%m-%d"
TODAY = datetime.today().strftime(DATE_FORMAT)
BASE_URL = "https://magic.wizards.com/en/articles/archive/mtgo-standings/"
PIONEER_LEAGUE_LINK = BASE_URL + "pioneer-league-{}".format(TODAY)
PIONEER_CHALLENGE_LINK = BASE_URL + "pioneer-challenge-{}".format(TODAY)
MODERN_LEAGUE_LINK = BASE_URL + "modern-league-{}".format(TODAY)
MODERN_CHALLENGE_LINK = BASE_URL + "modern-challenge-{}".format(TODAY)
TEST_LINK = BASE_URL + "modern-league-{}".format('2022-06-17')
LINKS = [PIONEER_LEAGUE_LINK,
         PIONEER_CHALLENGE_LINK,
         MODERN_LEAGUE_LINK,
         MODERN_CHALLENGE_LINK]
# xpath
X_NO_RESULT = './/p[@class="no-result"]'
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

    def run(self):
        self.start_session()
        while True:
            for link in LINKS:
                try:
                    print(link)
                    s = self.session.get(link, headers=self.headers)
                    tree = html.fromstring(s.content)
                    results = tree.find(X_NO_RESULT)
                    if results is None:
                        if link == PIONEER_LEAGUE_LINK:
                            print("PIONEER LEAGUE")
                            LAST_CHECKED_DATE['pioneer_league'] = TODAY
                        elif link == PIONEER_CHALLENGE_LINK:
                            print("PIONEER CHALLENGE")
                            LAST_CHECKED_DATE['pioneer_challenge'] = TODAY
                        elif link == MODERN_LEAGUE_LINK:
                            print("MODERN CHALLENGE")
                            LAST_CHECKED_DATE['modern_league'] = TODAY
                        elif link == MODERN_CHALLENGE_LINK:
                            print("MODERN CHALLENGE")
                            LAST_CHECKED_DATE['modern_challenge'] = TODAY
                except AttributeError as e:
                    print(e)
                time.sleep(5)
            print(LAST_CHECKED_DATE)


c = Checker()
c.run()
