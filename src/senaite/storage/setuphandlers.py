# -*- coding: utf-8 -*-
#
# This file is part of SENAITE.STORAGE
#
# Copyright 2019 by it's authors.

from Products.DCWorkflow.Guard import Guard
from bika.lims import api
from bika.lims.permissions import AddAnalysis
from bika.lims.permissions import AddAttachment
from bika.lims.permissions import CancelAndReinstate
from bika.lims.permissions import EditAR
from bika.lims.permissions import EditFieldResults
from bika.lims.permissions import EditResults
from bika.lims.permissions import PreserveSample
from bika.lims.permissions import Publish
from bika.lims.permissions import ScheduleSampling
from senaite.storage import PRODUCT_NAME
from senaite.storage import PROFILE_ID
from senaite.storage import logger
import random

CREATE_TEST_DATA = True
CREATE_TEST_DATA_RANDOM = False

ACTIONS_TO_HIDE = [
    # Tuples of (id, folder_id)
    # If folder_id is None, assume folder_id is portal
    ("bika_storagelocations", "bika_setup")
]

NEW_CONTENT_TYPES = [
    # Tuples of (id, folder_id)
    # If folder_id is None, assume folder_id is portal
    ("senaite_storage", None),
]

CATALOGS_BY_TYPE = [
    # Tuples of (type, [catalog])
    ("StorageContainer", ["senaite_storage_catalog"]),
    ("StorageFacility", ["senaite_storage_catalog"]),
    ("StorageRootFolder", ["senaite_storage_catalog"]),
    ("StorageSamplesContainer", ["senaite_storage_catalog"]),
]

INDEXES = [
    # Tuples of (catalog, id, indexed attribute, type)
]

COLUMNS = [
    # Tuples of (catalog, column name)
]

WORKFLOWS_TO_UPDATE = {
    "bika_ar_workflow": {
        "permissions": (),
        "states": {
            "sample_received": {
                # Do not remove transitions already there
                "preserve_transitions": True,
                "transitions": ("store",),
            },
            "stored": {
                "title": "Stored",
                "description": "Sample is stored",
                "transitions": ("recover",),
                # Copy permissions from sample_received first
                "permissions_copy_from": "sample_received",
                # Override permissions
                "permissions": {
                    AddAnalysis: (),
                    AddAttachment: (),
                    CancelAndReinstate: (),
                    EditAR: (),
                    EditFieldResults: (),
                    EditResults: (),
                    PreserveSample: (),
                    Publish: (),
                    ScheduleSampling: (),
                }
            }
        },
        "transitions": {
            "store": {
                "title": "Store",
                "new_state": "stored",
                "action": "Store sample",
                "guard": {
                    "guard_permissions": "",
                    "guard_roles": "",
                    "guard_expr": "",
                }
            },
            "recover": {
                "title": "Recover",
                "new_state": "sample_received",
                "action": "Recover sample",
                "guard": {
                    "guard_permissions": "",
                    "guard_roles": "",
                    "guard_expr": "",
                }
            }
        }
    }
}


def post_install(portal_setup):
    """Runs after the last import step of the *default* profile
    This handler is registered as a *post_handler* in the generic setup profile
    :param portal_setup: SetupTool
    """
    logger.info("{} install handler [BEGIN]".format(PRODUCT_NAME.upper()))
    context = portal_setup._getImportContext(PROFILE_ID)
    portal = context.getSite()  # noqa

    # Setup catalogs
    #setup_catalogs(portal)

    # Reindex new content types
    reindex_new_content_types(portal)

    # Hide actions
    hide_actions(portal)

    # Migrate "classic" storage locations
    migrate_storage_locations(portal)

    # Injects "store" and "recover" transitions into senaite's workflow
    setup_workflows(portal)

    # Create test data
    create_test_data(portal)

    logger.info("{} install handler [DONE]".format(PRODUCT_NAME.upper()))


