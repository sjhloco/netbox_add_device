########## After major refactor to add devices will no longer work, needs completely rewriting ##########


# import pytest
# from random import randint
# from rich.console import Console

# from nbox_add_device import NboxApi
# from nbox_add_device import CreateDm
# from nbox_add_device import CreateObject


# ############################ INZT_LOAD: Opens netbox connection and loads the variable file ############################


# # Fixture is run everytime pytest run to create variables from input file
# @pytest.fixture(scope="session", autouse=True)
# def load_input_attributes():
#     import yaml
#     import os
#     from rich.theme import Theme

#     rc = Console(theme=Theme({"repr.str": "black italic", "repr.ipv4": "black italic", "repr.number": "black italic"}))
#     argv = [None, os.path.join(os.path.dirname(__file__), 'test_files', 'test_yms.yml')]
#     with open(argv[1], 'r') as file_content:
#         my_vars = yaml.load(file_content, Loader=yaml.FullLoader)
#     global input_attr
#     input_attr = dict(argv=argv, my_vars=my_vars, rc=rc)

# # Fixtures to instanize the class that is being tested by the associated pytest class
# @pytest.fixture(scope="class")
# def instanize_createdm(load_input_attributes):
#     global create_dm
#     create_dm = CreateDm(None, input_attr['rc'], input_attr['argv'])
#     return create_dm

# @pytest.fixture(scope="class")
# def instanize_nboxapi(load_input_attributes, nbox_env):
#     global nbox
#     nbox = NboxApi(pynbox['nb'], input_attr['rc'])
#     return nbox

# @pytest.fixture(scope="class")
# def instanize_createobject(load_input_attributes, nbox_env):
#     global nbox
#     nbox = CreateObject(pynbox['nb'], input_attr['rc'])
#     return nbox

# # Fixture to to build (and teardown) test environment in Netbox
# @pytest.fixture(scope="session")
# def nbox_env(load_input_attributes):
#     import pynetbox
#     import creds
#     import operator

#     netbox_url = creds.netbox_url
#     token = creds.api_token
#     nb = pynetbox.api(url=netbox_url, token=token)
#     nb.http_session.verify = False
#     obj_exist, all_obj = ([] for i in range(2))
#     obj_id = {}
#     clstr_type = input_attr['my_vars']['test_env']['cluster_type']
#     tags = input_attr['my_vars']['cluster'][1]['vm'][0]['tags']
#     env_objects = [('virtualization.cluster_types', dict(name=clstr_type)),
#                    ('dcim.sites', dict(name=input_attr['my_vars']['test_env']['site'])),
#                    ('virtualization.clusters', dict(name=input_attr['my_vars']['cluster'][0]['name'], type=dict(name=clstr_type),
#                                                     site=dict(name=input_attr['my_vars']['test_env']['site']))),
#                    ('virtualization.clusters', dict(name=input_attr['my_vars']['cluster'][1]['name'], type=dict(name=clstr_type))),
#                    ('tenancy.tenants', dict(name=input_attr['my_vars']['cluster'][1]['vm'][0]['tenant'])),
#                    ('dcim.device_roles', dict(name=input_attr['my_vars']['cluster'][1]['vm'][0]['role'])),
#                    ('dcim.platforms', dict(name=input_attr['my_vars']['cluster'][1]['vm'][0]['platform'])),
#                    ('ipam.vlan-groups', dict(name=input_attr['my_vars']['cluster'][1]['vm'][0]['intf'][1]['grp_vl'][0])),
#                    ('ipam.vrfs', dict(name=input_attr['my_vars']['cluster'][1]['vm'][0]['intf'][3]['vrf_ip'][0])),
#                    ('ipam.vlans', input_attr['my_vars']['test_env']['vlans']),
#                    ('ipam.prefixes', input_attr['my_vars']['test_env']['prefixes']),
#                    ('virtualization.virtual_machines', dict(name=input_attr['my_vars']['cluster'][0]['vm'][0]['name'],
#                                                             cluster=dict(name=input_attr['my_vars']['cluster'][0]['name']))),
#                    ('virtualization.interfaces', input_attr['my_vars']['cluster'][0]['vm'][0]['intf'])]

