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

from DLockLib.db import dlock_dl_bootstrap
from DLockLib import dlock_globals
from DLockLib.db import dlock_db_errors


def validate_and_perform_db_upgrade(rds_host, rds_port, rds_dbname, rds_user, rds_passwd, mysql_ssl_enable, ssl_ca):
    from DLockLib.db.upgrade.dlock_db_upgrade import DLockDBUpgrade
    upgrader = DLockDBUpgrade(rds_host, rds_port, rds_dbname, rds_user, rds_passwd, mysql_ssl_enable, ssl_ca)
    upgrader.validate_dlock_db_upgrade()
    upgrader.start_dlock_db_upgrade()


#should we accept table name from consumer service and check if table actually exists to make sure db connection is rather working?
def configure(db_connection):
    if not db_connection:
        raise dlock_db_errors.DLockDBError(dlock_db_errors.ELOCKDBINVALIDCONNECTION)
    dlock_globals.connection = db_connection
        
