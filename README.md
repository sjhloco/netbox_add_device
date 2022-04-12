# NetBox Add Virtual Machine

This script will create or update virtual machines, their interfaces the IP addresses associated to the interface. There maybe a few hidden gotchas but the majority of it is kind of idempotent. The script doesn't check that every objects exists so to get meaningful outputs returned to screen it is best to only define the options that your are changing, is no need to define everything.

The VMs are defined in in a YAML file in a hierarchical structure that starts at the cluster and ends at the interface. The following variables can be defined for each VM with only a few of them being mandatory.

| Parent  | Key    | Mand | Description
|---------|--------|----------|------|------------
| cluster | `name` | Yes | The cluster all VMs below it are in
| cluster | `site` | Yes | The site that the cluster is in
| cluster/vm | `tenant` | No | The tenant the VM will be created in
| cluster/vm | `role` | No | The VM device-role
| cluster/vm | `platform` | No | The VM platform
| vm      | `name` | Yes | The VM name
| vm      | `name` | No | VM status, offline, active (default), planned, staged, failed, decommissioning
| vm      | `cpu` | No | The number of vCPUs (integer)
| vm      | `mem` | No | The amount of memory in MB  (integer)
| vm      | `disk` | No | The amount of HDD in GB  (integer)
| vm      | `comments` | No | Description for the VM
| vm      | `tags` | No | Dictionary {tag: tag_colour} of tags to assign to the VM


| Parent  | Key    | value    | Mand | Description
|---------|--------|----------|------|------------
| device_type | `name` | Yes | The device-type that the devices are grouped under
| device_type/ device | `site` | Yes | The site that the device is in
| device_type/ device | `tenant` | No | The tenant that the device is in
| device_type/ device | `device_role` | Yes | The role of the device
| device_type/ device | `platform` | No | The device platform
| device_type/ device | `cluster` | No | The cluster the device is in/ part of
| device_type/ device | `location` | No | The location of the device, MUST be the slug
| device_type/ device | `rack` | No | The rack within the location
| device | `name` | Yes | The device name
| device | `name` | No | Device status, offline, active (active), planned, staged, failed, inventory, decommissioning
| device | `position` | No | Devices position in the rack (integer)
| device | `face` | No | Front or rear facing, default is front
| device | `serial' | No | Device serial number
| device | `asset_tag' | No | Asset tag number
| device | `comments` | No | Description for the VM
| device | `tags` | No | Dictionary {tag: tag_colour} of tags to assign to the VM


virtual_chassis*	integer         x-nullable: true
vc_position	        integer         x-nullable: true
vc_priority	        integer         x-nullable: true


Interfaces are the same for VMs or devices

| Parent  | Key    | Mand | Description
|---------|--------|----------|------|------------
| intf    | `name` | Yes | Name of the interface (must be a string), is only mandatory if `intf` defined
| intf    | `grp_vl` | No | A two element list representing an access port [VLAN group, VLAN] or trunk [VLAN group, [VLAN]]
| intf    | `vrf_ip` | No | A two element list of [VRF, IPaddress/mask]
| intf    | `primary_ip` | No | By default first interface IP address is primary ip, set this to true on an other interface to overide
| intf    | `dns` | No | Domain name for the interface


If updated IP on an intefrace the original IP is  delted as if not wouldappendnew IP to interface with existing, so is only way to remove


VMs: Cluster name, Site and VM name are mandatory
Devices: Device-type name, Site, tenantm Device-role and device name are mandatory

ONLY thing that cant be inherited from cluster are cpu, mem, disk, comments
ONLY thing that cant be inherited from device-type are asset and serial numnber, comments, positin and face


- Only the Mandatory keys need to be defined
- Site is automatically automatically worked out from the cluster
- The interface must be a string, so if a integer add '' to ensure it is a string
- Defining interfaces is not mandatory, however if defined the `name` either is mandatory
- If for `grp_vl` only 1 VLAN is specified it is an untagged 'access' port, if a list of VLANs is specified it is a tagged 'trunk'
- By default IP addresses are primary, to make it non-primary add the `secondary_ip` dictionary
- To assign mulitple IPs to an interface name the interface muliple times
- If you change IP of the interface it wont delete the old IP will have to manaully do that. Reason is becaue IP is in IPAM and only associated to interface, so have to specifically say 'delete this IP address'

