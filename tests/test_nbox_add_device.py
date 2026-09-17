"""Tests for CreateDm.

Phase 1 covers the pure dict-building and error-reporting methods (they
operate on plain dicts, with any NetBox object IDs already resolved by the
caller). Phase 3 adds clstr_dtype_info/vm_device_info (which resolve real
object IDs via self.nbox) and the full engine() pipeline, using the
provision_base fixture and tests/test_files/test_inputs*.yml.
"""

import pytest

from nbox_add_device import CreateDm
from tests.conftest import (
    CLUSTER1,
    DTYPE1,
    LOCATION1_SLUG,
    PLATFORM1,
    RACK1,
    ROLE_SWITCH,
    ROLE_VM,
    SITE1,
    TENANT1,
    TENANT2,
)


# ----------------------------------------------------------------------------
# create_vm_dvc
# ----------------------------------------------------------------------------
class TestCreateVmDvc:
    def test_vm(self, create_dm: CreateDm) -> None:
        cltr_dtype = {"name": "UTEST_cluster1", "site": 1, "cltr": 2}
        vm_dvc = {"name": "UTEST_vm1", "tenant": 3, "platform": 4, "device_role": 5}
        vm_dvc_orig = {
            "name": "UTEST_vm1",
            "cpu": 4,
            "mem": 2,
            "disk": 32,
            "comments": "test",
        }

        dm = create_dm.create_vm_dvc("vm", cltr_dtype, vm_dvc, vm_dvc_orig)

        assert dm == {
            "cltr_dtype_name": "UTEST_cluster1",
            "name": "UTEST_vm1",
            "tenant": 3,
            "platform": 4,
            "status": "active",
            "comments": "test",
            "tags": None,
            "role": 5,
            "cluster": 2,
            "site": 1,
            "vcpus": 4,
            "memory": 2,
            "disk": 32,
        }

    def test_vm_status_override(self, create_dm: CreateDm) -> None:
        cltr_dtype = {"name": "c", "site": 1, "cltr": 2}
        vm_dvc = {"name": "vm1"}
        vm_dvc_orig = {"name": "vm1", "status": "decommissioning"}

        dm = create_dm.create_vm_dvc("vm", cltr_dtype, vm_dvc, vm_dvc_orig)

        assert dm["status"] == "decommissioning"

    def test_device_no_rack(self, create_dm: CreateDm) -> None:
        cltr_dtype = {"name": "d", "dtype": 10, "mftr": 11}
        vm_dvc = {"name": "dvc1", "site": 1}
        vm_dvc_orig = {"name": "dvc1"}

        dm = create_dm.create_vm_dvc("device", cltr_dtype, vm_dvc, vm_dvc_orig)

        assert "rack" not in dm
        assert "position" not in dm
        assert "face" not in dm
        assert dm["device_type"] == 10
        assert dm["manufacturer"] == 11
        assert dm["site"] == 1

    def test_device_with_rack_defaults(self, create_dm: CreateDm) -> None:
        cltr_dtype = {"name": "d", "dtype": 10, "mftr": 11}
        vm_dvc = {"name": "dvc1", "site": 1, "rack": 20}
        vm_dvc_orig = {"name": "dvc1"}

        dm = create_dm.create_vm_dvc("device", cltr_dtype, vm_dvc, vm_dvc_orig)

        assert dm["rack"] == 20
        assert dm["position"] is None
        assert dm["face"] == "front"

    def test_device_face_and_position_override(self, create_dm: CreateDm) -> None:
        cltr_dtype = {"name": "d", "dtype": 10, "mftr": 11}
        vm_dvc = {"name": "dvc1", "site": 1, "rack": 20}
        vm_dvc_orig = {"name": "dvc1", "position": 3, "face": "rear"}

        dm = create_dm.create_vm_dvc("device", cltr_dtype, vm_dvc, vm_dvc_orig)

        assert dm["position"] == 3
        assert dm["face"] == "rear"


