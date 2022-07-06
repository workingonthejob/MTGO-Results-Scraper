import praw
import re
import sys
import time
import warnings
import logging
from logging.config import fileConfig
from datetime import datetime
from praw.exceptions import APIException, ClientException, PRAWException
from prawcore.exceptions import PrawcoreException
from requests.exceptions import ConnectionError
from IniParser import IniParser
from database import Database


USER_AGENT = "Archives data to local storage."
# https://praw.readthedocs.io/en/latest/code_overview/models/submission.html
PATTERN = r'[\d{1}\.|\*]\s\[(.*)\]\(.*\):\s?\*\*(.*)\*\*'
DATE_FORMAT = "%Y-%m-%d"
TODAY = datetime.today().strftime(DATE_FORMAT)
BASE_URL = 'https://magic.wizards.com/en/articles/archive/mtgo-standings/'
PIONEER_LEAGUE_LINK = BASE_URL + f'pioneer-league{TODAY}'
PIONEER_CHALLENGE_LINK = BASE_URL + f'pioneer-challenge-{TODAY}'
PIONEER_SUPER_QUALIFIER = BASE_URL + f'pioneer-super-qualifier-{TODAY}'
MODERN_LEAGUE_LINK = BASE_URL + f'modern-league-{TODAY}'
MODERN_CHALLENGE_LINK = BASE_URL + f'modern-challenge-{TODAY}'
LINKS = [PIONEER_LEAGUE_LINK,
         PIONEER_CHALLENGE_LINK,
         PIONEER_SUPER_QUALIFIER]

RECOVERABLE_EXC = (
    APIException,
    ClientException,
    PRAWException,
    PrawcoreException,
    ConnectionError,
)

fileConfig('logging_config.ini')
log = logging.getLogger()

warnings.simplefilter("ignore")  # Ignore ResourceWarnings (because screw them)


class MTGOResultsPostFinder:
    def __init__(self,
                 username,
                 password,
                 client_id,
                 client_secret):
        self.username = username
        self.password = password
        self.client_id = client_id
        self.client_secret = client_secret
        self.headers = {}
        self._setup = False
        self.reddit = None
        self.db = Database('scraper')

    def run(self):
        """
        Checks through the submissions and archives and posts comments.
        """
        if not self._setup:
            raise Exception("{} not ready yet!").format(self.username)
        subreddit = self.reddit.subreddit('PioneerMTG')

        for submission in subreddit.new(limit=20):
        # for submission in subreddit.top(time_filter="hour"):
            submission_title = submission.title
            submission_url = submission.url
            submission_author = submission.author
            submission_id = submission.id
            submission_creation_time_utc = submission.created_utc
            submission_creation_time_readable = datetime.fromtimestamp(
                submission_creation_time_utc)

            for link in LINKS:
                if submission.is_self and link in submission.selftext:
                    seen_url = self.db.reddit_url_in_table(submission_url)
                    if not seen_url:
                        log.debug(submission_title)
                        log.debug(f'Adding {submission_url} to DB.')
                        self.db.add_reddit_row(
                            submission_url,
                            submission.selftext,
                            link)
                        new_list = []
                        matches = re.findall(PATTERN, submission.selftext)
                        # Remove duplicates but order is lost.
                        # matches = list(set(matches)) if matches else None
                        # Do not include duplicates but preserve order.
                        for match in matches:
                            if match not in new_list:
                                new_list.append(match)

                        with open('reddit-markdown.md', 'w+') as f:
                            blob = []
                            for match in new_list:
                                archetype = match[0]
                                player = match.replace('\\', 1) if r'\\' in match[1] else match[1]
                                line = f'* [{archetype}]({{}}): **{player}**'
                                log.debug(line)
                                blob.append(line)
                            o = '\n'.join(blob)
                            f.write(o)
                        sys.exit(0)

    def setup(self):
        """
        Logs into reddit and refreshs the header text.
        """
        self._login()
        self._setup = True

    def quit(self):
        self.headers = {}
        self._setup = False

    def _login(self):
        self.reddit = praw.Reddit(
            client_id=self.client_id,
            client_secret=self.client_secret,
            username=self.username,
            password=self.password,
            user_agent=USER_AGENT,
        )


if __name__ == "__main__":
    ip = IniParser("reddit-config.ini")
    username = ip.get_reddit_properties('REDDIT_USER')
    password = ip.get_reddit_properties('REDDIT_PASS')
    client_id = ip.get_reddit_properties('REDDIT_CLIENT_ID')
    client_secret = ip.get_reddit_properties('REDDIT_CLIENT_SECRET')
    # limit = int(ip.get_reddit_properties('LIMIT'))
    wait = int(ip.get_reddit_properties('WAIT'))
    refresh = int(ip.get_reddit_properties('REFRESH'))
    setup_has_been_run = False

    log.info("Starting...")
    try:
        cycles = 0
        while True:
            try:
                cycles += 1
                log.info("Running")
                bot = MTGOResultsPostFinder(
                    username,
                    password,
                    client_id,
                    client_secret)
                bot.setup() if not setup_has_been_run else None
                bot.run()
                log.info("Done")
                # This will refresh by default
                # around ~30 minutes (depending
                # on delays).
                if cycles > (refresh / wait) / 2:
                    log.info("Reloading header text and ignore list...")
                    cycles = 0
            except RECOVERABLE_EXC as e:
                log.exception(e)

            time.sleep(wait)
    except KeyboardInterrupt:
        pass
    finally:
        bot.quit()
    exit(0)
