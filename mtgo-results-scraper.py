import requests
import time
import sys
from lxml import html
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry


class MTGOResultsScraper():

    def __init__(self):
        self.url = "http://magic.wizards.com/en/articles/archive/mtgo-standings/modern-league-2022-05-27"
        self.x_deck_container = '//div[@class="deck-group"]'
        self.x_main_card_names ='.//div[@class="sorted-by-overview-container sortedContainer"]//span[@class="card-name"]/a'
        self.x_main_card_counts = './/div[@class="sorted-by-overview-container sortedContainer"]//span[@class="card-count"]'

    def run(self):
        session = requests.Session()
        retry = Retry(connect=3, backoff_factor=0.5)
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.67 Safari/537.36', 'accept': 'application/json'}
        r = session.get(self.url, headers=headers)
        tree = html.fromstring(r.content)
        deck_containers = tree.xpath(self.x_deck_container)
        for deck in deck_containers:
            player = deck.find('.//h4').text
            print("[{}]".format(player))
            main_card_names = deck.findall(self.x_main_card_names)
            main_card_counts = deck.findall('.//div[@class="sorted-by-overview-container sortedContainer"]//span[@class="card-count"]')
            side_card_names = deck.findall('.//div[@class="sorted-by-sideboard-container  clearfix element"]//span[@class="card-name"]/a')
            side_card_counts = deck.findall('.//div[@class="sorted-by-sideboard-container  clearfix element"]//span[@class="card-count"]')
            total_cards_main = 0
            total_cards_side = 0
            for i in range(len(main_card_counts)):
                print("{} {}".format(main_card_counts[i].text, main_card_names[i].text))
                total_cards_main += int(main_card_counts[i].text)

            print("{} total cards main deck.".format(total_cards_main))
            print("----------------")
            for i in range(len(side_card_counts)):
                print("{} {}".format(side_card_counts[i].text, side_card_names[i].text))
                total_cards_side += int(side_card_counts[i].text)

            print("{} total cards in sideboard.".format(total_cards_side))
            print("----------------")
            # time.sleep(5)


if __name__ == "__main__":
    scraper = MTGOResultsScraper()
    scraper.run()