def setup_catalogs(portal):
    """Setup Plone catalogs
    """
    logger.info("Setup Catalogs ...")

    # Setup catalogs by type
    for type_name, catalogs in CATALOGS_BY_TYPE:
        at = api.get_tool("archetype_tool")
        # get the current registered catalogs
        current_catalogs = at.getCatalogsByType(type_name)
        # get the desired catalogs this type should be in
        desired_catalogs = map(api.get_tool, catalogs)
        # check if the catalogs changed for this portal_type
        if set(current_catalogs).difference(desired_catalogs):
            # fetch the brains to reindex
            brains = api.search({"portal_type": type_name})
            # updated the catalogs
            at.setCatalogsByType(type_name, catalogs)
            logger.info("Assign '%s' type to Catalogs %s" %
                        (type_name, catalogs))
            for brain in brains:
                obj = api.get_object(brain)
                logger.info("Reindexing '%s'" % repr(obj))
                obj.reindexObject()

    # Setup catalog indexes
    to_index = []
    for catalog, name, attribute, meta_type in INDEXES:
        c = api.get_tool(catalog)
        indexes = c.indexes()
        if name in indexes:
            logger.info("Index '%s' already in Catalog [SKIP]" % name)
            continue

        logger.info("Adding Index '%s' for field '%s' to catalog ..."
                    % (meta_type, name))
        c.addIndex(name, meta_type)
        to_index.append((c, name))
        logger.info("Added Index '%s' for field '%s' to catalog [DONE]"
                    % (meta_type, name))

    for catalog, name in to_index:
        logger.info("Indexing new index '%s' ..." % name)
        catalog.manage_reindexIndex(name)
        logger.info("Indexing new index '%s' [DONE]" % name)

    # Setup catalog metadata columns
    for catalog, name in COLUMNS:
        c = api.get_tool(catalog)
        if name not in c.schema():
            logger.info("Adding Column '%s' to catalog '%s' ..."
                        % (name, catalog))
            c.addColumn(name)
            logger.info("Added Column '%s' to catalog '%s' [DONE]"
                        % (name, catalog))
        else:
            logger.info("Column '%s' already in catalog '%s'  [SKIP]"
                        % (name, catalog))
            continue


def reindex_new_content_types(portal):
    """Setup new content types"""
    logger.info("*** Reindex new content types ***")

    def reindex_content_type(obj_id, folder):
        logger.info("Reindexing {}".format(obj_id))
        obj = folder[obj_id]
        obj.unmarkCreationFlag()
        obj.reindexObject()

    # Index objects - Importing through GenericSetup doesn't
    for obj_id, folder_id in NEW_CONTENT_TYPES:
        folder = folder_id and portal[folder_id] or portal
        reindex_content_type(obj_id, folder)


def hide_actions(portal):
    """Excludes actions from both navigation portlet and from control_panel
    """
    logger.info("Hiding actions ...")
    for action_id, folder_id in ACTIONS_TO_HIDE:
        if folder_id and folder_id not in portal:
            logger.info("{} not found in portal [SKIP]".format(folder_id))
            continue
        folder = folder_id and portal[folder_id] or portal
        hide_action(folder, action_id)


def hide_action(folder, action_id):
    logger.info("Hiding {} from {} ...".format(action_id, folder.id))
    if action_id not in folder:
        logger.info("{} not found in {} [SKIP]".format(action_id, folder.id))
        return

    item = folder[action_id]
    logger.info("Hide {} ({}) from nav bar".format(action_id, item.Title()))
    item.setExcludeFromNav(True)

    def get_action_index(action_id):
        for n, action in enumerate(cp.listActions()):
            if action.getId() == action_id:
                return n
        return -1

    logger.info("Hide {} from control_panel".format(action_id, item.Title()))
    cp = api.get_tool("portal_controlpanel")
    action_index = get_action_index(action_id)
    if (action_index == -1):
        logger.info("{}  not found in control_panel [SKIP]".format(cp.id))
        return

    actions = cp._cloneActions()
    del actions[action_index]
    cp._actions = tuple(actions)
    cp._p_changed = 1


def migrate_storage_locations(portal):
    """Migrates classic StorageLocation objects to StorageSamplesContainer
    """
    logger.info("Migrating classic Storage Locations ...")
    query = dict(portal_type="StorageLocation")
    brains = api.search(query, "portal_catalog")
    if not brains:
        logger.info("No Storage Locations found [SKIP]")
        return

    total = len(brains)
    for num, brain in enumerate(brains):
        if num % 100 == 0:
            logger.info("Migrating Storage Locations: {}/{}".format(num, total))
        object = api.get_object(brain)
        # TODO Migrate


def setup_workflows(portal):
    """Injects 'store' and 'recover' transitions into workflow
    """
    logger.info("Setup storage workflow ...")
    for wf_id, settings in WORKFLOWS_TO_UPDATE.items():
        update_workflow(portal, wf_id, settings)


def update_workflow(portal, workflow_id, settings):
    """Injects 'store' and 'recover' transitions into workflow
    """
    logger.info("Updating workflow '{}' ...".format(workflow_id))
    wf_tool = api.get_tool("portal_workflow")
    workflow = wf_tool.getWorkflowById(workflow_id)
    if not workflow:
        logger.warn("Workflow '{}' not found [SKIP]".format(workflow_id))
    states = settings.get("states", {})
    for state_id, values in states.items():
        update_workflow_state(portal, workflow, state_id, values)

    transitions = settings.get("transitions", {})
    for transition_id, values in transitions.items():
        update_workflow_transition(portal, workflow, transition_id, values)


