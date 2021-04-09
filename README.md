# INFO

Each VM is entered as a list element under the main cluster dictionary

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
| intf    | `name` | *string* | Yes | Name of the interface
| intf    | `grp_vl` | *list* | No | 2 element list of VLAN group and a VLAN or list of VLANs
| intf    | `vrf_ip` | *list* | No | 2 element list of VRF and IP address and prefix
| intf    | `secondary_ip` | *True* | No | Add this if the IP address is not the VMs primary IP
| intf    | `dns` | *string* | No | Domain name for the VM

- Site is automatically automatically worked out from the cluster
- Only the Mandatory keys need to be defined
- If for `grp_vl` only 1 VLAN is specified it is an untagged access port, if a list of VLANs is specified it is a tagged trunk
- By default IP addresses are primary, to make it non-primary add the `secondary_ip` dictionary

The script first creates the VM, then the interfaces, then the IP addresses and finally sets the primary IP. If any of these elements for a VM fails the VM and all its elements are removed.

Methods used to check an object exists and get the objects ID which is required to create the VM.\
All methods have a catchall for unspecified errors such as token is wrong. The expected error from any call is an 'AttributeError'

***obj_create***
Creates the object based on the API URL and input list of object attributes

- obj_name: Used in the error messages to group them under the VM, interface or IP address
- api_attr: The API URL for the section this object lives under used in the API call
- input_obj: List of dictionaries which are the object attribute names and values
- all_results: Dictionary of the results used in the messages when an VM is successfully created
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