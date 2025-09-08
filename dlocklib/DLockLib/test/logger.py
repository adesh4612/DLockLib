from __future__ import print_function
#
# ******************************************************************************
# Druva Confidential and Proprietary
#
#  Copyright (C) 2017, Druva Technologies Pte. Ltd.  ALL RIGHTS RESERVED.
#
#  Except as specifically permitted herein, no portion of the
#  information, including but not limited to object code and source
#  code, may be reproduced, modified, distributed, republished or
#  otherwise utilized in any form or by any means for any purpose
#  without the prior written permission of Druva Technologies Pte. Ltd.
#
#  Visit http://www.druva.com/ for more information.
# ******************************************************************************
# SUPPORTS_PY2_PY3;

from builtins import object
import sys
import traceback


class Log(object):

    def __init__(self, log=None):
        self.prefix = '[DLockLib]'
        self.log = log

    def info(self, fmt, *args):
        if self.log:
            self.log.info(fmt, *args)
        else:
            print(self.prefix, '[INFO]', fmt % args)

    def debug(self, fmt, *args):
        if self.log:
            self.log.debug(fmt, *args)
        else:
            print(self.prefix, '[DEBUG]', fmt % args)

    def error(self, fmt, *args):
        if self.log:
            self.log.error(fmt, *args)
        else:
            print(self.prefix, '[ERROR]', fmt % args)

    def warn(self, fmt, *args):
        if self.log:
            self.log.warn(fmt, *args)
        else:
            print(self.prefix, '[WARN]', fmt % args)

    def traceback(self, fault):
        if self.log:
            self.log.traceback(fault)
        else:
            msg = 'Error %s:%s. Traceback -' % (str(fault.__class__), str(fault))
            msg += ''.join(traceback.format_exception(*sys.exc_info()))
            self.error('%s', msg)
