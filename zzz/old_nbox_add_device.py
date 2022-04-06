"""
###### Netbox blah, blah, blah ######

"""

# import config
import pynetbox
from pynetbox.core.query import RequestError
import yaml
import operator
import os
import ast
from sys import argv
import os
from pprint import PrettyPrinter, pprint
from collections import defaultdict
import copy
from rich.console import Console
from rich.theme import Theme

 ######################## Variables to change dependant on environment ########################
# Netbox login details (create from your user profile or in admin for other users)
netbox_url = "https://10.10.10.101"
token = "dc08510a144d487fc4048965594df7aa642de0c8"
# If using Self-signed cert must have been signed by a CA (can all be done on same box in openssl) and this points to that CA cert
os.environ['REQUESTS_CA_BUNDLE'] = os.path.expanduser('~/Documents/Coding/Netbox/nbox_py_scripts/myCA.pem')


############################ INZT_LOAD: Opens netbox connection and loads the variable file ############################
class Nbox():
    def __init__(self):
        self.nb = pynetbox.api(url=netbox_url, token=token)
        with open(argv[1], 'r') as file_content:
            self.my_vars = yaml.load(file_content, Loader=yaml.FullLoader)
        self.rc = Console(theme=Theme({"repr.str": "black italic", "repr.ipv4": "black italic", "repr.number": "black italic"}))


############################ OBJ_CREATE: API engine to create objects or error based on the details fed into it ############################
    def obj_create(self, obj_name, api_attr, input_obj, error):
        try:
            result = operator.attrgetter(api_attr)(self.nb).create(input_obj)
            return ['create', result]
        except RequestError as e:
            error.append({obj_name: ast.literal_eval(e.error), 'task_type': 'create'})


############################ OBJ_UPDATE: API engine to update objects or error based on the details fed into it ############################
    def obj_update(self, obj_name, nbox_obj, input_obj, error):
        try:
            nbox_obj.update(input_obj)
            return ['update', nbox_obj]
        except RequestError as e:
            error.append({obj_name: ast.literal_eval(e.error), 'task_type': 'update'})


