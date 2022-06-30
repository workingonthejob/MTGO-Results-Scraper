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

USER_AGENT = "Archives data to local storage."
# https://praw.readthedocs.io/en/latest/code_overview/models/submission.html
PATTERN = r'[\d{1}\.|\*]\s\[(.*)\]\(.*\):\s?\*\*(.*)\*\*'

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

    def run(self):
        """
        Checks through the submissions and archives and posts comments.
        """
        if not self._setup:
            raise Exception("{} not ready yet!").format(self.username)
        subreddit = self.reddit.subreddit('PioneerMTG')

        url = 'https://magic.wizards.com/en/articles/archive/mtgo-standings/pioneer-league-'

        # for submission in subreddit.new(limit=100):
        for submission in subreddit.top(time_filter="hour"):
            submission_title = submission.title
            submission_url = submission.url
            submission_author = submission.author
            submission_id = submission.id
            submission_creation_time_utc = submission.created_utc
            submission_creation_time_readable = datetime.fromtimestamp(
                submission_creation_time_utc)

            if submission.is_self:
                if url in submission.selftext:
                    log.debug(submission_title)
                    matches = re.findall(PATTERN, submission.selftext)
                    with open('reddit-markdown.md', 'w+') as f:
                        blob = []
                        for match in matches:
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
