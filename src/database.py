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
        self.cursor = self.db.cursor()
        self._create_imgur_table()
        self._create_reddit_table()

    def _create_imgur_table(self):
        self.cursor.execute("CREATE TABLE IF NOT EXISTS "
                            "{}("
                            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
                            "file text,"
                            "album_id text,"
                            "player text,"
                            "url text)"
                            .format(self.imgur_table))

    def _create_reddit_table(self):
        self.cursor.execute("CREATE TABLE IF NOT EXISTS "
                            "{}("
                            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
                            "url text,"
                            "submission_text text)"
                            .format(self.reddit_table))

    def update_row(self):
        # https://www.sqlitetutorial.net/sqlite-update/
        pass

    def add_imgur_row(self, file, album_id, player, url):
        self.cursor.execute("INSERT INTO "
                            "{}("
                            "file,"
                            "album_id,"
                            "player,"
                            "url) "
                            "VALUES (?, ?, ?, ?)"
                            .format(self.imgur_table),
                            (file,
                             album_id,
                             player,
                             url))
        self.commit()

    def add_reddit_row(self, url, submission_text):
        self.cursor.execute("INSERT INTO "
                            "{}("
                            "url,"
                            "submission_text) "
                            "VALUES (?, ?)"
                            .format(self.reddit_table),
                            (url,
                             submission_text))
        self.commit()

    def delete_file(self, file):
        self.cursor.execute(f'DELETE FROM {self.imgur_table} WHERE file = \'{file}\'')
        self.commit()

    def is_file_in_table(self, value):
        return self.column_contains(self.imgur_table, "file", value)

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

    def commit(self):
        self.db.commit()

    def close(self):
        log.debug("Closing database connection.")
        self.db.close()


if __name__ == "__main__":
    db = None
    try:
        db = Database("Uploads")
        db.add_imgur_row(r'C:\foo\smthing.png', 'xYfk29', 'Player_Name', 'https://something.com')
        # db.delete_file(r'C:\foo\smthing.png')
    except Exception as e:
        log.exception(e)
    finally:
        db.close()
