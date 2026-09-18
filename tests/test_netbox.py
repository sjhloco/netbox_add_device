"""Tests for NboxApi.

Phase 1 covers the pure formatting/transform methods (make_slug,
format_rslt_err, format_stdout_intf_ip) — no live NetBox calls, but the
`nbox` fixture still constructs a real NboxApi instance to match this
suite's live-box-only convention.

Phase 2 covers CRUD/lookup methods and the stdout/rollback reporting
methods that need real created objects (crte_upte_err, crte_upte_stdout,
print_tag_rt) — these use the `provision_base` fixture (see conftest.py)
for shared base objects, plus scratch objects created/torn down per test.

Phase 3 covers the engine-level orchestration methods (chk_create_vc,
create_update_vm_dvc, crte_upte_intf, crte_upte_ip, crte_upte_port) and the
full engine() pipeline, built on top of a real VM/device created via
create_update_vm_dvc itself.
"""

from collections.abc import Iterator

import pynetbox
import pytest

from nbox_add_device import CreateDm
from netbox import NboxApi
from tests.conftest import CLUSTER1, DTYPE1, SITE1, TENANT1, VLAN_GROUP1, VRF1


# ----------------------------------------------------------------------------
# make_slug
# ----------------------------------------------------------------------------
class TestMakeSlug:
    def test_lowercases_and_replaces_spaces(self, nbox: NboxApi) -> None:
        assert nbox.make_slug("UTEST Site One") == "utest_site_one"

    def test_int_input(self, nbox: NboxApi) -> None:
        assert nbox.make_slug(30) == "30"

    def test_multiple_spaces(self, nbox: NboxApi) -> None:
        assert nbox.make_slug("a  b   c") == "a__b___c"


# ----------------------------------------------------------------------------
# format_rslt_err
# ----------------------------------------------------------------------------
class TestFormatRsltErr:
    def test_error_dict(self, nbox: NboxApi) -> None:
        result = nbox.format_rslt_err(
            [{"eth0": {"vrf": ["err"]}, "task_type": "create"}]
        )

        assert dict(result) == {
            "deploy_type": "create",
            "err": [{"eth0": {"vrf": ["err"]}}],
        }

    def test_result_changed_true(self, nbox: NboxApi) -> None:
        result = nbox.format_rslt_err([["create", "vm1", True]])

        assert dict(result) == {
            "deploy_type": "create",
            "details": ["vm1"],
            "changed": True,
        }

    def test_result_changed_false_ignored(self, nbox: NboxApi) -> None:
        result = nbox.format_rslt_err([["update", "vm1", False]])

        assert dict(result) == {}

    def test_mixed_error_and_result(self, nbox: NboxApi) -> None:
        result = nbox.format_rslt_err(
            [
                {"eth0": {"vrf": ["err"]}, "task_type": "create"},
                ["create", "vm1", True],
            ]
        )

        assert dict(result) == {
            "deploy_type": "create",
            "err": [{"eth0": {"vrf": ["err"]}}],
            "details": ["vm1"],
            "changed": True,
        }


# ----------------------------------------------------------------------------
# format_stdout_intf_ip
# ----------------------------------------------------------------------------
class TestFormatStdoutIntfIp:
    def test_single_detail(self, nbox: NboxApi) -> None:
        result = nbox.format_stdout_intf_ip("interfaces/ports", {"details": ["eth0"]})

        assert result["details"] == "[i]interfaces/ports: eth0[/i], "

    def test_multiple_details(self, nbox: NboxApi) -> None:
        result = nbox.format_stdout_intf_ip(
            "IP addresses", {"details": ["10.10.10.1/24", "10.10.10.2/24"]}
        )

        assert (
            result["details"] == "[i]IP addresses: 10.10.10.1/24, 10.10.10.2/24[/i], "
        )


# ----------------------------------------------------------------------------
# get_single_id
# ----------------------------------------------------------------------------
@pytest.mark.usefixtures("provision_base")
class TestGetSingleId:
    def test_success_by_name(self, nbox: NboxApi) -> None:
        err: list = []

        result = nbox.get_single_id(
            "tenancy.tenants", {"name": TENANT1}, {"name": TENANT1}, err
        )

        assert isinstance(result, int)
        assert err == []

    def test_device_type_returns_full_object(self, nbox: NboxApi) -> None:
        err: list = []

        result = nbox.get_single_id(
            "dcim.device-types", {"name": DTYPE1}, {"model": DTYPE1}, err
        )

        assert not isinstance(result, int)
        assert result is not None
        assert result.model == DTYPE1
        assert err == []

    def test_not_found(self, nbox: NboxApi) -> None:
        err: list = []

        result = nbox.get_single_id(
            "tenancy.tenants",
            {"name": "UTEST_nonexistent"},
            {"name": "UTEST_nonexistent"},
            err,
        )

        assert result is None
        assert err == [
            ("UTEST_nonexistent", {"Tenant": "UTEST_nonexistent"}, "no object found")
        ]

    def test_by_address_branch(self, nbox: NboxApi) -> None:
        err: list = []

        result = nbox.get_single_id(
            "tenancy.tenants",
            {"address": "UTEST_addr_1"},
            {"name": "UTEST_nonexistent2"},
            err,
        )

        assert result is None
        assert err[0][0] == "UTEST_addr_1"


