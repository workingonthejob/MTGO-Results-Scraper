import requests
from lxml import html
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry


class MTGOResultsScraper():

    def __init__(self):
        self.url = "http://magic.wizards.com/en/articles/archive/mtgo-standings/modern-league-2022-05-27"
        self.x_deck_container = '//div[@class="deck-group"]'
        self.x_player = './/h4'
        self.x_main_card_names ='.//div[@class="sorted-by-overview-container sortedContainer"]//span[@class="card-name"]/a'
        self.x_main_card_counts = './/div[@class="sorted-by-overview-container sortedContainer"]//span[@class="card-count"]'
        self.x_side_card_names = './/div[@class="sorted-by-sideboard-container  clearfix element"]//span[@class="card-name"]/a'
        self.x_side_card_counts = './/div[@class="sorted-by-sideboard-container  clearfix element"]//span[@class="card-count"]'
        self.headers = {'User-Agent':
                        'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
                        'AppleWebKit/537.36 (KHTML, like Gecko)'
                        'Chrome/101.0.4951.67 Safari/537.36',
                        'accept': 'application/json'}

    def run(self):
        session = requests.Session()
        retry = Retry(connect=3, backoff_factor=0.5)
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        r = session.get(self.url, headers=self.headers)
        tree = html.fromstring(r.content)
        deck_containers = tree.xpath(self.x_deck_container)
        for deck in deck_containers:
            player = deck.find(self.x_player).text
            print("[{}]".format(player))
            main_card_names = deck.findall(self.x_main_card_names)
            main_card_counts = deck.findall(self.x_main_card_counts)
            side_card_names = deck.findall(self.x_side_card_names)
            side_card_counts = deck.findall(self.x_side_card_counts)
            total_cards_main = 0
            total_cards_side = 0
            for i in range(len(main_card_counts)):
                number_of_cards = int(main_card_counts[i].text)
                card_name = main_card_names[i].text
                print("{} {}".format(number_of_cards, card_name))
                total_cards_main += number_of_cards

            print("{} total cards main deck.".format(total_cards_main))
            print("----------------")
            for i in range(len(side_card_counts)):
                number_of_cards = int(side_card_counts[i].text)
                card_name = side_card_names[i].text
                print("{} {}".format(number_of_cards, card_name))
                total_cards_side += number_of_cards

            print("{} total cards in sideboard.".format(total_cards_side))
            print("----------------")


if __name__ == "__main__":
    scraper = MTGOResultsScraper()
    scraper.run()