#     # EXIST: If any of test environment netbox objects already exists (except VLANs, prefixes or interface) exit pytest
#     for api_attr, each_obj in env_objects:
#         if api_attr == 'ipam.vlans' or api_attr == 'ipam.prefixes' or api_attr == 'virtualization.interfaces':
#             pass
#         elif operator.attrgetter(api_attr)(nb).get(**{'name': each_obj['name']}) != None:
#             obj_exist.append(each_obj['name'])
#     if len(obj_exist) != 0:
#         pytest.exit("Can't create NetBox test environment as {} already exists".format(str(obj_exist).replace('[', '').replace(']', '')))
#     else:
#         # CREATE_OBJ: 'all_obj' is each nbox object created (used in cleanup) and 'obj_id' is ID of each object (used in test methods)
#         for api_attr, each_obj in env_objects:
#             # Create VLANs
#             if api_attr == 'ipam.vlans':
#                 vlan_ids = []
#                 for each_vl_id, each_vl_name in each_obj.items():
#                     nbox_obj = operator.attrgetter(api_attr)(nb).create(name=each_vl_name, vid=each_vl_id,
#                                                                         group=obj_id['vlan-groups'], tags=tags)
#                     vlan_ids.append(nbox_obj.id)
#                     all_obj.append(nbox_obj)
#                 obj_id[api_attr.split('.')[1]] = vlan_ids
#             # Create Prefixes
#             elif api_attr == 'ipam.prefixes':
#                 for each_prefix in each_obj:
#                     nbox_obj = operator.attrgetter(api_attr)(nb).create(prefix=each_prefix, vrf=obj_id['vrfs'], tags=tags)
#                     all_obj.append(nbox_obj)
#             # Create Interfaces (trunk, access and and IP addresses for access)
#             elif api_attr == 'virtualization.interfaces':
#                 operator.attrgetter(api_attr)(nb).create(dict(virtual_machine=obj_id['virtual_machines'], tags=tags,
#                                                               name=each_obj[1]['name'], mode='tagged', tagged_vlans=obj_id['vlans']))
#                 nbox_obj = operator.attrgetter(api_attr)(nb).create(dict(virtual_machine=obj_id['virtual_machines'], tags=tags,
#                                                                          name=each_obj[0]['name'], mode='access',
#                                                                          untagged_vlan=obj_id['vlans'][0]))
#                 obj_id['intf_access'] = nbox_obj.id
#                 nbox_obj = nb.ipam.ip_addresses.create(address=each_obj[0]['vrf_ip'][1], vrf=obj_id['vrfs'], interface=nbox_obj.id)
#             # Create all other objects
#             else:
#                 each_obj.update(dict(slug=each_obj['name'].replace(' ', '_').lower(), tags=tags))
#                 nbox_obj = operator.attrgetter(api_attr)(nb).create(each_obj)
#                 obj_id[api_attr.split('.')[1]] = nbox_obj.id
#                 all_obj.append(nbox_obj)

#     # As are two clusters creates separate dict keys, easy to work out ID as will be one less
#     obj_id['clusters'] = [obj_id['clusters'] - 1, obj_id['clusters']]

#     # Returns pynetbox object (nb) and object IDs (obj_id) to use in test methods. Yield ensures cleans up (deletes) nbox object afterwards
#     global pynbox
#     pynbox = dict(obj_id=obj_id, nb=nb)
#     yield pynbox

#     # Delete the VM if was created by test_obj_create and adds to 'all_obj' which is used to delete all objects after pytest completion
#     nbox_obj = pynbox['nb'].virtualization.virtual_machines.get(name=input_attr['my_vars']['cluster'][1]['vm'][0]['name'])
#     if nbox_obj != None:
#         all_obj.append(nbox_obj)
#     for x in reversed(all_obj):
#         x.delete()
#     # Tags are created automatically, so need to get object and delete last
#     tag_obj = nb.extras.tags.get(name=tags)
#     tag_obj.delete()     # Need to get tags object as