# ----------------------------------------------------------------------------
# get_vlan_id
# ----------------------------------------------------------------------------
@pytest.mark.usefixtures("provision_base")
class TestGetVlanId:
    def test_single_int(self, nbox: NboxApi) -> None:
        err: list = []

        result = nbox.get_vlan_id({"name": "eth0", "grp_vl": [VLAN_GROUP1, 20]}, err)

        assert isinstance(result, int)
        assert err == []

    def test_list(self, nbox: NboxApi) -> None:
        err: list = []

        result = nbox.get_vlan_id(
            {"name": "eth1", "grp_vl": [VLAN_GROUP1, [20, 30]]}, err
        )

        assert isinstance(result, list)
        assert len(result) == 2
        assert err == []

    def test_group_notexist(self, nbox: NboxApi) -> None:
        err: list = []

        result = nbox.get_vlan_id(
            {"name": "eth0", "grp_vl": ["UTEST_nonexistent_grp", 20]}, err
        )

        assert result is None
        assert len(err) == 1
        name, err_obj, exc = err[0]
        assert name == "eth0"
        assert err_obj == {"Vlan_group": "UTEST_nonexistent_grp"}
        assert isinstance(exc, TypeError)

    def test_vlan_notexist(self, nbox: NboxApi) -> None:
        err: list = []

        result = nbox.get_vlan_id({"name": "eth0", "grp_vl": [VLAN_GROUP1, 9999]}, err)

        assert result is None
        assert len(err) == 1
        name, err_obj, exc = err[0]
        assert name == "eth0"
        assert err_obj == {"Vlan": 9999}
        assert isinstance(exc, AttributeError)


# ----------------------------------------------------------------------------
# chk_exist
# ----------------------------------------------------------------------------
@pytest.mark.usefixtures("provision_base")
class TestChkExist:
    def test_found(self, nbox: NboxApi) -> None:
        result = nbox.chk_exist("tenancy.tenants", {"name": TENANT1}, "parent")

        assert result is not None
        assert str(result) == TENANT1

    def test_not_found(self, nbox: NboxApi) -> None:
        result = nbox.chk_exist(
            "tenancy.tenants", {"name": "UTEST_nonexistent"}, "parent"
        )

        assert result is None

    def test_invalid_filter_exits(self, nbox: NboxApi, raw_nb: pynetbox.api) -> None:
        # An unrecognized filter kwarg is ignored by NetBox, so .get() matches
        # every tenant — pynetbox raises ValueError for >1 result, which
        # chk_exist's bare `except Exception` catches and turns into exit().
        t1 = raw_nb.tenancy.tenants.create(name="UTEST_dupA", slug="utest_dupa")
        t2 = raw_nb.tenancy.tenants.create(name="UTEST_dupB", slug="utest_dupb")
        try:
            with pytest.raises(SystemExit):
                nbox.chk_exist(
                    "tenancy.tenants", {"nonexistent_field_xyz": "x"}, "parent"
                )
        finally:
            t1.delete()
            t2.delete()


# ----------------------------------------------------------------------------
# get_or_create_tag
# ----------------------------------------------------------------------------
class TestGetOrCreateTag:
    def test_creates_new(self, nbox: NboxApi, raw_nb: pynetbox.api) -> None:
        tag_exists: list = []
        tag_created: list = []
        try:
            ids = nbox.get_or_create_tag(
                {"UTEST_tag_new": "9e9e9e"}, tag_exists, tag_created
            )

            assert len(ids) == 1
            assert tag_created == ["UTEST_tag_new"]
            assert tag_exists == []
        finally:
            tag = raw_nb.extras.tags.get(name="UTEST_tag_new")
            if tag is not None:
                tag.delete()

    def test_existing_reused(self, nbox: NboxApi, raw_nb: pynetbox.api) -> None:
        raw_nb.extras.tags.create(
            name="UTEST_tag_existing", slug="utest_tag_existing", color="9e9e9e"
        )
        try:
            tag_exists: list = []
            tag_created: list = []
            nbox.get_or_create_tag(
                {"UTEST_tag_existing": "9e9e9e"}, tag_exists, tag_created
            )

            assert tag_exists == ["UTEST_tag_existing"]
            assert tag_created == []
        finally:
            tag = raw_nb.extras.tags.get(name="UTEST_tag_existing")
            if tag is not None:
                tag.delete()

    def test_none_input(self, nbox: NboxApi) -> None:
        assert nbox.get_or_create_tag(None, [], []) == []


# ----------------------------------------------------------------------------
# obj_create
# ----------------------------------------------------------------------------
class TestObjCreate:
    def test_success(self, nbox: NboxApi, raw_nb: pynetbox.api) -> None:
        err: list = []
        try:
            result = nbox.obj_create(
                "UTEST_scratch_c1",
                "tenancy.tenants",
                {"name": "UTEST_scratch_c1", "slug": "utest_scratch_c1"},
                err,
            )

            assert result[0] == "create"
            assert result[2] is True
            assert str(result[1]) == "UTEST_scratch_c1"
            assert err == []
        finally:
            tenant = raw_nb.tenancy.tenants.get(name="UTEST_scratch_c1")
            if tenant is not None:
                tenant.delete()

    def test_error(self, nbox: NboxApi) -> None:
        err: list = []

        result = nbox.obj_create(
            "UTEST_scratch_bad",
            "tenancy.tenants",
            {"name": "UTEST_scratch_bad"},  # missing required slug
            err,
        )

        assert result == ["create", "UTEST_scratch_bad", False]
        assert err[0]["task_type"] == "create"
        assert "UTEST_scratch_bad" in err[0]


# ----------------------------------------------------------------------------
# obj_update
# ----------------------------------------------------------------------------
class TestObjUpdate:
    @pytest.fixture
    def scratch_tenant(
        self, raw_nb: pynetbox.api
    ) -> Iterator[pynetbox.core.response.Record]:
        tenant = raw_nb.tenancy.tenants.create(
            name="UTEST_scratch_u1", slug="utest_scratch_u1", description="orig"
        )
        yield tenant
        existing = raw_nb.tenancy.tenants.get(name="UTEST_scratch_u1")
        if existing is not None:
            existing.delete()

    def test_changed(
        self, nbox: NboxApi, scratch_tenant: pynetbox.core.response.Record
    ) -> None:
        err: list = []

        result = nbox.obj_update(
            "UTEST_scratch_u1", scratch_tenant, {"description": "changed"}, err
        )

        assert result is not None
        assert result[0] == "update"
        assert result[2] is True
        assert err == []

    def test_no_change(
        self, nbox: NboxApi, scratch_tenant: pynetbox.core.response.Record
    ) -> None:
        err: list = []

        result = nbox.obj_update(
            "UTEST_scratch_u1", scratch_tenant, {"description": "orig"}, err
        )

        assert result is not None
        assert result[2] is False

    @pytest.mark.usefixtures("provision_base")
    def test_error(
        self, nbox: NboxApi, scratch_tenant: pynetbox.core.response.Record
    ) -> None:
        err: list = []

        result = nbox.obj_update(
            "UTEST_scratch_u1", scratch_tenant, {"name": TENANT1}, err
        )

        assert result is None
        assert err[0]["task_type"] == "update"


