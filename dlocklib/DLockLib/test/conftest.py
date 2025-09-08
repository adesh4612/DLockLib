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

import pytest
import sqlobject
from sqlobject import sqlbuilder
from sqlobject.sqlite import sqliteconnection
from DLockLib.db import dlock_dl_bootstrap
from DLockLib import dlock_globals
from DLockLib.db import dlockdb
from DLockLib.test.logger import Log


try:
    import MySQLdb
except ImportError:
    import pymysql
    pymysql.install_as_MySQLdb()
    import MySQLdb

try:
    from mock import MagicMock
    from mock import patch
except ImportError:
    from unittest.mock import MagicMock
    from unittest.mock import patch



@pytest.fixture(autouse=True, scope='session')
def builtin_session_scope():
    log= Log()
    dlock_globals.SyncLog = log
    
    
    
@pytest.fixture(autouse=True, scope='session')
def sqlite_db_session(tmpdir_factory):
    file = tmpdir_factory.mktemp('db').join('sqlite.db')
    conn = sqliteconnection.SQLiteConnection(str(file))
    sqlobject.sqlhub.processConnection = conn
    dlockdb.DLock.createTable(ifNotExists=True)
    yield conn
    conn.close()
    

