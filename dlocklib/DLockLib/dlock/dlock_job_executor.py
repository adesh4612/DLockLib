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
import json
import random
import uuid
import threading
import time

from DLockLib.dlock.dlock_api import DistributedLock
from abc import abstractmethod
from DLockLib.dlock import params
from DLockLib.dlock.dlock_stats import StatsManager
from DLockLib.db import dlock_db_errors


def lock_acquire_check(func):
    """
        this decorator checks if lock is still acquired before executing 'func'
        this decorator is used over functions which should perform dlock operations only if lock is still acquired
    """

    def new_func(self, *args, **kwargs):
        still_acquired, _ = self._dlock.is_acquired()
        if still_acquired:
            try:
                return func(self, *args, **kwargs)
            except Exception as fault:
                raise fault
        else:
            self._logger.error(
                "[DlockJobExecutor] Lock is no more owned for lock key:%s,for DlockJobExecutor thread with name:%s,identity:%s",
                self._lock_key, self.name, self.get_identity())

    return new_func


class DLockLeaseManager(threading.Thread):
    """
        This class is responsible for extending the lock lease periodically.

        Attributes
        ----------
        stop_event: threading.Event
            used for receiving stop event from PeriodicJobExecutor. once set thread is programed to exit
    """

    def __init__(self, executor_thread_identity, logger, dlock, lock_lease_time):
        self._logger = logger
        self._executor_thread_identity = executor_thread_identity
        self._dlock = dlock
        self._lock_lease_time = lock_lease_time
        self._stop_event = threading.Event()
        self.log_prefix = params.DLOCK_LEASE_MANAGER_LOG_PREFIX
        threading.Thread.__init__(self)

    def stop(self):
        """ sets the stop_event """
        self._logger.info("%s marked to stop at %s for executor_thread_identity:%s",
                          self.log_prefix,int(time.time()),
                          self._executor_thread_identity)
        self._stop_event.set()

    def is_stopped(self):
        """checks if set() operation was performed on stop_event"""
        return self._stop_event.isSet()

    def run(self):
        max_retries = params.DLOCK_LEASE_MANAGER_MAX_RETRIES
        retries = 0
        while True:
            if self.is_stopped():
                self._logger.info("%s exiting leaseManager at time:%s for executor_thread_identity:%s",
                                  self.log_prefix, int(time.time()), self._executor_thread_identity)
                break
            try:
                self._dlock.extend_lease(self._lock_lease_time)
                retries = 0
                self._logger.info(
                    "%s lock lease extended at time:%s for executor_thread_identity:%s",
                    self.log_prefix, int(time.time()), self._executor_thread_identity)
                time.sleep(int(self._lock_lease_time / 3))
            except Exception as fault:
                self._logger.error(
                    "%s Error in extending dlock lease for key:%s for executor_thread_identity:%s",
                    self.log_prefix, self._dlock.lock_key, self._executor_thread_identity)
                if isinstance(fault, dlock_db_errors.DLockDBError) and fault.errno in [
                    dlock_db_errors.ELOCKNOTOWNED]:
                    retries += 1
                    if retries >= max_retries:
                        self.stop()
                    else:
                        time.sleep(params.DLOCK_LEASE_MANAGER_SLEEP_AFTER_FAILED_RETRY)
                else:
                    self.stop()


