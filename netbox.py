import pynetbox
from pynetbox.core.query import RequestError
import ast
import operator
from collections import defaultdict


class NboxApi:
    def __init__(self, netbox_url, api_token, ssl, rc):
        self.nb = pynetbox.api(url=netbox_url, token=api_token)
        self.nb.http_session.verify = ssl
        self.rc = rc

    # ----------------------------------------------------------------------------
    # CRUD: Methods that interact with netbox to create, update or delete devices, VMs and interfaces
    # ----------------------------------------------------------------------------
    ## OBJ_CREATE: Create objects and return output and whether changed (T or F) in list or errors in dictionary
    def obj_create(self, obj_name, api_attr, input_obj, error):
        try:
            result = operator.attrgetter(api_attr)(self.nb).create(input_obj)
            return ["create", result, True]  # result returns device name for stdout
        except RequestError as e:
            error.append({obj_name: ast.literal_eval(e.error), "task_type": "create"})
            return ["create", obj_name, False]

    ## OBJ_UPDATE: Update objects return output and whether changed (T or F) in list or errors in dictionary
    def obj_update(self, obj_name, nbox_obj, input_obj, error):
        try:
            result = nbox_obj.update(input_obj)
            # pynetbox obj returns device name, result (T or F) whether updated
            return ["update", nbox_obj, result]
        except RequestError as e:
            error.append({obj_name: ast.literal_eval(e.error), "task_type": "update"})

    ## OBJ_DELETE: Deletes object, nbox_obj is the vm or interface and task_type informational
    def obj_delete(self, nbox_obj, task_type):
        try:
            nbox_obj.delete()
        except Exception as e:
            self.rc.print(
                ":x: [red]def {}[/red] error deleting [i red]{}[/i red] for task {}".format(
                    "obj_delete", str(nbox_obj), task_type
                )
            )

    ## DELETE_IP: Deletes IP address so that a new IP is assigned to interface (without would add extra IP to interface)
    def remove_intf_ip(self, obj_type, ip_dm):
        intf_id = ip_dm["assigned_object_id"]
        try:
            if obj_type == "Virtual_machine":
                ip_obj = self.nb.ipam.ip_addresses.get(vminterface_id=intf_id)
            elif obj_type == "Device":
                ip_obj = self.nb.ipam.ip_addresses.get(interface_id=intf_id)
            if str(ip_obj) != ip_dm["address"]:
                ip_obj.delete()
        except:
            pass

    # ----------------------------------------------------------------------------
    # GET: Methods that GET information from Netbox (object IDs) to be used in CRUD
    # ----------------------------------------------------------------------------
    ## GET_SINGLE_ID: Gets the ID for a single primary object (input_obj)
    def get_single_id(self, api_attr, obj, fltr, err):
        if obj.get("name") != None:
            name = obj["name"]
        elif obj.get("address") != None:
            name = obj["address"]
        obj_type = api_attr.split(".")[1][:-1]
        input_obj = list(fltr.values())[0]

        try:
            output = operator.attrgetter(api_attr)(self.nb).get(**fltr)
            # Incase doesnt error and returns nothing, add this to errors as no ID
            if output == None:
                err.append(
                    (name, {obj_type.capitalize(): input_obj}, "no object found")
                )
                return output
            # Return the nbox object so can get other object IDs for it
            elif obj_type == "device-type":
                return output
            # Return the nbox objectID
            else:
                return output.id
        except AttributeError as e:  # Errors are a list within a dictionary of the object (cluster, device type, vm or device) name
            err.append((name, {obj_type.capitalize(): input_obj}, e))
        # Catch-all for any other error
        except Exception as e:
            self.rc.print(
                f":x: def get_single_id using '{obj_type.capitalize()}' object '{input_obj}' - {e}"
            )
            exit()

    ## GET_VLAN_ID: Gets the VLAN group slug used to get single VLAN ID or create a list of all VLAN IDs
    def get_vlan_id(self, intf, error):
        vl_grp = intf["grp_vl"][0]
        vlan = intf["grp_vl"][1]

        try:
            slug = self.nb.ipam.vlan_groups.get(name=vl_grp)["slug"]
            if isinstance(vlan, list):
                vlan_id = []
                for each_vl in vlan:
                    vlan_id.append(self.nb.ipam.vlans.get(vid=each_vl, group=slug).id)
            else:
                vlan_id = self.nb.ipam.vlans.get(vid=vlan, group=slug).id
            return vlan_id
        # If the VLAN_group does not exist will cause an attribute error
        except TypeError as e:
            error.append((intf["name"], {"Vlan_group": vl_grp}, e))
        except AttributeError as e:
            error.append((intf["name"], {"Vlan": vlan}, e))
        except Exception as e:
            self.rc.print(
                f":x: def get_vlan_id with VLANs '{vlan}' in VLAN group '{vl_grp}' - {e}"
            )
            exit()

    ## CHK_EXIST: Check if object name already exists (VM or IP address) within the container (cluster or VRF)
    def chk_exist(self, api_attr, fltr, parent_obj_name):
        try:
            result = operator.attrgetter(api_attr)(self.nb).get(**fltr)
            return result
        # Catch-all for any other error
        except Exception as e:
            obj_type = api_attr.split(".")[1].capitalize()[:-1]
            name = list(fltr.values())[0]
            parent_obj_type = list(fltr.keys())[0]
            self.rc.print(
                f":x: def chk_exist using {obj_type} '{name}' in {parent_obj_type} '{parent_obj_name}' - {e}"
            )
            exit()

    # SLUG: Makes slug from name by making integers string, all characters lowercase and replacing whitespace with '_'
    def make_slug(self, obj: str) -> str:
        if isinstance(obj, int):
            obj = str(obj)
        return obj.replace(" ", "_").lower()

    ## TAGS: Gathers ID of existing tag or creates new one and returns ID (list of IDs)
    def get_or_create_tag(self, tag, tag_exists, tag_created):
        tags = []
        if tag != None:
            for name, colour in tag.items():
                name = str(name)
                tag = self.nb.extras.tags.get(name=name)
                if not tag:
                    tag = self.nb.extras.tags.create(
                        dict(name=name, slug=self.make_slug(name), color=colour)
                    )
                    tag_created.append(name)
                else:
                    tag_exists.append(name)
                tags.append(tag.id)
        return tags

    # ----------------------------------------------------------------------------
    # PRINT: Methods to edit the STDOUT formatting returned by CRUD operations
    # ----------------------------------------------------------------------------
    ## FORMAT_RSLT_ERR: Combines interface/ip error or result messages into dicts so easier to use in STDOUT messages
    def format_rslt_err(self, input_list):
        output_dict = defaultdict(list)
        for each_ele in input_list:
            try:  # If it is an error (deploy_err)
                output_dict["deploy_type"] = each_ele.pop("task_type")
                output_dict["err"].append(each_ele)
            except:  # If it is a result (intf_result or ip_result)
                if each_ele[2] is True:  # pynetbox returns True if anything was changed
                    output_dict["deploy_type"] = each_ele[0]
                    output_dict["details"].append(each_ele[1])
                    output_dict["changed"] = True
        return output_dict

    ## STDOUT_INTF_IP: Formats the output for interface or IP displayed message
    def format_stdout_intf_ip(self, obj_type, input_result):
        tmp_obj_list = []

        for each_obj in input_result["details"]:
            tmp_obj_list.append(str(each_obj))
        input_result[
            "details"
        ] = f"[i]{obj_type}: {', '.join(list(tmp_obj_list))}[/i], "
        return input_result

    ## FAIL_STDOUT: Prints out message for the user dependant on the task performed on VM/Device
    def crte_upte_err(self, obj_type, vm_dvc_exist, vm_dvc, deploy_err, intf_ip):
        # VM/DVC_NAME: Sets vm/device name dependant on whether is a new or existing
        if vm_dvc_exist != None:
            vm_dvc_name = vm_dvc_exist
        elif vm_dvc != None:
            vm_dvc_name = vm_dvc[1]

        # INTF_IP_ERROR: If new VM and has errors with interfaces deletes the VM and changes displayed error msg
        if vm_dvc_exist == None and intf_ip != "":
            self.obj_delete(vm_dvc_name, "crte_upte_" + intf_ip)
            intf_ip.replace("intf", "and interface").replace("intf", "and IP")

        # VM_INTF_IP_ERROR: Prints message if errors with VM attributes, interfaces or IPs
        err = self.format_rslt_err(deploy_err)
        self.rc.print(
            f":x: {obj_type} '{vm_dvc_name}' {intf_ip} {err['deploy_type']} failed with the following errors:"
        )
        for each_err in err["err"]:
            for obj_name, err_dict in each_err.items():
                for err_type, err_msg in err_dict.items():
                    # If is interface or ip adds that to rhe error message
                    if obj_name == str(vm_dvc_name):
                        self.rc.print(f" -[i]{err_type}: {'.'.join(err_msg)}[/i]")
                    else:
                        self.rc.print(
                            f" -[i]{obj_name} {err_type}: {'.'.join(err_msg)}[/i]"
                        )

    ## SUCCESS_STDOUT: Prints out message for the user dependant on the task performed on VM/Device
    def crte_upte_stdout(
        self, obj_type, vm_dvc_dm, vm_dvc, intf_result={}, ip_result={}
    ):
        vm_dvc_result = dict(changed=vm_dvc[2])
        intf_result = self.format_rslt_err(intf_result)
        ip_result = self.format_rslt_err(ip_result)

        changed = (
            vm_dvc_result["changed"]
            + intf_result.get("changed", False)
            + ip_result.get("changed", False)
        )

        ## NO_CHANGE: STDOUT if no changes made to VM/Device, Interface or IP
        if changed == False:
            self.rc.print(
                f"⚠️  {obj_type} '{vm_dvc[1]}' already exists with the correct details"
            )
        ## CHANGES: STDOUT if changes made to VM/Device, Interface or IP
        else:
            # VM_VAR: If VM created or updated remove unneeded attributes and create variable of changes
            if vm_dvc_result["changed"] == True:
                del vm_dvc_dm["name"], vm_dvc_dm["cltr_dtype_name"]
                if obj_type == "Virtual_machine":
                    del (vm_dvc_dm["cluster"], vm_dvc_dm["site"])
                vm_dvc_result[
                    "details"
                ] = f"attributes: [i]{', '.join(list(vm_dvc_dm.keys()))}[/i], "
            # INTF_IP_VAR: If Interface or IP created/updated create variable of changes
            if intf_result.get("changed", False) == True:
                self.format_stdout_intf_ip("interfaces", intf_result)
            if ip_result.get("changed", False) == True:
                self.format_stdout_intf_ip("IP addresses", ip_result)
            # STDOUT_CHANGE: Prints out message for user with result dependant tasks were perfromed (early variables)
            self.rc.print(
                f":white_heavy_check_mark: {obj_type} '{vm_dvc[1]}' {vm_dvc[0]}d with {vm_dvc_result.get('details', '')}"
                f"{intf_result.get('details', '')}{ip_result.get('details', '')}".rstrip(
                    ", "
                )
            )

    ## PRINT_TAG_RT: Prints the result of existing and newly created tags
    def print_tag_rt(self, obj_type, exists, created) -> None:
        if len(created) != 0:
            self.rc.print(
                f":white_check_mark: {obj_type} tags '{', '.join(created)}' successfully created"
            )
        elif len(exists) != 0:
            self.rc.print(f"⚠️  {obj_type} tags '{', '.join(exists)}' already exist")

    # ----------------------------------------------------------------------------
    # TASK: Tasks run by the engine that call the CRUD and STD methods
    # ----------------------------------------------------------------------------
    ## GET_CREATE_VC: Gets the details or creates the virtual-chassis
    def chk_create_vc(self, dvc_dm, deploy_err):
        vc_name = list(dvc_dm["vm_dvc"]["virtual_chassis"].keys())[0]
        vc_pos = list(dvc_dm["vm_dvc"]["virtual_chassis"].values())[0][0]
        vc_pri = list(dvc_dm["vm_dvc"]["virtual_chassis"].values())[0][1]
        dvc_dm["vm_dvc"]["vc_position"] = vc_pos
        dvc_dm["vm_dvc"]["vc_priority"] = vc_pri

        fltr = {"name": vc_name}
        result = self.chk_exist("dcim.virtual-chassis", fltr, dvc_dm["vm_dvc"]["name"])
        if result != None:
            dvc_dm["vm_dvc"]["virtual_chassis"] = result.id
        else:
            result = self.obj_create(vc_name, "dcim.virtual-chassis", fltr, deploy_err)
            if result[2] == True:
                dvc_dm["vm_dvc"]["virtual_chassis"] = result[1].id

        if len(deploy_err) != 0:
            self.crte_upte_err("Device", None, result, deploy_err, "")
        return deploy_err

    ## CREATE_VM_DVC: Creates the VM or device with all attributes or already exists updates it
    def create_update_vm_dvc(self, api_attr, dm, vm_dvc_exist):
        obj_type = api_attr.split(".")[1][:-1].capitalize()
        deploy_err = []

        # VM/DVC: create or update the VM or device
        if vm_dvc_exist == None:
            vm_dvc_result = self.obj_create(
                dm["vm_dvc"]["name"], api_attr, dm["vm_dvc"], deploy_err
            )
        elif vm_dvc_exist != None:
            vm_dvc_result = self.obj_update(
                dm["vm_dvc"]["name"], vm_dvc_exist, dm["vm_dvc"], deploy_err
            )

        # STDOUT: Only print message if error or no interfaces defined
        if len(deploy_err) == 0 and len(dm["intf"]) == 0:
            self.crte_upte_stdout(obj_type, dm["vm_dvc"], vm_dvc_result)

        elif len(deploy_err) != 0:
            self.crte_upte_err(obj_type, vm_dvc_exist, vm_dvc_result, deploy_err, "")

        result = dict(obj_type=obj_type, result=vm_dvc_result, deploy_err=deploy_err)
        return result

    ## CREATE_OR_UPDATE_INTF: Creates new VM interfaces or updates existing ones
    def crte_upte_intf(self, api_attr, dm, vm_dvc_exist, vm_dvc_result):
        intf_result = []
        obj_type = vm_dvc_result["obj_type"]
        vm_dvc_name = vm_dvc_result["result"][1]
        vm_dvc_id = vm_dvc_result["result"][1].id
        deploy_err = vm_dvc_result["deploy_err"]
        vm_dvc_result = vm_dvc_result["result"]

        for each_intf in dm["intf"]:
            # CHK_EXIST: Checks if interface exists to know whether to create new or update existing interface
            fltr = {
                "name": each_intf["name"],
                obj_type.lower() + "_id": vm_dvc_id,
            }
            intf_exist = self.chk_exist(api_attr, fltr, vm_dvc_name)

            # CREATE_INTF: Created individually so that error messages can have the interface name
            if intf_exist == None:
                intf_result.append(
                    self.obj_create(each_intf["name"], api_attr, each_intf, deploy_err)
                )
            # UPDATE_INTF: Update existing interface. If goes from access (untagged) to trunk (tagged) removes untagged VLAN
            elif intf_exist != None:

                if each_intf.get("mode") == "tagged":
                    each_intf["untagged_vlan"] = None
                del each_intf[obj_type.lower()], each_intf["name"]
                intf_result.append(
                    self.obj_update(str(intf_exist), intf_exist, each_intf, deploy_err)
                )
        # STDOUT: Only print message if error or no IPs defined
        if len(deploy_err) == 0 and len(dm["ip"]) == 0:
            self.crte_upte_stdout(obj_type, dm["vm_dvc"], vm_dvc_result, intf_result)

        elif len(deploy_err) != 0:
            self.crte_upte_err(
                obj_type, vm_dvc_exist, vm_dvc_result, deploy_err, "and interface"
            )
        result = dict(result=intf_result, deploy_err=deploy_err)
        return result

    ## CREATE_OR_UPDATE_IP: Creates new VM interface IP address or adds existing one to a VM interfaces
    def crte_upte_ip(self, api_attr, dm, vm_dvc_exist, vm_dvc_result, intf_result):
        obj_type = vm_dvc_result["obj_type"]
        deploy_err = vm_dvc_result["deploy_err"]
        vm_dvc_result = vm_dvc_result["result"]
        ip_result = []

        for each_ip in dm["ip"]:
            # GET_ID: Gets the interface ID
            fltr = {
                "name": each_ip["intf_name"]["name"],
                obj_type.lower() + "_id": vm_dvc_result[1].id,
            }
            each_ip["assigned_object_id"] = self.get_single_id(
                api_attr, each_ip, fltr, deploy_err
            )
            # PFX_ID: if the prefix already exists the prefix ID
            fltr = {
                "address": each_ip["address"],
                "vrf_id": each_ip["vrf"],
            }
            each_ip["ip_obj"] = self.chk_exist(
                "ipam.ip_addresses", fltr, each_ip["vrf_name"]
            )
            # ASSIGN_TYPE: if assigned to VM or device interface
            if obj_type == "Virtual_machine":
                each_ip["assigned_object_type"] = "virtualization.vminterface"
            elif obj_type == "Device":
                each_ip["assigned_object_type"] = "dcim.interface"

        # GET_ID_ERR: Failfast and delete the newly created VM if errors have occurred during attempt to get IDs
        if len(deploy_err) != 0:
            self.crte_upte_err(
                obj_type, vm_dvc_exist, vm_dvc_result, deploy_err, "and IP"
            )
        # ADD_ASSIGN_IP: Either create IP and assign to interface or if IP already exists assign it to the interface
        elif len(deploy_err) == 0:
            for each_ip in dm["ip"]:
                if each_ip["ip_obj"] == None:
                    self.remove_intf_ip(obj_type, each_ip)
                    tmp_ip_result = self.obj_create(
                        each_ip["address"], "ipam.ip_addresses", each_ip, deploy_err
                    )
                elif each_ip["ip_obj"] != None:
                    self.remove_intf_ip(obj_type, each_ip)
                    tmp_ip_result = self.obj_update(
                        each_ip["address"], each_ip["ip_obj"], each_ip, deploy_err
                    )
                # PRIMARY_IP: If it is the primary IP address updates the VM with the details
                if len(deploy_err) == 0:
                    if each_ip["primary_ip"] == True:
                        self.obj_update(
                            dm["vm_dvc"]["name"],
                            vm_dvc_result[1],
                            {"primary_ip4": tmp_ip_result[1].id},
                            deploy_err,
                        )
                    ip_result.append(tmp_ip_result)
        # STDOUT: Print message
        if len(deploy_err) == 0:
            self.crte_upte_stdout(
                obj_type, dm["vm_dvc"], vm_dvc_result, intf_result["result"], ip_result
            )
        elif len(deploy_err) != 0:
            self.crte_upte_err(
                obj_type, vm_dvc_exist, vm_dvc_result, deploy_err, "and IP"
            )

    # ----------------------------------------------------------------------------
    # ENGINE: Runs the methods in this class to perform API calls to create VMs, interfaces and IPs
    # ----------------------------------------------------------------------------
    def engine(self, obj_type, api_attr, dm):
        tag_exists, tag_created = ([] for i in range(2))

        # CHECK_VM: First checks whether the VM already exists and either creates new VM or updates existing VM if changes
        for each_vm_dvc in dm:
            # FLTR: Creates filter for checking if VM or Device exists
            if obj_type == "vm":
                fltr = {
                    "name": each_vm_dvc["vm_dvc"]["name"],
                    "cluster_id": each_vm_dvc["vm_dvc"]["cluster"],
                }
                intf_api = "virtualization.interfaces"

            elif obj_type == "device":
                fltr = {
                    "name": each_vm_dvc["vm_dvc"]["name"],
                    "site_id": each_vm_dvc["vm_dvc"]["site"],
                }
                intf_api = "dcim.interfaces"

            # VC: If a device and virtual chassis gets or creates the VC
            deploy_err = []
            if each_vm_dvc["vm_dvc"].get("virtual_chassis") != None:
                self.chk_create_vc(each_vm_dvc, deploy_err)
            if len(deploy_err) == 0:
                # EXIST: Gets netbox object ID for any VM/Devices that already exist
                vm_dvc_exist = self.chk_exist(
                    api_attr, fltr, each_vm_dvc["vm_dvc"]["cltr_dtype_name"]
                )
                # Checks if tag exists and gathers the ID. If doesn't exist creates it
                if each_vm_dvc["vm_dvc"].get("tags") != None:
                    each_vm_dvc["vm_dvc"]["tags"] = self.get_or_create_tag(
                        each_vm_dvc["vm_dvc"]["tags"], tag_exists, tag_created
                    )
                # CREATE_UPDATE: Done one at a time with all elements created at same iteration for easier reporting and rollback
                vm_dvc_result = self.create_update_vm_dvc(
                    api_attr, each_vm_dvc, vm_dvc_exist
                )

            # # CREATE_UPDATE_INTF: If VM create/update successful creates and/or updates (if interface already exist) interfaces
            if len(each_vm_dvc["intf"]) != 0:
                if len(vm_dvc_result.get("deploy_err", ["dummy"])) == 0:
                    intf_result = self.crte_upte_intf(
                        intf_api, each_vm_dvc, vm_dvc_exist, vm_dvc_result
                    )

                # CREATE_UPDATE_IP: If VM and INTF create/update successful creates (if IP doesn't exist) and associates IP to interfaces
                if len(each_vm_dvc["ip"]) != 0:
                    if (
                        len(vm_dvc_result.get("deploy_err", ["dummy"])) == 0
                        and len(intf_result.get("deploy_err", ["dummy"])) == 0
                    ):
                        self.crte_upte_ip(
                            intf_api,
                            each_vm_dvc,
                            vm_dvc_exist,
                            vm_dvc_result,
                            intf_result,
                        )

        # TAGs: Prints tag changes
        obj_type = api_attr.split(".")[1][:-1].capitalize()
        self.print_tag_rt(obj_type, tag_exists, tag_created)
