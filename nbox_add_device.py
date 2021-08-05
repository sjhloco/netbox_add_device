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


############################ NBOX_API: Opens netbox connection and performs API requests ############################
class NboxApi():
    def __init__(self, rc):
        self.nb = pynetbox.api(url=netbox_url, token=token)
        self.rc = rc


################### Make changes in Netbox ###################
    ### OBJ_CREATE: Create objects and return output and whether changed (T or F) in list or errors in dictionary
    def obj_create(self, obj_name, api_attr, input_obj, error):
        try:
            result = operator.attrgetter(api_attr)(self.nb).create(input_obj)
            return ['create', result, True]       # result returns device name for stdout
        except RequestError as e:
            error.append({obj_name: ast.literal_eval(e.error), 'task_type': 'create'})


    ### OBJ_UPDATE: Update objects return output and whether changed (T or F) in list or errors in dictionary
    def obj_update(self, obj_name, nbox_obj, input_obj, error):
        try:
            result = nbox_obj.update(input_obj)
            return ['update', nbox_obj, result]     # pynetbox obj returns device name, result (T or F) whether updated
        except RequestError as e:
            error.append({obj_name: ast.literal_eval(e.error), 'task_type': 'update'})


    ### OBJ_DELETE: Deletes object, api_obj is pynetbox object (vm) and ask_type informational
    def obj_delete(self, api_obj, task_type):
        try:
            api_obj.delete()
        except Exception as e:
            self.rc.print(":x: [red]def {}[/red] error deleting [i red]{}[/i red] for task {}".format(
                          'obj_delete', str(api_obj), task_type))


################### GET information from Netbox (object IDs) ###################
    ### GET_MULTI_ID: Gets IDs of primary object (input_obj) and secondary object (other_obj_type) within primary object
    def get_multi_id(self, api_attr, input_obj, input_obj_type, other_obj_type, error):
        result = {}

        try:
            result[input_obj_type] = operator.attrgetter(api_attr)(self.nb).get(name=input_obj).id
            # If the secondary object (other_obj) is defined also gets that objects ID
            if operator.attrgetter(other_obj_type)(operator.attrgetter(api_attr)(self.nb).get(name=input_obj)) != None:
                result[other_obj_type] = operator.attrgetter(other_obj_type)(operator.attrgetter(api_attr)(self.nb)
                                         .get(name=input_obj)).id
            return result
        except AttributeError as e:
            error.append((api_attr.split('.')[1].capitalize()[:-1], input_obj, e))
        # Catch-all for any other error
        except Exception as e:
            self.rc.print(":x: [red]def {}[/red] using {} [i red]{}[/i red] - {}".format('get_multi_id',
                          api_attr.split('.')[1].capitalize()[:-1], input_obj, e))
            exit()


    ### GET_SINGLE_ID: Gets the ID for a single primary object (input_obj)
    def get_single_id(self, vm_name, api_attr, input_obj, error):
        try:
            obj_id = operator.attrgetter(api_attr)(self.nb).get(name=input_obj).id
            return obj_id
        except AttributeError as e:         # Errors are a list within a dictionary of the VM name
            error.append((vm_name, {api_attr.split('.')[1].capitalize()[:-1]: input_obj}, e))
        # Catch-all for any other error
        except Exception as e:
            self.rc.print(":x: [red]def {}[/red] using {} object [i red]{}[/i red] - {}".format('get_single_id',
                          api_attr.split('.')[1].capitalize()[:-1], input_obj, e))
            exit()


    ### GET_SINGLE_FLTR_ID: Gets the ID for a single primary object (input_obj) based on name and its container (cntr)
    def get_single_fltr_id(self, api_attr, input_obj_fltr, input_obj, obj_cntr_fltr, obj_cntr_id, obj_cntr_name, error):
        try:
            return operator.attrgetter(api_attr)(self.nb).get(**{input_obj_fltr: input_obj, obj_cntr_fltr: obj_cntr_id}).id
        except AttributeError as e:
            error.append({input_obj + '(' + obj_cntr_name + ')': str(e), 'task_type': 'update'})
        # Catch-all for any other error
        except Exception as e:
            self.rc.print(":x: [red]def {}[/red] using {} object [i red]{}[/i red] - {}".format('get_single_fltr_id',
                          api_attr.split('.')[1].capitalize()[:-1], input_obj, e))
            exit()


    ### GET_VLAN_ID: Gets the VLAN group slug used to get single VLAN ID or create a list of all VLAN IDs
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
            self.rc.print(":x: [red]def {}[/red] with VLANs [i red]{}[/i red] in VLAN group [i]{}[/i] - {}".format(
                          'get_vlan_id', vlan, vl_grp, e))
            exit()


    ### CHK_EXIST: Check if object name already exists (VM or IP address) within the container (cluster or VRF)
    def chk_exist(self, api_attr, input_obj_fltr, input_obj, obj_cntr_fltr, obj_cntr_id, obj_cntr_name):
        try:
            return operator.attrgetter(api_attr)(self.nb).get(**{input_obj_fltr: input_obj, obj_cntr_fltr: obj_cntr_id})
        # Catch-all for any other error
        except Exception as e:
            self.rc.print(":x: [red]def {}[/red] using {} [i red]{}[/i red] in {} [i]{}[/i] - {}".format('chk_exist',
                        api_attr.split('.')[1].capitalize()[:-1], input_obj, obj_cntr_fltr, obj_cntr_name, e))
            exit()


