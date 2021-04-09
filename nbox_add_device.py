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
from pprint import pprint
from collections import defaultdict

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


############################ OBJ_CREATE: API engine to create objects or error based on the details fed into it ############################
    def obj_create(self, obj_name, api_attr, input_obj, all_results, error):
        try:
            result = operator.attrgetter(api_attr)(self.nb).create(input_obj)
            all_results.append({api_attr.split('.')[1].capitalize()[:-1]: input_obj})
            return result
        except RequestError as e:
            error.append({obj_name: ast.literal_eval(e.error)})


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
            print("{} {} - Method '{}' with {} object '{}'".format(u'\u274c', e, 'get_multi_id', api_attr.split('.')[1].capitalize()[:-1], input_obj))
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
            print("{} {} - Method '{}' with {} object '{}'".format(u'\u274c', e, 'get_single_id', api_attr.split('.')[1].capitalize()[:-1], input_obj))
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

    # EXIST: Checks whether an objected with that name already exists (VM or IP address) within the container (cluster or VRF)
    def chk_exist(self, api_attr, input_obj_fltr, input_obj, obj_container_fltr, obj_container_id, obj_container_name, error):
        try:
            if operator.attrgetter(api_attr)(self.nb).get(**{input_obj_fltr: input_obj, obj_container_fltr: obj_container_id}) != None:
                error.append((api_attr.split('.')[1].capitalize()[:-1], input_obj, [obj_container_fltr, obj_container_name]))
        # Catch-all for any other error
        except Exception as e:
            print("{} {} - Method '{}' with VLANs {} in VLAN group '{}'".format(u'\u274c', e, 'chk_exist', api_attr.split('.')[1].capitalize()[:-1], input_obj))
            exit()