# ----------------------------------------------------------------------------
# create_intf_dm
# ----------------------------------------------------------------------------
class TestCreateIntfDm:
    def test_vm_basic(self, create_dm: CreateDm) -> None:
        result = create_dm.create_intf_dm("vm", {}, {"name": "vm1"}, {"name": "eth0"})

        assert result == {
            "intf": {
                "virtual_machine": {"name": "vm1"},
                "name": "eth0",
                "description": "",
            },
            "ip": {},
        }

    def test_device_basic(self, create_dm: CreateDm) -> None:
        result = create_dm.create_intf_dm(
            "device", {}, {"name": "dvc1"}, {"name": "Gi0/1"}
        )

        intf = result["intf"]
        assert "virtual_machine" not in intf
        assert intf["device"] == {"name": "dvc1"}
        assert intf["type"] is None
        assert intf["lag"] is None

    def test_access_port(self, create_dm: CreateDm) -> None:
        result = create_dm.create_intf_dm(
            "vm", {"vlan": 20}, {"name": "vm1"}, {"name": "eth2"}
        )

        assert result["intf"]["mode"] == "access"
        assert result["intf"]["untagged_vlan"] == 20

    def test_trunk_port(self, create_dm: CreateDm) -> None:
        result = create_dm.create_intf_dm(
            "vm", {"vlan": [20, 30]}, {"name": "vm1"}, {"name": "eth1"}
        )

        assert result["intf"]["mode"] == "tagged"
        assert result["intf"]["tagged_vlans"] == [20, 30]

    def test_ip_full(self, create_dm: CreateDm) -> None:
        result = create_dm.create_intf_dm(
            "vm",
            {"vrf": 99},
            {"name": "vm1", "tenant": 5},
            {"name": "eth0", "vrf_ip": ["UTEST_vrf1", "10.10.10.1/24"]},
        )

        assert result["ip"] == {
            "address": "10.10.10.1/24",
            "tenant": 5,
            "vrf_name": "UTEST_vrf1",
            "vrf": 99,
            "intf_name": {"name": "eth0"},
            "dns_name": "",
            "primary_ip": False,
            "role": None,
        }

    def test_ip_dns_primary_role(self, create_dm: CreateDm) -> None:
        result = create_dm.create_intf_dm(
            "vm",
            {"vrf": 99},
            {"name": "vm1"},
            {
                "name": "eth0",
                "vrf_ip": ["UTEST_vrf1", "10.10.10.1/24"],
                "dns": "host.example.com",
                "primary_ip": True,
                "role": "loopback",
            },
        )

        assert result["ip"]["dns_name"] == "host.example.com"
        assert result["ip"]["primary_ip"] is True
        assert result["ip"]["role"] == "loopback"

    def test_no_vrf_ip_returns_empty_ip(self, create_dm: CreateDm) -> None:
        result = create_dm.create_intf_dm("vm", {}, {"name": "vm1"}, {"name": "eth0"})

        assert result["ip"] == {}


# ----------------------------------------------------------------------------
# create_port_dm
# ----------------------------------------------------------------------------
class TestCreatePortDm:
    def test_defaults(self, create_dm: CreateDm) -> None:
        port = create_dm.create_port_dm("UTEST_pp1", {"name": "1"})

        assert port == {
            "device": {"name": "UTEST_pp1"},
            "name": "1",
            "rear_port": "1",
            "type": "110-punch",
            "description": "",
            "label": "",
        }

    def test_overrides(self, create_dm: CreateDm) -> None:
        port = create_dm.create_port_dm(
            "UTEST_pp1",
            {
                "name": "27",
                "rear_port": "47",
                "type": "4p2c",
                "descr": "test port",
                "label": "01",
            },
        )

        assert port["rear_port"] == "47"
        assert port["type"] == "4p2c"
        assert port["description"] == "test port"
        assert port["label"] == "01"