############################ GET_ID: API call to get the Netbox object IDs ############################
    # MULTI_ID: Gets the ID for primary object (input_obj) as well as the ID for a secondary object (other_obj_type) within the primary object
    def get_multi_id(self, api_attr, input_obj, input_obj_type, other_obj_type, error):
        result = {}
        try:
            result[input_obj_type] = operator.attrgetter(api_attr)(self.nb).get(name=input_obj).id
            # If the secondary object (other_obj) is defined also gets that objects ID
            if operator.attrgetter(other_obj_type)(operator.attrgetter(api_attr)(self.nb).get(name=input_obj)) != None:
                result[other_obj_type] = operator.attrgetter(other_obj_type)(operator.attrgetter(api_attr)(self.nb).get(name=input_obj)).id
            return result
        except AttributeError as e:
            error.append((api_attr.split('.')[1].capitalize()[:-1], input_obj, e))
        # Catch-all for any other error
        except Exception as e:
            self.rc.print(":x: [red]def {}[/red] using {} [i red]{}[/i red] - {}".format('get_multi_id', api_attr.split('.')[1].capitalize()[:-1], input_obj, e))
            exit()

    # SINGLE_ID: Gets the ID for a single primary object (input_obj), errors are a list within a dictionary of the VM name
    def get_single_id(self, vm_name, api_attr, input_obj, error):
        try:
            obj_id = operator.attrgetter(api_attr)(self.nb).get(name=input_obj).id
            return obj_id
        except AttributeError as e:
            error.append((vm_name, {api_attr.split('.')[1].capitalize()[:-1]: input_obj}, e))
        # Catch-all for any other error
        except Exception as e:
            self.rc.print(":x: [red]def {}[/red] using {} object [i red]{}[/i red] - {}".format('get_single_id', api_attr.split('.')[1].capitalize()[:-1], input_obj, e))
            exit()

    # SINGLE_FLTR_ID: Gets the ID for a single primary object (input_obj) based on name and its container
    def get_single_fltr_id(self, api_attr, input_obj_fltr, input_obj, obj_container_fltr, obj_container_id, obj_container_name, error):
        try:
            return operator.attrgetter(api_attr)(self.nb).get(**{input_obj_fltr: input_obj, obj_container_fltr: obj_container_id}).id
        except AttributeError as e:
            error.append("{} ({}): {}".format(input_obj, obj_container_name, e))
        # Catch-all for any other error
        except Exception as e:
            self.rc.print(":x: [red]def {}[/red] using {} object [i red]{}[/i red] - {}".format('get_single_fltr_id', api_attr.split('.')[1].capitalize()[:-1], input_obj, e))
            exit()

    # Gets the VLAN group slug which is then used to get the single VLAN ID or create a list of all VLAN IDs
    def get_vlan_id(self, intf, vl_grp, vlan, error):
        try:
            slug = self.nb.ipam.vlan_groups.get(name=vl_grp)['slug']
            if isinstance(vlan, list):
                vlan_id = []
                for each_vl in vlan:
                    vlan_id.append(self.nb.ipam.vlans.get(vid=each_vl, group=slug).id)
            else:
                vlan_id = self.nb.ipam.vlans.get(vid=vlan, group=slug).id
            return vlan_id
        # If the VLAN_group does not exist will cause an attribute error
        except TypeError as e:
            error.append((intf, {'Vlan_group': vl_grp}, e))
        except AttributeError as e:
            error.append((intf, {'Vlan': vlan}, e))
        except Exception as e:
            self.rc.print(":x: [red]def {}[/red] with VLANs [i red]{}[/i red] in VLAN group [i]{}[/i] - {}".format('get_vlan_id', vlan, vl_grp, e))
            exit()

    # EXIST: Checks whether an objected with that name already exists (VM or IP address) within the container (cluster or VRF). EXIT if fail
    def chk_exist(self, api_attr, input_obj_fltr, input_obj, obj_container_fltr, obj_container_id, obj_container_name):
        try:
            return operator.attrgetter(api_attr)(self.nb).get(**{input_obj_fltr: input_obj, obj_container_fltr: obj_container_id})
        # Catch-all for any other error
        except Exception as e:
            self.rc.print(":x: [red]def {}[/red] using {} [i red]{}[/i red] in {} [i]{}[/i] - {}".format('chk_exist', api_attr.split('.')[1].capitalize()[:-1],
                    input_obj, obj_container_fltr, obj_container_name, e))
            exit()

    # REMOVE_EMPTY: Removes any empty attributes from the VM
    def rmv_empty(self, attr_list):
        tmp_attr = copy.deepcopy(attr_list)
        for each_attr, each_val in tmp_attr.items():
            if each_val == None:
                del attr_list[each_attr]
            elif isinstance(each_val, dict):
                if list(each_val.values())[0] == None:
                    del attr_list[each_attr]
            elif not isinstance(each_val, int):
                if len(each_val) == 0:
                    del attr_list[each_attr]
        return attr_list

    # FORMAT_RSLT_ERR: Combines error or result messages into dicts of lists with key of either 'create' or 'update'
    def format_rslt_err(self, input_list):

        output_dict = defaultdict(list)
        for each_ele in input_list:
            try:
                output_dict[each_ele.pop('task_type')].append(each_ele)
            except:
                output_dict[each_ele[0]].append(each_ele[1])
        return output_dict