#     # USED TO TEMP ADD DEIVECS BUT NOT DELETE
#     # obj_id['cluster_types'] = 111
#     # obj_id['clusters'] = [111, 112]
#     # obj_id['device_roles'] = 105
#     # obj_id['intf_access'] = 812
#     # obj_id['intf_trunk'] = 811
#     # obj_id['intf_ip'] = 246
#     # obj_id['platforms'] = 94
#     # obj_id['sites'] = 107
#     # obj_id['tenants'] = 97
#     # obj_id['virtual_machines'] = 363
#     # obj_id['vlan-groups'] = 78
#     # obj_id['vlans'] = [116, 117, 118]
#     # obj_id['vrfs'] = 103


#     # global pynbox
#     # pynbox = dict(obj_id=obj_id, nb=nb)
#     # return pynbox


# # 1. Test running it all properly for createDM and NboxApI              <<<<< DONE
# # 2. Workout all the unit tests for CreateObject (all but engine)
# # 3. Get objects and hash out build to create and test CreateObject
# # 4. do  engine for both as well as main, this  is integration tests, seperate to pytests. Do as per this
# # https://stackoverflow.com/questions/54898578/how-to-keep-unit-tests-and-integrations-tests-separate-in-pytest


# # ========================================= Tests methods in CreateObject =========================================
# @pytest.mark.usefixtures("instanize_createobject")
# class TestCreateObject():

#     ### 1. Tests the creation of the VM data model
#     def test_create_vm_dm(self):
#         assert 'test' == 'test'


# # ========================================= Tests methods in NboxApi =========================================
# @pytest.mark.usefixtures("nbox_env", "instanize_nboxapi")
# class TestNboxApi():


#     ### 1. Tests the netbox creation of a new VM with all its attributes (including optional)
#     def test_obj_create(self):
#         clstr = input_attr['my_vars']['cluster'][1]['name']
#         api_attr = 'virtualization.virtual_machines'
#         vm = input_attr['my_vars']['cluster'][1]['vm'][0]
#         input_obj = dict(name=vm['name'], clstr_name=clstr, cluster=pynbox['obj_id']['clusters'][1],
#                          tenant=pynbox['obj_id']['tenants'], role=pynbox['obj_id']['device_roles'],
#                          platform=pynbox['obj_id']['platforms'], vcpus=vm['cpu'], memory= vm['mem'],
#                          disk=vm['disk'], comments=vm['comments'], tags=vm['tags'])
#         err = 'Assertion of VM creation with all VM attributes failed'
#         assert str(nbox.obj_create(vm['name'], api_attr, input_obj, [])) == "['create', {}, True]".format(vm['name']), err

#     ### 2. Tests the netbox update of an existing VM
#     def test_obj_update(self):
#         clstr = input_attr['my_vars']['cluster'][0]['name']
#         vm = input_attr['my_vars']['cluster'][0]['vm'][0]
#         nbox_obj = pynbox['nb'].virtualization.virtual_machines.get(pynbox['obj_id']['virtual_machines'])
#         #2a. Runs assertion of VM update when no VM attributes have changed, result is False
#         input_obj = {'name': vm['name'], 'clstr_name': clstr, 'cluster': pynbox['obj_id']['clusters'][0]}
#         err = 'Assertion of VM update with no changes to VM attributes failed'
#         assert str(nbox.obj_update(vm['name'], nbox_obj, input_obj, [])) == "['update', {}, False]".format(vm['name']), err
#         #2b. Runs assertion of VM update when VM attributes have changed, result is True
#         input_obj = {'name': vm['name'], 'clstr_name': clstr, 'cluster': pynbox['obj_id']['clusters'][0], 'vcpus': randint(0, 100)}
#         err = 'Assertion of VM update with changes to VM attributes failed'
#         assert str(nbox.obj_update(vm['name'], nbox_obj, input_obj, [])) == "['update', {}, True]".format(vm['name']), err

#     ### 3. Tests the netbox deletion of an existing VM (if test_obj_create not run creates VM first)
#     def test_obj_delete(self):
#         vm = input_attr['my_vars']['cluster'][1]['vm'][0]
#         nbox_obj = pynbox['nb'].virtualization.virtual_machines.get(name=vm['name'])
#         if nbox_obj == None:
#             clstr = input_attr['my_vars']['cluster'][1]['name']
#             nbox_obj = pynbox['nb'].virtualization.virtual_machines.create(dict(name=vm['name'], clstr_name=clstr,
#                                                                                 cluster=pynbox['obj_id']['clusters'][1]))
#         delete_obj = nbox.obj_delete(nbox_obj, 'test_obj_create_and_delete')
#         assert delete_obj == None, 'Assertion of VM deletion failed'
#         assert pynbox['nb'].virtualization.virtual_machines.get(name=vm['name']) == None, 'Assertion of VM deletion failed'

