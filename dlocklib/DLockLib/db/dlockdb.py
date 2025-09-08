#
# ******************************************************************************
# Druva Confidential and Proprietary
#
#  Copyright (C) 2014, Druva Technologies Pte. Ltd.  ALL RIGHTS RESERVED.
#
#  Except as specifically permitted herein, no portion of the
#  information, including but not limited to object code and source
#  code, may be reproduced, modified, distributed, republished or
#  otherwise utilized in any form or by any means for any purpose
#  without the prior written permission of Druva Technologies Pte. Ltd.
#
#  Visit http://www.druva.com/ for more information.
# ******************************************************************************

import sqlobject
from DLockLib.dlock import params


class DLock(sqlobject.SQLObject):
    lock_key = sqlobject.UnicodeCol(unique=True, length=512)
    consumer_uuid = sqlobject.UnicodeCol(default='', length=128)
    state = sqlobject.UnicodeCol(default=params.STATE_LOCKED)
    opaque_stats = sqlobject.BLOBCol(default=b'', length=512 * 1024)
    acquired_at = sqlobject.BigIntCol(default=0)
    released_at = sqlobject.BigIntCol(default=0)
    time_to_live = sqlobject.BigIntCol(default=0)
    lock_key_index = sqlobject.DatabaseIndex(
        {'column': lock_key, 'length': 256})

    class sqlmeta:
        table = "dlock"


class DLockDBVersion(sqlobject.SQLObject):
    dbname = sqlobject.UnicodeCol(length=30, unique=True)
    schemaversion = sqlobject.IntCol(default=0)
    dataversion = sqlobject.IntCol(default=0)
    inupgrade = sqlobject.BoolCol(default=True)
    class sqlmeta:
        table = "dlock_db_version"


class DLockDBVersionHistory(sqlobject.SQLObject):
    dbname = sqlobject.UnicodeCol()
    versionnumber = sqlobject.IntCol()
    timestamp = sqlobject.DateTimeCol(sqlType='DATETIME')
    description = sqlobject.UnicodeCol()
    dbindex = sqlobject.DatabaseIndex(
        {'column': dbname, 'length': 15}, versionnumber, unique=True)

    class sqlmeta:
        table = "dlock_db_version_history"


def init_tables():
    DLock.createTable(ifNotExists=True)