############################# DM_CREATE: Ensures that objects don't already exist and creates the DMs ready for API call to add VMs, INTF and IP ############################
    def create_dm(self):
        all_vm = []

        # CLUSTER_SITE: Get the cluster and site ID (if there is a site in cluster). If cluster does not exist does failfast and exist playbook
        for each_clstr in self.my_vars['cluster']:
            clstr_err = []
            clstr_site = self.get_multi_id('virtualization.clusters', each_clstr['name'], 'clstr', 'site', clstr_err)

            # OPTIONAL_OBJ: Gets the ID for all the optional variables that can be set for the VM
            if len(clstr_err) == 0:
                for each_vm in each_clstr['vm']:
                    vm_err = []
                    tmp_vm = {}

                    # GET_OBJ_ID: Gets ID of the optional objects
                    if each_vm.get('tenant') != None:
                        tmp_vm['tenant'] = self.get_single_id(each_vm['name'], 'tenancy.tenants', each_vm['tenant'], vm_err)
                    if each_vm.get('role') != None:
                        tmp_vm['role'] = self.get_single_id(each_vm['name'], 'dcim.device_roles', each_vm['role'], vm_err)
                    if each_vm.get('platform') != None:
                        tmp_vm['platform'] = self.get_single_id(each_vm['name'], 'dcim.platforms', each_vm['platform'], vm_err)

                    # CREATE_VM_DM: If there are no errors creates the data-model for creating the VM
                    if len(vm_err) == 0:
                        vm = dict(name=each_vm['name'], clstr_name=each_clstr['name'], cluster=clstr_site['clstr'], site=clstr_site.get('site', None),
                                  tenant=tmp_vm.get('tenant', None), role=tmp_vm.get('role', None), platform=dict(name=each_vm.get('platform', None)),
                                  vcpus=each_vm.get('cpu', None), memory=each_vm.get('mem', None), disk=each_vm.get('disk', None),
                                  comments=each_vm.get('comments', ''), tags=each_vm.get('tags', []))
                        # CLEAN_DM: Removes any None values or empty lists
                        vm = self.rmv_empty(vm)

                        # INTF_IP: Gathers object IDs for objects used to create VM interfaces and associated IP addresses
                        intf_err, intf, ip = ([] for i in range(3))
                        if each_vm.get('intf', None) != None:
                            for each_intf in each_vm['intf']:
                                tmp_intf, tmp_ip = ([] for i in range(2))
                                tmp_intf_dict = {}
                                # LAYER2: If set uses the vlan_group and VLAN ID to get the VLANs object ID
                                if each_intf.get('grp_vl') != None:
                                    tmp_intf_dict['vlan'] = self.get_vlan_id(each_intf['name'], each_intf['grp_vl'][0], each_intf['grp_vl'][1], intf_err)
                                # LAYER3: If it is a Layer3 interface, so has an IP checks the VRF is valid and that the IP address does no already exist in that VRF
                                if each_intf.get('vrf_ip', None) != None:
                                    tmp_intf_dict['vrf'] = self.get_single_id(each_intf['name'], 'ipam.vrfs', each_intf['vrf_ip'][0], intf_err)

                                # CREATE_INTF_DM: If are no errors creates the data-models to be used to create the interface
                                if len(intf_err) == 0:
                                    if tmp_intf_dict.get('vlan') == None:
                                        tmp_intf.append(dict(virtual_machine=dict(name=each_vm['name']), name=each_intf['name'], tags=each_intf.get('tags', [])))
                                    elif isinstance(tmp_intf_dict['vlan'], int):
                                        tmp_intf.append(dict(virtual_machine=dict(name=each_vm['name']), name=each_intf['name'], mode='access', untagged_vlan=tmp_intf_dict['vlan'], tags=each_intf.get('tags', [])))
                                    elif isinstance(tmp_intf_dict['vlan'], list):
                                        tmp_intf.append(dict(virtual_machine=dict(name=each_vm['name']), name=each_intf['name'], mode='tagged', tagged_vlans=tmp_intf_dict['vlan'], tags=each_intf.get('tags', [])))
                                    # CREATE_IP_DM: Creates the data-models to be used to create the IP addresses. If is the primary IP adds extra tag to be used popped and used at end
                                    if each_intf.get('vrf_ip', None) != None:
                                        tmp_ip.append(dict(address=each_intf['vrf_ip'][1], vrf=tmp_intf_dict['vrf'], vrf_name=each_intf['vrf_ip'][0], tenant=tmp_vm.get('tenant', None),
                                                       intf_name=dict(name=each_intf['name']), dns_name=each_intf.get('dns', ''), sec_ip=each_intf.get('secondary_ip', False), tags=each_intf.get('tags', [])))
                                    # CLEAN_DM: Removes any None values or empty lists
                                    for each_intf in tmp_intf:
                                        intf.append(self.rmv_empty(each_intf))
                                    for each_ip in tmp_ip:
                                        ip.append(self.rmv_empty(each_ip))

                            # FAILFAST_INTF: Reports error message if any of the VM interface objects don't exist. Groups together all errors for each interface
                            if len(intf_err) != 0:
                                tmp_intf_err = defaultdict(dict)
                                tmp_ip_err = []
                                for intf, vlan_ip, err in intf_err:
                                    if isinstance(err, list):
                                        tmp_ip_err.append(vlan_ip)
                                    else:
                                        tmp_intf_err[intf].update(vlan_ip)
                                self.rc.print(":x: Virtual Machine [i red]{}[/i red] interface objects may not exist. Failed to get object.id for - {}".format(
                                               each_vm['name'], str(dict(tmp_intf_err)).replace('{', '').replace('}', '')))

                        # COMPLETE_VM: If not errors adds a dict of the VM objects (VM, INTF, IP) to the all VMs list
                        if len(intf_err) == 0:
                            all_vm.append(dict(vm=vm, intf=intf, ip=ip))

                    # FAILFAST_VM: Reports error message if any of the VM objects don't exist
                    elif len(vm_err) != 0:
                        tmp_errors = {}
                        for vm_name, err_obj, err in vm_err:
                            tmp_errors.update(err_obj)
                        self.rc.print(":x: Virtual Machine [i red]{}[/i red] objects may not exist. Failed to get object.id for - {}".format(vm_name,
                                      str(tmp_errors).replace('{', '').replace('}', '')))
            # FAILFAST_CLUSTER: Reports error message if Cluster does not exist
            elif len(clstr_err) != 0:
                for obj_type, name, err in clstr_err:
                    self.rc.print(":x: {} [i red]{}[/i red] may not exist. Failed to get object.id - {}".format(obj_type, name, err))
        # RETURN: Returns the new Data models
        return all_vm