# ----------------------------------------------------------------------------
# obj_delete
# ----------------------------------------------------------------------------
class TestObjDelete:
    def test_success(self, nbox: NboxApi, raw_nb: pynetbox.api) -> None:
        tenant = raw_nb.tenancy.tenants.create(
            name="UTEST_scratch_d1", slug="utest_scratch_d1"
        )

        nbox.obj_delete(tenant, "test_delete")

        assert raw_nb.tenancy.tenants.get(name="UTEST_scratch_d1") is None

    def test_error_prints_message(
        self, nbox: NboxApi, raw_nb: pynetbox.api, capsys: pytest.CaptureFixture[str]
    ) -> None:
        tenant = raw_nb.tenancy.tenants.create(
            name="UTEST_scratch_d2", slug="utest_scratch_d2"
        )
        tenant.delete()  # already gone

        nbox.obj_delete(tenant, "test_delete")

        out = capsys.readouterr().out
        assert "error deleting" in out


# ----------------------------------------------------------------------------
# remove_intf_ip
# ----------------------------------------------------------------------------
@pytest.mark.usefixtures("provision_base")
class TestRemoveIntfIp:
    @pytest.fixture
    def scratch_vm_intf(
        self, raw_nb: pynetbox.api
    ) -> Iterator[tuple[pynetbox.core.response.Record, pynetbox.core.response.Record]]:
        vm = raw_nb.virtualization.virtual_machines.create(
            name="UTEST_scratch_vm1", cluster={"name": CLUSTER1}
        )
        intf = raw_nb.virtualization.interfaces.create(
            name="eth0", virtual_machine={"id": vm.id}
        )
        yield vm, intf
        for ip in raw_nb.ipam.ip_addresses.filter(vminterface_id=intf.id):
            ip.delete()
        intf.delete()
        vm.delete()

    def test_deletes_changed_address(
        self,
        nbox: NboxApi,
        raw_nb: pynetbox.api,
        scratch_vm_intf: tuple[
            pynetbox.core.response.Record, pynetbox.core.response.Record
        ],
    ) -> None:
        _vm, intf = scratch_vm_intf
        old_ip = raw_nb.ipam.ip_addresses.create(
            address="10.250.0.1/32",
            assigned_object_type="virtualization.vminterface",
            assigned_object_id=intf.id,
        )

        nbox.remove_intf_ip(
            "Virtual_machine",
            {"assigned_object_id": intf.id, "address": "10.250.0.2/32"},
        )

        assert raw_nb.ipam.ip_addresses.get(id=old_ip.id) is None

    def test_noop_same_address(
        self,
        nbox: NboxApi,
        raw_nb: pynetbox.api,
        scratch_vm_intf: tuple[
            pynetbox.core.response.Record, pynetbox.core.response.Record
        ],
    ) -> None:
        _vm, intf = scratch_vm_intf
        existing_ip = raw_nb.ipam.ip_addresses.create(
            address="10.250.0.3/32",
            assigned_object_type="virtualization.vminterface",
            assigned_object_id=intf.id,
        )

        nbox.remove_intf_ip(
            "Virtual_machine",
            {"assigned_object_id": intf.id, "address": "10.250.0.3/32"},
        )

        assert raw_nb.ipam.ip_addresses.get(id=existing_ip.id) is not None

    def test_noop_when_no_existing_ip(
        self,
        nbox: NboxApi,
        scratch_vm_intf: tuple[
            pynetbox.core.response.Record, pynetbox.core.response.Record
        ],
    ) -> None:
        _vm, intf = scratch_vm_intf

        nbox.remove_intf_ip(
            "Virtual_machine",
            {"assigned_object_id": intf.id, "address": "10.250.0.9/32"},
        )


# ----------------------------------------------------------------------------
# crte_upte_err
# ----------------------------------------------------------------------------
@pytest.mark.usefixtures("provision_base")
class TestCrteUpteErr:
    def test_new_vm_rolls_back(
        self, nbox: NboxApi, raw_nb: pynetbox.api, capsys: pytest.CaptureFixture[str]
    ) -> None:
        vm = raw_nb.virtualization.virtual_machines.create(
            name="UTEST_scratch_err1", cluster={"name": CLUSTER1}
        )
        deploy_err = [{"eth0": {"vrf": ["error"]}, "task_type": "create"}]

        nbox.crte_upte_err(
            "Virtual_machine", None, ["create", vm, True], deploy_err, "intf"
        )

        assert raw_nb.virtualization.virtual_machines.get(id=vm.id) is None
        out = capsys.readouterr().out
        assert "failed with the following errors" in out

    def test_existing_vm_no_rollback(self, nbox: NboxApi, raw_nb: pynetbox.api) -> None:
        vm = raw_nb.virtualization.virtual_machines.create(
            name="UTEST_scratch_err2", cluster={"name": CLUSTER1}
        )
        try:
            deploy_err = [{"eth0": {"vrf": ["error"]}, "task_type": "update"}]

            nbox.crte_upte_err(
                "Virtual_machine", vm, ["update", vm, True], deploy_err, "intf"
            )

            assert raw_nb.virtualization.virtual_machines.get(id=vm.id) is not None
        finally:
            existing = raw_nb.virtualization.virtual_machines.get(id=vm.id)
            if existing is not None:
                existing.delete()

    def test_message_groups_by_own_name_vs_other(
        self, nbox: NboxApi, capsys: pytest.CaptureFixture[str]
    ) -> None:
        deploy_err = [
            {"UTEST_vm3": {"tenant": ["bad"]}, "task_type": "create"},
            {"eth0": {"vlan": ["bad"]}, "task_type": "create"},
        ]

        nbox.crte_upte_err(
            "Virtual_machine",
            "UTEST_vm3",
            ["create", "UTEST_vm3", True],
            deploy_err,
            "",
        )

        out = capsys.readouterr().out
        assert "tenant: bad" in out
        assert "eth0 vlan: bad" in out


