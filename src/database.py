import sqlite3


class Database():

    def __init__(self, name):
        self.db = sqlite3.connect("{}.sqlite3".format(name))
        self.tables = ["modern_results", "pioneer_results"]
        self.cursor = self.db.cursor()
        self._create_hashes_table()

    def _create_hashes_table(self):
        for table in self.tables:
            self.cursor.execute("CREATE TABLE IF NOT EXISTS "
                                "{}("
                                "id INTEGER PRIMARY KEY AUTOINCREMENT,"
                                "file text,"
                                "hash text)"
                                .format(table))

    def update_row(self):
        # https://www.sqlitetutorial.net/sqlite-update/
        pass

    def add_row(self, file, md5):
        self.cursor.execute("INSERT INTO "
                            "{}("
                            "file,"
                            "hash) "
                            "VALUES (?, ?)"
                            .format(self.table),
                            ('{}'.format(file),
                             '{}'.format(md5)))
        self.commit()

    def is_hash_in_table(self, value):
        return self.column_contains(self.table, "hash", value)

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