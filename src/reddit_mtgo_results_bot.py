import praw
import re
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
from zoneinfo import ZoneInfo


SUBREDDIT = 'PioneerMTG'
TIME_ZONE = ZoneInfo('America/Los_Angeles')
USER_AGENT = "Archives data to local storage."
# https://praw.readthedocs.io/en/latest/code_overview/models/submission.html
PATTERN = r'[\d{1}\.|\*]\s\[(.*)\]\(.*\):\s?\*\*(.*)\*\*'
# PATTERN = r'[\d{1}\.|\*]\s\[(.*)\]\(.*\):\s?\*(.+?)(\s\(.+?\))?\*'
DATE_FORMAT = "%Y-%m-%d"
# TODAY = datetime.today().strftime(DATE_FORMAT)
TODAY = datetime.now(TIME_ZONE).strftime(DATE_FORMAT)
BASE_URL = 'https://magic.wizards.com/en/articles/archive/mtgo-standings/'
PIONEER_LEAGUE_LINK = BASE_URL + f'pioneer-league-{TODAY}'
PIONEER_CHALLENGE_LINK = BASE_URL + f'pioneer-challenge-{TODAY}'
PIONEER_SHOWCASE_CHALLENGE = BASE_URL + f'pioneer-showcase-challenge-{TODAY}'
PIONEER_SUPER_QUALIFIER = BASE_URL + f'pioneer-super-qualifier-{TODAY}'
MODERN_LEAGUE_LINK = BASE_URL + f'modern-league-{TODAY}'
MODERN_CHALLENGE_LINK = BASE_URL + f'modern-challenge-{TODAY}'
LINKS = [PIONEER_LEAGUE_LINK,
         PIONEER_CHALLENGE_LINK,
         PIONEER_SUPER_QUALIFIER,
         PIONEER_SHOWCASE_CHALLENGE]

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

    def sanitize_for_markdown(self, text):
        s = text.replace('\\', 1) if r'\\' in text else text
        return s

    def write_line_to_markdown(self, line, event):
        output_file = f'{event}.md'
        with open(output_file, 'a') as f:
            f.write(line + '\n')

    def build_markdown(self, submission_text, link):
        imgur_album_id = self.db.imgur_get_album_with_link(link)
        markdown = (f'Here are the screenshots for the deck lists.'
                    f'Highlighted are DMU cards.\n\n'
                    f'[Imgur Album](https://imgur.com/a/{imgur_album_id})\n\n')
        total_decks = self.db.wizards_get_total_decklist_for_link(link)
        counter = 0
        lines = submission_text.split('\n')

        for line in lines:
            if counter >= total_decks:
                break
            matches = re.findall(PATTERN, line)
            if matches:
                counter += 1
                for match in matches:
                    try:
                        archetype = match[0]
                        escaped_player = match[1]
                        player = match[1].replace('\\', '') if '\\' in match[1] else match[1]
                        r = self.db.imgur_find_rows_matching_link(link, player)
                        # This assumes there are no duplicate players
                        imgur_link = r[0][4]
                        line = f'* [{archetype}]({imgur_link}): **{escaped_player}**\n'
                        markdown += line
                    except IndexError:
                        line = f'* [{archetype}](): **{escaped_player}**\n'
                        markdown += line
        return markdown

    def write_to_markdown(self, submission_text, event, link):
        output_file = f'{event}.md'
        markdown = self.build_markdown(submission_text, link)
        with open(output_file, 'a') as f:
            f.write(markdown)

    def create_markdown_based_on_current_state(self):
        '''
        Create the markdown based on reddit links not submitted
        yet and only use what's currently in the DB.
        '''
        pass

    def all_checks_passed(self, results_url, markdown):
        '''
            Perform checks that the data that is being posted
            is correct.
        '''
        is_true = False
        is_true = self.db.total_decks_match_for_link(results_url)
        is_true = self._check_imgur_links_appear_only_once(results_url,
                                                           markdown)
        return is_true

    def _check_imgur_links_appear_only_once(self, results_url, markdown):
        '''
        Check that all links from the imgur table appear
        only once inside the markdown.
        '''
        rows = self.db.imgur_all_rows_with_link(results_url)
        for row in rows:
            imgur_url = row[4]
            count = markdown.count(imgur_url)
            if count > 1:
                log.debug(f'{imgur_url} showed up twice!')
                return False
        return True

    def find_new_results(self):
        for link in LINKS:
            parsed_link = link.split('?')[0]
            for submission in subreddit.new(limit=20):
            # for submission in subreddit.top(time_filter="hour"):
                seen_url = self.db.reddit_url_in_table(submission.url)
                if submission.is_self and parsed_link in submission.selftext and not seen_url:
                    log.debug(f'Adding {submission.url} to DB.')
                    self.db.add_reddit_row(
                        submission.url,
                        submission.selftext,
                        parsed_link,
                        0)

    def test_build_markdown(self, results_url):
        with open('reddit_test_input.txt', 'r') as f:
            submission_text = f.readlines()
            return self.build_markdown(submission_text, results_url)

    def run(self):
        """
        Checks through the submissions and archives and posts comments.
        """
        try:
            self.find_new_results()
            rows_not_posted = self.db.reddit_get_all_rows_that_didnt_post()
            for row in rows_not_posted:
                reddit_url = row[1]
                submission_text = row[2]
                results_url = row[3]
                log.debug(results_url)
                submission = self.reddit.submission(url=reddit_url)
                if self.db.total_decks_match_for_link(results_url):
                    markdown = self.build_markdown(submission_text, results_url)
                    self.write_to_markdown(
                        submission_text,
                        submission.title,
                        results_url)
                    self.db.reddit_update_posted_screenshot(1, results_url)
                    if self.all_checks_passed(results_url, markdown):
                        # submission.reply(markdown)
                        pass
        except Exception as e:
            log.exception(e)

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
    ip = IniParser("pioneer-mtg-bot.ini")
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
        try:
            log.info("Running")
            bot = MTGOResultsPostFinder(
                username,
                password,
                client_id,
                client_secret)
            bot.setup() if not setup_has_been_run else None
            bot.run()
            log.info("Done")
        except RECOVERABLE_EXC as e:
            log.exception(e)

            time.sleep(wait)
    except KeyboardInterrupt:
        pass
    finally:
        bot.quit()
    exit(0)