# ----------------------------------------------------------------------------
# rmv_empty_attr
# ----------------------------------------------------------------------------
class TestRmvEmptyAttr:
    def test_removes_none_values(self, create_dm: CreateDm) -> None:
        result = create_dm.rmv_empty_attr({"a": None, "b": "x"})

        assert result == {"b": "x"}

    def test_keeps_tenant_and_rack_when_none(self, create_dm: CreateDm) -> None:
        result = create_dm.rmv_empty_attr({"tenant": None, "rack": None, "b": "x"})

        assert result == {"tenant": None, "rack": None, "b": "x"}

    def test_removes_dict_with_none_first_value(self, create_dm: CreateDm) -> None:
        result = create_dm.rmv_empty_attr({"lag": {"name": None}, "b": "x"})

        assert result == {"b": "x"}

    def test_removes_empty_string_and_list(self, create_dm: CreateDm) -> None:
        result = create_dm.rmv_empty_attr({"comments": "", "tags": [], "b": "x"})

        assert result == {"b": "x"}

    def test_keeps_int_zero(self, create_dm: CreateDm) -> None:
        result = create_dm.rmv_empty_attr({"cpu": 0})

        assert result == {"cpu": 0}

    def test_mutates_and_returns_same_object(self, create_dm: CreateDm) -> None:
        attr_dict = {"a": None, "b": "x"}

        result = create_dm.rmv_empty_attr(attr_dict)

        assert result is attr_dict
        assert attr_dict == {"b": "x"}


# ----------------------------------------------------------------------------
# set_primary_ip
# ----------------------------------------------------------------------------
class TestSetPrimaryIp:
    def test_empty_list(self, create_dm: CreateDm) -> None:
        assert create_dm.set_primary_ip([]) == []

    def test_single_ip_forced_primary(self, create_dm: CreateDm) -> None:
        ip = [{"primary_ip": False}]

        result = create_dm.set_primary_ip(ip)

        assert result[0]["primary_ip"] is True

    def test_multiple_none_marked_forces_first(self, create_dm: CreateDm) -> None:
        ip = [{"primary_ip": False}, {"primary_ip": False}]

        result = create_dm.set_primary_ip(ip)

        assert result[0]["primary_ip"] is True
        assert result[1]["primary_ip"] is False

    def test_existing_primary_on_other_preserved(self, create_dm: CreateDm) -> None:
        ip = [{"primary_ip": False}, {"primary_ip": True}]

        result = create_dm.set_primary_ip(ip)

        assert result[0]["primary_ip"] is False
        assert result[1]["primary_ip"] is True

    def test_first_already_true_others_false(self, create_dm: CreateDm) -> None:
        ip = [{"primary_ip": True}, {"primary_ip": False}]

        result = create_dm.set_primary_ip(ip)

        assert result[0]["primary_ip"] is True
        assert result[1]["primary_ip"] is False


# ----------------------------------------------------------------------------
# mand_err_msg
# ----------------------------------------------------------------------------
class TestMandErrMsg:
    def test_cluster_dict_missing(
        self, create_dm: CreateDm, capsys: pytest.CaptureFixture[str]
    ) -> None:
        create_dm.mand_err_msg("cluster", [("unknown", "cluster", None)])

        out = capsys.readouterr().out
        assert (
            "mandatory top level 'cluster' dictionary is needed if you are trying "
            "to create VMs" in out
        )

    def test_device_type_dict_missing(
        self, create_dm: CreateDm, capsys: pytest.CaptureFixture[str]
    ) -> None:
        create_dm.mand_err_msg("cluster", [("unknown", "device_type", None)])

        out = capsys.readouterr().out
        assert (
            "mandatory top level 'device_type' dictionary is needed if you are "
            "trying to create Devices" in out
        )

    def test_all_unknown_names_grouped_by_count(
        self, create_dm: CreateDm, capsys: pytest.CaptureFixture[str]
    ) -> None:
        create_dm.mand_err_msg(
            "vm", [("unknown", "site", None), ("unknown", "site", None)]
        )

        out = capsys.readouterr().out
        assert "Vm mandatory dictionary 'site' is missing in 2 vms" in out

    def test_named_objects_grouped_by_name(
        self, create_dm: CreateDm, capsys: pytest.CaptureFixture[str]
    ) -> None:
        create_dm.mand_err_msg(
            "vm",
            [("vm1", "device_role", None), ("vm2", "device_role", None)],
        )

        out = capsys.readouterr().out
        assert (
            "Vm mandatory dictionary 'device_role' is missing in vms 'vm1, vm2'" in out
        )


