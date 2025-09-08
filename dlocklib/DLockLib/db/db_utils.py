#
# ******************************************************************************
# Druva Confidential and Proprietary
#
#  Copyright (C) 2019, Druva Technologies Pte. Ltd.  ALL RIGHTS RESERVED.
#
#  Except as specifically permitted herein, no portion of the
#  information, including but not limited to object code and source
#  code, may be reproduced, modified, distributed, republished or
#  otherwise utilized in any form or by any means for any purpose
#  without the prior written permission of Druva Technologies Pte. Ltd.
#
#  Visit http: //www.druva.com/ for more information.
# ******************************************************************************

import sqlobject
from DLockLib import dlock_globals
from DLockLib.db import dlock_db_errors
from DLockLib import dlock_globals as Globals

try:
    import MySQLdb
except ImportError:
    import pymysql

    pymysql.install_as_MySQLdb()
    import MySQLdb

import codecs

CHARACTER_SET_NAME = "utf8mb4"
COLLATION_NAME = "utf8mb4_unicode_520_ci"


def registerAliasForUtf8mb4Encoding():
    # Need to be set by all the processes which makes Mysql Connection with encoding as utf8mb4.
    codecs.register(lambda name: codecs.lookup('utf8') if name == 'utf8mb4' else None)


def get_connection():
    try:
        connection = dlock_globals.connection
        if not connection:
            raise dlock_db_errors.DLockDBError(dlock_db_errors.ELOCKDBINVALIDCONNECTION)
        return connection
    except Exception as fault:
        SyncLog.error("Error getting dlock db connection.  Error:%s", fault)
        raise fault


def mysql_connect(rds_host, rds_port, rds_dbname, rds_user, rds_passwd, mysql_ssl_enable, ssl_ca):
    ssl_settings = {'ca': ssl_ca}
    kwargs = {'charset': CHARACTER_SET_NAME}
    if mysql_ssl_enable:
        connection = MySQLdb.connect(user=rds_user, passwd=rds_passwd,
                                     host=rds_host, port=rds_port, db=rds_dbname, ssl=ssl_settings, **kwargs)
    else:
        connection = MySQLdb.connect(user=rds_user, passwd=rds_passwd,
                                     host=rds_host, port=rds_port, db=rds_dbname, **kwargs)

    registerAliasForUtf8mb4Encoding()
    return connection
