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
import time
import uuid

from DLockLib.db import db_utils
from dblib import dl as DLockDL
from DLockLib.dlock import params
from sqlobject.dberrors import DuplicateEntryError
from DLockLib.db import dlock_db_errors
from DLockLib import dlock_globals as Globals


class API(object):
    def get_lock_record_by_lock_key(self, lock_key):
        return DLockDL.get_dlock_by_lock_key(lock_key)

    def is_lock_expired(self, lock_key):
        lock_item = DLockDL.get_dlock_by_lock_key(lock_key)
        if lock_item is None:
            raise dlock_db_errors.DLockDBError(dlock_db_errors.ELOCKNOTFOUND)
        return lock_item.time_to_live < int(time.time())


class DistributedLock(object):
    def __init__(self, lock_key):
        self.lock_key = lock_key
        self.__consumer_uuid = None
    
    def __clear_counsumer_uuid(self):
        self.__consumer_uuid = None

    def get_consumer_uuid(self):
        return self.__consumer_uuid

    def acquire(self, lease_time=params.MIN_LOCK_LEASE_TIME):
        """
        acquires lock for a consumer for a specified lock key
            if lock already exists and unreleased lock grant fails
            if lock is successfully acquired system generated consumer uuid is assigned to the consumer

        Parameters:
        ----------
        lease_time: integer
            initially lock is leased to the consumer for the specified 'lease_time' interval
        ----------
        """
        try:
            connection = db_utils.get_connection()
            transaction = connection.transaction()
            try:
                dlock = DLockDL.QBDLock
                lock_item = list(dlock.select(dlock.q.lock_key == self.lock_key, connection=transaction, forUpdate=True))
                lock_item = lock_item[0] if lock_item else None
                if lock_item is not None:
                    if lock_item.state == params.STATE_RELEASED or lock_item.time_to_live < int(time.time()):
                        where_expr = dlock.q.lock_key == self.lock_key
                        dlock.deleteMany(where = where_expr, connection=transaction)
                        SyncLog.info("Successfully deleted lock record for the lock key:%s",self.lock_key)
                    else:
                        transaction.commit(close=True)
                        return False
            except Exception as fault:
                SyncLog.error("Error in deleting dlock with lock key:%s, Error:%s", self.lock_key, fault)
                SyncLog.traceback(fault)
                transaction.rollback()
                return False
            else:
                transaction.commit(close=True)

            lock = {}
            now = int(time.time())
            cuuid = str(uuid.uuid4())
            lock['lock_key'] = self.lock_key
            lock['consumer_uuid'] = cuuid
            lock['acquired_at'] = now
            lock['time_to_live'] = now + int(lease_time)
            DLockDL.add_dlock(**lock)
            self.__consumer_uuid = cuuid
            SyncLog.info("Successfully acquired lock for lock key:%s consumer uuid:%s", self.lock_key, self.__consumer_uuid)
            return True
        except Exception as fault:
            # in case of lock_key unique constraints violation error will be of type:DuplicateEntryError
            SyncLog.error("Error processing acquire lock request for lock key:%s. Error: %s", self.lock_key,
                                  fault)
            if isinstance(fault, DuplicateEntryError):
                return False
            raise dlock_db_errors.DLockDBError(dlock_db_errors.ELOCKINTERNAL)

    def release(self):
        """
        releases lock for a lock key upon consumer request
        lock is successfully released only when lock is owned by the consumer
        upon successful lock release consumer uuid is reset

        ----------
        returns:
            Boolean
            True if lock is successfully released else False
        ----------
        """
        try:
            connection = db_utils.get_connection()
            transaction = connection.transaction()
            dlock = DLockDL.QBDLock
            lock_item = list(dlock.select(
                sqlobject.AND(dlock.q.lock_key == self.lock_key, dlock.q.consumer_uuid == self.__consumer_uuid),
                connection=transaction, forUpdate=True))
            lock_item = lock_item[0] if lock_item else None
            if not lock_item:
                raise dlock_db_errors.DLockDBError(dlock_db_errors.ELOCKNOTOWNED)

            if lock_item.state == params.STATE_RELEASED:
                    raise dlock_db_errors.DLockDBError(dlock_db_errors.ELOCKALREADYRELEASED)
            now = int(time.time())
            lock_item.update(state=params.STATE_RELEASED, released_at=now, time_to_live=now)
            SyncLog.info("Successfully released lock for lock key:%s by consumer uuid:%s", self.lock_key,
                                 self.__consumer_uuid)
            self.__clear_counsumer_uuid()
            transaction.commit(close=True)
            return True 
        except Exception as fault:
            SyncLog.error("Error in releasing dlock with lock key:%s, Error:%s", self.lock_key, fault)
            SyncLog.traceback(fault)
            transaction.rollback()
            if isinstance(fault, dlock_db_errors.DLockDBError):
                if fault.errno in [dlock_db_errors.ELOCKNOTOWNED, dlock_db_errors.ELOCKALREADYRELEASED]:
                    return False
            raise dlock_db_errors.DLockDBError(dlock_db_errors.ELOCKINTERNAL)
           

    # raise all 
    def extend_lease(self, lease_time):
        """
        extends lock for a lock key upon consumer request by specified lease time
        lock lease is successfully extends only when lock is owned by the consumer
        lock ttl is updated to current time+ lease time
        ----------
        Parameters:
            lease_time: int
            time in (seconds) by which lock lease is extended
        ----------
        """
        try:
            connection = db_utils.get_connection()
            transaction = connection.transaction()
            if lease_time < params.MIN_LOCK_LEASE_TIME:
                raise dlock_db_errors.DLockDBError(dlock_db_errors.EMINLOCKLEASEVIOLATION)
            dlock = DLockDL.QBDLock
            lock_item = list(dlock.select(
                sqlobject.AND(dlock.q.lock_key == self.lock_key, dlock.q.consumer_uuid == self.__consumer_uuid),
                connection=transaction, forUpdate=True))
            lock_item = lock_item[0] if lock_item else None
            if not lock_item:
                raise dlock_db_errors.DLockDBError(dlock_db_errors.ELOCKNOTOWNED)
            if lock_item and lock_item.state == params.STATE_RELEASED:
                    raise dlock_db_errors.DLockDBError(dlock_db_errors.ELOCKALREADYRELEASED)
            lock_item.update(time_to_live=int(time.time() + lease_time))
            transaction.commit(close=True)
            SyncLog.info("Successfully extended lock lease for lock key:%s by consumer uuid:%s", self.lock_key,
                                 self.__consumer_uuid)
        except Exception as fault:
            SyncLog.error("Error in extending dlock lease with lock key:%s, Error:%s", self.lock_key, fault)
            SyncLog.traceback(fault)
            transaction.rollback()
            raise fault 

    def is_acquired(self):
        """
        check is lock is still acquired by requested consumer for the specific lock key
        lock is still acquired only when lock entry for a consumer exists and lock is in 'locked' state

        ----------
        returns:
            1.acquired:Boolean
                True if lock is holds the lock and lock is in 'locked' state else False
            2.expired:Boolean
                  True if lock is expired based on ttl value else False
        ----------
        """
        dlock = DLockDL.get_dlock_by_lock_key_consumer_uuid(self.lock_key, self.__consumer_uuid)
        acquired, expired = False, True
        if dlock:
            expired = True if dlock.time_to_live < int(time.time()) else False
            if dlock.state == params.STATE_LOCKED:
                acquired = True
        return acquired, expired

    def remove_entry(self):
        """delete lock record from db."""
        try:
            DLockDL.remove_dlock(self.lock_key, consumer_uuid=self.__consumer_uuid)
            self.__clear_counsumer_uuid()
        except Exception as fault:
            raise fault