########################################################## CREATE_VM: Creates the new VM  #########################################################
    def create_vm(self, dm):
        deploy_err = []

        #1a. CREATE_VM: Attempt to create the VM.
        vm_result = self.obj_create(dm['vm']['name'], 'virtualization.virtual_machines', dm['vm'], deploy_err)
        #1b. VM_ERROR: Failfast if errors have occurred or print success if no interfaces to be created.
        if len(deploy_err) != 0:
            self.rc.print(":x: Virtual Machine [i red]{}[/i red] {} failed because of the following attribute errors - {}".format(dm['vm']['name'],
                            deploy_err[0]['task_type'], str(list(deploy_err[0].values())[0]).replace('{', '').replace('}', '').replace('[', '').replace(']', '')))
        elif len(deploy_err) == 0:
            #1c. VM_ONLY_SUCCESS: If are no interfaces defined prints VM creation message with the attributes added
            if len(dm['intf']) == 0:
                self.rc.print(":white_heavy_check_mark: Virtual Machine [i green]{}[/i green] successfully {}d with the attributes [i]{}[/i]".format(vm_result[1],
                              vm_result[0], str(list(dm['vm'].keys())).replace('[', '').replace(']', '')))
        return dict(vm_result=vm_result, deploy_err=deploy_err)


################################################# UPDATE_VM: Updates an already existing VM ################################################
    def update_vm(self, dm, vm_exist):
        deploy_err = []
        vm_result = None

        #1a. UPDATE_VM: Only needs to update the VM if it has attributes to change, so if it has more than 4 (name, clstr_name, cluster and site)
        if len(dm['vm']) > 4:
            vm_result = self.obj_update(dm['vm']['name'], vm_exist, dm['vm'], deploy_err)
        else:
            vm_result = ['update', vm_exist]       # Replicates what would be returned by obj_update
        #1b. VM_ERROR: Failfast if errors have occurred or print success if no interfaces to be created.
        if len(deploy_err) != 0:
            self.rc.print(":x: Virtual Machine [i red]{}[/i red] {} failed because of the following attribute errors - {}".format(dm['vm']['name'],
                            deploy_err[0]['task_type'], str(list(deploy_err[0].values())[0]).replace('{', '').replace('}', '').replace('[', '').replace(']', '')))
        elif len(deploy_err) == 0:
            #1c. VM_ONLY_SUCCESS: If are no interfaces defined and something has been changed prints VM creation message with the attributes added
            if len(dm['intf']) == 0:
                if len(dm['vm']) > 4:
                    del dm['vm']['name'], dm['vm']['clstr_name'], dm['vm']['cluster'], dm['vm']['site']             # To get list just of the attributed added or updated
                    self.rc.print(":white_heavy_check_mark: Virtual Machine [i green]{}[/i green] successfully {}d with the attributes [i]{}[/i]".format(vm_result[1],
                                    vm_result[0], str(list(dm['vm'].keys())).replace('[', '').replace(']', '')))
        return dict(vm_result=vm_result, deploy_err=deploy_err)


