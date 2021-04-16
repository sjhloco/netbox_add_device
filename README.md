# NetBox Add Virtual Machine

This script will create or update virtual machines, their interfaces the IP addresses associated to the interface. There maybe a few hidden gotchas but the majority of it is kind of idempotent. The script doesn't check that every objects exists so to get meaningful outputs returned to screen it is best to only define the options that your are changing, is no need to define everything.

The VMs are defined in in a YAML file in a hierarchical structure that starts at the cluster and ends at the interface. The following variables can be defined for each VM with only a few of them being mandatory.

| Parent  | Key    | value    | Mand | Description
|---------|--------|----------|------|------------
| cluster | `name` | *string* | Yes | The cluster all VMs below it are in
| vm      | `name` | *string* | Yes | The VM name
| vm      | `tenant` | *string* | No | The tenant the VM will be created in
| vm      | `role` | *string* | No | The VM device-role
| vm      | `platform` | *string* | No | The VM platform
| vm      | `cpu` | *integer* | No | The number of vCPUs
| vm      | `mem` | *integer* | No | The amount of memory in MB
| vm      | `disk` | *integer* | No | The amount of HDD in GB
| vm      | `tags` | *list* | No | List of tags to assign to the VM
| vm      | `comments` | *string* | No | Description for the VM
| intf    | `name` | *string* | Yes | Name of the interface (must be a string), is only mandatory if `intf` defined
| intf    | `grp_vl` | *list* | No | A two element list of VLAN group and a VLAN or list of VLANs
| intf    | `vrf_ip` | *list* | No | A two element list of VRF and IP address/mask
| intf    | `secondary_ip` | *True* | No | Required if the IP address is not the VMs primary IP
| intf    | `dns` | *string* | No | Domain name for the VM

- Only the Mandatory keys need to be defined
- Site is automatically automatically worked out from the cluster
- The interface must be a string, so if a integer add '' to ensure it is a string
- Defining interfaces is not mandatory, however if defined the `name` either is mandatory
- If for `grp_vl` only 1 VLAN is specified it is an untagged 'access' port, if a list of VLANs is specified it is a tagged 'trunk'
- By default IP addresses are primary, to make it non-primary add the `secondary_ip` dictionary

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


Now need to look if can easily updatable
- Dont think is too hard to add the logic into the deployment seciton
- need to remove the warning and failfast if VM or IP exist, but use same symbol for an update
- Updating shouldnt be too hard, problme will be:
  - What happens with the default values, guess these ned removing as would rest current settings
  - How do you report on the changes made?
Loop thruhg and remove all Dicts with a None vlaue
Add validation checker using NTC

TODO:
- Add Update for VMs
- Add update for interfaces
- Add create for IPs
- add update IPs
- ~~Fix up errors with RICH~~
- ~~remove  all_results if not neededZZ


If an address is assigned as primary cant use on another VM
❌ Virtual Machine hme-win-ws019 IP address update failed - '10.10.10.50/24': 'interface': 'IP address is primary for virtual
machine hme-win-ws018 but assigned to hme-win-ws019 (eth1)'




1. add to notes, if in swapper it says 'x-nullable: true' measn you can reset the vlaue by using none
2. fix cluster-cloud issue
3. Create add device script. Hopefully will be very much same as this, need to move all the methods to external script. Update read me with details and write blog
4. refactor this to be the same as add device
5. Add pre-val check using NTC tool
6. write unit tests for these and setup env
7. combine with setup env and blog
8. refactor for newer version