class DLockJobExecutor(object):
    """
    This class contains dlock related attribute necessary to execute and manage given Job Function.
    Subclass is responsible for managing dlock life cycle(acquire,extend_lease_release) for a given Job Function.

    Attributes
    ----------
    name : string
        name of this executor.Used for logging
    logger : InsycLog
        used for logging formatted string. Types include info/error/debug/traceback etc
    lock_key : string
        passed to underlying dlock instance. All executors of same type compete for the lock using dlock interface for
        the same lock key
    lock_lease_time : int
        value for which lock lease time extended for. passed to the underlying dlock instance
    dlock: DistributedLock
        dlock object which actually responsible for lock related operations
    job_function: function
        core function which executes the critical section.
    iteration_sleep_interval: int
       gap between successive iterations of successful iterations of executors.i.e executors which acquired the lock.
       executed job_function and also completed dlock life cycle.
    lock_retry_sleep_interval: int
        time after which executor tries to acquire the lock.basically, the start of the next iteration of executor which could not
        acquire the lock in the previous iteration/attempt
    initial_sleep: int
        time for which executor sleeps before the start of 1st ever iteration.
    delegate_lease_manage: Boolean
         if only True then  DLockLeaseManager is spawnned. DLockLeaseManager is responsible for extending lock lease time
         periodically. In some case we might not need to extend the lock lease if job_function is expected to finish in
         very less time.
    job_function_args: tuple
        passed to the underlying job_function. acts as function args
    job_function_kwargs: dict
        passed to the underlying job_function. acts as function kwargs
    lease_manager: DLockLeaseManager
        extends the lock lease periodically.
    iteration_start: int
        records the time at which iteration is started . value is set only after lock is acquired
`   iteration_end: int
        records the time at which iteration is ended.
    identity : string
        randomly generated unique id for thread. used for logging.
    last_lock_status_checked: int
        value is epoc time. used by/for job_function to keep track of time when it has to perform lock checks.
        job_function should ideally be allowed to perform critical operations only when lock is still acquired by
        the executor
    delegate_lease_manage: Boolean
        if only True then  DLockLeaseManager is spawned. DLockLeaseManager is responsible for extending lock lease time
        periodically. In some case we might not need to extend the lock lease if job_function is expected to finish in
        very less time.
    cleanup_after_finish: Boolean
        if this flag is true, then after finishing job function lock record for specified lock key will be deleted.
        In many cases, previous lock state(ex.stats) are not required, consumer can set this flag as True so that stale
        entries of such lock records will be eliminated
    -------
    """

    def __init__(self, name, logger, lock_key, lock_lease_time, job_function,
                 initial_sleep=params.JOB_EXECUTOR_DEFAULT_INITIAL_SLEEP, delegate_lease_manage=True,
                 cleanup_after_finish=False,
                 args=(), kwargs={}):
        self.name = name
        self._logger = logger
        self._lock_key = lock_key
        self._lock_lease_time = lock_lease_time
        self._dlock = DistributedLock(lock_key)
        self._initial_sleep = initial_sleep
        self._stats_manager = StatsManager(self._lock_key)
        self._job_function = job_function
        self._job_function_args = args
        self._job_function_kwargs = kwargs
        self._last_lock_status_checked = 0
        self._delegate_lease_manage = delegate_lease_manage
        self._cleanup_after_finish = cleanup_after_finish
        self._lease_manager = None
        self._iteration_start = 0
        self._iteration_end = 0
        self._identity = str(uuid.uuid4())
        self._perform_pre_init_checks()
        self._pre_init_checks=0
        self._exit=False


    def _perform_pre_init_checks(self):
        try:
            if self._lock_lease_time < params.MIN_LOCK_LEASE_TIME:
                if
                raise dlock_db_errors.DLockDBError(dlock_db_errors.EMINLOCKLEASEVIOLATION)
        except Exception as fault:
            self._logger.
                "[DlockJobExecutor] Error in initialising dlock DlockJobExecutor notrwFa;for lock key:%s,name:%s,Error:%s",
                self._lock_key, self.name, fault)
            raise fault

    def get_identity(self):
        if not self.check_if_lock_acquired():
            return self._identity
        else
            return None

    def implement_common_consensus(self):
        return x == y




    def set_last_lock_status_checked(self):
        """
            used by/for job_function to keep track of lock status check time
        """
        self._last_lock_status_checked = int(time.time())

    def get_last_lock_status_checked(self):
        return self._last_lock_status_checked

    def is_lock_status_check_due(self):
        """
            -------
            Returns: Boolean
            lock status checked periodically. if status check is due return True otherwise False
        """
        if self.get_last_lock_status_checked() + int(self._lock_lease_time / 2) < int(time.time()):
            return True
        return False

    def check_current_lock_status(self):
        """
            This method is called from job_function. we pass executor object to job_function.
            job_function is allowed to perform critical operations only if executor still holds the lock.
            also lock status is checked at certain intervals to avoid DB query overheads
        """
        if self.is_lock_status_check_due():
            if not self.check_if_lock_acquired():
                raise dlock_db_errors.DLockDBError(dlock_db_errors.ELOCKNOTOWNED)
            self.set_last_lock_status_checked()

    def check_if_lock_acquired(self):
        """
            Returns: Boolean
            return True is lock is still acquired by dlock consumer/executor else False.
            basically used to restrict further critical operations based on lock status
        """
        acquired, _ = self._dlock.is_acquired()
        return acquired

    @lock_acquire_check
    def release_lock(self):
        try:
            self._dlock.release()
        except Exception as fault:
            self._logger.error(
                "[DlockJobExecutor] Error in releasing dlock for lock key:%s,for DlockJobExecutor thread with name:%s ,identity:%s. Error:%s",
                self._lock_key, self.name, self.get_identity(), fault)
            self._logger.traceback(fault)

    @lock_acquire_check
    def remove_lock_entry(self):
        try:
            self._dlock.remove_entry()
        except Exception as fault:
            self._logger.error(
                "[DlockJobExecutor] Error in deleting lock entry from db for lock key:%s,for DlockJobExecutor thread with name:%s ,identity:%s. Error:%s",
                self._lock_key, self.name, self.get_identity(), fault)
            self._logger.traceback(fault)
            raise fault
    def extend_lock_lease(self, lease_time=0):
        try:
            if not lease_time:
                lease_time = self._lock_lease_time
            self._dlock.extend_lease(lease_time)
        except Exception as fault:
            self._logger.error(
                "[DlockJobExecutor] Error in extending lock lease for lock key:%s,for DlockJobExecutor thread with name:%s ,identity:%s. Error:%s",
                self._lock_key, self.name, self.get_identity(), fault)

    def check_and_extend_lock_validity(self, lease_time=0):
        try:
            if self.get_last_lock_status_checked() + 10 < int(time.time()):
                self.extend_lock_lease(lease_time=lease_time)
                self.set_last_lock_status_checked()
        except Exception as fault:
            raise fault

    def get_dlock_stats(self):
        stats = self._stats_manager.get_stats()
        stats = json.loads(stats) if stats else {}
        return stats

    def update_current_dlock_stats(self, stats_to_update={}):
        if stats_to_update:
            stats = self.get_dlock_stats()
            stats.update(stats_to_update)
            self._stats_manager.update_stats(stats)

    @abstractmethod
    def execute_job(self):
        pass