##################################### CREATE_OR_UPDATE_INTF: Creates new VM interfaces or updates existing ones ###################################
    def crte_upte_intf(self, dm, vm_exist, vm_result, deploy_err):
        intf_result = []

        for each_intf in dm['intf']:
            # 1. CHK_EXIST: Checks if interface exists to know whether to create a new interface or updates an existing one
            intf_exist = self.chk_exist('virtualization.interfaces', 'name', each_intf['name'], 'virtual_machine_id', vm_result[1].id, each_intf['name'])
            #2a. CREATE_INTF: Created individually so that error messages can have the interface name
            if intf_exist == None:
                intf_result.append(self.obj_create(each_intf['name'], 'virtualization.interfaces', each_intf, deploy_err))
            #2b. UPDATE_INTF: Update existing interface. If goes from access (untagged) to trunk (tagged) port need to remove the untagged VLAN
            elif intf_exist != None:
                if each_intf.get('mode') == 'tagged':
                    each_intf['untagged_vlan'] = None
                intf_result.append(self.obj_update(each_intf['name'], intf_exist, each_intf, deploy_err))

        #3a. INTF_ERROR: Failfast if errors have occurred during attempt to create or update the VM interfaces. If new VM deletes the VM
        if len(deploy_err) != 0:
            if vm_exist == None:
                vm_result[1].delete()
            for deploy_type, intf_err in self.format_rslt_err(deploy_err).items():
                self.rc.print(":x: Virtual Machine [i red]{}[/i red] interface {} failed - {}".format(dm['vm']['name'], deploy_type,
                                str(intf_err).replace('{', '').replace('}', '').replace('[', '').replace(']', '')))
        elif len(deploy_err) == 0:
            #2c. INTF_ONLY_SUCCESS: If are no IP addresses defined prints VM creation message with the interfaces added. Different message for new or existing VMs
            if len(dm['ip']) == 0:
                for deploy_type, intf in self.format_rslt_err(intf_result).items():
                    if vm_exist == None:
                        self.rc.print(":white_heavy_check_mark: Virtual Machine [i green]{}[/i green] successfully {}d with interfaces [i]{}[/i]".format(dm['vm']['name'],
                                deploy_type, str(intf).replace('{', '').replace('}', '').replace('[', '').replace(']', '')))
                    elif vm_exist != None:
                        # Only displays if is a change, so more than just interface 'name' in dict (reason why 'virtual_machine' is removed)
                        del each_intf['virtual_machine']
                        if len(each_intf) > 1:
                            self.rc.print(":white_heavy_check_mark: Virtual Machine [i green]{}[/i green] {}d interfaces [i]{}[/i]".format(dm['vm']['name'],
                                        deploy_type, str(intf).replace('{', '').replace('}', '').replace('[', '').replace(']', '')))
        return dict(intf_result=intf_result, deploy_err=deploy_err)

