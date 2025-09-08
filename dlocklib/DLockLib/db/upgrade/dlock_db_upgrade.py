import time
import os
from datetime import datetime

from DLockLib.db import db_utils
from DLockLib.db import db_params
from DLockLib.db import dlockdb
from DLockLib import dlock_globals as Globals

class DLockDBUpgrade:
    def __init__(self, rds_host, rds_port, rds_dbname, rds_user, rds_passwd, mysql_ssl_enable, ssl_ca):
        self.rds_host = rds_host
        self.rds_port = rds_port
        self.rds_dbname = rds_dbname
        self.rds_user = rds_user
        self.rds_passwd = rds_passwd
        self.mysql_ssl_enable = mysql_ssl_enable
        self.ssl_ca = ssl_ca

    def mysql_connect(self):
        connection = db_utils.mysql_connect(self.rds_host, self.rds_port, self.rds_dbname, self.rds_user,
                                            self.rds_passwd,
                                            self.mysql_ssl_enable,
                                            self.ssl_ca)
        cursor = connection.cursor()
        return connection, cursor


    def is_init(self, cursor):
        ret = True
        cursor.execute("""
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_name = 'dlock' AND table_schema = '%s'
            """ % (self.rds_dbname))
        if cursor.fetchone()[0] == 1:
            ret = False
        return ret

    def validate_dlock_db_upgrade(self):
        retry_count = 5
        while retry_count:
            try:
                connection, _ = self.mysql_connect()
                break
            except Exception as fault:
                SyncLog.traceback(fault)
                retry_count -= 1
                time.sleep(5)
                if not retry_count:
                    return True

        try:
            cursor = connection.cursor()
            cursor.execute("""
                    SELECT COUNT(*)
                    FROM information_schema.tables
                    WHERE table_name = 'dlock_db_version' AND table_schema = '%s'
                    """ % (self.rds_dbname))

            if cursor.fetchone()[0] == 1:
                query = 'select count(*) from dlock_db_version where inupgrade=1'
                cursor.execute(query)
                count = cursor.fetchone()
                if count[0]:
                    SyncLog.error("Cannot start Service due to previous DLock DBupgrade failure. %s",
                                  "Please contact druva support.")
                    os._exit(0)

                query = """select dataversion from  dlock_db_version where dbname = '%s'""" % (
                    self.rds_dbname)
                cursor.execute(query)
                count = cursor.fetchone()
                if count[0] > db_params.DLOCK_DB_VERSION:
                    SyncLog.error(
                        "DLockDB is at newer version than system software. Cannot start Service. version: %s",
                        count[0])
                    os._exit(0)
            cursor.close()
        except:
            return
        finally:
            connection.close()

    def update_version_info(self, db, cursor, version, is_schema=False):
        query = "UPDATE dlock_db_version SET "
        if is_schema:
            query = query + "schemaversion=%d" % (version)
        else:
            query = query + "dataversion=%d" % (version)
        query = query + """ WHERE dbname='%s'""" % (db_params.DLOCK_DB_NAME)
        cursor.execute(query)
        db.commit()

        if not is_schema:
            if version == 1:
                dlockdb.DLockDBVersionHistory(dbname=db_params.DLOCK_DB_NAME,
                                              versionnumber=version,
                                              timestamp=datetime.now(),
                                              description="Initialized DLock DB ")

    def pre_populate_data(self, db, cursor):
        pass

    def upgrade_schema(self, db, cursor, version):
        # operations here have to be idempotent so that upgrade works seamlessly inspite of multiple crashes and
        # restarts during its execution
        # DO NOT USE SQLOBJECT BUT ONLY MYSQL CONNECTION FOR DATABASE ACCESS HERE
        try:
            while version < db_params.DLOCK_DB_VERSION:
                if version == 0:
                    pass
                version = version + 1
                self.update_version_info(db, cursor, version, is_schema=True)
                SyncLog.info("Upgraded DLock DB Schema to version %s", version)
        except Exception as fault:
            SyncLog.traceback(fault)
            SyncLog.error("Something went wrong during DLock DB upgrade, please contact druva support version %s",
                          version)
            SyncLog.error("Service will now stop till the problem is resolved version %s", version)
            os._exit(0)

    def upgrade_tables(self, db, cursor, version):
        try:
            while version < db_params.DLOCK_DB_VERSION:
                if version == 0:
                    pass
                version = version + 1
                self.update_version_info(db, cursor, version, is_schema=False)
                SyncLog.info("Upgraded DLock DB Tables to version %s", version)
        except Exception as fault:
            SyncLog.traceback(fault)
            SyncLog.error(
                "Something went wrong during DLock DB upgrade, please contact druva support. verison %s", version)
            SyncLog.error("Services will now stop till the problem is resolved. %s", version)
            os._exit(0)

    def get_dlock_db_version(self, cursor, dbname, is_schema=False):
        if_exists = False
        version = 0
        if is_schema:
            query = """SELECT schemaversion FROM dlock_db_version WHERE dbname='%s'""" % (dbname)
        else:
            query = """SELECT dataversion FROM dlock_db_version WHERE dbname='%s'""" % (dbname)
        cursor.execute(query)
        row = cursor.fetchone()
        if row:
            version = row[0]
            if_exists = True
        return if_exists, version

    def mark_in_upgrade(self, db, cursor, dbname, if_exists):
        if if_exists:
            cursor.execute("""UPDATE dlock_db_version SET inupgrade=1 WHERE dbname='%s'""" % (dbname))
        else:
            cursor.execute("""INSERT INTO dlock_db_version(dbname, schemaversion, dataversion, inupgrade)
                    VALUES ('%s', %d, %d, %d)""" % (dbname, 0, 0, 1))
        db.commit()

    def clear_in_upgrade(self):
        entry = list(dlockdb.DLockDBVersion.selectBy(dbname=db_params.DLOCK_DB_NAME))
        entry[0].inupgrade = False
        entry = list(dlockdb.DLockDBVersionHistory.selectBy(dbname=db_params.DLOCK_DB_NAME,
                                                            versionnumber=db_params.DLOCK_DB_VERSION))
        if not entry:
            SyncLog.error(
                'An entry in dlock_db_version_history table for the latest version number %d of %s is missing',
                db_params.DLOCK_DB_VERSION, db_params.DLOCK_DB_NAME)
            os._exit(0)

    def start_dlock_db_upgrade(self):
        dlockdb.DLockDBVersion.createTable(ifNotExists=True)
        dlockdb.DLockDBVersionHistory.createTable(ifNotExists=True)

        db, cursor = self.mysql_connect()
        is_dlockdb_init = self.is_init(cursor)
        if_exists, dlock_db_version = self.get_dlock_db_version(cursor,
                                                                db_params.DLOCK_DB_NAME)

        if is_dlockdb_init or dlock_db_version < db_params.DLOCK_DB_VERSION:
            self.mark_in_upgrade(db, cursor, db_params.DLOCK_DB_NAME, if_exists)
            if is_dlockdb_init:
                SyncLog.info("DLock DB  initialization started at time=%s", time.time())
            else:
                SyncLog.info("DLock DB Upgrade started at time=%s", time.time())
            dlockdb.init_tables()
        else:
            SyncLog.info("DLock DB  already at version %s", dlock_db_version)
        if is_dlockdb_init:
            self.update_version_info(db, cursor, db_params.DLOCK_DB_VERSION, is_schema=True)
            self.pre_populate_data(db, cursor)
            self.update_version_info(db, cursor, db_params.DLOCK_DB_VERSION)
            self.clear_in_upgrade()
        elif dlock_db_version < db_params.DLOCK_DB_VERSION:
            _, dlock_db_version = self.get_dlock_db_version(cursor,
                                                            db_params.DLOCK_DB_NAME,
                                                            is_schema=True)
            self.upgrade_schema(db, cursor, dlock_db_version)
            self.upgrade_tables(db, cursor, dlock_db_version)
            self.clear_in_upgrade()