class OneTimeJobExecutor(DLockJobExecutor):
    def __init__(self, name, logger, lock_key, lock_lease_time, job_function,
                 initial_sleep=params.JOB_EXECUTOR_DEFAULT_INITIAL_SLEEP, delegate_lease_manage=True,
                 cleanup_after_finish=False,
                 args=(), kwargs={}):
        DLockJobExecutor.__init__(self, name, logger, lock_key, lock_lease_time, job_function,
                                  initial_sleep=initial_sleep, delegate_lease_manage=delegate_lease_manage,
                                  cleanup_after_finish=cleanup_after_finish,
                                  args=args, kwargs=kwargs)
        self.log_prefix = params.DLOCK_ONETIME_JOB_EXECUTOR_LOG_PREFIX

    def execute_job(self):
        time.sleep(self._initial_sleep)
        acquired = False
        try:
            started_at = int(time.time())
            self._iteration_start, self._iteration_end = started_at, started_at
            try:
                acquired = self._dlock.acquire(self._lock_lease_time)
            except Exception as fault:
                SyncLog.error("lock acquire request failed for lock key:%s. Error: %s", self._lock_key, fault)
                acquired = False

            if not acquired:
                raise dlock_db_errors.DLockDBError(dlock_db_errors.ELOCKACQUIREFAILED)

            self._logger.info("%s Starting iteration for DlockJobExecutor with name:%s,identity:%s at %s",
                              self.log_prefix, self.name, self.get_identity(), self._iteration_start)
            self.set_last_lock_status_checked()
            if self._delegate_lease_manage:
                self._lease_manager = DLockLeaseManager(self.get_identity(), self._logger, self._dlock,
                                                        lock_lease_time=self._lock_lease_time)
                self._lease_manager.start()
            self._job_function(self, *self._job_function_args, **self._job_function_kwargs)
            self._iteration_end = int(time.time())
            self._logger.info("%s Ended iteration for DlockJobExecutor with name:%s,identity:%s at %s",
                              self.log_prefix, self.name, self.get_identity(), self._iteration_end)

        except Exception as fault:
            self._logger.info("%s Error in DlockJobExecutor with lock key:%s,name:%s,identity:%s.Error:%s ",
                              self.log_prefix, self._lock_key, self.name, self.get_identity(), fault)
            self._logger.traceback(fault)
            raise fault
        finally:
            if self._lease_manager is not None:
                self._lease_manager.stop()
            self._lease_manager = None
            if acquired:
                if self._cleanup_after_finish:
                    try:
                        # if job_executor is unable to delete lock entry , then it tries to release the lock
                        self.remove_lock_entry()
                    except Exception as fault:
                        self.release_lock()
                else:
                    self.release_lock()