To run the script reference the VM variable file
`python nbox_add_device.py vms.yml`

To allow for easier reporting and rollback each VM is created or updated on a one-by-one basis so that all VM elements (VM attributes, interfaces and IP addresses) are created under the same one loop iteration. For newly created VMs if any of the element creation fails ((VM attributes, interfaces or IPs) that VM creation is  rollback by removing the VM and any objects associated with it.

The script is split into lots of different methods which are either run by the main engine method or called by one of the other supplication method. Below is a list

Methods used to check an object exists and get the objects ID which is required to create the VM.\
All methods have a catchall for unspecified errors such as token is wrong. The expected error from any call is an 'AttributeError'

***obj_create***
Creates the object based on the API URL and input list of object attributes

- obj_name: Used in the error messages to group them under the VM, interface or IP address
- api_attr: The API URL for the section this object lives under used in the API call
- input_obj: List of dictionaries which are the object attribute names and values
- error: Dictionary with the key the obj_name and the value a list of all errors created that this method appends to if the API call fails

***obj_update***
Updates the object by using the netbox initialized object and an input list of object attributes

- obj_name: Used in the error messages to group them under the VM, interface or IP address
- nbox_obj: The netbox initialized object that the update command is run against to edit that object
- input_obj: List of dictionaries which are the object attribute names and values
- error: Dictionary with the key the obj_name and the value a list of all errors created that this method appends to if the API call fails


***obj_delete***
(api_obj, task_type)


***get_multi_id***
Gets the ID of the main primary object as well as the ID of an optional secondary object based on the first object

- api_attr: The API URL for the section this object lives under used in the API call (virtualization.clusters)
- input_obj: The primary object value which the object ID is needed for (cluster name)
- input_obj_type: The primary object type used as the dict key to save the primary object ID (clstr)
- other_obj_type: The secondary object type used with the the primary object (input_obj) to get the secondary object ID (site)
- error: List of all errors created that this method appends to if the API call fails

***get_single_id***
Gets the ID of a single primary object

- vm_name: VM name is required for error messages as they are grouped into one dictionary for errors for a particular VM
- api_attr: The API URL for the section this object lives under used in the API call
- input_obj: The primary object value which the object ID is needed for
- error: Dictionary with the key the VM name and the value a list of all errors created that this method appends to if the API call fails

***get_single_fltr_id***
api_attr, input_obj_fltr, input_obj, obj_cntr_fltr, obj_cntr_id, obj_cntr_name, error)


***get_vlan_id***
Gets the VLAN group slug which is then used to get the single VLAN ID or create a list of all VLAN IDs

- intf: Interface name is required for error messages as they are grouped into one dictionary for errors for a particular interface
- vl_grp: VLAN group name that the unique VLANs are within
- vlan: VLAN name ID within the VLAN group from which the VLAN object IDs are got
- error: Dictionary with the key the interface name and the value a list of all errors created that this method appends to if the API call fails

***chk_exist***
Checks whether an objected with that name already exists (VM or IP address) within the container (cluster or VRF)

- api_attr: The API URL for the section this object lives under used in the API call
- input_obj_fltr: The attribute filter that goes in the API call, so for a VM is 'name', for a IP address is 'address'
- input_obj:  The object value which the object ID is to be got for from using the input_obj_fltr
- obj_container_fltr: The Container is where the object lives, for example a VM lives in cluster. This is the attribute filter of the container
- obj_container_id: The object ID of the container that will check if the object exists within
- obj_container_name: Container name to be used in the error messages to help identify the duplicate VM or IP address
- error: List of all errors created that this method appends to if the API finds a duplicate VM or IP address





TODO:
~~1. Create class diagram~~
1. Create function diagram
2. Create unit tests
3. Rewrite readme
4. Add validation checker using NTC
5. Design adding devices to script
6. Write tests for devices
7. Write script for devices

8. Redo create env, so refactor, draw up and add testing
9.  fix cluster-group issue, doesnt seem to be working as not added azure cluster to azure VSC cluster group



===== CREATE ERRORS =====