def update_workflow_state(portal, workflow, status_id, settings):
    logger.info("Updating workflow '{}', status: '{}' ..."
                .format(workflow.id, status_id))

    # Create the status (if does not exist yet)
    new_status = workflow.states.get(status_id)
    if not new_status:
        workflow.states.addState(status_id)
        new_status = workflow.states.get(status_id)

    # Set basic info (title, description, etc.)
    new_status.title = settings.get("title", new_status.title)
    new_status.description = settings.get("description", new_status.description)

    # Set transitions
    trans = settings.get("transitions", ())
    if settings.get("preserve_transitions", False):
        trans = tuple(set(new_status.transitions+trans))
    new_status.transitions = trans

    # Set permissions
    update_workflow_state_permissions(portal, workflow, new_status, settings)


def update_workflow_state_permissions(portal, workflow, status, settings):
    # Copy permissions from another state?
    permissions_copy_from = settings.get("permissions_copy_from", None)
    if permissions_copy_from:
        logger.info("Copying permissions from '{}' to '{}' ..."
                    .format(permissions_copy_from, status.id))
        copy_from_state = workflow.states.get(permissions_copy_from)
        if not copy_from_state:
            logger.info("State '{}' not found [SKIP]".format(copy_from_state))
        else:
            source_permissions = copy_from_state.permission_roles
            for perm_id, roles in source_permissions.items():
                logger.info("Setting permission '{}': '{}'"
                            .format(perm_id, ', '.join(roles)))
                status.setPermission(perm_id, False, roles)

    # Override permissions
    logger.info("Overriding permissions for '{}' ...".format(status.id))
    state_permissions = settings.get('permissions', {})
    if not state_permissions:
        logger.info("No permissions set for '{}' [SKIP]".format(status.id))
        return
    for permission_id, roles in state_permissions.items():
        state_roles = roles and roles or ()
        logger.info("Setting permission '{}': '{}'"
                    .format(permission_id, ', '.join(state_roles)))
        status.setPermission(permission_id, False, state_roles)


def update_workflow_transition(portal, workflow, transition_id, settings):
    logger.info("Updating workflow '{}', transition: '{}'"
                .format(workflow.id, transition_id))
    if transition_id not in workflow.transitions:
        workflow.transitions.addTransition(transition_id)
    transition = workflow.transitions.get(transition_id)
    transition.setProperties(
        title=settings.get("title"),
        new_state_id=settings.get("new_state"),
        after_script_name=settings.get("after_script", ""),
        actbox_name=settings.get("action", "")
    )
    guard = transition.guard or Guard()
    guard_props = {"guard_permissions": "",
                   "guard_roles": "",
                   "guard_expr": ""}
    guard_props = settings.get("guard", guard_props)
    guard.changeFromProperties(guard_props)
    transition.guard = guard


def create_test_data(portal):
    """Populates with storage-like test data
    """
    if not CREATE_TEST_DATA:
        return
    logger.info("Creating test data ...")
    facilities = portal.senaite_storage
    if len(facilities.objectValues()) > 0:
        logger.info("There are facilities created already [SKIP]")
        return

    def get_random(min, max):
        if not CREATE_TEST_DATA_RANDOM:
            return min
        return int(round(random.uniform(min, max)))

    # Facilities
    for x in range(get_random(3,8)):
        facility = api.create(
            facilities,
            "StorageFacility",
            title="Storage facility {:02d}".format(x+1),
            Phone="123456789",
            EmailAddress="storage{:02d}@example.com".format(x+1),
            PhysicalAddress={
                "address": "Av. Via Augusta 15 - 25",
                "city": "Sant Cugat del Valles",
                "zip": "08174",
                "state": "",
                "country": "Spain",}
        )

        # Fridges
        for i in range(get_random(2,5)):
            container = api.create(facility, "StorageContainer",
                                   title="Fridge {:02d}".format(i+1),
                                   Rows=get_random(4,8),
                                   Columns=get_random(4,6))

            # Racks
            for j in range(get_random(4, container.get_capacity())):
                rack = api.create(container, "StorageContainer",
                                  title="Rack {:02d}".format(j+1),
                                  Rows=get_random(3,4),
                                  Columns=get_random(2,3))

                # Boxes
                for k in range(get_random(2, rack.get_capacity())):
                    box = api.create(rack, "StorageSamplesContainer",
                                     title="Sample box {:02d}".format(k+1),
                                     Rows=get_random(5,10),
                                     Columns=get_random(5,10))