#     ### 3. Test getting netbox IDs of primary object and secondary object within primary object
#     def test_get_multi_id(self):
#         #3a. Runs assertion with just one object ID lookup (cluster)
#         api_attr = 'virtualization.clusters'
#         clstr = input_attr['my_vars']['cluster'][1]['name']
#         err = 'Assertion of get_multi_id with only one object failed'
#         assert nbox.get_multi_id(api_attr, clstr, 'clstr', 'site', []) == {'clstr': pynbox['obj_id']['clusters'][1]}, err
#         #3b. Runs assertion with two object ID lookup (cluster and site)
#         clstr = input_attr['my_vars']['cluster'][0]['name']
#         err = 'Assertion of get_multi_id with two objects failed'
#         assert nbox.get_multi_id(api_attr, clstr, 'clstr', 'site', []) == {'clstr': pynbox['obj_id']['clusters'][0],
#                                                                            'site': pynbox['obj_id']['sites']}, err
#     ### 4. Test getting netbox IDs of an object
#     def test_get_single_id(self):
#         vm = input_attr['my_vars']['cluster'][0]['vm'][0]
#         err = 'Assertion of get_single_id to get single netbox object ID failed'
#         assert nbox.get_single_id(vm['name'], 'tenancy.tenants', vm['tenant'], []) == pynbox['obj_id']['tenants'], err

#     ### 5. Test getting netbox IDs of an object based another objects netbox object ID
#     def test_get_single_fltr_id(self):
#         intf = input_attr['my_vars']['cluster'][0]['vm'][0]['intf'][0]
#         api_attr = 'virtualization.interfaces'
#         err = 'Assertion of get_single_fltr_id to get single netbox object ID based on another object ID failed'
#         assert nbox.get_single_fltr_id(api_attr, 'name', intf['name'], 'virtual_machine_id', pynbox['obj_id']['virtual_machines'],
#                                        intf['vrf_ip'][1], []) == pynbox['obj_id']['intf_access'], err

#     ### 6. Test getting netbox IDs of a single VLAN (access port) or a list of VLANs (trunk)
#     def test_get_vlan_id(self):
#         intf = input_attr['my_vars']['cluster'][0]['vm'][0]['intf'][0]
#         err = 'Assertion of get_vlan_id to get the object ID of a single VLAN failed'
#         assert nbox.get_vlan_id(intf['name'], intf['grp_vl'][0], intf['grp_vl'][1], []) == pynbox['obj_id']['vlans'][0], err
#         intf = input_attr['my_vars']['cluster'][0]['vm'][0]['intf'][1]
#         err = 'Assertion of get_vlan_id to get the object ID of a list of VLANs failed'
#         assert nbox.get_vlan_id(intf['name'], intf['grp_vl'][0], intf['grp_vl'][1], []) == pynbox['obj_id']['vlans'][1:], err

#     ### 7. Test that an object exists using its name or address and the container object ID it is in (like VRF)
#     def test_chk_exist(self):
#         vm = input_attr['my_vars']['cluster'][0]['vm'][0]
#         intf = input_attr['my_vars']['cluster'][0]['vm'][0]['intf'][0]
#         api_attr = 'ipam.ip_addresses'
#         err = 'Assertion of test_chk_exist using its container object ID failed'
#         assert str(nbox.chk_exist(api_attr, 'address', intf['vrf_ip'][1], 'vrf_id', pynbox['obj_id']['vrfs'],
#                               intf['vrf_ip'][0])) == intf['vrf_ip'][1], err


# # ========================================= Tests methods in CreateDM =========================================
# @pytest.mark.usefixtures("instanize_createdm")
# class TestCreateDm():

