import pytest

from nbox_add_device import CreateDm				# importing a class
# from main import test_csv				<<< importing a function



# If using Self-signed cert must have been signed by a CA (can all be done on same box in opnessl) and this points to that CA cert



############################ INZT_LOAD: Opens netbox connection and loads the variable file ############################

# Tests can be independent functions or methods group under a class

# Fixture is run everytime pytest run to create variables from input file
@pytest.fixture(scope="session", autouse=True)
def load_input_attributes():
    import os
    import yaml
    from rich.console import Console
    from rich.theme import Theme

    rc = Console(theme=Theme({"repr.str": "black italic", "repr.ipv4": "black italic", "repr.number": "black italic"}))
    argv = [None, os.path.join(os.path.dirname(__file__), 'test_files', 'test_yms.yml')]
    with open(argv[1], 'r') as file_content:
        my_vars = yaml.load(file_content, Loader=yaml.FullLoader)
    global input_attr
    input_attr = dict(argv=argv, my_vars=my_vars, rc=rc)

# Fixtures to instanize the class that is being tested by the associated pytest class
@pytest.fixture(scope="class", autouse=True)
def instanize_createdm(load_input_attributes):
    global create_dm
    create_dm = CreateDm(None, input_attr['rc'], input_attr['argv'])
    return create_dm

# @pytest.fixture
# def nbox_env():
#     import pynetbox
#     from pynetbox.core.query import RequestError
#     import ast
#     import yaml
#     import creds
#     import operator
#     import os
#     from rich.console import Console

#     netbox_url = creds.netbox_url
#     token = creds.api_token
#     os.environ['REQUESTS_CA_BUNDLE'] = os.path.expanduser('~/Documents/Coding/Netbox/nbox_py_scripts/myCA.pem')
#     rc = Console()


#     nb = pynetbox.api(url=netbox_url, token=token)
#     argv = [None, os.path.join(os.path.dirname(__file__), 'test_files', 'test_yms.yml')]
#     with open(argv[1], 'r') as file_content:
#         my_vars = yaml.load(file_content, Loader=yaml.FullLoader)

#     env_objects = [('virtualization.cluster_types', my_vars['test_env']['cluster_type']),
#                    ('virtualization.clusters', my_vars['test_env']['cluster']),
#                    ('tenancy.tenants', my_vars['test_env']['tenant']),
#                    ('dcim.sites', my_vars['test_env']['site']),
#                    ('dcim.device_roles', my_vars['test_env']['role']),
#                    ('dcim.platforms', my_vars['test_env']['platform']),
#                    ('ipam.vrfs', my_vars['test_env']['vrf']),
#                    ('ipam.vlan-groups', my_vars['test_env']['grp_vl']),
#                    ]

# #   nbox.obj_check('VLAN Group', 'ipam.vlan-groups', 'name', ipam['vlan_grp'])
# #     nbox.obj_check('VRF', 'ipam.vrfs', 'name', ipam['vrf'])


#     obj_exist, all_obj = ([] for i in range(2))
#     obj_id = {}
#     for api_attr, each_obj in env_objects:
#         if operator.attrgetter(api_attr)(nb).get(**{'name': each_obj}) != None:
#             obj_exist.append(each_obj)

#     if len(obj_exist) != 0:
#         rc.print(":x: Can't create NetBox test environment as [i red]{}[/i red] already exists".
#                  format(str(obj_exist).replace('[', '').replace(']', '')))
#         # exit()
#     # The obj_id dict created holds all the NetBox object IDs that can be used in the calls
#     else:
#         for api_attr, each_obj in env_objects:
#             if api_attr == 'virtualization.clusters':
#                 nbox_obj = operator.attrgetter(api_attr)(nb).create(name=each_obj, type=dict(name=my_vars['test_env']['cluster_type']), slug=each_obj.replace(' ', '_').lower())
#                 obj_id[api_attr.split('.')[1]] = nbox_obj.id
#                 all_obj.append(nbox_obj)
#             else:
#                 nbox_obj = operator.attrgetter(api_attr)(nb).create(name=each_obj, slug=each_obj.replace(' ', '_').lower())
#                 obj_id[api_attr.split('.')[1]] = nbox_obj.id
#                 all_obj.append(nbox_obj)


#     yield dict(argv=argv, my_vars=my_vars, obj_id=obj_id, nb=nb)
#     for x in reversed(all_obj):
#         x.delete()