############################# CREATE_DM: Ensures objects don't already exist & creates the DMs for API call ############################
class CreateDm():
    def __init__(self, nbox, rc):
        self.rc = rc
        self.nbox = nbox
        with open(argv[1], 'r') as file_content:
            self.my_vars = yaml.load(file_content, Loader=yaml.FullLoader)


    ### CREATE_VM_DM: Creates the data-model with all options for creating the VM
    def create_vm(self, clstr_site, each_clstr, each_vm, tmp_vm):
        vm = dict(name=each_vm['name'], clstr_name=each_clstr['name'], cluster=clstr_site['clstr'], site=clstr_site.get('site', None),
                    tenant=tmp_vm.get('tenant', None), role=tmp_vm.get('role', None), platform=tmp_vm.get('platform', None),
                    vcpus=each_vm.get('cpu', None), memory=each_vm.get('mem', None), disk=each_vm.get('disk', None),
                    comments=each_vm.get('comments', ''), tags=each_vm.get('tags', []))
        return vm


    ### REMOVE_EMPTY: Removes any empty attributes from the VM
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


    ### CREATE_INTF_DM: Creates the data-models to be used to create the VM interface (interface and IP)
    def create_intf_dm(self, tmp_intf_dict, each_vm, each_intf, tmp_vm, intf, ip):
        tmp_intf, tmp_ip = ([] for i in range(2))

        if tmp_intf_dict.get('vlan') == None:
            tmp_intf.append(dict(virtual_machine=dict(name=each_vm['name']), name=each_intf['name'], tags=each_intf.get('tags', [])))
        elif isinstance(tmp_intf_dict['vlan'], int):
            tmp_intf.append(dict(virtual_machine=dict(name=each_vm['name']), name=each_intf['name'], mode='access',
                                 untagged_vlan=tmp_intf_dict['vlan'], tags=each_intf.get('tags', [])))
        elif isinstance(tmp_intf_dict['vlan'], list):
            tmp_intf.append(dict(virtual_machine=dict(name=each_vm['name']), name=each_intf['name'], mode='tagged',
                                 tagged_vlans=tmp_intf_dict['vlan'], tags=each_intf.get('tags', [])))
        # CREATE_IP_DM: Creates the data-models to be used to create the IP addresses
        if each_intf.get('vrf_ip', None) != None:
            tmp_ip.append(dict(address=each_intf['vrf_ip'][1], tenant=tmp_vm.get('tenant', None), vrf_name=each_intf['vrf_ip'][0],
                               vrf=tmp_intf_dict['vrf'], intf_name=dict(name=each_intf['name']), dns_name=each_intf.get('dns', ''),
                               sec_ip=each_intf.get('secondary_ip', False), tags=each_intf.get('tags', [])))
        return tmp_intf, tmp_ip


    ### VM_ERROR: Reports errors if any VM or VM interface objects don't exist (groups interfaces together together to report in one line)
    def vm_error(self, vm_name, input_err):
        tmp_err = defaultdict(dict)

        for name, err_obj, err in input_err:
            if name == vm_name:
                tmp_err.update(err_obj)
            else:
                tmp_err[name].update(err_obj)
        self.rc.print(":x: Virtual Machine [i red]{}[/i red] interface objects may not exist. Failed to get object.id for - {}".
                      format(vm_name, str(dict(tmp_err)).replace('{', '').replace('}', '')))


   ### ENGINE: Run all the other methods in this class to build API call to create VMs, interfaces and IPs
    def engine(self):
        all_vm = []

        # CLUSTER_SITE: Get the cluster and site ID (if is a site in cluster). If cluster does not exist failfast and exit
        for each_clstr in self.my_vars['cluster']:
            clstr_err = []                       # Need to be reset each cluster iteration
            clstr_site = self.nbox.get_multi_id('virtualization.clusters', each_clstr['name'], 'clstr', 'site', clstr_err)

            # GET_OPTIONAL_OBJ: Gets the ID for all the optional variables that can be set for the VM
            if len(clstr_err) == 0:
                for each_vm in each_clstr['vm']:
                    vm_err, intf_err, intf, ip = ([] for i in range(4))         # Need to be reset each VM iteration
                    tmp_vm = {}
                    for obj, uri in dict(tenant='tenancy.tenants', role='dcim.device_roles', platform='dcim.platforms').items():
                        if each_vm.get(obj) != None:
                            tmp_vm[obj] = self.nbox.get_single_id(each_vm['name'], uri, each_vm[obj], vm_err)

                    # CREATE_VM_DM: If there are no errors builds the data-model for creating the VM
                    if len(vm_err) == 0:
                        vm = self.create_vm(clstr_site, each_clstr, each_vm, tmp_vm)
                        # CLEAN_DM: Removes any None values or empty lists
                        vm = self.rmv_empty(vm)
                        # GET_INTF_IP: Gathers object IDs (unique VLAN in GRP or IP in VRF) to create VM interfaces and associated IPs
                        if each_vm.get('intf', None) != None:
                            for each_intf in each_vm['intf']:
                                tmp_intf_dict = {}
                                if each_intf.get('grp_vl') != None:
                                    tmp_intf_dict['vlan'] = self.nbox.get_vlan_id(each_intf['name'], each_intf['grp_vl'][0],
                                                                             each_intf['grp_vl'][1], intf_err)
                                if each_intf.get('vrf_ip', None) != None:
                                    tmp_intf_dict['vrf'] = self.nbox.get_single_id(each_intf['name'], 'ipam.vrfs',
                                                                                   each_intf['vrf_ip'][0], intf_err)
                                # CREATE_INTF_DM: If are no errors creates the data-models to be used to create the interface
                                if len(intf_err) == 0:
                                    tmp_intf_ip = self.create_intf_dm(tmp_intf_dict, each_vm, each_intf, tmp_vm, intf, ip)
                                    # CLEAN_DM: Removes any None values or empty lists
                                    for each_intf in tmp_intf_ip[0]:
                                        intf.append(self.rmv_empty(each_intf))
                                    for each_ip in tmp_intf_ip[1]:
                                        ip.append(self.rmv_empty(each_ip))

                            # FAILFAST_INTF: Reports error message if any of the VM interface objects don't exist
                            if len(intf_err) != 0:
                                self.vm_error(each_vm['name'], intf_err)
                        # COMPLETE_VM: If not errors adds a dict of the VM objects (VM, INTF, IP) to the all VMs list
                        if len(intf_err) == 0:
                            all_vm.append(dict(vm=vm, intf=intf, ip=ip))
                    #FAILFAST_VM: Reports error message if any of the VM objects don't exist
                    elif len(vm_err) != 0:
                        self.vm_error(each_vm['name'], vm_err)
            # FAILFAST_CLUSTER: Reports error message if Cluster does not exist
            elif len(clstr_err) != 0:
                for obj_type, name, err in clstr_err:
                    self.rc.print(":x: {} [i red]{}[/i red] may not exist. Failed to get object.id - {}".format(obj_type, name, err))
        return all_vm


