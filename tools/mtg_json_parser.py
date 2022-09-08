import json
import glob

exclude = ("Plains", "Swamp", "Island", "Forest", "Mountain", "Disdainful Stroke", "Negate")


def parse_mtg_json_for_latest_cards():
    card_tracker = []
    file = glob.glob('../resources/*.json')[0]
    with open(file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        with open(r'..\resources\latest_cards.txt', 'w', encoding='utf-8') as handle:
            for card in data['data']['cards']:
                card_name = card['name']
                # Remove duplicates and exclude specific cards
                if card_name not in card_tracker and card_name not in exclude:
                    handle.write(card_name + '\n')
                    card_tracker.append(card_name)
            # Remove newline at EOF
            handle.truncate(handle.tell() - 2)


parse_mtg_json_for_latest_cards()
