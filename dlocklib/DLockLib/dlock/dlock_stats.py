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


from DLockLib.db import dlock_db_errors
from dblib import dl as DLockDL

class StatsManager(object):
    def __init__(self, lock_key):
        self.lock_key = lock_key

    def update_stats(self, stats):
        dlock = DLockDL.get_dlock_by_lock_key(self.lock_key)
        if not dlock:
            raise dlock_db_errors.DLockDBError(dlock_db_errors.ELOCKNOTOWNED)
        dlock.update(opaque_stats=stats)

    def get_stats(self):
        dlock = DLockDL.get_dlock_by_lock_key(self.lock_key)
        if dlock:
            return dlock.opaque_stats
        return {}
    