# ----------------------------------------------------------------------------
# crte_upte_stdout
# ----------------------------------------------------------------------------
class TestCrteUpteStdout:
    def test_no_change(self, nbox: NboxApi, capsys: pytest.CaptureFixture[str]) -> None:
        vm_dvc_dm = {
            "name": "vm1",
            "cltr_dtype_name": "c1",
            "cluster": 1,
            "site": 2,
            "tenant": 3,
        }

        nbox.crte_upte_stdout("Virtual_machine", vm_dvc_dm, ["update", "vm1", False])

        out = capsys.readouterr().out
        assert "vm1' already exists with the correct details" in out
        assert vm_dvc_dm == {
            "name": "vm1",
            "cltr_dtype_name": "c1",
            "cluster": 1,
            "site": 2,
            "tenant": 3,
        }

    def test_vm_created_only(
        self, nbox: NboxApi, capsys: pytest.CaptureFixture[str]
    ) -> None:
        vm_dvc_dm = {
            "name": "vm1",
            "cltr_dtype_name": "c1",
            "cluster": 1,
            "site": 2,
            "tenant": 3,
        }

        nbox.crte_upte_stdout("Virtual_machine", vm_dvc_dm, ["create", "vm1", True])

        out = capsys.readouterr().out
        assert "vm1' created with attributes: tenant" in out

    def test_mutates_input_dict(self, nbox: NboxApi) -> None:
        vm_dvc_dm = {
            "name": "vm1",
            "cltr_dtype_name": "c1",
            "cluster": 1,
            "site": 2,
            "tenant": 3,
        }

        nbox.crte_upte_stdout("Virtual_machine", vm_dvc_dm, ["create", "vm1", True])

        assert vm_dvc_dm == {"tenant": 3}

    def test_with_interfaces(
        self, nbox: NboxApi, capsys: pytest.CaptureFixture[str]
    ) -> None:
        vm_dvc_dm = {"name": "vm1", "cltr_dtype_name": "c1", "cluster": 1, "site": 2}

        nbox.crte_upte_stdout(
            "Virtual_machine",
            vm_dvc_dm,
            ["update", "vm1", False],
            [["create", "eth0", True]],
        )

        out = capsys.readouterr().out
        assert "interfaces/ports: eth0" in out


# ----------------------------------------------------------------------------
# print_tag_rt
# ----------------------------------------------------------------------------
class TestPrintTagRt:
    def test_created(self, nbox: NboxApi, capsys: pytest.CaptureFixture[str]) -> None:
        nbox.print_tag_rt("Vm", [], ["UTEST_tag1"])

        out = capsys.readouterr().out
        assert "Vm tags 'UTEST_tag1' successfully created" in out

    def test_exists(self, nbox: NboxApi, capsys: pytest.CaptureFixture[str]) -> None:
        nbox.print_tag_rt("Vm", ["UTEST_tag1"], [])

        out = capsys.readouterr().out
        assert "Vm tags 'UTEST_tag1' already exist" in out

    def test_neither_prints_nothing(
        self, nbox: NboxApi, capsys: pytest.CaptureFixture[str]
    ) -> None:
        nbox.print_tag_rt("Vm", [], [])

        out = capsys.readouterr().out
        assert out == ""


# ----------------------------------------------------------------------------
# chk_create_vc
# ----------------------------------------------------------------------------
class TestChkCreateVc:
    def test_creates_new(self, nbox: NboxApi, raw_nb: pynetbox.api) -> None:
        dvc_dm = {
            "vm_dvc": {
                "name": "UTEST_scratch_vc_dvc1",
                "virtual_chassis": {"UTEST_vc_new": [2, 100]},
            }
        }
        deploy_err: list = []
        try:
            nbox.chk_create_vc(dvc_dm, deploy_err)

            assert isinstance(dvc_dm["vm_dvc"]["virtual_chassis"], int)
            assert dvc_dm["vm_dvc"]["vc_position"] == 2
            assert dvc_dm["vm_dvc"]["vc_priority"] == 100
            assert deploy_err == []
        finally:
            vc = raw_nb.dcim.virtual_chassis.get(name="UTEST_vc_new")
            if vc is not None:
                vc.delete()

    def test_reuses_existing(self, nbox: NboxApi, raw_nb: pynetbox.api) -> None:
        existing_vc = raw_nb.dcim.virtual_chassis.create(name="UTEST_vc_existing")
        try:
            dvc_dm = {
                "vm_dvc": {
                    "name": "UTEST_scratch_vc_dvc2",
                    "virtual_chassis": {"UTEST_vc_existing": [1, 50]},
                }
            }
            deploy_err: list = []

            nbox.chk_create_vc(dvc_dm, deploy_err)

            assert dvc_dm["vm_dvc"]["virtual_chassis"] == existing_vc.id
            assert deploy_err == []
        finally:
            existing_vc.delete()