class OneTimeJobExecutorThread(threading.Thread, OneTimeJobExecutor):
    def __init__(self, name, logger, lock_key, lock_lease_time, job_function,
                 initial_sleep=params.JOB_EXECUTOR_DEFAULT_INITIAL_SLEEP, delegate_lease_manage=True,
                 cleanup_after_finish=False,
                 args=(), kwargs={}):
        threading.Thread.__init__(self, name=name)
        OneTimeJobExecutor.__init__(self, name, logger, lock_key, lock_lease_time, job_function,
                                    initial_sleep=initial_sleep, delegate_lease_manage=delegate_lease_manage,
                                    cleanup_after_finish=cleanup_after_finish,
                                    args=args, kwargs=kwargs)
        self.log_prefix = params.DLOCK_ONETIME_JOB_EXECUTOR_LOG_PREFIX

    def run(self):
        try:
            self.execute_job()
        except Exception as fault:
            self._logger.error("%s Error in execute_job() function for the for key:%s error:%s", self.log_prefix,
                               self._lock_key, fault)
            self._logger.traceback(fault)


class BaseDLockPeriodicJobExecutor(threading.Thread, DLockJobExecutor):
    """
    This is the base class responsible for managing dlock life cycle(acquire,extend_lease_release) for a given Job Function.
    This runs iterations of given job_function periodically.It basically wraps around the job_function.

    Attributes
    ----------

    iteration_sleep_interval: int
       gap between successive iterations of successful iterations of executors.i.e executors which acquired the lock.
       executed job_function and also completed dlock life cycle.
    lock_retry_sleep_interval: int
        time after which executor tries to acquire the lock.basically, the start of the next iteration of executor which could not
        acquire the lock in the previous iteration/attempt
    iteration_start: int
        records the time at which iteration is started . value is set only after lock is acquired
`   iteration_end: int
        records the time at which iteration is ended.
    iteration_id: int
        keeps track of number of iterations for current thread. Value is incremented only after lock is acquired
    """

    def __init__(self, name, logger, lock_key, lock_lease_time, job_function, iteration_sleep_interval,
                 lock_retry_sleep_interval=params.JOB_EXECUTOR_DEFAULT_LOCK_RETRY_SLEEP_INTERVAL,
                 initial_sleep=params.JOB_EXECUTOR_DEFAULT_INITIAL_SLEEP,
                 delegate_lease_manage=True, cleanup_after_finish=False,
                 args=(), kwargs={}):
        threading.Thread.__init__(self, name=name)
        DLockJobExecutor.__init__(self, name, logger, lock_key, lock_lease_time, job_function,
                                  initial_sleep=initial_sleep,
                                  delegate_lease_manage=delegate_lease_manage,
                                  cleanup_after_finish=cleanup_after_finish,
                                  args=args, kwargs=kwargs)
        self.log_prefix = params.DLOCK_PERIODIC_JOB_EXECUTOR_LOG_PREFIX
        self._iteration_sleep_interval = iteration_sleep_interval
        self._iteration_id = 0
        self._lock_retry_sleep_interval = lock_retry_sleep_interval
        self._next_check = self._lock_retry_sleep_interval

    @abstractmethod
    def _update_next_trigger_time(self):
        """
            should be called from only currently running executor thread to which lock was granted.
            sets 'next_trigger_after'(epoch time) in dlock opaque_stats.next iterations of executors are only allowed to
            contend for lock current time >  next_trigger_after.
        """
        raise NotImplementedError

    def _get_next_iteration_sleep_interval(self):
        """
            returns time for which current executor goes to sleep.if previous executor(which owned the lock) iteration
            is completed then any executor should be run after next_trigger_due_time otherwise any executor will not be
            allowed to get the lock because of is_next_trigger_due check
        """
        now = int(time.time())
        next_trigger_due_time = self.get_next_trigger_due_time()
        if now > next_trigger_due_time:
            next_sleep = self._lock_retry_sleep_interval
        else:
            next_sleep = next_trigger_due_time - now
        next_sleep += random.randint(0, 60)
        return next_sleep

    def _set_next_trigger_time(self, next_trigger_after_interval):
        """
            sets next_trigger_after time(epoch time) in dlock opaque_stats.
        """
        stats = self.get_dlock_stats()
        stats['next_trigger_after'] = int(time.time()) + next_trigger_after_interval
        stats = json.dumps(stats).encode('utf-8')
        self._stats_manager.update_stats(stats)

    def is_next_trigger_due(self):
        """
            check if next executor iteration is due for run.'next_trigger_after' was updated from previous successful
            executor iteration
        """
        if self.get_next_trigger_due_time() < int(time.time()):
            return True
        return False

    def get_next_trigger_due_time(self):
        stats = self.get_dlock_stats()
        return stats.get('next_trigger_after', 0)

    def execute_job(self):
        time.sleep(self._initial_sleep)
        while True:
            acquired = False
            try:
                self._next_check = self._lock_retry_sleep_interval
                if self.is_next_trigger_due():
                    started_at = int(time.time())
                    self._iteration_start, self._iteration_end = started_at, started_at
                    acquired = self._dlock.acquire(self._lock_lease_time)
                    if acquired:
                        self._iteration_id += 1
                        self._logger.info(
                            "%s Starting iteration for DlockJobExecutor with name:%s,identity:%s,iteration_id:%s at %s",
                            self.log_prefix,self.name, self.get_identity(), self._iteration_id, self._iteration_start)
                        self.set_last_lock_status_checked()
                        if self._delegate_lease_manage:
                            self._lease_manager = DLockLeaseManager(self.get_identity(), self._logger, self._dlock,
                                                                    lock_lease_time=self._lock_lease_time)
                            self._lease_manager.start()
                        self._job_function(self, *self._job_function_args, **self._job_function_kwargs)
                        self._iteration_end = int(time.time())
                        self._update_next_trigger_time()
                        self._logger.info(
                            "%s Ended iteration for DlockJobExecutor with name:%s,identity:%s,iteration_id:%s with next_trigger_due_time:%s at %s",
                            self.log_prefix,self.name, self.get_identity(), self._iteration_id, self.get_next_trigger_due_time(),
                            self._iteration_end)
                self._next_check = self._get_next_iteration_sleep_interval()
            except Exception as fault:
                self._logger.info(
                    "%s Error in DlockJobExecutor with lock key:%s,name:%s,identity:%s.Error:%s ",
                    self.log_prefix,self._lock_key, self.name, self.get_identity(), fault)
                self._logger.traceback(fault)
            finally:
                if self._lease_manager is not None:
                    self._lease_manager.stop()
                self._lease_manager = None
                if acquired:
                    if self._cleanup_after_finish:
                        try:
                            # if job_executor is unable to delete lock entry , then it tries to release the lock
                            self.remove_lock_entry()
                        except Exception as fault:
                            self.release_lock()
                    else:
                        self.release_lock()
                time.sleep(self._next_check)

    def run(self):
        self.execute_job()


