#!/bin/bash
RUN_REDDIT_SCRIPT=$()
OUTPUT=$(ps -aux | grep -i "results_page_checker.py" | grep -v "grep")
if [[ ! "$OUTPUT" ]]
then
    echo $(cd /root/mtgo-results-scraper/src && /root/mtgo-results-scraper/reddit-results-bot/bin/python3 /root/mtgo-results-scraper/src/results_page_checker.py)
else
	echo "$OUTPUT"
fi