######################### CREATE_OR_UPDATE_IP: Creates new VM interface IP address or adds existing one to a VM interfaces ##########################
    def crte_upte_ip(self, dm, vm_exist, vm_result, intf_result, deploy_err):
        ip_result = []

        #1a. GET_ID: Gets the interface ID and the prefix ID if the prefix already exists
        for each_ip in dm['ip']:
            each_ip['interface'] = self.get_single_fltr_id('virtualization.interfaces', 'name', each_ip['intf_name']['name'], 'virtual_machine_id',
                                                                vm_result[1].id, each_ip['address'], deploy_err)
            each_ip['ip_obj'] = self.chk_exist('ipam.ip_addresses', 'address', each_ip['address'], 'vrf_id', each_ip['vrf'], each_ip['vrf_name'])
        #1b. GET_ID_ERR: Failfast and delete the newly created VM if errors have occurred during attempt to get IDs
        if len(deploy_err) != 0:
            vm_result[1].delete()
            self.rc.print(":x: Virtual Machine [i red]{}[/i red] IP address interface ID lookup failed - {}".format(dm['vm']['name'],
                            str(deploy_err).replace('[', '').replace(']', '')))

        #2a. ADD_ASSIGN_IP: Either create IP and assign to interface or if IP already exists assign it to the interface
        elif len(deploy_err) == 0:
            for each_ip in dm['ip']:
                if each_ip['ip_obj'] == None:
                    tmp_ip_result = self.obj_create(each_ip['address'], 'ipam.ip_addresses', each_ip, deploy_err)
                elif each_ip['ip_obj'] != None:
                    tmp_ip_result = self.obj_update(each_ip['address'], each_ip['ip_obj'], each_ip, deploy_err)
                # 2b. PRIMARY_IP: If it is the primary IP address updates the VM with the details
                if len(deploy_err) == 0:
                    if each_ip['sec_ip'] == False:
                        self.obj_update(dm['vm']['name'], vm_result[1], {"primary_ip4": tmp_ip_result[1].id}, deploy_err)
                    ip_result.append(tmp_ip_result)
        # 2c. IP_ERR: Failfast if errors have occurred during attempt to create or update the VM interface IPs. If new VM deletes the VM
        if len(deploy_err) != 0:
            if vm_exist == None:
                vm_result[1].delete()
            for deploy_type, intf_err in self.format_rslt_err(deploy_err).items():
                self.rc.print(":x: Virtual Machine [i red]{}[/i red] IP address {} failed - {}".format(dm['vm']['name'], deploy_type,
                                str(intf_err).replace('{', '').replace('}', '').replace('[', '').replace(']', '')))
        #2d. VM_INTF_IP_SUCCESS: Prints success message with details of VM, interfaces and IP addresses added. Different message for new or existing VMs
        elif len(deploy_err) == 0:
            all_intf = self.format_rslt_err(intf_result)
            all_ip = self.format_rslt_err(ip_result)
            if vm_exist == None:
                self.rc.print(":white_heavy_check_mark: Virtual Machine [i green]{}[/i green] successfully created with interfaces [i]{}[/i] and IPs [i]{}[/i]".format(
                                dm['vm']['name'], (str(list(all_intf.values()))).replace('[', '').replace(']', ''), (str(list(all_ip.values()))).replace('[', '').replace(']', '')))
            elif vm_exist != None:
                self.rc.print(":white_heavy_check_mark: Virtual Machine [i green]{}[/i green] updated with interfaces [i]{}[/i] and IPs [i]{}[/i]".format(
                                dm['vm']['name'], (str(list(all_intf.values()))).replace('[', '').replace(']', ''), (str(list(all_ip.values()))).replace('[', '').replace(']', '')))


################################################# ENGINE: Runs the methods of the script #################################################
def main():
    #1. LOAD: Opens netbox connection and loads the variable file
    script, first = argv
    nbox = Nbox()
    #2. DM: Create Data-Model for API calls. Has catchall of exit if empty as no changes need to be made
    dm = nbox.create_dm()
    if len(dm) == 0:
        exit()

    #3a. VM: First checks whether the VM already exists and either creates new VM or updates existing VM if changes
    vm_info, intf_info = ({} for i in range(2))                         # Empty dicts to stop erroring
    for each_vm in dm:
        vm_exist = nbox.chk_exist('virtualization.virtual_machines', 'name', each_vm['vm']['name'], 'cluster', each_vm['vm']['cluster'], each_vm['vm']['clstr_name'])
    #3b. CREATE_VM: Created on a one-by-one basis so that all VM elements (VM_ATTR, INTF & IP) are created at same iteration to allow for easier reporting and rollback
        if vm_exist == None:
            vm_info = nbox.create_vm(each_vm)
    #3c. UPDATE_VM: Updated on a one-by-one basis so that all VM elements (VM_ATTR, INTF & IP) are created at same iteration to allow for easier reporting
        elif vm_exist != None:
            vm_info = nbox.update_vm(each_vm, vm_exist)

    #4. CREATE_UPDATE_INTF: If VM creation or update was successful creates and/or updates (if interface already exist) all interfaces and L2 settings
        if len(each_vm['intf']) != 0:
            if len(vm_info.get('deploy_err', ['dummy'])) == 0:
                intf_info = nbox.crte_upte_intf(each_vm, vm_exist, vm_info['vm_result'], vm_info['deploy_err'])

            #5. CREATE_UPDATE_IP: If VM and INTF creation and/or update was successful creates (if IP doesn't exist) and associates IP addresses to interfaces
                if len(each_vm['ip']) != 0:
                    if len(intf_info.get('deploy_err', ['dummy'])) == 0:
                        nbox.crte_upte_ip(each_vm, vm_exist, vm_info['vm_result'], intf_info['intf_result'], intf_info['deploy_err'])

if __name__ == '__main__':
    main()

