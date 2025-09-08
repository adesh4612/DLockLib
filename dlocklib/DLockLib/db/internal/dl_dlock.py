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


from DLockLib.db import dlockdb
from dblib import dl as DLockDL
#from DLockLib.db.lib import DLBase
from dblib.dl_base import DLBase, DLMeta
import sqlobject

class DLDLock(DLBase):
    """
    DL class for DLock table..
    """

    attrlist = {}
    __metaclass__ = DLMeta

    @classmethod
    def __classinit__(cls):
        DLBase.init_common(cls, dlockdb.DLock, cls.attrlist)
        cls.attrlist.update({})

    def __init__(self, obj):
        DLBase.__init__(self, obj)

    def update(self, **kwargs):
        self.__obj.set(**kwargs)

    def __eq__(self, other):
        return self.id == other.id

    def __ne__(self, other):
        return self.id != other.id


def add_dlock(*args, **kwargs):
    _obj = dlockdb.DLock(*args, **kwargs)
    return DLDLock(_obj)


def remove_dlock(lock_key, consumer_uuid=None):
    dlock = DLockDL.QBDLock
    where_clause = dlock.q.lock_key == lock_key
    if consumer_uuid is not None:
        where_clause = sqlobject.AND(where_clause, dlock.q.consumer_uuid == consumer_uuid)
    dlock.deleteMany(where_clause)

def get_dlock_by_lock_key(lock_key):
    dlock = DLockDL.QBDLock
    locks = list(dlock.select(dlock.q.lock_key == lock_key))
    return locks[0] if len(locks) else None


def get_dlock_by_lock_key_consumer_uuid(lock_key, consumer_uuid):
    dlock = DLockDL.QBDLock
    locks = list(dlock.select(dlock.q.lock_key == lock_key).filter(
        dlock.q.consumer_uuid == consumer_uuid))
    return locks[0] if len(locks) else None
    


DLockDL.DLDLock = DLDLock
DLockDL.add_dlock = add_dlock
DLockDL.get_dlock_by_lock_key_consumer_uuid = get_dlock_by_lock_key_consumer_uuid
DLockDL.get_dlock_by_lock_key = get_dlock_by_lock_key
DLockDL.remove_dlock = remove_dlock