############################# DM_CREATE: Ensures that objects don't already exist and creates the DMs ready for API call to add VMs, INTF and IP ############################
    def create_dm(self):
        all_vm = {}
        # CLUSTER_SITE: Get the cluster and site ID (if there is a site in cluster). If cluster does not exist does failfast and exist playbook
        for each_clstr in self.my_vars['cluster']:
            clstr_err = []
            clstr_site = self.get_multi_id('virtualization.clusters', each_clstr['name'], 'clstr', 'site', clstr_err)

            # OPTIONAL_OBJ: Gets the ID for all the optional variables that can be set for the VM
            if len(clstr_err) == 0:
                for each_vm in each_clstr['vm']:
                    vm_err = []
                    tmp_vm = {}

                    # CHK_OBJ_EXIST: Check the VM does not already exist in the cluster
                    self.chk_exist('virtualization.virtual_machines', 'name', each_vm['name'], 'cluster', clstr_site['clstr'], each_clstr['name'], vm_err)
                    # GET_OBJ_ID: Gets ID of the optional objects
                    if each_vm.get('tenant') != None:
                        tmp_vm['tenant'] = self.get_single_id(each_vm['name'], 'tenancy.tenants', each_vm['tenant'], vm_err)
                    if each_vm.get('role') != None:
                        tmp_vm['role'] = self.get_single_id(each_vm['name'], 'dcim.device_roles', each_vm['role'], vm_err)
                    if each_vm.get('platform') != None:
                        tmp_vm['platform'] = self.get_single_id(each_vm['name'], 'dcim.platforms', each_vm['platform'], vm_err)

                    # CREATE_VM_DM: If there are no errors creates the data-model for creating the VM
                    if len(vm_err) == 0:
                        vm = dict(name=each_vm['name'], cluster=clstr_site['clstr'], site=clstr_site.get('site', None),
                                  tenant=tmp_vm.get('tenant', None), role=tmp_vm.get('role', None), platform=each_vm.get('platform', None),
                                  vcpus=each_vm.get('cpu', None), memory=each_vm.get('mem', None), disk=each_vm.get('disk', None),
                                  comments=each_vm.get('comments', ''), tags=each_vm.get('tags', []))

                        # INTF_IP: Gathers object IDs for objects used to create VM interfaces and associated IP addresses
                        if each_vm.get('intf', None) != None:
                            intf_err, intf, ip = ([] for i in range(3))
                            for each_intf in each_vm['intf']:
                                tmp_intf = {}
                                # LAYER2: If set uses the vlan_group and VLAN ID to get the VLANs object ID
                                if each_intf.get('grp_vl') != None:
                                    tmp_intf['vlan'] = self.get_vlan_id(each_intf['name'], each_intf['grp_vl'][0], each_intf['grp_vl'][1], intf_err)
                                # LAYER3: If it is a Layer3 interface, so has an IP checks the VRF is valid and that the IP address does no already exist in that VRF
                                if each_intf.get('vrf_ip', None) != None:
                                    tmp_intf['vrf'] = self.get_single_id(each_intf['name'], 'ipam.vrfs', each_intf['vrf_ip'][0], intf_err)
                                    if tmp_intf.get('vrf') != None:
                                        self.chk_exist('ipam.ip_addresses', 'address', each_intf['vrf_ip'][1], 'vrf_id', tmp_intf['vrf'], each_intf['vrf_ip'][0], intf_err)

                                # CREATE_INTF_DM: If are no errors creates the data-models to be used to create the interface
                                if len(intf_err) == 0:
                                    if tmp_intf.get('vlan') == None:
                                        intf.append(dict(virtual_machine=dict(name=each_vm['name']), name=each_intf['name'], tags=each_intf.get('tags', [])))
                                    elif isinstance(tmp_intf['vlan'], int):
                                        intf.append(dict(virtual_machine=dict(name=each_vm['name']), name=each_intf['name'], mode='access', untagged_vlan=tmp_intf['vlan'], tags=each_intf.get('tags', [])))
                                    elif isinstance(tmp_intf['vlan'], list):
                                        intf.append(dict(virtual_machine=dict(name=each_vm['name']), name=each_intf['name'], mode='tagged', tagged_vlans=tmp_intf['vlan'], tags=each_intf.get('tags', [])))

                                    # CREATE_IP_DM: Creates the data-models to be used to create the IP addresses. If is the primary IP adds extra tag to be used popped and used at end
                                    if each_intf.get('vrf_ip', None) != None and each_intf.get('secondary_ip', None) == None:
                                        ip.append(dict(address=each_intf['vrf_ip'][1], vrf=tmp_intf['vrf'], tenant=tmp_vm.get('tenant', None), intf_name=dict(name=each_intf['name']),
                                                       dns_name=each_intf.get('dns', ''), tags=each_intf.get('tags', []), primary=True))
                                    elif each_intf.get('vrf_ip', None) != None:
                                        ip.append(dict(address=each_intf['vrf_ip'][1], vrf=tmp_intf['vrf'], tenant=tmp_vm.get('tenant', None), intf_name=dict(name=each_intf['name']),
                                                       dns_name=each_intf.get('dns', ''), tags=each_intf.get('tags', [])))

                            # FAILFAST_INTF: Reports error message if an IP address is already used or any of the VM interface objects don't exist
                            if len(intf_err) != 0:
                                tmp_intf_err = defaultdict(dict)
                                tmp_ip_err = []
                                # Groups all IP address errors and interfaces errors into their own lists or dictionaries so can group error messages
                                for intf, vlan_ip, err in intf_err:
                                    if isinstance(err, list):
                                        tmp_ip_err.append(vlan_ip)
                                    else:
                                        tmp_intf_err[intf].update(vlan_ip)
                                if len(tmp_ip_err) != 0:
                                    print("{}  IP Address: '{}' IP addresses '{}' already exist".format(u'\u26A0\uFE0F', each_vm['name'], tmp_ip_err))
                                if len(tmp_intf_err) != 0:
                                    print("{} Interface: '{}' interface objects may not exist. Failed to get object.id for {}".format(u'\u274c',
                                            each_vm['name'], dict(tmp_intf_err)))
                                exit()

                        # CREATE_VM: Are created on a one-by-one basis as all elements (VM, INTF & IP) created for each VM so can fail and remove if something cant be created
                        all_results, deploy_err = ([] for i in range(2))
                        vm_result = self.obj_create(each_vm['name'], 'virtualization.virtual_machines', vm, all_results, deploy_err)

                        # CREATE_INTF: Only creates interfaces if VM creation was successful. Created individually so  that error messages can have the interface name
                        if vm_result != None:
                            intf_result = []
                            for each_intf in intf:
                                tmp_intf_result = self.obj_create(each_intf['name'], 'virtualization.interfaces', each_intf, all_results, deploy_err)
                                intf_result.append(tmp_intf_result)

                            # CREATE_IP: Only creates IP addresses if VM and interfaces creation was successful. Each IP address created individually to get object ID to add primary interface
                            if len(deploy_err) == 0:
                                try:                        # Use try statement as doing direct API calls rather than through another method
                                    ip_result = []
                                    for each_ip in ip:
                                        # Gets the interface ID and uses that rather than the interface name when creating the IP address
                                        each_ip['interface'] = self.nb.virtualization.interfaces.get(name=each_ip['intf_name']['name'], virtual_machine_id=vm_result.id).id
                                        tmp_ip_result = self.obj_create(each_ip['intf_name']['name'], 'ipam.ip_addresses', each_ip, all_results, deploy_err)
                                        # If it is the primary IP address updates the VM with the details
                                        if each_ip.get('primary') != None:
                                            vm_obj = self.nb.virtualization.virtual_machines.get(vm_result.id)
                                            vm_obj.update({"primary_ip4": tmp_ip_result.id})
                                        ip_result.append(tmp_ip_result)
                                    # If IP address creation failed raise an exception
                                    if len(deploy_err) != 0:
                                        raise Exception()
                                    # Print message with details of VM created
                                    print("{} '{}' successfully created with interfaces {} and IPs {}".format(u'\u2705', vm_result,
                                          str(intf_result).replace("[","'" ).replace("]", "'"), str(ip_result).replace("[", "'").replace("]", "'")))

                                # INTF_ERROR: Errors that occurred during attempt to create the VM interfaces. Rollback the VM creation
                                except Exception as e:
                                    vm_result.delete()
                                    print("{} IP Address: '{}' creation failed because of the following IP address errors - {}".format(u'\u274c', each_vm['name'], deploy_err))
                            # INTF_ERROR: Errors that occurred during attempt to create the VM interfaces. Rollback the VM creation
                            else:
                                print("{} Interface: '{}' creation failed because of the following interface errors - {}".format(u'\u274c', each_vm['name'], deploy_err))
                                vm_result.delete()
                        # VM_ERROR: Errors that occurred during attempt to create the VM
                        else:
                            print("{} Virtual Machine: '{}' creation failed because of the following VM object errors - {}".format(u'\u274c', each_vm['name'], list(deploy_err[0].values())[0]))

                    # FAILFAST_VM: Reports error message if VM already exists or any of the VM objects don't exist or
                    elif len(vm_err) != 0:
                        tmp_errors = {}
                        for vm_name, err_obj, err in vm_err:
                            if isinstance(err, list):
                                print("{}  {}: '{}' already exists in {} '{}'".format(u'\u26A0\uFE0F', vm_name, err_obj, err[0], err[1]))
                            # Groups all object ID errors into the one error message
                            else:
                                tmp_errors.update(err_obj)
                        if len(tmp_errors) != 0:
                            print("{} Virtual Machine: '{}' objects may not exist. Failed to get object.id for {}".format(u'\u274c', each_vm['name'], tmp_errors))
                        exit()
            # FAILFAST_CLUSTER: Reports error message if Cluster does not exist
            elif len(clstr_err) != 0:
                for obj_type, name, err in clstr_err:
                    print("{} {}: '{}' may not exist, failed to get object.id - {}".format(u'\u274c', obj_type, name, err))
                exit()


