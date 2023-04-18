import praw
import re
import logging
from logging.config import fileConfig
from datetime import datetime
from datetime import timedelta
from praw.exceptions import APIException, ClientException, PRAWException
from prawcore.exceptions import PrawcoreException
from requests.exceptions import ConnectionError
from IniParser import IniParser
from database import Database
from zoneinfo import ZoneInfo
from exceptions import MarkdownCheckErrors


SUBREDDIT = 'PioneerMTG'
TIME_ZONE = ZoneInfo('America/Los_Angeles')
USER_AGENT = "Archives data to local storage."
MARKDOWN_HEADER = (f'Here are the screenshots for the deck lists. '
                   f'Highlighted are MOM cards.\n\n'
                   '[Imgur Album](https://imgur.com/a/{imgur_album_id})\n\n')
MARKDOWN_PLAYER = ('* [{archetype}]'
                   '({imgur_link}): '
                   '**{escaped_player}**\n')
# https://praw.readthedocs.io/en/latest/code_overview/models/submission.html
PATTERN = r'[\d{1}\.|\*]\s\[(.*)\]\(.*\):\s?\*\*(.*?)(\s)?(\(.*\))?\*\*'
DATE_FORMAT = "%Y-%m-%d"
RE_DATE_PATTERN = r'\d{4}\-\d{2}\-\d{2}'
EVENT_ID = r'(\d{1,})?'
TODAY = datetime.now(TIME_ZONE).strftime(DATE_FORMAT)
YESTERDAY = (datetime.now(TIME_ZONE) - timedelta(days=1)).strftime(DATE_FORMAT)
BASE_URL = 'https://www.mtgo.com/en/mtgo/decklist/'

PIONEER_LEAGUE_LINK = '(' + BASE_URL + fr'pioneer-league-{RE_DATE_PATTERN}{EVENT_ID})'
PIONEER_CHALLENGE_LINK = '(' + BASE_URL + fr'pioneer-challenge-{RE_DATE_PATTERN}{EVENT_ID})'
PIONEER_SHOWCASE_CHALLENGE = '(' + BASE_URL + fr'pioneer-showcase-challenge-{RE_DATE_PATTERN}{EVENT_ID})'
PIONEER_SUPER_QUALIFIER = '(' + BASE_URL + fr'pioneer-super-qualifier-{RE_DATE_PATTERN}{EVENT_ID})'
PIONEER_PREMIER = '(' + BASE_URL + fr'pioneer-premier-{RE_DATE_PATTERN}{EVENT_ID})'
# MODERN_LEAGUE_LINK = BASE_URL + f'modern-league-{RE_DATE_PATTERN}{EVENT_ID}'
# MODERN_CHALLENGE_LINK = BASE_URL + f'modern-challenge-{RE_DATE_PATTERN}{EVENT_ID}'

LINKS = [PIONEER_LEAGUE_LINK,
         PIONEER_CHALLENGE_LINK,
         PIONEER_SUPER_QUALIFIER,
         PIONEER_SHOWCASE_CHALLENGE,
         PIONEER_PREMIER]

RECOVERABLE_EXC = (
    APIException,
    ClientException,
    PRAWException,
    PrawcoreException,
    ConnectionError,
)


fileConfig('logging_config.ini')
log = logging.getLogger()