1. Just VM error
❌ Virtual Machine TEST vm update failed - 'TEST': 'vcpus': 'A valid integer is required.', 'memory': 'A valid integer is required.'
2. Just VM and interface error - Not applicable as wont run if VM creation failed.
3. Just Interface error with new or existing VM
❌ Virtual Machine TEST vm and interface create failed - 'eth1': 'mode': 'acces is not a valid choice.', 'eth2': 'mode': 'acces is not a valid choice.', 'Port1': 'mode': 'tagge is not a valid choice.'
4. VLAN or vlan group not exist
❌ Virtual Machine TEST interface objects may not exist. Failed to get object.id for - 'eth3': 'Vlan_group': 'stesworl'
5. IP fail if cant get interface object ID (set input_obj = 'eth5' in get_single_fltr_id)
❌ Virtual Machine TEST4 ip update failed - 'eth5(10.10.20.152/24)': AttributeError("'NoneType' object has no attribute 'id'"
6. If an address is assigned as primary cant use on another VM
❌ Virtual Machine TEST ip update failed - '10.10.20.166/24': 'IP address is primary for virtual machine TEST2 but assigned to TEST (eth5)'
7. VRF not exist for IP interface
❌ Virtual Machine TEST interface objects may not exist. Failed to get object.id for - 'eth5': 'Vrf': 'HME_BL'

===== CREATE/UPDATE just vm =====

1. Just VM create
✅ Virtual Machine TEST created with attributes: 'tenant', 'role', 'vcpus', 'memory', 'disk', 'comments', 'tags'
2. No change to VM
⚠️  Virtual Machine TEST already exists with the correct details
3. Update just VM, always shows any attributes defined, even havent been changed (shouldnt be defining them unless changing)
✅ Virtual Machine TEST updated with attributes: 'tenant', 'role', 'vcpus', 'memory', 'disk', 'comments', 'tags'

===== CREATE VM and Interface =====

1. Create VM with attributes and interface
✅ Virtual Machine TEST1 created with attributes: 'tenant', 'role', 'vcpus', 'memory', 'disk', 'comments', 'tags' interfaces: 'eth3', 'Port1'
2. No change to VM with interfaces
⚠️  Virtual Machine TEST1 already exists with the correct details

===== CREATE VM, Interface and IP =====

1. Create VM with attributes, interface and IP
✅ Virtual Machine TEST2 created with attributes: 'tenant', 'role', 'vcpus', 'memory', 'disk', 'comments', 'tags' interfaces: 'eth0', 'eth3', 'Port1' IP addresses: '10.10.20.166/24'
2. No change to VM with interfaces and IP
⚠️  Virtual Machine TEST2 already exists with the correct details

===== Add Interface and IP to existing VM =====

1. Add interface to existing VM
✅ Virtual Machine TEST updated with  interfaces: 'eth3', 'Port1'
2. Add interface with IP to existing VM
✅ Virtual Machine TEST updated with  interfaces: 'eth5' IP addresses: '10.10.20.167/24'

===== Update VM or interface =====

1. Update VM attributes but not interface
✅ Virtual Machine TEST updated with attributes: 'tenant', 'role', 'vcpus', 'memory', 'disk', 'comments', 'tags'
2. Update only interface
✅ Virtual Machine TEST updated with  interfaces: 'eth3', 'Port1'
3. Update only IP
✅ Virtual Machine TEST updated with   IP addresses: '10.10.20.169/24'
4. Update all
✅ Virtual Machine TEST4 updated with attributes: 'tenant', 'role', 'vcpus', 'memory', 'disk', 'comments', 'tags' interfaces: 'eth3' IP addresses: '10.10.20.185/24'


######## testing
Add methods out of this to my notes https://stackoverflow.com/questions/36456920/is-there-a-way-to-specify-which-pytest-tests-to-run-from-a-file

pytest -vv test/test_main.py::TestNboxApi


test_main.py

##########
write up one line if statements, can either use just if
if each_intf.get('grp_vl') != None: tmp_intf_dict['vlan'] = each_intf.get('grp_vl')[0])

or if/else
tmp_intf_dict['vlan'] = each_intf.get('grp_vl')[1] if each_intf.get('grp_vl') != None else None

https://www.codegrepper.com/code-examples/python/one+line+if+statement+python+without+else