# ----------------------------------------------------------------------------
# obj_err_msg
# ----------------------------------------------------------------------------
class TestObjErrMsg:
    def test_cluster_toplevel_notexist(
        self, create_dm: CreateDm, capsys: pytest.CaptureFixture[str]
    ) -> None:
        create_dm.obj_err_msg(
            "cluster",
            None,
            [("UTEST_cluster1", {"Cluster": "UTEST_cluster1"}, "no object found")],
        )

        out = capsys.readouterr().out
        assert (
            "Cluster 'UTEST_cluster1' may not exist as could not get the object.id"
            in out
        )

    def test_device_type_toplevel_notexist_even_for_device(
        self, create_dm: CreateDm, capsys: pytest.CaptureFixture[str]
    ) -> None:
        create_dm.obj_err_msg(
            "device",
            None,
            [("UTEST_dtype1", {"Device-type": "UTEST_dtype1"}, "no object found")],
        )

        out = capsys.readouterr().out
        assert (
            "Device 'UTEST_dtype1' may not exist as could not get the object.id" in out
        )

    def test_groups_error_under_vm_own_name(
        self, create_dm: CreateDm, capsys: pytest.CaptureFixture[str]
    ) -> None:
        create_dm.obj_err_msg(
            "vm",
            "UTEST_vm1",
            [("UTEST_vm1", {"Tenant": "bad_tenant"}, "no object found")],
        )

        out = capsys.readouterr().out
        assert (
            "Vm 'UTEST_vm1' objects may not exist. Failed to get object.id for - "
            "Tenant: bad_tenant" in out
        )

    def test_groups_error_under_interface_name(
        self, create_dm: CreateDm, capsys: pytest.CaptureFixture[str]
    ) -> None:
        create_dm.obj_err_msg(
            "vm",
            "UTEST_vm1",
            [("eth0", {"Vlan": "99"}, "no object found")],
        )

        out = capsys.readouterr().out
        assert (
            "Vm 'UTEST_vm1' objects may not exist. Failed to get object.id for - "
            "eth0: Vlan: 99" in out
        )

    def test_delegates_mandatory_errors_to_mand_err_msg(
        self, create_dm: CreateDm, capsys: pytest.CaptureFixture[str]
    ) -> None:
        create_dm.obj_err_msg("vm", "UTEST_vm1", [("UTEST_vm1", "device_role", None)])

        out = capsys.readouterr().out
        assert "Vm mandatory dictionary 'device_role' is missing" in out

    def test_vm_name_none_defaults_to_unknown(
        self, create_dm: CreateDm, capsys: pytest.CaptureFixture[str]
    ) -> None:
        create_dm.obj_err_msg(
            "vm", None, [("unknown", {"Tenant": "bad_tenant"}, "no object found")]
        )

        out = capsys.readouterr().out
        assert "Vm 'unknown' objects may not exist" in out


# ----------------------------------------------------------------------------
# clstr_dtype_info
# ----------------------------------------------------------------------------
@pytest.mark.usefixtures("provision_base")
class TestClstrDtypeInfo:
    def test_cluster_success(self, create_dm: CreateDm) -> None:
        err: list = []

        result = create_dm.clstr_dtype_info(
            {"name": CLUSTER1, "site": SITE1}, "cluster", err
        )

        assert result["name"] == CLUSTER1
        assert isinstance(result["site"], int)
        assert isinstance(result["cltr"], int)
        assert err == []

    def test_cluster_missing_site(self, create_dm: CreateDm) -> None:
        err: list = []

        result = create_dm.clstr_dtype_info({"name": CLUSTER1}, "cluster", err)

        assert err == [[CLUSTER1, "site", None]]
        assert "site" not in result
        assert "cltr" not in result

    def test_cluster_notexist(self, create_dm: CreateDm) -> None:
        err: list = []

        result = create_dm.clstr_dtype_info(
            {"name": "UTEST_nonexistent_cluster", "site": SITE1}, "cluster", err
        )

        assert result["cltr"] is None
        assert any(e[1] == {"Cluster": "UTEST_nonexistent_cluster"} for e in err)

    def test_device_type_success(self, create_dm: CreateDm) -> None:
        err: list = []

        result = create_dm.clstr_dtype_info({"name": DTYPE1}, "device_type", err)

        assert isinstance(result["dtype"], int)
        assert isinstance(result["mftr"], int)
        assert err == []

    def test_device_type_notexist(self, create_dm: CreateDm) -> None:
        err: list = []

        result = create_dm.clstr_dtype_info(
            {"name": "UTEST_nonexistent_dtype"}, "device_type", err
        )

        assert "dtype" not in result
        assert "mftr" not in result
        assert len(err) == 1

    def test_missing_name(self, create_dm: CreateDm) -> None:
        err: list = []

        result = create_dm.clstr_dtype_info({}, "cluster", err)

        assert result == {}
        assert err == [["unknown", "name", None]]