# ----------------------------------------------------------------------------
# create_update_vm_dvc
# ----------------------------------------------------------------------------
@pytest.mark.usefixtures("provision_base")
class TestCreateUpdateVmDvc:
    def test_create_no_intf_port(
        self,
        nbox: NboxApi,
        raw_nb: pynetbox.api,
        cluster1_id: int,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        dm = {
            "vm_dvc": {
                "name": "UTEST_scratch_cuvd1",
                "cluster": cluster1_id,
                "site": None,
                "cltr_dtype_name": CLUSTER1,
            }
        }
        try:
            result = nbox.create_update_vm_dvc(
                "virtualization.virtual_machines", dm, None
            )

            assert result["obj_type"] == "Virtual_machine"
            assert result["deploy_err"] == []
            out = capsys.readouterr().out
            assert "created with attributes" in out
        finally:
            vm = raw_nb.virtualization.virtual_machines.get(name="UTEST_scratch_cuvd1")
            if vm is not None:
                vm.delete()

    def test_update_existing(
        self, nbox: NboxApi, raw_nb: pynetbox.api, cluster1_id: int
    ) -> None:
        existing_vm = raw_nb.virtualization.virtual_machines.create(
            name="UTEST_scratch_cuvd2", cluster=cluster1_id
        )
        try:
            dm = {
                "vm_dvc": {
                    "name": "UTEST_scratch_cuvd2",
                    "cluster": cluster1_id,
                    "site": None,
                    "cltr_dtype_name": CLUSTER1,
                    "comments": "updated",
                }
            }

            result = nbox.create_update_vm_dvc(
                "virtualization.virtual_machines", dm, existing_vm
            )

            assert result["deploy_err"] == []
            assert result["result"][2] is True
        finally:
            existing_vm.delete()

    def test_error_stdout(
        self, nbox: NboxApi, capsys: pytest.CaptureFixture[str]
    ) -> None:
        dm = {
            "vm_dvc": {"name": "UTEST_scratch_cuvd_bad", "cltr_dtype_name": "x"}
        }  # no cluster/site

        result = nbox.create_update_vm_dvc("virtualization.virtual_machines", dm, None)

        assert result["deploy_err"] != []
        out = capsys.readouterr().out
        assert "failed with the following errors" in out

    def test_with_intf_defers_stdout(
        self,
        nbox: NboxApi,
        raw_nb: pynetbox.api,
        cluster1_id: int,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        dm = {
            "vm_dvc": {
                "name": "UTEST_scratch_cuvd3",
                "cluster": cluster1_id,
                "cltr_dtype_name": CLUSTER1,
            },
            "intf": [{"name": "eth0"}],
        }
        try:
            result = nbox.create_update_vm_dvc(
                "virtualization.virtual_machines", dm, None
            )

            assert result["deploy_err"] == []
            assert capsys.readouterr().out == ""
        finally:
            vm = raw_nb.virtualization.virtual_machines.get(name="UTEST_scratch_cuvd3")
            if vm is not None:
                vm.delete()


# ----------------------------------------------------------------------------
# crte_upte_intf
# ----------------------------------------------------------------------------
@pytest.mark.usefixtures("provision_base")
class TestCrteUpteIntf:
    @pytest.fixture
    def scratch_vm(
        self, raw_nb: pynetbox.api, cluster1_id: int
    ) -> Iterator[pynetbox.core.response.Record]:
        vm = raw_nb.virtualization.virtual_machines.create(
            name="UTEST_scratch_intf_vm", cluster=cluster1_id
        )
        yield vm
        existing = raw_nb.virtualization.virtual_machines.get(
            name="UTEST_scratch_intf_vm"
        )
        if existing is not None:
            existing.delete()

    @staticmethod
    def _vm_dvc_result(vm: pynetbox.core.response.Record) -> dict:
        return {
            "obj_type": "Virtual_machine",
            "result": ["create", vm, True],
            "deploy_err": [],
        }

    @staticmethod
    def _vm_dvc_dm() -> dict:
        return {
            "name": "UTEST_scratch_intf_vm",
            "cltr_dtype_name": "x",
            "cluster": 1,
            "site": 1,
        }

    def test_create_new(
        self, nbox: NboxApi, scratch_vm: pynetbox.core.response.Record
    ) -> None:
        dm = {
            "vm_dvc": self._vm_dvc_dm(),
            "intf": [
                {"name": "eth0", "virtual_machine": {"name": "UTEST_scratch_intf_vm"}}
            ],
            "ip": [],
        }

        result = nbox.crte_upte_intf(
            "virtualization.interfaces", dm, None, self._vm_dvc_result(scratch_vm)
        )

        assert result["deploy_err"] == []
        assert len(result["result"]) == 1
        assert result["result"][0][0] == "create"

    def test_access_to_trunk_clears_untagged(
        self,
        nbox: NboxApi,
        raw_nb: pynetbox.api,
        scratch_vm: pynetbox.core.response.Record,
    ) -> None:
        raw_nb.virtualization.interfaces.create(
            name="eth0", virtual_machine=scratch_vm.id, mode="access"
        )
        dm = {
            "vm_dvc": self._vm_dvc_dm(),
            "intf": [
                {
                    "name": "eth0",
                    "mode": "tagged",
                    "virtual_machine": {"name": "UTEST_scratch_intf_vm"},
                }
            ],
            "ip": [],
        }

        result = nbox.crte_upte_intf(
            "virtualization.interfaces", dm, scratch_vm, self._vm_dvc_result(scratch_vm)
        )

        assert result["deploy_err"] == []
        updated = raw_nb.virtualization.interfaces.get(
            name="eth0", virtual_machine_id=scratch_vm.id
        )
        assert updated.mode.value == "tagged"
        assert updated.untagged_vlan is None

    def test_device_new_defaults_type_virtual(
        self,
        nbox: NboxApi,
        raw_nb: pynetbox.api,
        scratch_device: pynetbox.core.response.Record,
    ) -> None:
        dm = {
            "vm_dvc": {"name": "UTEST_scratch_device", "cltr_dtype_name": "x"},
            "intf": [{"name": "Gi0/9", "device": {"name": "UTEST_scratch_device"}}],
            "ip": [],
        }
        vm_dvc_result = {
            "obj_type": "Device",
            "result": ["create", scratch_device, True],
            "deploy_err": [],
        }

        result = nbox.crte_upte_intf("dcim.interfaces", dm, None, vm_dvc_result)

        assert result["deploy_err"] == []
        created = raw_nb.dcim.interfaces.get(name="Gi0/9", device_id=scratch_device.id)
        assert created.type.value == "virtual"

    def test_device_existing_type_carried_over(
        self,
        nbox: NboxApi,
        raw_nb: pynetbox.api,
        scratch_device: pynetbox.core.response.Record,
    ) -> None:
        raw_nb.dcim.interfaces.create(
            name="Gi0/8", device=scratch_device.id, type="1000base-t"
        )
        dm = {
            "vm_dvc": {"name": "UTEST_scratch_device", "cltr_dtype_name": "x"},
            "intf": [
                {
                    "name": "Gi0/8",
                    "description": "updated",
                    "device": {"name": "UTEST_scratch_device"},
                }
            ],
            "ip": [],
        }
        vm_dvc_result = {
            "obj_type": "Device",
            "result": ["update", scratch_device, True],
            "deploy_err": [],
        }

        result = nbox.crte_upte_intf(
            "dcim.interfaces", dm, scratch_device, vm_dvc_result
        )

        assert result["deploy_err"] == []
        updated = raw_nb.dcim.interfaces.get(name="Gi0/8", device_id=scratch_device.id)
        assert updated.type.value == "1000base-t"

    def test_lag_member(
        self,
        nbox: NboxApi,
        raw_nb: pynetbox.api,
        scratch_device: pynetbox.core.response.Record,
    ) -> None:
        raw_nb.dcim.interfaces.create(
            name="Port-channel1", device=scratch_device.id, type="lag"
        )
        dm = {
            "vm_dvc": {"name": "UTEST_scratch_device", "cltr_dtype_name": "x"},
            "intf": [
                {
                    "name": "Gi0/7",
                    "type": "1000base-t",
                    "lag": "Port-channel1",
                    "device": {"name": "UTEST_scratch_device"},
                }
            ],
            "ip": [],
        }
        vm_dvc_result = {
            "obj_type": "Device",
            "result": ["create", scratch_device, True],
            "deploy_err": [],
        }

        result = nbox.crte_upte_intf("dcim.interfaces", dm, None, vm_dvc_result)

        assert result["deploy_err"] == []
        member = raw_nb.dcim.interfaces.get(name="Gi0/7", device_id=scratch_device.id)
        assert member.lag is not None

    def test_error_rolls_back_new_vm(
        self,
        nbox: NboxApi,
        raw_nb: pynetbox.api,
        scratch_vm: pynetbox.core.response.Record,
    ) -> None:
        dm = {
            "vm_dvc": self._vm_dvc_dm(),
            "intf": [{"name": "eth0", "mode": "invalid_mode_xyz"}],
            "ip": [],
        }

        nbox.crte_upte_intf(
            "virtualization.interfaces", dm, None, self._vm_dvc_result(scratch_vm)
        )

        assert raw_nb.virtualization.virtual_machines.get(id=scratch_vm.id) is None


# ----------------------------------------------------------------------------
# crte_upte_ip
# ----------------------------------------------------------------------------
@pytest.mark.usefixtures("provision_base")
class TestCrteUpteIp:
    @pytest.fixture
    def scratch_vm_intf(
        self, raw_nb: pynetbox.api, cluster1_id: int
    ) -> Iterator[tuple[pynetbox.core.response.Record, pynetbox.core.response.Record]]:
        vm = raw_nb.virtualization.virtual_machines.create(
            name="UTEST_scratch_ip_vm", cluster=cluster1_id
        )
        intf = raw_nb.virtualization.interfaces.create(
            name="eth0", virtual_machine=vm.id
        )
        yield vm, intf
        # A rollback test may have already deleted the vm (cascading the
        # interface) — guard against operating on now-nonexistent ids.
        if raw_nb.virtualization.virtual_machines.get(id=vm.id) is None:
            return
        for ip in raw_nb.ipam.ip_addresses.filter(vminterface_id=intf.id):
            ip.delete()
        intf.delete()
        vm.delete()

    @staticmethod
    def _vm_dvc_result(vm: pynetbox.core.response.Record) -> dict:
        return {
            "obj_type": "Virtual_machine",
            "result": ["create", vm, True],
            "deploy_err": [],
        }

    @staticmethod
    def _vm_dvc_dm() -> dict:
        return {
            "name": "UTEST_scratch_ip_vm",
            "cltr_dtype_name": "x",
            "cluster": 1,
            "site": 1,
        }

    @staticmethod
    def _empty_intf_result() -> dict:
        return {"result": [], "deploy_err": []}

    def test_create_new_ip(
        self,
        nbox: NboxApi,
        raw_nb: pynetbox.api,
        scratch_vm_intf: tuple[
            pynetbox.core.response.Record, pynetbox.core.response.Record
        ],
    ) -> None:
        vm, intf = scratch_vm_intf
        dm = {
            "vm_dvc": self._vm_dvc_dm(),
            "ip": [
                {
                    "address": "10.251.0.1/32",
                    "vrf": None,
                    "vrf_name": "global",
                    "intf_name": {"name": "eth0"},
                    "primary_ip": False,
                }
            ],
        }

        nbox.crte_upte_ip(
            "virtualization.interfaces",
            dm,
            None,
            self._vm_dvc_result(vm),
            self._empty_intf_result(),
        )

        assert (
            raw_nb.ipam.ip_addresses.get(
                address="10.251.0.1/32", vminterface_id=intf.id
            )
            is not None
        )

    def test_reuses_existing_unassigned_ip(
        self,
        nbox: NboxApi,
        raw_nb: pynetbox.api,
        scratch_vm_intf: tuple[
            pynetbox.core.response.Record, pynetbox.core.response.Record
        ],
    ) -> None:
        vm, intf = scratch_vm_intf
        pre_existing_ip = raw_nb.ipam.ip_addresses.create(address="10.251.0.2/32")
        dm = {
            "vm_dvc": self._vm_dvc_dm(),
            "ip": [
                {
                    "address": "10.251.0.2/32",
                    "vrf": None,
                    "vrf_name": "global",
                    "intf_name": {"name": "eth0"},
                    "primary_ip": False,
                }
            ],
        }

        nbox.crte_upte_ip(
            "virtualization.interfaces",
            dm,
            None,
            self._vm_dvc_result(vm),
            self._empty_intf_result(),
        )

        updated_ip = raw_nb.ipam.ip_addresses.get(id=pre_existing_ip.id)
        assert updated_ip.assigned_object_id == intf.id

    def test_get_id_error_rolls_back(
        self,
        nbox: NboxApi,
        raw_nb: pynetbox.api,
        scratch_vm_intf: tuple[
            pynetbox.core.response.Record, pynetbox.core.response.Record
        ],
    ) -> None:
        vm, _intf = scratch_vm_intf
        dm = {
            "vm_dvc": self._vm_dvc_dm(),
            "ip": [
                {
                    "address": "10.251.0.3/32",
                    "vrf": None,
                    "vrf_name": "global",
                    "intf_name": {"name": "eth_nonexistent"},
                    "primary_ip": False,
                }
            ],
        }

        nbox.crte_upte_ip(
            "virtualization.interfaces",
            dm,
            None,
            self._vm_dvc_result(vm),
            self._empty_intf_result(),
        )

        assert raw_nb.virtualization.virtual_machines.get(id=vm.id) is None

    def test_primary_updates_vm(
        self,
        nbox: NboxApi,
        raw_nb: pynetbox.api,
        scratch_vm_intf: tuple[
            pynetbox.core.response.Record, pynetbox.core.response.Record
        ],
    ) -> None:
        vm, _intf = scratch_vm_intf
        dm = {
            "vm_dvc": self._vm_dvc_dm(),
            "ip": [
                {
                    "address": "10.251.0.4/32",
                    "vrf": None,
                    "vrf_name": "global",
                    "intf_name": {"name": "eth0"},
                    "primary_ip": True,
                }
            ],
        }

        nbox.crte_upte_ip(
            "virtualization.interfaces",
            dm,
            None,
            self._vm_dvc_result(vm),
            self._empty_intf_result(),
        )

        updated_vm = raw_nb.virtualization.virtual_machines.get(id=vm.id)
        assert updated_vm.primary_ip4 is not None

    def test_non_primary_no_vm_update(
        self,
        nbox: NboxApi,
        raw_nb: pynetbox.api,
        scratch_vm_intf: tuple[
            pynetbox.core.response.Record, pynetbox.core.response.Record
        ],
    ) -> None:
        vm, _intf = scratch_vm_intf
        dm = {
            "vm_dvc": self._vm_dvc_dm(),
            "ip": [
                {
                    "address": "10.251.0.5/32",
                    "vrf": None,
                    "vrf_name": "global",
                    "intf_name": {"name": "eth0"},
                    "primary_ip": False,
                }
            ],
        }

        nbox.crte_upte_ip(
            "virtualization.interfaces",
            dm,
            None,
            self._vm_dvc_result(vm),
            self._empty_intf_result(),
        )

        updated_vm = raw_nb.virtualization.virtual_machines.get(id=vm.id)
        assert updated_vm.primary_ip4 is None


# ----------------------------------------------------------------------------
# crte_upte_port
# ----------------------------------------------------------------------------
@pytest.mark.usefixtures("provision_base")
class TestCrteUptePort:
    @staticmethod
    def _vm_dvc_result(device: pynetbox.core.response.Record) -> dict:
        return {
            "obj_type": "Device",
            "result": ["create", device, True],
            "deploy_err": [],
        }

    @staticmethod
    def _vm_dvc_dm() -> dict:
        return {"name": "UTEST_scratch_device", "cltr_dtype_name": "x"}

    @pytest.fixture
    def existing_port_pair(
        self, raw_nb: pynetbox.api, scratch_device: pynetbox.core.response.Record
    ) -> tuple[pynetbox.core.response.Record, pynetbox.core.response.Record]:
        rport = raw_nb.dcim.rear_ports.create(
            device=scratch_device.id, name="5", type="110-punch"
        )
        fport = raw_nb.dcim.front_ports.create(
            device=scratch_device.id,
            name="5",
            type="110-punch",
            rear_ports=[{"rear_port": rport.id, "position": 1}],
            label="",
            description="",
        )
        return fport, rport

    def test_create_default_rear(
        self,
        nbox: NboxApi,
        raw_nb: pynetbox.api,
        scratch_device: pynetbox.core.response.Record,
    ) -> None:
        dm = {
            "vm_dvc": self._vm_dvc_dm(),
            "port": [
                {
                    "device": {"name": "UTEST_scratch_device"},
                    "name": "1",
                    "rear_port": "1",
                    "type": "110-punch",
                    "description": "",
                    "label": "",
                }
            ],
        }

        result = nbox.crte_upte_port(dm, None, self._vm_dvc_result(scratch_device))

        assert result["deploy_err"] == []
        assert (
            raw_nb.dcim.front_ports.get(name="1", device_id=scratch_device.id)
            is not None
        )
        assert (
            raw_nb.dcim.rear_ports.get(name="1", device_id=scratch_device.id)
            is not None
        )

    def test_create_explicit_rear(
        self,
        nbox: NboxApi,
        raw_nb: pynetbox.api,
        scratch_device: pynetbox.core.response.Record,
    ) -> None:
        dm = {
            "vm_dvc": self._vm_dvc_dm(),
            "port": [
                {
                    "device": {"name": "UTEST_scratch_device"},
                    "name": "27",
                    "rear_port": "47",
                    "type": "4p2c",
                    "description": "",
                    "label": "",
                }
            ],
        }

        result = nbox.crte_upte_port(dm, None, self._vm_dvc_result(scratch_device))

        assert result["deploy_err"] == []
        assert (
            raw_nb.dcim.rear_ports.get(name="47", device_id=scratch_device.id)
            is not None
        )

    def test_update_type_change(
        self,
        nbox: NboxApi,
        raw_nb: pynetbox.api,
        scratch_device: pynetbox.core.response.Record,
        existing_port_pair: tuple[
            pynetbox.core.response.Record, pynetbox.core.response.Record
        ],
    ) -> None:
        fport, _rport = existing_port_pair
        dm = {
            "vm_dvc": self._vm_dvc_dm(),
            "port": [
                {
                    "device": {"name": "UTEST_scratch_device"},
                    "name": "5",
                    "rear_port": "5",
                    "type": "8p8c",
                    "description": "",
                    "label": "",
                }
            ],
        }

        result = nbox.crte_upte_port(
            dm, scratch_device, self._vm_dvc_result(scratch_device)
        )

        assert result["deploy_err"] == []
        updated = raw_nb.dcim.front_ports.get(id=fport.id)
        assert updated.type.value == "8p8c"

    def test_update_rear_port_change_deletes_old(
        self,
        nbox: NboxApi,
        raw_nb: pynetbox.api,
        scratch_device: pynetbox.core.response.Record,
        existing_port_pair: tuple[
            pynetbox.core.response.Record, pynetbox.core.response.Record
        ],
    ) -> None:
        _fport, rport = existing_port_pair
        dm = {
            "vm_dvc": self._vm_dvc_dm(),
            "port": [
                {
                    "device": {"name": "UTEST_scratch_device"},
                    "name": "5",
                    "rear_port": "55",
                    "type": "110-punch",
                    "description": "",
                    "label": "",
                }
            ],
        }

        result = nbox.crte_upte_port(
            dm, scratch_device, self._vm_dvc_result(scratch_device)
        )

        assert result["deploy_err"] == []
        assert raw_nb.dcim.rear_ports.get(id=rport.id) is None
        assert (
            raw_nb.dcim.rear_ports.get(name="55", device_id=scratch_device.id)
            is not None
        )

    def test_update_label_description_only(
        self,
        nbox: NboxApi,
        raw_nb: pynetbox.api,
        scratch_device: pynetbox.core.response.Record,
        existing_port_pair: tuple[
            pynetbox.core.response.Record, pynetbox.core.response.Record
        ],
    ) -> None:
        fport, _rport = existing_port_pair
        dm = {
            "vm_dvc": self._vm_dvc_dm(),
            "port": [
                {
                    "device": {"name": "UTEST_scratch_device"},
                    "name": "5",
                    "rear_port": "5",
                    "type": "110-punch",
                    "description": "changed desc",
                    "label": "L1",
                }
            ],
        }

        result = nbox.crte_upte_port(
            dm, scratch_device, self._vm_dvc_result(scratch_device)
        )

        assert result["deploy_err"] == []
        updated = raw_nb.dcim.front_ports.get(id=fport.id)
        assert updated.description == "changed desc"
        assert updated.label == "L1"

    @pytest.mark.usefixtures("existing_port_pair")
    def test_update_no_change(
        self, nbox: NboxApi, scratch_device: pynetbox.core.response.Record
    ) -> None:
        dm = {
            "vm_dvc": self._vm_dvc_dm(),
            "port": [
                {
                    "device": {"name": "UTEST_scratch_device"},
                    "name": "5",
                    "rear_port": "5",
                    "type": "110-punch",
                    "description": "",
                    "label": "",
                }
            ],
        }

        result = nbox.crte_upte_port(
            dm, scratch_device, self._vm_dvc_result(scratch_device)
        )

        assert result["deploy_err"] == []
        assert result["result"] == []

    def test_error_reported(
        self, nbox: NboxApi, scratch_device: pynetbox.core.response.Record
    ) -> None:
        dm = {
            "vm_dvc": self._vm_dvc_dm(),
            "port": [
                {
                    "device": {"name": "UTEST_scratch_device"},
                    "name": "9",
                    "rear_port": "9",
                    "type": "invalid_type_xyz",
                    "description": "",
                    "label": "",
                }
            ],
        }

        result = nbox.crte_upte_port(dm, None, self._vm_dvc_result(scratch_device))

        assert result["deploy_err"] != []


# ----------------------------------------------------------------------------
# engine (full pipeline: CreateDm.engine() -> NboxApi.engine())
# ----------------------------------------------------------------------------
@pytest.mark.usefixtures("provision_base")
class TestNboxEngine:
    def test_vm_create_then_update_idempotent(
        self,
        create_dm: CreateDm,
        nbox: NboxApi,
        raw_nb: pynetbox.api,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        try:
            vm_dm = create_dm.engine("cluster", "vm", "Virtual machine")
            nbox.engine("vm", "virtualization.virtual_machines", vm_dm)
            out1 = capsys.readouterr().out
            assert "UTEST_vm1" in out1
            assert "UTEST_vm2" in out1

            vm_dm2 = create_dm.engine("cluster", "vm", "Virtual machine")
            nbox.engine("vm", "virtualization.virtual_machines", vm_dm2)
            out2 = capsys.readouterr().out
            assert "already exists with the correct details" in out2

            assert (
                raw_nb.virtualization.virtual_machines.get(name="UTEST_vm1") is not None
            )
            assert (
                raw_nb.virtualization.virtual_machines.get(name="UTEST_vm2") is not None
            )
        finally:
            for addr in ("10.10.10.1/24", "10.10.10.2/24"):
                ip = raw_nb.ipam.ip_addresses.get(address=addr)
                if ip is not None:
                    ip.delete()
            for name in ("UTEST_vm1", "UTEST_vm2"):
                vm = raw_nb.virtualization.virtual_machines.get(name=name)
                if vm is not None:
                    vm.delete()
            tag = raw_nb.extras.tags.get(name="UTEST_tag_fw")
            if tag is not None:
                tag.delete()

    def test_device_with_vc_and_ports(
        self,
        create_dm: CreateDm,
        nbox: NboxApi,
        raw_nb: pynetbox.api,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        try:
            dvc_dm = create_dm.engine("device_type", "device", "Device")
            nbox.engine("device", "dcim.devices", dvc_dm)
            out = capsys.readouterr().out
            assert "UTEST_dvc1" in out
            assert "UTEST_pp1" in out

            assert raw_nb.dcim.devices.get(name="UTEST_dvc1") is not None
            assert raw_nb.dcim.devices.get(name="UTEST_dvc2") is not None
            assert raw_nb.dcim.devices.get(name="UTEST_pp1") is not None
            assert raw_nb.dcim.virtual_chassis.get(name="UTEST_vc1") is not None
        finally:
            for addr in ("10.10.50.1/24", "10.10.20.11/24"):
                ip = raw_nb.ipam.ip_addresses.get(address=addr)
                if ip is not None:
                    ip.delete()
            for name in ("UTEST_dvc1", "UTEST_dvc2", "UTEST_pp1"):
                dvc = raw_nb.dcim.devices.get(name=name)
                if dvc is not None:
                    dvc.delete()
            vc = raw_nb.dcim.virtual_chassis.get(name="UTEST_vc1")
            if vc is not None:
                vc.delete()
