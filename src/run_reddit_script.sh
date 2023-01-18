#!/bin/bash
RUN_REDDIT_SCRIPT=$()
OUTPUT=$(ps -aux | grep -i "reddit_mtgo_results_bot.py" | grep -v "grep")
if [[ ! "$OUTPUT" ]]
then
    echo $(cd /root/mtgo-results-scraper/src && /root/mtgo-results-scraper/reddit-results-bot/bin/python3 /root/mtgo-results-scraper/src/reddit_mtgo_results_bot.py)
else
	echo "$OUTPUT"
fi