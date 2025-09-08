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

import time
import pytest
import sqlobject
import datetime
from sqlobject import sqlbuilder
from sqlobject.sqlite import sqliteconnection
from dblib import dl as DLockDL
import uuid
from DLockLib.dlock import params
from DLockLib.dlock.dlock_api import DistributedLock
from DLockLib.db import dlock_db_errors

TEST_LOCK_KEY = 'test_app_task'
TEST_CONSUMER_UUID = str(uuid.uuid4())

try:
    import mock
    from mock import MagicMock
    from mock import patch, PropertyMock
except ImportError:
    from unittest import mock
    from unittest.mock import MagicMock
    from unittest.mock import patch, PropertyMock



@pytest.fixture
def remove_lock():
    try:
        DLockDL.remove_dlock(TEST_LOCK_KEY)
    except Exception as fault:
        print(fault)
        
@pytest.fixture
def add_lock():
    try:
        lock = {}
        now = time.time()
        cuuid = str(uuid.uuid4())
        lock['lock_key'] = TEST_LOCK_KEY
        lock['consumer_uuid'] = cuuid
        lock['acquired_at'] = now
        lock['time_to_live'] = now + params.MIN_LOCK_LEASE_TIME
        DLockDL.add_dlock(**lock)

    except Exception as fault:
        print(fault)
    yield
    try:
        DLockDL.remove_dlock(TEST_LOCK_KEY)
    except Exception as fault:
        print(fault)



@pytest.fixture
def add_lock_with_released_state():
    try:
        lock = {}
        now = time.time()
        lock['lock_key'] = TEST_LOCK_KEY
        lock['state'] = params.STATE_RELEASED
        lock['consumer_uuid'] = TEST_CONSUMER_UUID
        lock['acquired_at'] = now - params.MIN_LOCK_LEASE_TIME
        lock['released_at'] = now
        lock['time_to_live'] =now
        DLockDL.add_dlock(**lock)
    except Exception as fault:
        print(fault)
        
    yield 
    
    try:
        DLockDL.remove_dlock(TEST_LOCK_KEY)
    except Exception as fault:
        print(fault)


@pytest.fixture
def add_lock_with_ttl_expired():
    try:
        lock = {}
        now = time.time()
        lock['lock_key'] = TEST_LOCK_KEY
        lock['state'] = params.STATE_LOCKED
        lock['consumer_uuid'] = TEST_CONSUMER_UUID
        lock['acquired_at'] = now - 2* params.MIN_LOCK_LEASE_TIME
        lock['time_to_live'] = now -  params.MIN_LOCK_LEASE_TIME
        DLockDL.add_dlock(**lock)
    except Exception as fault:
        print(fault)
    yield
    try:
        DLockDL.remove_dlock(TEST_LOCK_KEY)
    except Exception as fault:
        print(fault)


class TestDistributedLock:

    def test_acquire_lock_with_no_record_exists(self):
        dlock_obj = DistributedLock(TEST_LOCK_KEY)
        acquired = dlock_obj.acquire()
        assert acquired == True

    def test_acquire_lock_with_previous_lock_released(self,add_lock_with_released_state):
        dlock_obj = DistributedLock(TEST_LOCK_KEY)
        acquired = dlock_obj.acquire()
        assert acquired == True
        assert dlock_obj.__consumer_uuid != TEST_CONSUMER_UUID
        
    def test_acquire_lock_with_previous_lock_ttl_expired(self, add_lock_with_ttl_expired):
        dlock_obj = DistributedLock(TEST_LOCK_KEY)
        acquired = dlock_obj.acquire()
        assert acquired == True
        assert dlock_obj.__consumer_uuid != TEST_CONSUMER_UUID


    def test_acquire_lock_with_lock_already_owned_by_other(self, add_lock ):
        dlock_obj = DistributedLock(TEST_LOCK_KEY)
        acquired = dlock_obj.acquire()
        assert acquired == False
    

    def test_release_lock(self, add_lock):
        dlock_obj = DistributedLock(TEST_LOCK_KEY)
        dlock_obj.__consumer_uuid = TEST_CONSUMER_UUID
        released = dlock_obj.release()
        assert released == True

    def test_release_lock_when_already_released(self,add_lock_with_released_state):
        with pytest.raises(Exception) as e:
            dlock_obj = DistributedLock(TEST_LOCK_KEY)
            dlock_obj.__consumer_uuid = TEST_CONSUMER_UUID
            released = dlock_obj.release()
        assert e.type == dlock_db_errors.DLockDBError
        assert e.errno == dlock_db_errors.ELOCKALREADYRELEASED

    def test_release_lock_when_not_owned(self, add_lock):
        with pytest.raises(Exception) as e:
            dlock_obj = DistributedLock(TEST_LOCK_KEY)
            dlock_obj.__consumer_uuid = str(uuid.uuid4())
            released = dlock_obj.release()
        assert e.type == dlock_db_errors.DLockDBError
        assert e.errno == dlock_db_errors.ELOCKNOTOWNED
        

    def test_extend_lock_lease(self, add_lock):
        dlock_obj = DistributedLock(TEST_LOCK_KEY)
        now = time.time()
        lease_time = params.MIN_LOCK_LEASE_TIME
        dlock_obj.extend_lease(lease_time=lease_time)
        lock_obj = DLockDL.get_dlock_by_lock_key_consumer_uuid(TEST_LOCK_KEY, TEST_CONSUMER_UUID)
        assert lock_obj is not None
        assert lock_obj.ttl - now >= params.MIN_LOCK_LEASE_TIME
        

    def test_extend_lock_lease_with_min_lease_time_violation(self, add_lock):
        lease_time = params.MIN_LOCK_LEASE_TIME
        with pytest.raises(Exception) as e:
            dlock_obj = DistributedLock(TEST_LOCK_KEY)
            dlock_obj.__consumer_uuid = TEST_CONSUMER_UUID
            dlock_obj.extend_lease(lease_time=0.5 * lease_time)
        assert e.type == dlock_db_errors.DLockDBError
        assert e.errno == dlock_db_errors.EMINLOCKLEASEVIOLATION


    def test_extend_lock_lease_with_when_not_owned(self, add_lock):
        lease_time = params.MIN_LOCK_LEASE_TIME
        with pytest.raises(Exception) as e:
            dlock_obj = DistributedLock(TEST_LOCK_KEY)
            dlock_obj.__consumer_uuid = TEST_CONSUMER_UUID
            dlock_obj.extend_lease(lease_time=lease_time)
        assert e.type == dlock_db_errors.DLockDBError
        assert e.errno == dlock_db_errors.ELOCKNOTOWNED


    def test_is_acquired_with_lock_not_exists(self, remove_lock):
        dlock_obj = DistributedLock(TEST_LOCK_KEY)
        dlock_obj.__consumer_uuid = TEST_CONSUMER_UUID
        is_acquired = dlock_obj.is_acquired()
        assert is_acquired == False

    def test_is_acquired_with_lock_state_not_locked(self, add_lock_with_released_state):
        dlock_obj = DistributedLock(TEST_LOCK_KEY)
        dlock_obj.__consumer_uuid = TEST_CONSUMER_UUID
        is_acquired = dlock_obj.is_acquired()
        assert is_acquired == False

    def test_is_acquired_with_lock_not_owned(self, add_lock):
        dlock_obj = DistributedLock(TEST_LOCK_KEY)
        dlock_obj.__consumer_uuid =  str(uuid.uuid4())
        is_acquired = dlock_obj.is_acquired()
        assert is_acquired == False
        
