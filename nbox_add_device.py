"""
Creates VMs and devices from a YAML file that starts at either the clusters (VMs) or devices-types (devices) and ends at the interface.
-VMs: Cluster name, Site and VM name are mandatory
-Devices: Device-type name, Site, tenants, Device-role and device name are mandatory

The only things that cant be inherited from cluster are cpu, mem, disk, comments
The only things that be inherited from device-type are asset and serial number, comments, position, face and virtual-chassis

To run the script reference the VM variable file
python nbox_add_device.py devices_and_vms.yml
"""

import yaml
from sys import argv
from collections import defaultdict
import copy
from rich.console import Console
from rich.theme import Theme

import config
from netbox import NboxApi

# ----------------------------------------------------------------------------
# Variables to change dependant on environment
# ----------------------------------------------------------------------------
netbox_url = config.netbox_url
api_token = config.api_token
ssl = False
# If using Self-signed cert rather than disbaling SSL verification (nb.http_session.verify = False) can specify the CA cert
# os.environ['REQUESTS_CA_BUNDLE'] = os.path.expanduser('~/Documents/Coding/Netbox/nbox_py_scripts/myCA.pem')


class CreateDm:
    def __init__(self, nbox, rc, argv):
        self.rc = rc
        self.nbox = nbox
        with open(argv[1], "r") as file_content:
            self.my_vars = yaml.load(file_content, Loader=yaml.FullLoader)

    # ----------------------------------------------------------------------------
    # 1. DM: Creates the DMs for VM, Device, Interfaces and IP addresses
    # ----------------------------------------------------------------------------
    ## 1a. CREATE_VM_DM: Creates the data-model with all options for creating the VM
    def create_vm_dvc(self, obj_type, cltr_dtype, vm_dvc, vm_dvc_orig):
        dm = dict(
            cltr_dtype_name=cltr_dtype["name"],
            name=vm_dvc["name"],
            tenant=vm_dvc.get("tenant", None),
            platform=vm_dvc.get("platform", None),
            status=vm_dvc_orig.get("status", "active"),
            comments=vm_dvc_orig.get("comments", ""),
            tags=vm_dvc_orig.get("tags", None),
        )

        if obj_type == "vm":
            dm["cluster"] = cltr_dtype["cltr"]
            dm["site"] = cltr_dtype["site"]
            dm["role"] = vm_dvc.get("device_role", None)
            dm["vcpus"] = vm_dvc_orig.get("cpu", None)
            dm["memory"] = vm_dvc_orig.get("mem", None)
            dm["disk"] = vm_dvc_orig.get("disk", None)
        elif obj_type == "device":
            dm["device_type"] = cltr_dtype["dtype"]
            dm["manufacturer"] = cltr_dtype["mftr"]
            dm["device_role"] = vm_dvc["device_role"]
            dm["site"] = vm_dvc["site"]
            dm["cluster"] = vm_dvc.get("cluster")
            dm["location"] = vm_dvc.get("location")
            dm["serial"] = vm_dvc_orig.get("serial", None)
            dm["asset_tag"] = vm_dvc_orig.get("asset_tag", None)
            dm["virtual_chassis"] = vm_dvc_orig.get("virtual_chassis", None)
            if vm_dvc.get("rack") != None:
                dm["rack"] = vm_dvc.get("rack")
                dm["position"] = vm_dvc_orig.get("position", None)
                dm["face"] = vm_dvc_orig.get("face", "front")
        return dm

    ## 1b. CREATE_INTF_DM: Creates the data-models to be used to create the VM interface (interface and IP)
    def create_intf_dm(self, obj_type, vl_vrf, vm_dvc, each_intf):
        intf = dict(
            virtual_machine=dict(name=vm_dvc["name"]),
            name=each_intf["name"],
            description=each_intf.get("descr", ""),
        )
        # Only required for device interface
        if obj_type == "device":
            del intf["virtual_machine"]
            intf["device"] = dict(name=vm_dvc["name"])
            intf["type"] = each_intf.get("type", None)
        # INTF_DM: Sets whether an access or trunk port
        if vl_vrf.get("vlan") != None:
            if isinstance(vl_vrf["vlan"], int):
                intf["mode"] = "access"
                intf["untagged_vlan"] = vl_vrf["vlan"]
            elif isinstance(vl_vrf["vlan"], list):
                intf["mode"] = "tagged"
                intf["tagged_vlans"] = vl_vrf["vlan"]
        # CREATE_IP_DM: Creates the data-models to be used to create the IP addresses
        ip = {}
        if each_intf.get("vrf_ip", None) != None:
            ip = dict(
                address=each_intf["vrf_ip"][1],
                tenant=vm_dvc.get("tenant", None),
                vrf_name=each_intf["vrf_ip"][0],
                vrf=vl_vrf["vrf"],
                intf_name=dict(name=each_intf["name"]),
                dns_name=each_intf.get("dns", ""),
                primary_ip=each_intf.get("primary_ip", False),
            )
        return dict(intf=intf, ip=ip)

    ## 1c. REMOVE_EMPTY: Removes any empty attributes from the VM/DVC, INTF or IP DMs
    def rmv_empty_attr(self, attr_dict):
        tmp_attr_dict = copy.deepcopy(attr_dict)

        for each_attr, each_val in tmp_attr_dict.items():
            if each_attr == "tenant" or each_attr == "rack":
                pass
            elif each_val == None:
                del attr_dict[each_attr]
            elif isinstance(each_val, dict):
                if list(each_val.values())[0] == None:
                    del attr_dict[each_attr]
            elif not isinstance(each_val, int):
                if len(each_val) == 0:
                    del attr_dict[each_attr]
        return attr_dict

    ## 1d. PRIM_IP: Sets 1st IP as primary if not set on any other interface
    def set_primary_ip(self, ip):
        primary_ip_set = False

        if len(ip) != 0:
            for each_ip in ip[1:]:
                primary_ip_set = primary_ip_set + each_ip["primary_ip"]
            if primary_ip_set == False:
                ip[0]["primary_ip"] = True
        return ip

    # ----------------------------------------------------------------------------
    # 2. GET_OBJ: Methods used by VM and Device DMs to call netbox.py methods and get object IDs
    # ----------------------------------------------------------------------------
    ## 2a. Get the top level cluster and device type attribute object IDs
    def clstr_dtype_info(self, obj, info, err):
        all_obj = {}

        if obj.get("name") != None:
            all_obj["name"] = obj["name"]
            # Cluster checks (site is a missing mandatory object as used to get unique cluster ID)
            if info == "cluster" and obj.get("site") == None:
                err.append([obj["name"], "site", None])
            elif info == "cluster":
                fltr = dict(name=obj["site"])
                all_obj["site"] = self.nbox.get_single_id("dcim.sites", obj, fltr, err)
                fltr = dict(name=obj["name"], site_id=all_obj["site"])
                all_obj["cltr"] = self.nbox.get_single_id(
                    "virtualization.clusters", obj, fltr, err
                )
            # Device-type Checks
            elif info == "device_type":
                fltr = dict(model=obj["name"])
                tmp_obj = self.nbox.get_single_id("dcim.device-types", obj, fltr, err)
                if tmp_obj != None:
                    all_obj["dtype"] = tmp_obj.id
                    all_obj["mftr"] = tmp_obj["manufacturer"]["id"]
        else:
            err.append(["unknown", "name", None])
        return all_obj

    ## 2b. Get the VM or device attribute object IDs
    def vm_device_info(self, parent_obj, obj, info, err):
        all_obj = {}

        if obj.get("name") != None:
            all_obj["name"] = obj["name"]
            # For devices both site and role is mandatory (as site can be inherited is not done in clstr_dtype_info)
            if info == "device":
                inherit_dvc_role = obj.get("device_role", parent_obj.get("device_role"))
                inherit_dvc_site = obj.get("site", parent_obj.get("site"))
                if inherit_dvc_role == None:
                    err.append([obj["name"], "device_role", None])
                if inherit_dvc_site == None:
                    err.append([obj["name"], "site", None])
            # ALL_OPTIONAL: Shared VM/device objects, checks if defined in cluster/device-type if empty
            for api_attr in [
                "tenancy.tenants",
                "dcim.device_roles",
                "dcim.platforms",
                "dcim.sites",
            ]:
                obj_type = api_attr.split(".")[1][:-1]
                inherit_obj = obj.get(obj_type, parent_obj.get(obj_type))
                if inherit_obj != None:
                    all_obj[obj_type] = self.nbox.get_single_id(
                        api_attr, obj, {"name": inherit_obj}, err
                    )
            # DVC_OPTIONAL: Device only optional attributes
            inherit_cltr = obj.get("cluster", parent_obj.get("cluster"))
            if info == "device" and inherit_cltr != None:
                fltr = dict(name=inherit_cltr, site_id=all_obj.get("site"))
                all_obj["cltr"] = self.nbox.get_single_id(
                    "virtualization.clusters", obj, fltr, err
                )
            inherit_loc = obj.get("location", parent_obj.get("location"))
            if info == "device" and inherit_loc != None:
                all_obj["location"] = self.nbox.get_single_id(
                    "dcim.locations", obj, {"slug": inherit_loc}, err
                )
                inherit_rack = obj.get("rack", parent_obj.get("rack"))
                if all_obj["location"] != None and inherit_rack != None:
                    fltr = dict(name=inherit_rack, location_id=all_obj["location"])
                    all_obj["rack"] = self.nbox.get_single_id(
                        "dcim.racks", obj, fltr, err
                    )
        else:
            err.append(["unknown", "name", None])
        return all_obj

    # ----------------------------------------------------------------------------
    # 3. ERRORS: Prettifies error messages and prints to stdout
    # ---------------------------------------------------------------------------
    ## 3a. MAND_ERROR_MSG: Prettifies and prints error messages for missing mandatory dictionaries
    def mand_err_msg(self, obj_type, input_err):
        tmp_err = defaultdict(list)
        # Group errors as {missing_key: [obj_names]} before printing
        for name, err_obj, err in input_err:
            tmp_err[err_obj].append(name)
        # STDOUT for the differnet missing mandatory attribute errors
        for dict_name, obj_name in tmp_err.items():
            if dict_name == "cluster":
                self.rc.print(
                    f":x: The mandatory top level '{dict_name}' dictionary is needed if you are trying to create VMs"
                )
            elif dict_name == "device_type":
                self.rc.print(
                    f":x: The mandatory top level '{dict_name}' dictionary is needed if you are trying to create Devices"
                )
            elif set(obj_name) == {"unknown"}:
                self.rc.print(
                    f":x: {obj_type.capitalize()} mandatory dictionary '{dict_name}' is missing in {len(obj_name)} {obj_type}s"
                )
            else:
                self.rc.print(
                    f":x: {obj_type.capitalize()} mandatory dictionary '{dict_name}' is missing in {obj_type}s '{', '.join(list(obj_name))}'"
                )

    ## 3b. OBJ_ERROR_MSG: Error messages if any VM/device or interface objects don't exist (groups interfaces together to report in one line)
    def obj_err_msg(self, obj_type, vm_name, input_err):
        tmp_err = defaultdict(dict)
        mand_err = []
        if vm_name == None:
            vm_name = "unknown"

        for name, err_obj, err in input_err:
            # MAND: If a mandatory element does not exist adds to list run by mand_err_msg
            if err == None:
                mand_err.append([name, err_obj, err])
            # TOP-LEVEL-DICT: Error if cant get cluster or device-type object ID (top level dictionary)
            elif (
                obj_type != "device" and list(err_obj.keys())[0] == "Cluster"
            ) or list(err_obj.keys())[0] == "Device-type":
                self.rc.print(
                    f":x: {obj_type.capitalize()} '{name}' may not exist as could not get the object.id"
                )
            # OBJ: Error messages for all other object IDs couldnt not get
            else:
                if name == vm_name:
                    tmp_err.update(err_obj)
                # If object an interface groups all errors under the same interface
                else:
                    tmp_err[name].update(err_obj)

        # PRINT: Print any object error messages
        if len(tmp_err) != 0:
            err = str(dict(tmp_err)).replace("{", "").replace("}", "").replace("'", "")
            self.rc.print(
                f":x: {obj_type.capitalize()} '{vm_name}' objects may not exist. Failed to get object.id for - [i]{err}[/i]"
            )
        # MAND: Send any Mandatory to the mand_err_msg method to print error message
        if len(mand_err) != 0:
            self.mand_err_msg(obj_type, mand_err)

    # ----------------------------------------------------------------------------
    # 4. Engine: Runs methods to get object IDs creating data model used in to create VMs, devices, interfaces and IPs
    # ----------------------------------------------------------------------------
    def engine(self, cltr_dtype, vm_dvc, vm_dvc_fname):
        all_obj = []
        cltr_dtype_err = []

        ## 4a. CLTR/DTYPE:: Based on parent object (cluster or device-type) creates the objects (VM or device) DM by its getting attributes IDs
        if self.my_vars.get(cltr_dtype) == None:
            cltr_dtype_err.append(("unknown", cltr_dtype, None))
        else:
            for each_cltr_dtype in self.my_vars[cltr_dtype]:
                cltr = self.clstr_dtype_info(
                    each_cltr_dtype, cltr_dtype, cltr_dtype_err
                )
                if each_cltr_dtype.get(vm_dvc) == None:
                    cltr_dtype_err.append(
                        (each_cltr_dtype.get("name", "unknown"), vm_dvc, None)
                    )

                ## 4b. VM/DVC: VM or device attributes object IDs collection, only proceeds if no cluster/device-type errors
                if len(cltr_dtype_err) == 0:
                    for each_vm_dvc in each_cltr_dtype[vm_dvc]:
                        vm_dvc_err, intf_err, intf, ip = ([] for i in range(4))
                        tmp_vm_dvc = self.vm_device_info(
                            each_cltr_dtype, each_vm_dvc, vm_dvc, vm_dvc_err
                        )
                        # CREATE_VM/DVC_DM: If there are no errors builds the data-model for creating the VM or device
                        if len(vm_dvc_err) == 0:
                            dm_vm_dvc = self.create_vm_dvc(
                                vm_dvc, cltr, tmp_vm_dvc, each_vm_dvc
                            )
                            # CLEAN_DM: Removes any None values or empty lists
                            dm_vm_dvc = self.rmv_empty_attr(dm_vm_dvc)

                            ## 4c. GET_INTF_IP: Gathers object IDs (unique VLAN in GRP or IP in VRF) to create VM interfaces and associated IPs
                            if each_vm_dvc.get("intf", None) != None:
                                for each_intf in each_vm_dvc["intf"]:
                                    vl_vrf = {}
                                    if each_intf.get("name") == None:
                                        intf_err.append(
                                            (each_vm_dvc["name"], "intf name", None)
                                        )
                                    else:
                                        # Get VLAN IDs and VRF ID
                                        if each_intf.get("grp_vl") != None:
                                            vl_vrf["vlan"] = self.nbox.get_vlan_id(
                                                each_intf, intf_err
                                            )
                                        if each_intf.get("vrf_ip", None) != None:
                                            fltr = dict(name=each_intf["vrf_ip"][0])
                                            vl_vrf["vrf"] = self.nbox.get_single_id(
                                                "ipam.vrfs", each_intf, fltr, intf_err
                                            )
                                        # 4d. CREATE_INTF_DM: If are no errors creates the data-models to be used to create the interface
                                        if len(intf_err) == 0:
                                            tmp_intf_ip = self.create_intf_dm(
                                                vm_dvc, vl_vrf, dm_vm_dvc, each_intf
                                            )
                                            # 4e. CLEAN_DM: Removes any None values or empty lists
                                            intf.append(
                                                self.rmv_empty_attr(tmp_intf_ip["intf"])
                                            )
                                            if len(tmp_intf_ip["ip"]) != 0:
                                                ip.append(
                                                    self.rmv_empty_attr(
                                                        tmp_intf_ip["ip"]
                                                    )
                                                )

                            # INTF_IP_ERR: Reports error message if any of the VM interface objects don't exist
                            if len(intf_err) != 0:
                                self.obj_err_msg(
                                    vm_dvc_fname, each_vm_dvc.get("name"), intf_err
                                )
                            # 4f. CREATE_DM: If no VM/device errors and no interface/IP errors sets primary IP and creates the DM
                            elif len(intf_err) == 0:
                                ip = self.set_primary_ip(ip)
                                all_obj.append(dict(vm_dvc=dm_vm_dvc, intf=intf, ip=ip))

                        # VM/DVC_ERR: Groups and reports any VM based errors
                        if len(vm_dvc_err) != 0:
                            self.obj_err_msg(
                                vm_dvc_fname, each_vm_dvc.get("name"), vm_dvc_err
                            )

        # CLTR_DTYPE_ERR: Groups and reports any cluster or device-type based errors
        if len(cltr_dtype_err) != 0:
            self.obj_err_msg("cluster", None, cltr_dtype_err)

        return all_obj


# ----------------------------------------------------------------------------
# RUN: Runs the script
# ----------------------------------------------------------------------------
def main():
    ## 1. LOAD: Opens netbox connection and loads the variable file
    script, first = argv
    my_theme = {"repr.ipv4": "none", "repr.number": "none", "repr.call": "none"}
    rc = Console(theme=Theme(my_theme))
    nbox = NboxApi(netbox_url, api_token, ssl, rc)

    ## 2. DM: Create Data-Model for API calls. Has catchall of exit if empty as no changes need to be made
    create_dm = CreateDm(nbox, rc, argv)
    vm = create_dm.engine("cluster", "vm", "Virtual machine")
    dvc = create_dm.engine("device_type", "device", "Device")

    ## 3. NBOX: Create or update VMs using nbox API
    if len(vm) != 0:
        nbox.engine("vm", "virtualization.virtual_machines", vm)
    if len(dvc) != 0:
        nbox.engine("device", "dcim.devices", dvc)


if __name__ == "__main__":
    main()
