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


STATE_RELEASED = 'released'
STATE_LOCKED = 'locked'

MIN_LOCK_LEASE_TIME = 5 *60


# dlock_job_executor params
JOB_EXECUTOR_DEFAULT_INITIAL_SLEEP = 0
JOB_EXECUTOR_DEFAULT_LOCK_RETRY_SLEEP_INTERVAL = 30
JOB_EXECUTOR_MIN_LOCK_LEASE_TIME = 5 * 60
DLOCK_LEASE_MANAGER_MAX_RETRIES = 6
DLOCK_LEASE_MANAGER_SLEEP_AFTER_FAILED_RETRY = 30
JOB_EXECUTOR_NEXT_TRIGGER_SLEEP = 5* 60
DLOCK_ONETIME_JOB_EXECUTOR_LOG_PREFIX = "[DLockOneTimeJobExecutor]"
DLOCK_PERIODIC_JOB_EXECUTOR_LOG_PREFIX = "[DLockPeriodicJobExecutor]"
DLOCK_LEASE_MANAGER_LOG_PREFIX = "[DLockPeriodicJobExecutor]"