class MTGOResultsPostFinder:
    def __init__(self,
                 username,
                 password,
                 client_id,
                 client_secret,
                 limit):
        self.username = username
        self.password = password
        self.client_id = client_id
        self.client_secret = client_secret
        self.limit = limit
        self.headers = {}
        self._setup = False
        self.reddit = None
        self.db = Database('scraper')

    def sanitize_for_markdown(self, text):
        s = text.replace('_', r'\\_') if r'_' in text else text
        return s

    def sanitize_name(self, text):
        s = text.replace('\\', '') if '\\' in text else text
        return s

    def write_line_to_markdown(self, line, event):
        output_file = f'{event}.md'.replace(' ', '-')
        with open(output_file, 'w') as f:
            f.write(line + '\n')

    def build_markdown(self, submission_text, link):
        imgur_album_id = self.db.imgur_get_album_with_link(link)
        markdown = MARKDOWN_HEADER.format(imgur_album_id=imgur_album_id)
        total_decks = self.db.wizards_get_total_decklist_for_link(link)
        names_seen = []
        counter = 0
        lines = submission_text.split('\n')

        for idx, line in enumerate(lines):
            link_specific_pattern = fr'[\d{1}\.|\*]\s\[(.*)\]\({link}.*\):\s?\*\*(.*?)(\s)?(\(.*\))?\*\*'
            link_specific_match = re.search(link_specific_pattern, line)

            if counter >= total_decks:
                break
            matches = re.findall(link_specific_pattern, line)
            # if a couple of lines matched but then encounters
            # a line that doesn't while the counter is less than
            # the expected total deck number either the submission text
            # is missing a deck or the matched lines are red herrings
            # so reset counter to 0
            if not matches and counter <= total_decks:
                counter = 0

            if matches:
                counter += 1
                for match in matches:
                    archetype = match[0]
                    escaped_player = match[1]
                    player = self.sanitize_name(escaped_player)
                    # Keep track of players in case they appear in one event
                    # more than once.
                    names_seen.append(player)
                    # What happens to index if not all images are uploaded
                    # for a user that appears twice in one event?
                    index = names_seen.count(player) - 1
                    try:
                        r = self.db.imgur_find_rows_matching_link(link, player)
                        imgur_link = r[index][4]
                        md_line = MARKDOWN_PLAYER.format(archetype=archetype,
                                                         imgur_link=imgur_link,
                                                         escaped_player=escaped_player)
                        markdown += md_line
                    except IndexError:
                        pass
        return markdown

    def write_to_markdown(self, submission_text, event, link):
        output_file = f'{event}.md'.replace(' ', '-')
        markdown = self.build_markdown(submission_text, link)
        with open(output_file, 'w') as f:
            f.write(markdown)

    def create_markdown_based_on_current_state(self):
        '''
        Create the markdown based on reddit links not submitted
        yet and only use what's currently in the DB.
        '''
        pass

    def all_checks_passed(self, results_url, markdown):
        '''
        Perform checks that the data being posted
        is correct.
        '''
        is_true = False
        try:
            is_true = self.db.total_decks_match_for_link(results_url)
            is_true = self._check_imgur_links_appear_only_once(results_url,
                                                               markdown)
            is_true = self._check_all_markdown_exists(results_url,
                                                      markdown)
        except MarkdownCheckErrors as e:
            is_true = False
            log.warning(e)

        return is_true

    def _check_all_markdown_exists(self, results_url, markdown):
        rows = self.db.imgur_all_rows_with_link(results_url)
        for row in rows:
            imgur_link = row[4]
            player = self.sanitize_for_markdown(row[3])
            line = r'\({imgur_link}\): \*\*{player}\*\*'.format(
                imgur_link=imgur_link, player=player)
            line_in_md = re.search(line, markdown)
            if not line_in_md:
                raise MarkdownCheckErrors(f'Line "{line}" not in markdown.')
        return True

    def _check_imgur_links_appear_only_once(self, results_url, markdown):
        '''
        Check that all links from the imgur table appear
        only once inside the markdown.
        '''
        rows = self.db.imgur_all_rows_with_link(results_url)
        for row in rows:
            imgur_url = row[4]
            count = markdown.count(imgur_url)
            if count != 1:
                raise MarkdownCheckErrors(f'{imgur_url} showed up {count} times!')
        return True

    def test_build_markdown(self, file, results_url):
        with open(file, 'r') as f:
            submission_text = f.read()
            return self.build_markdown(submission_text, results_url)

    def find_new_results(self):
        subreddit = self.reddit.subreddit(SUBREDDIT)
        for link in LINKS:
            for submission in subreddit.new(limit=self.limit):
                link_in_self_text_fa = set(re.findall(link,
                                                      submission.selftext))
                for match in link_in_self_text_fa:
                    result_url = match[0]
                    url_in_db = self.db.reddit_result_url_in_table(result_url)
                    if not url_in_db:
                        log.debug(f'Adding {submission.url} to DB.')
                        self.db.add_reddit_row(
                            submission.url,
                            submission.selftext,
                            result_url,
                            0)

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
                event = results_url.split('/')[-1]
                log.info(results_url)
                submission = self.reddit.submission(url=reddit_url)
                if self.db.total_decks_match_for_link(results_url):
                    markdown = self.build_markdown(submission_text,
                                                   results_url)
                    self.write_to_markdown(
                        submission_text,
                        event,
                        results_url)
                    if self.all_checks_passed(results_url, markdown):
                        log.debug('Posting to reddit...')
                        submission.reply(body=markdown)
                        self.db.reddit_update_posted_screenshot(1, results_url)
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
    limit = int(ip.get_reddit_properties('LIMIT'))
    wait = int(ip.get_reddit_properties('WAIT'))
    refresh = int(ip.get_reddit_properties('REFRESH'))
    subreddits = ip.get_reddit_properties('SUBREDDITS')
    setup_has_been_run = False

    log.info("Starting...")
    try:
        try:
            log.info("Running")
            bot = MTGOResultsPostFinder(
                username,
                password,
                client_id,
                client_secret,
                limit)
            bot.setup() if not setup_has_been_run else None
            bot.run()
            log.info("Done")
        except RECOVERABLE_EXC as e:
            log.exception(e)
    except KeyboardInterrupt:
        pass
    finally:
        bot.quit()
    exit(0)
