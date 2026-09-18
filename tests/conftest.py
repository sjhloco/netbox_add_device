"""Shared fixtures for the netbox_add_device test suite.

Every test here runs against a real NetBox instance (no mocking), using the
same NBOX_URL/NBOX_TOKEN/NBOX_SSL convention as nbox_add_device.py and the
sibling netbox_env_setup project.
"""

import operator
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import pynetbox
import pytest
import yaml
from pynetbox.core.query import RequestError
from rich.console import Console
from rich.theme import Theme

from nbox_add_device import CreateDm
from netbox import NboxApi

TEST_DIR = Path(__file__).parent
TEST_INPUT = TEST_DIR / "test_files" / "test_inputs.yml"
TEST_INPUT_ERRORS = TEST_DIR / "test_files" / "test_inputs_errors.yml"

# Same env vars/defaults as nbox_add_device.py
NBOX_URL = os.environ.get("NBOX_URL", "http://netbox.netbox-docker.orb.local")
NBOX_TOKEN = os.environ.get("NBOX_TOKEN")
NBOX_SSL = os.environ.get("NBOX_SSL", False)

# Base objects provisioned once per session (see provision_base below) and
# shared by name across test modules.
TENANT1 = "UTEST_tenant1"
TENANT2 = "UTEST_tenant2"
SITE1 = "UTEST_site1"
CTYPE1 = "UTEST_ctype1"
CLUSTER1 = "UTEST_cluster1"
MFTR1 = "UTEST_mftr1"
DTYPE1 = "UTEST_dtype1"
DTYPE_PP = "UTEST_dtype_pp"
ROLE_VM = "UTEST_role_vm"
ROLE_SWITCH = "UTEST_role_switch"
ROLE_PP = "UTEST_role_pp"
PLATFORM1 = "UTEST_platform1"
LOCATION1_SLUG = "utest_location1"
RACK1 = "UTEST_rack1"
VRF1 = "UTEST_vrf1"
VLAN_GROUP1 = "UTEST_vlgrp1"
VLAN_IDS = (10, 20, 30)


def _ssl_verify() -> bool:
    return (
        NBOX_SSL
        if isinstance(NBOX_SSL, bool)
        else NBOX_SSL.strip().lower() in ("1", "true", "yes")
    )


@pytest.fixture(scope="session")
def my_vars() -> dict[str, Any]:
    """Happy-path test input, shared read-only across tests."""
    with open(TEST_INPUT) as file_content:
        return cast("dict[str, Any]", yaml.load(file_content, Loader=yaml.FullLoader))


@pytest.fixture(scope="session")
def rc() -> Console:
    my_theme = {"repr.ipv4": "none", "repr.number": "none", "repr.call": "none"}
    return Console(theme=Theme(my_theme), width=200)


@pytest.fixture(scope="session")
def nbox(rc: Console) -> NboxApi:
    assert NBOX_TOKEN is not None, "NBOX_TOKEN environment variable must be set"
    return NboxApi(NBOX_URL, NBOX_TOKEN, _ssl_verify(), rc)


@pytest.fixture
def create_dm(nbox: NboxApi, rc: Console) -> CreateDm:
    return CreateDm(nbox, rc, ["nbox_add_device.py", str(TEST_INPUT)])


@pytest.fixture
def create_dm_errors(nbox: NboxApi, rc: Console) -> CreateDm:
    return CreateDm(nbox, rc, ["nbox_add_device.py", str(TEST_INPUT_ERRORS)])


@pytest.fixture(scope="session")
def raw_nb() -> pynetbox.api:
    """A plain pynetbox client for provisioning/scratch objects in tests.

    Kept separate from the `nbox` (NboxApi) fixture so tests can set up
    supporting objects directly, the same way netbox_env_setup's tests do.
    """
    nb = pynetbox.api(url=NBOX_URL, token=NBOX_TOKEN)
    nb.http_session.verify = _ssl_verify()
    return nb


def cr_nbox_obj(
    nb: pynetbox.api,
    api_attr: str,
    fltr: dict[str, Any],
    obj_name: str,
    id_fltr: dict[str, Any] | None = None,
) -> None:
    """Get-or-create so re-running after a crashed prior session is safe."""
    endpoint = operator.attrgetter(api_attr)(nb)
    try:
        if endpoint.get(**(id_fltr or {"name": obj_name})) is None:
            endpoint.create(fltr)
    except Exception as e:  # noqa: BLE001 - provisioning must never fail the run
        print(f"XX error creating test '{api_attr}' object '{obj_name}' - {e}")


