#
# ******************************************************************************
# Druva Confidential and Proprietary
#
#  Copyright (C) 2014, Druva Technologies Pte. Ltd.  ALL RIGHTS RESERVED.
#
#  Except as specifically permitted herein, no portion of the
#  information, including but not limited to object code and source
#  code, may be reproduced, modified, distributed, republished or
#  otherwise utilized in any form or by any means for any purpose
#  without the prior written permission of Druva Technologies Pte. Ltd.
#
#  Visit http://www.druva.com/ for more information.
# ******************************************************************************
from six import with_metaclass

#from DLockLib.db.lib.DLQueryBase import QBBase, QBMeta
from dblib.dl_query_base import QBBase, QBMeta
from dblib import dl as DLockDL
from DLockLib.db import dlockdb


class QBDLock(with_metaclass(QBMeta, QBBase)):
    soclass = dlockdb.DLock
    resultclass = DLockDL.DLDLock

    @classmethod
    def __classinit__(cls):
        QBBase.init_common(cls, cls.soclass)

DLockDL.QBDLock = QBDLock