class DLockPeriodicJobExecutor(BaseDLockPeriodicJobExecutor):
    def __init__(self, name, logger, lock_key, lock_lease_time, job_function, iteration_sleep_interval,
                 initial_sleep=0, lock_retry_sleep_interval=30,
                 delegate_lease_manage=True, cleanup_after_finish=False,
                 args=(), kwargs={}):
        BaseDLockPeriodicJobExecutor.__init__(self, name, logger, lock_key, lock_lease_time, job_function,
                                              iteration_sleep_interval,
                                              initial_sleep=initial_sleep,
                                              lock_retry_sleep_interval=lock_retry_sleep_interval,
                                              delegate_lease_manage=delegate_lease_manage,
                                              cleanup_after_finish=cleanup_after_finish,
                                              args=args, kwargs=kwargs)

    @lock_acquire_check
    def _update_next_trigger_time(self):
        """
            always set next_trigger_after time to current_time + iteration_sleep_interval after successful iteration
            execution of executor
        """
        self._set_next_trigger_time(next_trigger_after_interval=self._iteration_sleep_interval)


class DLockPeriodicJobExecutorWithFixedSLA(BaseDLockPeriodicJobExecutor):
    """
        this is a particular variation in which job_function is supposed to execute after fixed intervals.
        for ex. every 20 hours, irrespective of when the last iteration was finished. i.e there is fixed interval between
        start of prev. iteration and start of current/next possible iteration
    """

    def __init__(self, name, logger, lock_key, lock_lease_time, job_function, iteration_sleep_interval,
                 initial_sleep=0, lock_retry_sleep_interval=30,
                 delegate_lease_manage=True, cleanup_after_finish=False,
                 args=(), kwargs={}):
        BaseDLockPeriodicJobExecutor.__init__(self, name, logger, lock_key, lock_lease_time, job_function,
                                              iteration_sleep_interval,
                                              initial_sleep=initial_sleep,
                                              lock_retry_sleep_interval=lock_retry_sleep_interval,
                                              delegate_lease_manage=delegate_lease_manage,
                                              cleanup_after_finish=cleanup_after_finish,
                                              args=args, kwargs=kwargs)

    @lock_acquire_check
    def _update_next_trigger_time(self):
        """
            in this variation, if current executor iteration time > iteration_sleep_interval then next_trigger_time
            is set for current time +JOB_EXECUTOR_NEXT_TRIGGER_SLEEP otherwise next_trigger_time is set to  current time+
            difference(iteration_sleep_interval,current executor iteration time) so that SLA is always meet
        """
        current_iteration_interval = self._iteration_end - self._iteration_start
        next_trigger_after_interval = self._iteration_sleep_interval - current_iteration_interval
        if next_trigger_after_interval < 0:
            next_trigger_after_interval = params.JOB_EXECUTOR_NEXT_TRIGGER_SLEEP
        self._set_next_trigger_time(next_trigger_after_interval=next_trigger_after_interval)