def del_nbox_obj(nb: pynetbox.api, api_attr: str, obj_fltr: str, obj_name: str | int) -> None:
    try:
        obj = operator.attrgetter(api_attr)(nb).get(**{obj_fltr: obj_name})
        if obj is not None:
            obj.delete()
    except (RequestError, ValueError) as e:
        print(f"XX error deleting test '{api_attr}' object '{obj_name}' - {e}")


@pytest.fixture(scope="session")
def provision_base(raw_nb: pynetbox.api, nbox: NboxApi) -> Iterator[None]:
    """Base objects shared by Phase 2/3 tests.

    Tenants, sites, a cluster, device-types, roles/platform, a location+rack,
    a VRF and VLANs — everything tests/test_files/test_inputs.yml refers to.
    """
    cr_nbox_obj(
        raw_nb, "tenancy.tenants", {"name": TENANT1, "slug": nbox.make_slug(TENANT1)}, TENANT1
    )
    cr_nbox_obj(
        raw_nb, "tenancy.tenants", {"name": TENANT2, "slug": nbox.make_slug(TENANT2)}, TENANT2
    )
    cr_nbox_obj(raw_nb, "dcim.sites", {"name": SITE1, "slug": nbox.make_slug(SITE1)}, SITE1)
    cr_nbox_obj(
        raw_nb,
        "dcim.device_roles",
        {"name": ROLE_VM, "slug": nbox.make_slug(ROLE_VM)},
        ROLE_VM,
    )
    cr_nbox_obj(
        raw_nb,
        "dcim.device_roles",
        {"name": ROLE_SWITCH, "slug": nbox.make_slug(ROLE_SWITCH)},
        ROLE_SWITCH,
    )
    cr_nbox_obj(
        raw_nb,
        "dcim.device_roles",
        {"name": ROLE_PP, "slug": nbox.make_slug(ROLE_PP)},
        ROLE_PP,
    )
    cr_nbox_obj(
        raw_nb,
        "dcim.platforms",
        {"name": PLATFORM1, "slug": nbox.make_slug(PLATFORM1)},
        PLATFORM1,
    )
    cr_nbox_obj(
        raw_nb,
        "dcim.locations",
        {"name": "UTEST Location One", "slug": LOCATION1_SLUG, "site": {"name": SITE1}},
        "UTEST Location One",
        id_fltr={"slug": LOCATION1_SLUG},
    )
    cr_nbox_obj(
        raw_nb,
        "dcim.racks",
        {"name": RACK1, "site": {"name": SITE1}, "location": {"slug": LOCATION1_SLUG}},
        RACK1,
    )
    cr_nbox_obj(raw_nb, "ipam.vrfs", {"name": VRF1, "rd": "UTEST:1"}, VRF1)
    cr_nbox_obj(
        raw_nb,
        "virtualization.cluster-types",
        {"name": CTYPE1, "slug": nbox.make_slug(CTYPE1)},
        CTYPE1,
    )
    cr_nbox_obj(
        raw_nb,
        "virtualization.clusters",
        {
            "name": CLUSTER1,
            "type": {"name": CTYPE1},
            # NetBox 4.x replaced Cluster.site with a generic scope relation —
            # "site": {...} is silently dropped on create, leaving the
            # cluster unscoped, which then fails clstr_dtype_info's
            # site_id-scoped lookup even though NetBox still accepts
            # site_id as a filter alias for scope.
            "scope_type": "dcim.site",
            "scope_id": raw_nb.dcim.sites.get(name=SITE1).id,
        },
        CLUSTER1,
    )
    cr_nbox_obj(
        raw_nb, "dcim.manufacturers", {"name": MFTR1, "slug": nbox.make_slug(MFTR1)}, MFTR1
    )
    cr_nbox_obj(
        raw_nb,
        "dcim.device-types",
        {
            "model": DTYPE1,
            "slug": nbox.make_slug(DTYPE1),
            "manufacturer": {"name": MFTR1},
        },
        DTYPE1,
        id_fltr={"model": DTYPE1},
    )
    cr_nbox_obj(
        raw_nb,
        "dcim.device-types",
        {
            "model": DTYPE_PP,
            "slug": nbox.make_slug(DTYPE_PP),
            "manufacturer": {"name": MFTR1},
        },
        DTYPE_PP,
        id_fltr={"model": DTYPE_PP},
    )
    cr_nbox_obj(
        raw_nb,
        "ipam.vlan-groups",
        {"name": VLAN_GROUP1, "slug": nbox.make_slug(VLAN_GROUP1)},
        VLAN_GROUP1,
    )
    for vid in VLAN_IDS:
        cr_nbox_obj(
            raw_nb,
            "ipam.vlans",
            {"name": f"UTEST_vlan{vid}", "vid": vid, "group": {"name": VLAN_GROUP1}},
            f"UTEST_vlan{vid}",
        )

    yield

    for vid in VLAN_IDS:
        del_nbox_obj(raw_nb, "ipam.vlans", "name", f"UTEST_vlan{vid}")
    del_nbox_obj(raw_nb, "ipam.vlan-groups", "slug", nbox.make_slug(VLAN_GROUP1))
    del_nbox_obj(raw_nb, "dcim.device-types", "slug", nbox.make_slug(DTYPE_PP))
    del_nbox_obj(raw_nb, "dcim.device-types", "slug", nbox.make_slug(DTYPE1))
    del_nbox_obj(raw_nb, "dcim.manufacturers", "slug", nbox.make_slug(MFTR1))
    del_nbox_obj(raw_nb, "virtualization.clusters", "name", CLUSTER1)
    del_nbox_obj(raw_nb, "virtualization.cluster-types", "slug", nbox.make_slug(CTYPE1))
    del_nbox_obj(raw_nb, "ipam.vrfs", "name", VRF1)
    del_nbox_obj(raw_nb, "dcim.racks", "name", RACK1)
    del_nbox_obj(raw_nb, "dcim.locations", "slug", LOCATION1_SLUG)
    del_nbox_obj(raw_nb, "dcim.platforms", "slug", nbox.make_slug(PLATFORM1))
    del_nbox_obj(raw_nb, "dcim.device_roles", "slug", nbox.make_slug(ROLE_PP))
    del_nbox_obj(raw_nb, "dcim.device_roles", "slug", nbox.make_slug(ROLE_SWITCH))
    del_nbox_obj(raw_nb, "dcim.device_roles", "slug", nbox.make_slug(ROLE_VM))
    del_nbox_obj(raw_nb, "dcim.sites", "slug", nbox.make_slug(SITE1))
    del_nbox_obj(raw_nb, "tenancy.tenants", "slug", nbox.make_slug(TENANT2))
    del_nbox_obj(raw_nb, "tenancy.tenants", "slug", nbox.make_slug(TENANT1))