############################################### CREATE_OBJ Creates or updates VM, interface and IP  ###############################################
class CreateObject():
    def __init__(self, nbox, rc):
        self.rc = rc
        self.nbox = nbox


################### STDOUT and formatting ###################
    ### FORMAT_RSLT_ERR: Combines interface/ip error or result messages into dicts so easier to use in STDOUT messages
    def format_rslt_err(self, input_list):
        output_dict = defaultdict(list)

        for each_ele in input_list:
            try:                                # If it is an error (deploy_err)
                output_dict['deploy_type'] = each_ele.pop('task_type')
                output_dict['err'].append(each_ele)
            except:                             # If it is a result (intf_result or ip_result)
                if each_ele[2] is True:         # pynetbox returns True if anything was changed
                    output_dict['deploy_type'] = each_ele[0]
                    output_dict['details'].append(each_ele[1])
                    output_dict['changed'] = True
        return output_dict


    ### STDOUT_INTF_IP: formats the out put for interface or IP displayed message
    def format_stdout_intf_ip(self, obj_type, input_rslt):
        tmp_obj_list = []

        for each_obj in input_rslt['details']:
            tmp_obj_list.append(str(each_obj))
        input_rslt['details'] = str(tmp_obj_list).replace('[', '').replace(']', '')
        input_rslt['details'] = '[b #000000]{}:[/b #000000] [i]{}[/i]'.format(obj_type, input_rslt['details'])
        return input_rslt


    ### VM_STDOUT: Prints out message for the user dependant on an error or the task perfromed on a VM
    def crte_upte_stdout(self, obj_type, vm_exist, dm, deploy_err, vm_result, intf_result={}, ip_result={}):
        if len(deploy_err) != 0:

            # INTF_IP_ERROR: If new VM and has errors with interfaces deletes the VM and changes displayed error msg
            if vm_exist == None and obj_type != 'vm':
                self.nbox.obj_delete(vm_result[1], 'crte_upte_' + obj_type)
                obj_type = 'vm and ' + obj_type
            # VM_INTF_IP_ERROR: Prints message if errors with VM attributes, interfaces or IPs
            err = self.format_rslt_err(deploy_err)
            self.rc.print(":x: Virtual Machine [i red]{}[/i red] {} {} failed - {}".format(dm['vm']['name'], obj_type,
                         err['deploy_type'], str(err['err']).replace('{', '').replace('}', '').replace('[', '')
                         .replace(']', '').replace("'interface': ",  '')))

        elif len(deploy_err) == 0:
            # Results of the API calls used to dictate whether VM, interface or IP has changed
            vm_rslt = dict(changed=vm_result[2])
            intf_rslt = self.format_rslt_err(intf_result)
            ip_rslt = self.format_rslt_err(ip_result)

            # STDOUT_NO_CHANGE: If nothing change, False for VM, interface and IP changes
            if vm_rslt['changed'] == False and intf_rslt.get('changed', False) == False and ip_rslt.get('changed', False) == False:
                self.rc.print("\u26A0\uFE0F  Virtual Machine [i yellow]{}[/i yellow] already exists with the correct details".
                                format(vm_result[1]))
            else:
                # VM_VAR: If VM created or updated remove unneeded attributes and create variable of changes
                if vm_rslt['changed'] == True:
                    del dm['vm']['name'], dm['vm']['clstr_name'], dm['vm']['cluster'], dm['vm']['site']
                    vm_rslt = dict(details=str(list(dm['vm'].keys())).replace('[', '').replace(']', ''))
                    vm_rslt['details'] = '[b #000000]attributes:[/b #000000] [i]{}[/i]'.format(vm_rslt['details'])
                # INTF_IP_VAR: If Interface or IP created/updated create variable of changes
                if intf_rslt.get('changed', False) == True:
                    self.format_stdout_intf_ip('interfaces', intf_rslt)
                if ip_rslt.get('changed', False) == True:
                    self.format_stdout_intf_ip('IP addresses', ip_rslt)
                # STDOUT_CHANGE: Prints out message for user with result dependant tasks were perfromed (early variables)
                self.rc.print(":white_heavy_check_mark: Virtual Machine [i green]{}[/i green] {}d with {} {} {}".format(
                              vm_result[1], vm_result[0], vm_rslt.get('details', ''), intf_rslt.get('details', ''),
                              ip_rslt.get('details', '')))


