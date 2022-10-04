# MTGO Results Scraper

## Description
Scrape any of the results Wizards releases for MTGO.

For reference here is what the page looks like for a single deck with highlighting of cards:

![Screenshot](screenshot.PNG)

Here's the an example of the output:

```
{'Mainboard': {"Archmage's Charm": 3,
               'Brazen Borrower': 1,
               'Consider': 4,
               'Counterspell': 4,
               'Expressive Iteration': 4,
               'Fiery Islet': 1,
               'Fire // Ice': 1,
               'Flooded Strand': 3,
               'Force of Negation': 1,
               'Ledger Shredder': 4,
               'Lightning Bolt': 3,
               "Mishra's Bauble": 4,
               'Murktide Regent': 3,
               'Otawara, Soaring City': 1,
               'Polluted Delta': 2,
               'Ragavan, Nimble Pilferer': 4,
               'Scalding Tarn': 2,
               'Snow-Covered Island': 3,
               'Spell Pierce': 1,
               'Spirebluff Canal': 4,
               'Steam Vents': 3,
               'Unholy Heat': 4},
 'Player': 'fer_magic',
 'Sideboard': {'Chandra, Awakened Inferno': 1,
               'Dress Down': 1,
               'Engineered Explosives': 2,
               'Flusterstorm': 2,
               'Fury': 1,
               'Magus of the Moon': 2,
               'Mystical Dispute': 2,
               'Subtlety': 1,
               'Test of Talents': 1,
               'Unlicensed Hearse': 2}}
```

For output examples of `-s/--take-screenshots` look [here](examples/take-screenshots). The corresponding MTGO results link for the screenshots can be found [here](https://magic.wizards.com/en/articles/archive/mtgo-standings/pioneer-league-2022-06-02).

---
## How it works

The application can be broken down into these pieces:

**Screenshot Taker**:

Scheduled as a cron job that is run at a set interval. Since the format of the decklist dumps is in a known format the application checks these end points until it sees the results posted where it then highlights the latest Standard released cards and takes screenshots of the decklist. Once the screenshots are taken then they are cropped to omit the card preview on the decklist page and then uploaded to imgur.

**Reddit Results Post Finder**:

Scheduled as a cron job that is run at a set interval that searches Reddit for a post containing a link to deck dump for a league, challenge, or showcase. If the result URL is not in the database then record that the post has been made. Thereafter check whether the application has already processed and uploaded the decklist screenshots and if so generate the markdown and post the markdown to the Reddit post.

Install the requirements:

`pip install -r requirements.txt`

Other Dependencies:

```
Chrome
```

Here is the help menu for the tool:

```
usage: mtgo_results_scraper.py [-h] [-o OUTPUT_DIR] [-c] [-s] -u URL

Scrape and/or screenshot the Magic: The Gathering match results.

optional arguments:
  -h, --help            show this help message and exit
  -o OUTPUT_DIR, --output-dir OUTPUT_DIR
                        The directory to save content to.
  -c, --crop-screenshots
                        Crop the screenshots of the card preview.
  -s, --take-screenshots
                        Take screenshots of the decks.
  -u URL, --url URL     The page to start at or create screenshots of.
  ```