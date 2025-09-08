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

import os
import sys
from DLockLib import dlock_globals as Globals

class DLockDBError(Exception):
    def __init__(
            self, errno, msg="", trace="", uname=None, response=None, log=True, errargs=()
    ):
        # errargs should be a tuple. It should not contain any encoded string in its elements.
        if not (isinstance(errno, int)):
            raise Exception("Not a valid SF Error. : %s" % errno)
        self.errno = errno
        self.errargs = errargs
        if msg:
            self.errmsg = msg
        elif errno > EMIN:
            self.errmsg = self.error_str()
        else:
            # should be a OSError/IOError
            self.errmsg = os.strerror(errno)
        self.uname = uname

        # compatibility with python exceptions
        self.args = (errno, msg)
        self.trace = trace

        # for returning response if required (edge server)
        self.response = response

        # If error is non-critical and need not be logged, pass False.
        self.log = log

    def error_str_status(self, isync=False):
        # This method should be used to generate error status in a format
        # that can be dumped in MD_STATS. The format of the returned error
        # will support localisation and will be babel compliant.

        errstr = ERROR_MAP.get(self.errno, ERR_NOT_FOUND)

        if errstr == ERR_NOT_FOUND:
            return _(errstr)

        try:
            status = []

            if len(self.errargs) > 0:  # Parametrized error string.
                errmsg = []
                errmsg.append(errstr)
                errmsg.extend(self.errargs)
                status.append(errmsg)
            else:
                status.append(errstr)

            status_placeholder = " ".join(["%s"] * len(status))
            status.insert(0, status_placeholder)
            return status
        except Exception as fault:
            SyncLog.error(
                "Problem in formatting error status. %s errstr is %s",
                str(fault),
                str(errstr),
            )
            return _(ERR_NOT_FOUND)

    def error_str(self):
        # This method is used to generate error string that will be logged
        # in the client logs.
        errstr = ERROR_MAP.get(self.errno, ERR_NOT_FOUND)
        if errstr == ERR_NOT_FOUND:
            return errstr
        try:
            errargs_new = self.errargs
            if len(self.errargs) > 0:
                errargs_new = convertUnicodeToString(
                    list(self.errargs), replacement=" "
                )
                errargs_new = tuple(errargs_new)
            errstr = errstr % errargs_new
            return errstr
        except Exception as fault:
            SyncLog.error(
                "Problem in formatting errlog string: %s.", str(fault))
            return ERR_NOT_FOUND

    def __unicode__(self):
        if self.trace:
            msg = "%s. Traceback - %s" % (self.errmsg, self.trace)
        else:
            msg = self.errmsg
        return "%s (#%x)" % (msg, self.errno)

    def __str__(self):
        try:
            return str(self.__unicode__())
        except:
            return self.__repr__()

    def __repr__(self):
        return repr(self.__unicode__())


def _(str):
    return str


# converts fault to a dict which can be passed via RPC


def convert_fault_to_dict(fault):
    fault_dict = {}
    fault_dict["type"] = get_fault_type(fault)
    fault_dict["errno"] = get_errno(fault, fault_dict["type"])
    fault_dict["repr"] = get_repr(fault)
    return fault_dict


def get_fault_type(fault):
    if isinstance(fault, SFDBError):
        fault_type = FAULT_TYPE_SYNCERROR
    elif sys.platform == 'win32' and isinstance(fault, WindowsError):
        fault_type = FAULT_TYPE_WINDOWS_ERROR
    elif isinstance(fault, OSError):
        fault_type = FAULT_TYPE_OSERROR
    else:
        fault_type = FAULT_TYPE_GENERICERROR
    return fault_type


def get_errno(fault, fault_type):
    if hasattr(fault, "errno"):
        fault_errno = fault.errno
    else:
        fault_errno = None
    return fault_errno


def get_repr(fault):
    try:
        fault_repr = repr(fault)
    except Exception as fault:
        fault_repr = ""
    return fault_repr


def convertUnicodeToString(inputlist=None, replacement=""):
    # Converts any unicode type object to string.
    newlist = []
    if len(inputlist) < 1:
        return newlist
    for elem in inputlist:
        try:
            elem = repr(elem)
        except Exception as fault:
            SyncLog.debug(
                "Could not convert element of type %s to string. Fault=%s",
                type(elem),
                str(fault),
            )
            elem = replacement
        finally:
            newlist.append(elem)
    return newlist


FAULT_TYPE_WINDOWS_ERROR = 1
FAULT_TYPE_SYNCERROR = 2
FAULT_TYPE_OSERROR = 3
FAULT_TYPE_GENERICERROR = 4

ERR_NOT_FOUND = "Internal Error!!"

EMIN = 0x100000000
EINTERNAL = 0x100000001
ELOCKKEYUNIQUEVIOLATION = 0x100000002
ELOCKNOTOWNED = 0x100000003
EDLOCKDBCONNECT = 0x100000004
ELOCKALREADYRELEASED = 0x100000005
EMINLOCKLEASEVIOLATION = 0x100000006
ELOCKNOTFOUND = 0x100000007
ELOCKINTERNAL = 0x100000008
ELOCKDBINVALIDCONNECTION = 0x100000009


ELOCKACQUIREFAILED = 0x210000000

ERROR_MAP = {}
ERROR_MAP[ELOCKINTERNAL] = _("Internal DLock DB error.")
ERROR_MAP[ELOCKKEYUNIQUEVIOLATION] = _("Lock for a lock key already Exists")
ERROR_MAP[ELOCKNOTOWNED] = _("lock does not exist or Lock no more owned by consumer.")
ERROR_MAP[EDLOCKDBCONNECT] = _("Could not connect to Dlock DB.")
ERROR_MAP[ELOCKALREADYRELEASED] = _("Lock is already released.")
ERROR_MAP[EMINLOCKLEASEVIOLATION] = _("lock lease time should be greater than expected minimum value")
ERROR_MAP[ELOCKNOTFOUND] = _("DB entry for Lock Key not found.")
ERROR_MAP[ELOCKDBINVALIDCONNECTION] = _("Invalid DLock db connection")
ERROR_MAP[ELOCKACQUIREFAILED] = _("lock acquire request failed")