# tmp_vm = {'tenant': 20, 'role': 34}
#  clstr_site = {'clstr': 20, 'site': 33}

# 1. Do final vm_create test with assert based on stdout
# 2. Test NboxApi, is no engine for this, just functions
# 3. test CreateObject, do all but the engine
# 4. do  engine for both as well as main, this  is integration tests, seperate to pytests. Do as per this
# https://stackoverflow.com/questions/54898578/how-to-keep-unit-tests-and-integrations-tests-separate-in-pytest


# ========================================= Tests methods in CreateDM =========================================
@pytest.mark.usefixtures("instanize_createdm")
class TestCreateDm():

    ### 1. Tests the creation of the VM data model
    def test_create_vm_dm(self):
        # 1c. Assertion function run for different VM inputs
        def assert_vm(each_vm, clstr_site, assert_value, error):
            each_clstr = input_attr['my_vars']['cluster'][0]
            assert create_dm.create_vm(clstr_site, each_clstr, each_vm, each_vm) == assert_value, error
        # 1a. Runs assertion with minimal VM attributes (only mandatory)
        min_attr_vm = input_attr['my_vars']['cluster'][0]['vm'][0]
        min_attr_assert = dict(name='UTEST_VM1', clstr_name='UTEST_CLSTR', cluster=1, site=None, tenant=None, role=None,
                            platform=None, vcpus=None, memory=None, disk=None, comments='', tags=[])
        assert_vm(min_attr_vm, {'clstr': 1}, min_attr_assert, 'Assertion of VM DM creation with minimal VM attributes failed')
        # 1b. Runs assertion with all VM attributes (including optional)
        full_attr_vm = input_attr['my_vars']['cluster'][0]['vm'][1]
        full_attr_assert = dict(name='UTEST_VM2', clstr_name='UTEST_CLSTR', cluster=1, site=1, tenant='UTEST_TNT', role='UTEST_DVC_ROLE',
                                platform='UTEST_PLTFM', vcpus=1, memory=2, disk=32, comments='COMMENT', tags=['UTEST_TAG'])
        assert_vm(full_attr_vm, {'clstr': 1, 'site': 1}, full_attr_assert, 'Assertion of VM DM creation with all VM attributes failed')

    ### 2. Tests the removal of any empty dictionary attributes (lists, dicts or None)
    def test_remove_empty_attr(self):
        attr_dict = dict(string='UTEST_CLSTR', integer=9, nothing=None, my_list=['a', 'b', 'c'], empty_list=[],
                        my_dict=dict(my_dict='my_dict'), empty_dict=dict(empty_dict=None))
        assert create_dm.rmv_empty_attr(attr_dict) == dict(string='UTEST_CLSTR', integer=9, my_dict=dict(my_dict='my_dict'),
                                                            my_list=['a', 'b', 'c'])

    ### 3. Tests the creation of the Interface and IP data model
    def test_create_intf_dm(self):
        vm = input_attr['my_vars']['cluster'][0]['vm'][1]

        # 3f. Assertion function run for different Interface inputs
        def assert_vm(each_intf, assert_value, error):
            tmp_intf_dict = {}
            if each_intf.get('grp_vl') != None: tmp_intf_dict['vlan'] = each_intf.get('grp_vl')[1]
            if each_intf.get('vrf_ip') != None: tmp_intf_dict['vrf'] = each_intf.get('vrf_ip')[0]
            assert create_dm.create_intf_dm(tmp_intf_dict, vm, each_intf, vm) == assert_value, error
        # 3a. Runs assertion with interface only attributes, no VLAN or IP
        intf = input_attr['my_vars']['cluster'][0]['vm'][1]['intf'][0]
        assert_value = ([dict(virtual_machine=dict(name='UTEST_VM2'), name='eth0', tags=[])], [])
        assert_vm(intf, assert_value, 'Assertion of VM INTF DM creation with no VLAN details failed')
        # 3b. Runs assertion with access VLAN interface attributes
        intf = input_attr['my_vars']['cluster'][0]['vm'][1]['intf'][1]
        assert_value = ([dict(virtual_machine=dict(name='UTEST_VM2'), name='eth1', tags=['access_port'],
                        mode='access', untagged_vlan=10)], [])
        assert_vm(intf, assert_value, 'Assertion of VM INTF DM creation with access VLAN details failed')
        # 3c. Runs assertion with trunked VLAN interface attributes
        intf = input_attr['my_vars']['cluster'][0]['vm'][1]['intf'][2]
        assert_value = ([dict(virtual_machine=dict(name='UTEST_VM2'), name='eth2', tags=[], mode='tagged',
                            tagged_vlans=[10,20,30])], [])
        assert_vm(intf, assert_value, 'Assertion of VM INTF DM creation with trunked VLAN details failed')
        # 3d. Runs assertion with secondary IP address interface attributes
        intf = input_attr['my_vars']['cluster'][0]['vm'][1]['intf'][3]
        assert_value = ([dict(virtual_machine=dict(name='UTEST_VM2'), name='eth3', tags=[])],
                                            [dict(address='99.99.99.202/24', tenant='UTEST_TNT', vrf_name='UTEST_VRF',
                                                vrf='UTEST_VRF', intf_name={'name': 'eth3'}, dns_name='',
                                                sec_ip=True, tags=[])])
        assert_vm(intf, assert_value, 'Assertion of VM INTF DM creation with secondary IP details failed')
        # 3e. Runs assertion with primary IP address interface attributes
        intf = input_attr['my_vars']['cluster'][0]['vm'][1]['intf'][4]
        assert_value = ([dict(virtual_machine=dict(name='UTEST_VM2'), name='eth4', mode='access', untagged_vlan=10, tags=['mgmt_ip'])],
                                            [dict(address='99.99.99.201/24', tenant='UTEST_TNT', vrf_name='UTEST_VRF',
                                                vrf='UTEST_VRF', intf_name={'name': 'eth4'}, dns_name='mob-win-ws01.utest.com',
                                                sec_ip=False, tags=['mgmt_ip'])])
        assert_vm(intf, assert_value, 'Assertion of VM INTF DM creation with primary IP details failed')

    ### 4. Tests prettifying error messages, asserts based on stdout returned to screen
    def test_vm_error(self, capsys):
        err = [('UTEST_VM3', {'Tenant': 'UTEST_TNT1'}, AttributeError("'NoneType' object has no attribute 'id'")),
        ('UTEST_VM3', {'Device_role': 'UTEST_DVC_ROLE1'}, AttributeError("'NoneType' object has no attribute 'id'")),
        ('Port1', {'Vlan_group': 'stesworl'}, TypeError("'NoneType' object is not subscriptable")),
        ('Port1', {'Vlan': 190}, AttributeError("'NoneType' object has no attribute 'id'")),
        ('UTEST_VM3', {'Vrf': 'HME_GLOBA'}, AttributeError("'NoneType' object has no attribute 'id'"))]
        create_dm.vm_error('UTEST_VM3', err)
        stdout = capsys.readouterr()
        assert stdout.out == "❌ Virtual Machine UTEST_VM3 objects may not exist. Failed to get object.id for \n"\
                            "- 'Tenant': 'UTEST_TNT1', 'Device_role': 'UTEST_DVC_ROLE1', 'Port1': \n"\
                            "'Vlan_group': 'stesworl', 'Vlan': 190, 'Vrf': 'HME_GLOBA'\n"


    # @pytest.mark.integtest
    # def test_integration(self):
    #    assert create_dm.engine == []


    #





# TEST CREATE VM DM
# def test_dm(nbox_env):
#     create_dm = CreateDm(None, None, nbox_env['argv'])			# Instantize the class

#     tmp_vm = dict(tenant=nbox_env['obj_id']['tenants'], role=nbox_env['obj_id']['device_roles'], platform=nbox_env['obj_id']['platforms'])
#     clstr_site = {'clstr': nbox_env['obj_id']['clusters'], 'site': nbox_env['obj_id']['sites']}
#     each_clstr = nbox_env['my_vars']['cluster'][0]
#     each_vm = nbox_env['my_vars']['cluster'][0]['vm'][0]

#     rslt_create_dm = dict(clstr_name='UTEST_CLUSTER', cluster=clstr_site['clstr'], comments='UTEST COMMENT', disk=32, memory=2,
#                           name='UTEST_VM', platform=tmp_vm['platform'], role=tmp_vm['role'], site=clstr_site['site'],
#                           tags=['UTEST_TAG'], tenant=tmp_vm['tenant'], vcpus=1)

#     assert create_dm.create_vm(clstr_site, each_clstr, each_vm, tmp_vm) == rslt_create_dm