# ----------------------------------------------------------------------------
# vm_device_info
# ----------------------------------------------------------------------------
@pytest.mark.usefixtures("provision_base")
class TestVmDeviceInfo:
    def test_vm_inherits_from_parent(self, create_dm: CreateDm) -> None:
        parent = {
            "tenant": TENANT1,
            "device_role": ROLE_VM,
            "platform": PLATFORM1,
            "site": SITE1,
        }
        err: list = []

        result = create_dm.vm_device_info(parent, {"name": "UTEST_vm_x"}, "vm", err)

        assert isinstance(result["tenant"], int)
        assert isinstance(result["device_role"], int)
        assert isinstance(result["platform"], int)
        assert isinstance(result["site"], int)
        assert err == []

    def test_vm_overrides_parent(self, create_dm: CreateDm) -> None:
        parent = {"tenant": TENANT1}
        err: list = []

        result = create_dm.vm_device_info(
            parent, {"name": "UTEST_vm_x", "tenant": TENANT2}, "vm", err
        )

        tenant2_id = create_dm.nbox.get_single_id(
            "tenancy.tenants", {"name": TENANT2}, {"name": TENANT2}, []
        )
        assert result["tenant"] == tenant2_id

    def test_device_missing_mandatory_role_and_site(self, create_dm: CreateDm) -> None:
        err: list = []

        create_dm.vm_device_info({}, {"name": "UTEST_dvc_x"}, "device", err)

        missing = [e[1] for e in err if e[0] == "UTEST_dvc_x"]
        assert missing == ["device_role", "site"]

    def test_device_cluster_location_rack(self, create_dm: CreateDm) -> None:
        parent = {"site": SITE1}
        obj = {
            "name": "UTEST_dvc_x",
            "device_role": ROLE_SWITCH,
            "cluster": CLUSTER1,
            "location": LOCATION1_SLUG,
            "rack": RACK1,
        }
        err: list = []

        result = create_dm.vm_device_info(parent, obj, "device", err)

        assert isinstance(result["cltr"], int)
        assert isinstance(result["location"], int)
        assert isinstance(result["rack"], int)
        assert err == []

    def test_device_location_without_rack(self, create_dm: CreateDm) -> None:
        parent = {"site": SITE1}
        obj = {
            "name": "UTEST_dvc_x",
            "device_role": ROLE_SWITCH,
            "location": LOCATION1_SLUG,
        }
        err: list = []

        result = create_dm.vm_device_info(parent, obj, "device", err)

        assert "location" in result
        assert "rack" not in result

    def test_missing_name(self, create_dm: CreateDm) -> None:
        err: list = []

        result = create_dm.vm_device_info({}, {}, "vm", err)

        assert result == {}
        assert err == [["unknown", "name", None]]

    def test_optional_obj_notexist(self, create_dm: CreateDm) -> None:
        err: list = []

        result = create_dm.vm_device_info(
            {}, {"name": "UTEST_vm_x", "tenant": "UTEST_bad_tenant"}, "vm", err
        )

        assert result.get("tenant") is None
        assert any(e[1] == {"Tenant": "UTEST_bad_tenant"} for e in err)