# Small id lookups, reused across Phase 3 tests that build real create/update
# payloads by hand. Depending on provision_base means requesting one of these
# implicitly provisions the base objects too.
@pytest.fixture(scope="session")
def cluster1_id(raw_nb: pynetbox.api, provision_base: None) -> int:  # noqa: ARG001
    return int(raw_nb.virtualization.clusters.get(name=CLUSTER1).id)


@pytest.fixture(scope="session")
def site1_id(raw_nb: pynetbox.api, provision_base: None) -> int:  # noqa: ARG001
    return int(raw_nb.dcim.sites.get(name=SITE1).id)


@pytest.fixture(scope="session")
def dtype1_id(raw_nb: pynetbox.api, provision_base: None) -> int:  # noqa: ARG001
    return int(raw_nb.dcim.device_types.get(model=DTYPE1).id)


@pytest.fixture(scope="session")
def role_switch_id(raw_nb: pynetbox.api, provision_base: None) -> int:  # noqa: ARG001
    return int(raw_nb.dcim.device_roles.get(name=ROLE_SWITCH).id)


@pytest.fixture
def scratch_device(
    raw_nb: pynetbox.api, dtype1_id: int, site1_id: int, role_switch_id: int
) -> Iterator[pynetbox.core.response.Record]:
    device = raw_nb.dcim.devices.create(
        name="UTEST_scratch_device",
        device_type=dtype1_id,
        role=role_switch_id,
        site=site1_id,
    )
    yield device
    existing = raw_nb.dcim.devices.get(name="UTEST_scratch_device")
    if existing is not None:
        existing.delete()
