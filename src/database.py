import sqlite3
import logging
from logging.config import fileConfig


fileConfig('logging_config.ini')
log = logging.getLogger()


class Database():

    def __init__(self, name):
        self.db = sqlite3.connect("{}.sqlite3".format(
            name.split('.sqlite3')[0]))
        self.tables = ["imgur_uploads"]
        self.cursor = self.db.cursor()
        self._create_imgur_tables()

    def _create_imgur_tables(self):
        for table in self.tables:
            self.cursor.execute("CREATE TABLE IF NOT EXISTS "
                                "{}("
                                "id INTEGER PRIMARY KEY AUTOINCREMENT,"
                                "file text,"
                                "album_id text,"
                                "player text,"
                                "url text)"
                                .format(table))

    def update_row(self):
        # https://www.sqlitetutorial.net/sqlite-update/
        pass

    def add_row(self, file, album_id, player, url):
        self.cursor.execute("INSERT INTO "
                            "{}("
                            "file,"
                            "album_id,"
                            "player,"
                            "url) "
                            "VALUES (?, ?, ?, ?)"
                            .format('imgur_uploads'),
                            (file,
                             album_id,
                             player,
                             url))
        self.commit()

    def delete_file(self, file):
        self.cursor.execute("DELETE FROM {} WHERE file = '{}'".format(
            'imgur_uploads', file))
        self.commit()

    def is_file_in_table(self, value):
        return self.column_contains(self.table, "file", value)

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
        # db.add_row(r'C:\foo\smthing.png', 'xYfk29', 'Player_Name', 'https://something.com')
        db.delete_file(r'C:\foo\smthing.png')
    except Exception as e:
        log.exception(e)
    finally:
        db.close()