#     ### 1. Tests the creation of the VM data model
#     def test_create_vm_dm(self):
#         # 1a. Runs assertion with minimal VM attributes (only mandatory and tenant)
#         clstr = input_attr['my_vars']['cluster'][0]
#         vm = input_attr['my_vars']['cluster'][0]['vm'][0]
#         min_attr_assert = dict(name=vm['name'], clstr_name=clstr['name'], cluster=1, site=None, tenant=vm['tenant'],
#                                role=None, platform=None, vcpus=None, memory=None, disk=None, comments='', tags=[])
#         error = 'Assertion of VM DM creation with minimal VM attributes failed'
#         assert create_dm.create_vm({'clstr': 1}, clstr, vm, vm) == min_attr_assert, error
#         # 1b. Runs assertion with all VM attributes (including optional)
#         clstr = input_attr['my_vars']['cluster'][1]
#         vm = input_attr['my_vars']['cluster'][1]['vm'][0]
#         full_attr_assert = dict(name=vm['name'], clstr_name=clstr['name'], cluster=1, site=1, tenant=vm['tenant'],
#                                 role=vm['role'], platform=vm['platform'], vcpus=vm['cpu'], memory=vm['mem'],
#                                 disk=vm['disk'], comments=vm['comments'], tags=vm['tags'])
#         error = 'Assertion of VM DM creation with all VM attributes failed'
#         assert create_dm.create_vm({'clstr': 1, 'site': 1}, clstr, vm, vm) == full_attr_assert, error

#     ### 2. Tests the removal of any empty dictionary attributes (lists, dicts or None)
#     def test_remove_empty_attr(self):
#         attr_dict = dict(string='UTEST_CLSTR', integer=9, nothing=None, my_list=['a', 'b', 'c'], empty_list=[],
#                          my_dict=dict(my_dict='my_dict'), empty_dict=dict(empty_dict=None))
#         assert create_dm.rmv_empty_attr(attr_dict) == dict(string='UTEST_CLSTR', integer=9, my_dict=dict(my_dict='my_dict'),
#                                                            my_list=['a', 'b', 'c'])

#     ### 3. Tests the creation of the Interface and IP data model
#     def test_create_intf_dm(self):
#         vm = input_attr['my_vars']['cluster'][1]['vm'][0]
#         # 3f. Assertion function run for different Interface inputs
#         def assert_vm(each_intf, assert_value, error):
#             tmp_intf_dict = {}
#             if each_intf.get('grp_vl') != None: tmp_intf_dict['vlan'] = each_intf.get('grp_vl')[1]
#             if each_intf.get('vrf_ip') != None: tmp_intf_dict['vrf'] = each_intf.get('vrf_ip')[0]
#             assert create_dm.create_intf_dm(tmp_intf_dict, vm, each_intf, vm) == assert_value, error
#         # 3a. Runs assertion with interface only attributes, no VLAN or IP
#         intf = input_attr['my_vars']['cluster'][1]['vm'][0]['intf'][0]
#         intf_assert = ([dict(virtual_machine=dict(name=vm['name']), name=intf['name'], tags=intf.get('tags', []))], [])
#         assert_vm(intf, intf_assert, 'Assertion of VM INTF DM creation with no VLAN details failed')
#         # 3b. Runs assertion with access VLAN interface attributes
#         intf = input_attr['my_vars']['cluster'][1]['vm'][0]['intf'][1]
#         intf_vlan_assert = ([dict(virtual_machine=dict(name=vm['name']), name=intf['name'], tags=intf.get('tags', []),
#                                   mode='access', untagged_vlan=intf['grp_vl'][1])], [])
#         assert_vm(intf, intf_vlan_assert, 'Assertion of VM INTF DM creation with access VLAN details failed')
#         # 3c. Runs assertion with trunked VLAN interface attributes
#         intf = input_attr['my_vars']['cluster'][1]['vm'][0]['intf'][2]
#         intf_trunk_assert = ([dict(virtual_machine=dict(name=vm['name']), name=intf['name'], tags=intf.get('tags', []),
#                                    mode='tagged', tagged_vlans=intf['grp_vl'][1])], [])
#         assert_vm(intf, intf_trunk_assert, 'Assertion of VM INTF DM creation with trunked VLAN details failed')
#         # 3d. Runs assertion with secondary IP address interface attributes
#         intf = input_attr['my_vars']['cluster'][1]['vm'][0]['intf'][3]
#         intf_sec_ip_assert = ([dict(virtual_machine=dict(name=vm['name']), name=intf['name'], tags=intf.get('tags', []))],
#                               [dict(address=intf['vrf_ip'][1], tenant=vm['tenant'], vrf_name=intf['vrf_ip'][0],
#                                     vrf=intf['vrf_ip'][0], intf_name={'name': intf['name']}, dns_name=intf.get('dns', ''),
#                                     sec_ip=intf.get('secondary_ip', False), tags=intf.get('tags', []))])
#         assert_vm(intf, intf_sec_ip_assert, 'Assertion of VM INTF DM creation with secondary IP details failed')
#         # 3e. Runs assertion with primary IP address interface attributes
#         intf = input_attr['my_vars']['cluster'][1]['vm'][0]['intf'][4]
#         intf_prim_ip_assert = ([dict(virtual_machine=dict(name=vm['name']), name=intf['name'], mode='access',
#                                      untagged_vlan=10, tags=intf.get('tags', []))],
#                                [dict(address=intf['vrf_ip'][1], tenant=vm['tenant'], vrf_name=intf['vrf_ip'][0],
#                                      vrf=intf['vrf_ip'][0], intf_name={'name': intf['name']}, dns_name=intf.get('dns', ''),
#                                      sec_ip=intf.get('secondary_ip', False), tags=intf.get('tags', []))])
#         assert_vm(intf, intf_prim_ip_assert, 'Assertion of VM INTF DM creation with primary IP details failed')

