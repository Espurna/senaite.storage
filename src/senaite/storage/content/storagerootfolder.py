# -*- coding: utf-8 -*-
#
# This file is part of SENAITE.STORAGE.
#
# SENAITE.CORE.LISTING is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by the Free
# Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright 2019-2020 by it's authors.
# Some rights reserved, see README and LICENSE.

from Products.Archetypes.atapi import registerType
from bika.lims.content.bikaschema import BikaFolderSchema
from bika.lims.interfaces import IHaveNoBreadCrumbs
from plone.app.folder.folder import ATFolder
from senaite.storage import PRODUCT_NAME
from senaite.storage.interfaces import IStorageRootFolder
from zope.interface import implements

schema = BikaFolderSchema.copy()

class StorageRootFolder(ATFolder):
    """Storage module root object
    """
    implements(IStorageRootFolder, IHaveNoBreadCrumbs)
    displayContentsTab = False
    schema = schema

registerType(StorageRootFolder, PRODUCT_NAME)