# ----------------------------------------------------------------------------
# engine (happy path, using test_files/test_inputs.yml)
# ----------------------------------------------------------------------------
@pytest.mark.usefixtures("provision_base")
class TestEngineHappyPath:
    def test_vm(self, create_dm: CreateDm) -> None:
        result = create_dm.engine("cluster", "vm", "Virtual machine")

        names = [r["vm_dvc"]["name"] for r in result]
        assert names == ["UTEST_vm1", "UTEST_vm2"]

        vm1 = result[0]
        assert len(vm1["intf"]) == 3
        modes = {i["name"]: i.get("mode") for i in vm1["intf"]}
        assert modes["eth1"] == "tagged"
        assert modes["eth2"] == "access"
        assert "mode" not in vm1["intf"][0]
        assert len(vm1["ip"]) == 1
        assert vm1["ip"][0]["address"] == "10.10.10.1/24"

        vm2 = result[1]
        assert len(vm2["ip"]) == 1
        assert vm2["ip"][0]["primary_ip"] is True

    def test_device(self, create_dm: CreateDm) -> None:
        result = create_dm.engine("device_type", "device", "Device")

        dvc1 = next(r for r in result if r["vm_dvc"]["name"] == "UTEST_dvc1")
        assert dvc1["vm_dvc"]["rack"] is not None
        assert dvc1["vm_dvc"]["position"] == 2
        assert dvc1["vm_dvc"]["face"] == "rear"
        assert dvc1["vm_dvc"]["virtual_chassis"] == {"UTEST_vc1": [1, 1]}
        assert len(dvc1["intf"]) == 3
        lag_trunk_intf = next(
            i for i in dvc1["intf"] if i["name"] == "GigabitEthernet0/2"
        )
        assert lag_trunk_intf["mode"] == "tagged"

        dvc2 = next(r for r in result if r["vm_dvc"]["name"] == "UTEST_dvc2")
        # dvc2 overrides tenant but leaves site/rack/location unset, so it
        # inherits those from the parent device_type block, same as dvc1.
        tenant2_id = create_dm.nbox.get_single_id(
            "tenancy.tenants", {"name": TENANT2}, {"name": TENANT2}, []
        )
        assert dvc2["vm_dvc"]["tenant"] == tenant2_id
        assert dvc2["vm_dvc"]["rack"] == dvc1["vm_dvc"]["rack"]
        assert dvc2["intf"][0]["type"] == "virtual"

    def test_patch_panel_ports_only(self, create_dm: CreateDm) -> None:
        result = create_dm.engine("device_type", "device", "Device")

        pp1 = next(r for r in result if r["vm_dvc"]["name"] == "UTEST_pp1")
        assert "intf" not in pp1
        assert len(pp1["port"]) == 3


# ----------------------------------------------------------------------------
# engine (error paths)
# ----------------------------------------------------------------------------
@pytest.mark.usefixtures("provision_base")
class TestEngineErrors:
    def test_missing_top_level_dict(
        self, create_dm: CreateDm, capsys: pytest.CaptureFixture[str]
    ) -> None:
        create_dm.my_vars = {}

        result = create_dm.engine("device_type", "device", "Device")

        assert result == []
        out = capsys.readouterr().out
        assert "mandatory top level 'device_type' dictionary is needed" in out

    def test_cluster_missing_site_skips_its_vms(
        self, create_dm: CreateDm, capsys: pytest.CaptureFixture[str]
    ) -> None:
        create_dm.my_vars = {
            "cluster": [
                {
                    "name": "UTEST_cluster_missing_site",
                    "tenant": TENANT1,
                    "device_role": ROLE_VM,
                    "vm": [{"name": "UTEST_vm_orphan"}],
                }
            ]
        }

        result = create_dm.engine("cluster", "vm", "Virtual machine")

        assert result == []
        out = capsys.readouterr().out
        assert "mandatory dictionary 'site'" in out

    def test_interface_error_excludes_vm(
        self, create_dm_errors: CreateDm, capsys: pytest.CaptureFixture[str]
    ) -> None:
        result = create_dm_errors.engine("cluster", "vm", "Virtual machine")

        names = [r["vm_dvc"]["name"] for r in result]
        assert "UTEST_vm_bad_intf" not in names
        out = capsys.readouterr().out
        assert "Vrf: UTEST_nonexistent_vrf" in out

    def test_vm_missing_name_reported_as_unknown(
        self, create_dm_errors: CreateDm, capsys: pytest.CaptureFixture[str]
    ) -> None:
        result = create_dm_errors.engine("cluster", "vm", "Virtual machine")

        assert result == []
        out = capsys.readouterr().out
        assert "mandatory dictionary 'name'" in out