#     ### 4. Tests prettifying error messages, asserts based on stdout returned to screen
#     def test_vm_error(self, capsys):
#         err = [('UTEST_VM3', {'Tenant': 'UTEST_TNT1'}, AttributeError("'NoneType' object has no attribute 'id'")),
#         ('UTEST_VM3', {'Device_role': 'UTEST_DVC_ROLE1'}, AttributeError("'NoneType' object has no attribute 'id'")),
#         ('Port1', {'Vlan_group': 'stesworl'}, TypeError("'NoneType' object is not subscriptable")),
#         ('Port1', {'Vlan': 190}, AttributeError("'NoneType' object has no attribute 'id'")),
#         ('UTEST_VM3', {'Vrf': 'HME_GLOBA'}, AttributeError("'NoneType' object has no attribute 'id'"))]
#         create_dm.vm_error('UTEST_VM3', err)
#         stdout = capsys.readouterr()
#         assert stdout.out == "❌ Virtual Machine UTEST_VM3 objects may not exist. Failed to get object.id for \n"\
#                             "- 'Tenant': 'UTEST_TNT1', 'Device_role': 'UTEST_DVC_ROLE1', 'Port1': \n"\
#                             "'Vlan_group': 'stesworl', 'Vlan': 190, 'Vrf': 'HME_GLOBA'\n"


#     # @pytest.mark.integtest
#     # def test_integration(self):
#     #    assert create_dm.engine == []


# # TEST CREATE VM DM
# # def test_dm(nbox_env):
# #     create_dm = CreateDm(None, None, nbox_env['argv'])			# Instantize the class

# #     tmp_vm = dict(tenant=nbox_env['obj_id']['tenants'], role=nbox_env['obj_id']['device_roles'], platform=nbox_env['obj_id']['platforms'])
# #     clstr_site = {'clstr': nbox_env['obj_id']['clusters'], 'site': nbox_env['obj_id']['sites']}
# #     each_clstr = nbox_env['my_vars']['cluster'][1]
# #     each_vm = nbox_env['my_vars']['cluster'][1]['vm'][0]

# #     rslt_create_dm = dict(clstr_name='UTEST_CLUSTER', cluster=clstr_site['clstr'], comments='UTEST COMMENT', disk=32, memory=2,
# #                           name='UTEST_VM', platform=tmp_vm['platform'], role=tmp_vm['role'], site=clstr_site['site'],
# #                           tags=['UTEST_TAG'], tenant=tmp_vm['tenant'], vcpus=1)

# #     assert create_dm.create_vm(clstr_site, each_clstr, each_vm, tmp_vm) == rslt_create_dm
