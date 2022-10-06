import sqlite3
import logging
from logging.config import fileConfig


fileConfig('logging_config.ini')
log = logging.getLogger()


class Database():

    def __init__(self, name):
        self.db = sqlite3.connect("{}.sqlite3".format(
            name.split('.sqlite3')[0]))
        self.tables = ['imgur_uploads', 'reddit']
        self.imgur_table = 'imgur_uploads'
        self.reddit_table = 'reddit'
        self.wizards_table = 'wizards'
        self.decklist_table = 'decklists'
        self.cursor = self.db.cursor()
        self._create_imgur_table()
        self._create_reddit_table()
        self._create_wizards_table()

    def _create_imgur_table(self):
        self.cursor.execute("CREATE TABLE IF NOT EXISTS "
                            "{}("
                            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
                            "file text,"
                            "album_id text,"
                            "player text,"
                            "url text,"
                            "result_url text)"
                            .format(self.imgur_table))

    def _create_reddit_table(self):
        self.cursor.execute("CREATE TABLE IF NOT EXISTS "
                            "{}("
                            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
                            "url text,"
                            "submission_text text,"
                            "result_url text,"
                            "posted_screenshots integer)"
                            .format(self.reddit_table))

    """
        Create a table for the url and total deck numbers
        the other tables can use as reference.
    """

    def _create_wizards_table(self):
        self.cursor.execute("CREATE TABLE IF NOT EXISTS "
                            "{}("
                            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
                            "url text,"
                            "total_decks integer)"
                            .format(self.wizards_table))

    def _create_decklist_table(self):
        self.cursor.execute("CREATE TABLE IF NOT EXISTS "
                            "{}("
                            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
                            "date text,"
                            "url text,"
                            "decklist integer)"
                            .format(self.decklist_table))

    def update_row(self):
        # https://www.sqlitetutorial.net/sqlite-update/
        pass

    def add_imgur_row(self, file, album_id, player, url, result_url):
        self.cursor.execute("INSERT INTO "
                            "{}("
                            "file,"
                            "album_id,"
                            "player,"
                            "url,"
                            "result_url) "
                            "VALUES (?, ?, ?, ?, ?)"
                            .format(self.imgur_table),
                            (file,
                             album_id,
                             player,
                             url,
                             result_url))
        self.commit()

    def add_reddit_row(self, url, submission_text, result_url, posted_screenshots):
        self.cursor.execute("INSERT INTO "
                            "{}("
                            "url,"
                            "submission_text,"
                            "result_url,"
                            "posted_screenshots) "
                            "VALUES (?, ?, ?, ?)"
                            .format(self.reddit_table),
                            (url,
                             submission_text,
                             result_url,
                             posted_screenshots))
        self.commit()

    def add_wizards_row(self, url, total_decks):
        self.cursor.execute("INSERT INTO "
                            "{}("
                            "url,"
                            "total_decks) "
                            "VALUES (?, ?)"
                            .format(self.wizards_table),
                            (url,
                             total_decks))
        self.commit()

    def delete_file(self, file):
        self.cursor.execute(f'DELETE FROM {self.imgur_table} WHERE file = \'{file}\'')
        self.commit()

    def is_file_in_table(self, value):
        return self.column_contains(self.imgur_table, "file", value)

    def reddit_url_in_table(self, value):
        return self.column_contains(self.reddit_table, 'url', value)

    def reddit_result_url_in_table(self, value):
        return self.column_contains(self.reddit_table, 'result_url', value)

    def is_result_link_in_imgur_table(self, value):
        return self.column_contains(self.imgur_table, "result_url", value)

    def total_decks_match_for_link(self, link):
        wizards = self.wizards_get_total_decklist_for_link(link)
        imgur = self.imgur_get_total_decklist_for_link(link)
        return True if wizards == imgur else False

    def wizards_get_total_decklist_for_link(self, link):
        sql = "\
          SELECT {column}\
          FROM {table}\
          WHERE url = '{link}'\
        ".format(table=self.wizards_table, column='total_decks', link=link)
        try:
            response = self.cursor.execute(sql).fetchall()
            return int(response[0][0])
        except IndexError:
            pass

    def imgur_all_duplicate_pilots_with_link(self, link):
        '''
        Return a list of the players that have two decklist
        screenshots
        '''
        sql = "\
          SELECT {column}\
          FROM {table}\
          WHERE result_url = '{link}'\
        ".format(column='player', table=self.imgur_table, link=link)
        response = self.cursor.execute(sql).fetchall()
        results = [x[0] for x in response]
        duplicates = set([x for x in results if results.count(x) > 1])
        return list(duplicates)

    def imgur_all_rows_with_link(self, link):
        sql = "\
          SELECT *\
          FROM {table}\
          WHERE result_url = '{link}'\
        ".format(table=self.imgur_table, link=link)
        response = self.cursor.execute(sql).fetchall()
        return response

    def imgur_get_total_decklist_for_link(self, link):
        sql = "\
          SELECT *\
          FROM {table}\
          WHERE result_url = '{link}'\
        ".format(table=self.imgur_table, link=link)
        response = self.cursor.execute(sql).fetchall()
        return int(len(response))

    def imgur_find_rows_matching_link(self, link, player):
        sql = "\
          SELECT *\
          FROM {table}\
          WHERE result_url = '{link}' and player = '{player}'\
        ".format(table=self.imgur_table, link=link, player=player)
        response = self.cursor.execute(sql).fetchall()
        return response

    def imgur_get_album_with_link(self, link):
        sql = "\
          SELECT *\
          FROM {table}\
          WHERE result_url = '{link}'\
        ".format(table=self.imgur_table, link=link)
        response = self.cursor.execute(sql).fetchall()
        return response[0][2]

    def column_contains(self, table, column, value):
        sql = "\
        SELECT CASE WHEN EXISTS(\
          SELECT {column}\
          FROM {table}\
          WHERE {column}= '{value}'\
        )\
        THEN CAST(True AS BIT)\
        ELSE CAST(False AS BIT)\
        END".format(column=column, table=table, value=value)

        for row in self.cursor.execute(sql):
            return True if row[0] == 1 else False

    def reddit_get_all_rows_that_didnt_post(self):
        sql = "\
          SELECT *\
          FROM {table}\
          WHERE posted_screenshots = '{value}'\
        ".format(table=self.reddit_table, value=0)
        response = self.cursor.execute(sql).fetchall()
        return [row for row in response]

    def reddit_update_posted_screenshot(self, oneOrZero, result_url):
        sql = "\
          UPDATE {table}\
          SET posted_screenshots = '{value}'\
          WHERE result_url = '{result_url}'\
        ".format(table=self.reddit_table, value=oneOrZero, result_url=result_url)
        self.cursor.execute(sql).fetchall()
        self.db.commit()

    def commit(self):
        self.db.commit()

    def close(self):
        log.debug("Closing database connection.")
        self.db.close()

    def output_all(self):
        sql = "\
          SELECT *\
          FROM {table}".format(table=self.imgur_table)
        response = self.cursor.execute(sql).fetchall()
        return response[len(response) - 1]


if __name__ == "__main__":
    db = None
    try:
        db_file = f"scraper.sqlite3"
        db = Database(db_file)
        # db.add_imgur_row(r'C:\foo\smthing.png', 'xYfk29', 'Player_Name', 'https://something.com')
        # db.delete_file(r'C:\foo\smthing.png')
    except Exception as e:
        log.exception(e)
    finally:
        db.close()