################### CREATE or UPDATE objects ###################
    ### CREATE_VM: Creates the VM with all attributes except interfaces and IPs
    def create_vm(self, dm, vm_exist):
        deploy_err = []

        vm_result = self.nbox.obj_create(dm['vm']['name'], 'virtualization.virtual_machines', dm['vm'], deploy_err)
        # STDOUT: Only print message if error or no interfaces defined
        if len(deploy_err) != 0 or len(dm['intf']) == 0:
            self.crte_upte_stdout('vm', vm_exist, dm, deploy_err, vm_result)
        return dict(vm_result=vm_result, deploy_err=deploy_err)


    ### UPDATE_VM: Updates VM if already exists and something has changed
    def update_vm(self, dm, vm_exist):
        deploy_err = []
        vm_result = None

        # UPDATE_VM: Only needs to update the VM if it has attributes to change, so if it has more than 4 (name, clstr_name, cluster and site)
        if len(dm['vm']) > 4:
            vm_result = self.nbox.obj_update(dm['vm']['name'], vm_exist, dm['vm'], deploy_err)
        else:
            vm_result = ['update', vm_exist, False]       # Replicates what would be returned by nbox.obj_update
        # STDOUT: Only print message if error or no interfaces defined
        if len(deploy_err) != 0 or len(dm['intf']) == 0:
            self.crte_upte_stdout('vm', vm_exist, dm, deploy_err, vm_result)
        return dict(vm_result=vm_result, deploy_err=deploy_err)


    ### CREATE_OR_UPDATE_INTF: Creates new VM interfaces or updates existing ones
    def crte_upte_intf(self, dm, vm_exist, vm_result, deploy_err):
        intf_result = []

        for each_intf in dm['intf']:
            # CHK_EXIST: Checks if interface exists to know whether to create new or update existing interface
            intf_exist = self.nbox.chk_exist('virtualization.interfaces', 'name', each_intf['name'], 'virtual_machine_id',
                                        vm_result[1].id, each_intf['name'])
            # CREATE_INTF: Created individually so that error messages can have the interface name
            if intf_exist == None:
                intf_result.append(self.nbox.obj_create(each_intf['name'], 'virtualization.interfaces', each_intf, deploy_err))
            # UPDATE_INTF: Update existing interface. If goes from access (untagged) to trunk (tagged) removes untagged VLAN
            elif intf_exist != None:
                if each_intf.get('mode') == 'tagged':
                    each_intf['untagged_vlan'] = None
                del each_intf['virtual_machine'], each_intf['name']
                intf_result.append(self.nbox.obj_update(str(intf_exist), intf_exist, each_intf, deploy_err))
        # STDOUT: Prints error messages or if no IPs success or no changes message
        if len(deploy_err) != 0 or len(dm['ip']) == 0:
            self.crte_upte_stdout('interface', vm_exist, dm, deploy_err, vm_result, intf_result)
        return dict(intf_result=intf_result, deploy_err=deploy_err)


    ### CREATE_OR_UPDATE_IP: Creates new VM interface IP address or adds existing one to a VM interfaces
    def crte_upte_ip(self, dm, vm_exist, vm_result, intf_result, deploy_err):
        ip_result = []

        # GET_ID: Gets the interface ID and the prefix ID if the prefix already exists
        for each_ip in dm['ip']:
            each_ip['interface'] = self.nbox.get_single_fltr_id('virtualization.interfaces', 'name', each_ip['intf_name']['name'],
                                                           'virtual_machine_id', vm_result[1].id, each_ip['address'], deploy_err)
            each_ip['ip_obj'] = self.nbox.chk_exist('ipam.ip_addresses', 'address', each_ip['address'], 'vrf_id', each_ip['vrf'],
                                               each_ip['vrf_name'])
        # GET_ID_ERR: Failfast and delete the newly created VM if errors have occurred during attempt to get IDs
        if len(deploy_err) != 0:
            self.crte_upte_stdout('ip', vm_exist, dm, deploy_err, vm_result, intf_result)
        # ADD_ASSIGN_IP: Either create IP and assign to interface or if IP already exists assign it to the interface
        elif len(deploy_err) == 0:
            for each_ip in dm['ip']:
                if each_ip['ip_obj'] == None:
                    tmp_ip_result = self.nbox.obj_create(each_ip['address'], 'ipam.ip_addresses', each_ip, deploy_err)
                elif each_ip['ip_obj'] != None:
                    tmp_ip_result = self.nbox.obj_update(each_ip['address'], each_ip['ip_obj'], each_ip, deploy_err)
                # PRIMARY_IP: If it is the primary IP address updates the VM with the details
                if len(deploy_err) == 0:
                    if each_ip['sec_ip'] == False:
                        self.nbox.obj_update(dm['vm']['name'], vm_result[1], {"primary_ip4": tmp_ip_result[1].id}, deploy_err)
                    ip_result.append(tmp_ip_result)
        self.crte_upte_stdout('ip', vm_exist, dm, deploy_err, vm_result, intf_result, ip_result)


   ### ENGINE: Run all the other methods in this class to perform API calls to create VMs, interfaces and IPs
    def engine(self, dm):
        vm_info, intf_info = ({} for i in range(2))

        # CHECK_VM: First checks whether the VM already exists and either creates new VM or updates existing VM if changes
        for each_vm in dm:
            vm_exist = self.nbox.chk_exist('virtualization.virtual_machines', 'name', each_vm['vm']['name'], 'cluster',
                                           each_vm['vm']['cluster'], each_vm['vm']['clstr_name'])
            # CREATE_UPDATE_VM: Done one at a time with all elements created at same iteration for easier reporting and rollback
            if vm_exist == None:
                vm_info = self.create_vm(each_vm, vm_exist)
            elif vm_exist != None:
                vm_info = self.update_vm(each_vm, vm_exist)
            # CREATE_UPDATE_INTF: If VM create/update successful creates and/or updates (if interface already exist) interfaces
            if len(each_vm['intf']) != 0:
                if len(vm_info.get('deploy_err', ['dummy'])) == 0:
                    intf_info = self.crte_upte_intf(each_vm, vm_exist, vm_info['vm_result'], vm_info['deploy_err'])
            # CREATE_UPDATE_IP: If VM and INTF create/update successful creates (if IP doesn't exist) and associates IP to interfaces
                if len(each_vm['ip']) != 0:
                    if len(intf_info.get('deploy_err', ['dummy'])) == 0:
                        self.crte_upte_ip(each_vm, vm_exist, vm_info['vm_result'], intf_info['intf_result'], intf_info['deploy_err'])


################################################# ENGINE: Runs the methods of the script ###########################################
def main():
    #1. LOAD: Opens netbox connection and loads the variable file
    script, first = argv
    rc = Console(theme=Theme({"repr.str": "black italic", "repr.ipv4": "black italic", "repr.number": "black italic"}))
    nbox = NboxApi(rc)

    #2. DM: Create Data-Model for API calls. Has catchall of exit if empty as no changes need to be made
    create_dm = CreateDm(nbox, rc)
    dm = create_dm.engine()
    if len(dm) == 0:
        exit()

    #3. NBOX: Create or update VMs using nbox API
    create_obj = CreateObject(nbox, rc)
    create_obj.engine(dm)

if __name__ == '__main__':
    main()