######################## ENGINE: Runs the methods of the script ########################
def main():
    # Opens netbox connection and loads the variable file
    script, first = argv
    nbox = Nbox()
    nbox.create_dm()

if __name__ == '__main__':
    main()






#  nb.virtualization.virtual_machines.get(name='test1', cluster=dict(name='ESX Home'))
# self.nb.virtualization.virtual_machines.create(

# nb.virtualization.interfaces.create([{'virtual_machine': {'name': 'test'}, 'name': 'Port1', 'mode': 'tagged', 'tagged_vlans': [57, 58, 59], 'tags': []},
                                    #  {'virtual_machine': {'name': 'test'}, 'name': 'management', 'mode': 'access', 'untagged_vlan': 57, 'tags': []},
                                    #  {'virtual_machine': {'name': 'test'}, 'name': 'hme_untrust_vl30', 'tags': []}])


# nb.ipam.vlans.get(vid=5, group='30').id
# nb.ipam.ip_addresses.get(address='10.10.10.10/24', vrf_id='51')

# nb.ipam.ip_addresses.create([{'address': '10.10.10.11/24', 'vrf': 51, 'tenant': 20, 'interface': {'name': 'management'}, 'dns_name': 'hme-air-wlc01.stesworld.com', 'tags': []},
#                              {'address': '10.10.30.11/24', 'vrf': 51, 'tenant': None, 'interface': {'name': 'hme_untrust_vl30'}, 'dns_name': '', 'tags': []}])

