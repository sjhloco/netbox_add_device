# NetBox - Add Virtual Machine or Device

Creates or updates virtual machines or devices as well as the the interfaces and IP addresses associated to those interface. There maybe a few hidden gotchas but the majority of it is kind of idempotent. The script doesn't check that every objects exists so to get meaningful outputs returned to screen it is best to only define the options that your are changing, is no need to define everything.

## Input yaml file

VMs and devices are defined in a hierarchically structured YAML file that starts at either the *clusters* (VMs) or *devices-types* (devices) and ends at the interface. Within the file you can define cluster (VMs), device-types (devices) or both.

- The majority of the attributes are optional, with a few of the higher level being mandatory
- Some of the attributes can be defined under the cluster or device-type to use them for all VMs or devices (can be overridden on a per-vm or pre-device basis)
- For physical devices if the location is specified it MUST be the location slug (all other attributes use names)
- Defining interfaces is not mandatory, however if defined the *name* is mandatory and must be a string (use '' to make integers a string)
- For Layer2 interfaces if only 1 VLAN is specified it is an untagged *'access'* port, if a list of VLANs is specified it is a tagged *'trunk'*
- For Layer3 interfaces by default the first IP address is the primary IP, this can be overridden using *primary_ip*
- If an interface IP address is updated the original IP will be deleted

#### Virtual Machine attributes

| Parent  | Key    | Mand | Description
|---------|--------|------|-------------
| cluster | `name` | Yes | The cluster that all VMs under it are in
| cluster | `site` | Yes | The site that the cluster is in
| cluster/vm | `tenant` | No | The tenant the VM will be created in
| cluster/vm | `role` | No | The VM device-role
| cluster/vm | `platform` | No | The VM platform
| vm      | `name` | Yes | The VM name
| vm      | `status` | No | VM status, default is active
| vm      | `cpu` | No | The number of vCPUs (integer)
| vm      | `mem` | No | The amount of memory in MB (integer)
| vm      | `disk` | No | The amount of HDD in GB (integer)
| vm      | `comments` | No | Description for the VM
| vm      | `tags` | No | Dictionary *{tag: tag_colour}* of tags to assign to the VM

#### Device attributes

| Parent  | Key    | Mand | Description
|---------|--------|------|-------------
| device_type | `name` | Yes | The device-type that the devices are grouped under
| device_type/device | `site` | Yes | The site that the device is in
| device_type/device | `tenant` | No | The tenant that the device is in
| device_type/device | `device_role` | Yes | The role of the device
| device_type/device | `platform` | No | The device platform
| device_type/device | `cluster` | No | The cluster the device is part of
| device_type/device | `location` | No | The location of the device, ***MUST be the slug***
| device_type/device | `rack` | No | The rack within the location
| device | `name` | Yes | The device name
| device | `name` | No | Device status, default is active
| device | `position` | No | Devices position in the rack (integer)
| device | `face` | No | Front or rear facing, default is front
| device | `serial` | No | Device serial number
| device | `asset_tag` | No | Asset tag number
| device | `comments` | No | Description for the VM
| device | `tags` | No | Dictionary *{tag: tag_colour}* of tags to assign to the VM
| device | `virtual_chassis` | No | Virtual chassis in format *{vc_name: [vc_position, vc_priority]}*

#### Virtual Machine/ Device attributes

Interfaces are the same for VMs or devices except for *type* which only applies to physical device interfaces. It type is not specified it will either use the existing interface type (includes those defined in the device-type) or for new interfaces default to *virtual*.

| Parent  | Key    | Mand | Description
|---------|--------|------|-------------
| intf    | `name` | Yes | Name of the interface (must be a string), is only mandatory if `intf` defined
| intf    | `grp_vl` | No | A two element list representing an access port *[VLAN group, VLAN]* or trunk *[VLAN group, [VLAN]]*
| intf    | `vrf_ip` | No | A two element list of *[VRF, IP/mask]*
| intf    | `primary_ip` | No | By default first interface IP address is primary ip, set this to true on an other interface to override
| intf    | `dns` | No | Domain name for the interface
| intf    | `descr` | No | Description for the interface
| intf    | `type` | No | Only needed on device interfaces. If not specified and a new interface will default to *virtual*
| intf    | `lag` | No | Name of of the LAG this interface is a member of

## Installation and Prerequisites

Clone the repository and create a virtual environment.

```css
git clone https://github.com/sjhloco/netbox_add_device
python -m venv ~/venv/nbox/
source ~/venv/nbox1/bin/activate
```

Install all required the python packages into the virtual environment.

```bash
pip install -r requirements.txt
```

The token and NetBox API URL is set in a separate config.py variable file that I *.gitignore* so as not to share with the rest of the world. This is imported with import config so you either need to add this file or remove the import line and add the token and URL directly in the script. All that config.py holds is a single token variable:

```bash
netbox_url = "http://10.30.10.104:8000/"
api_token = 'my_token_got_from_netbox'
```

SSL checking can be disabled or the SSL CA cert location defined if using HTTPS with a self-signed certificate.

```bash
ssl = False
os.environ['REQUESTS_CA_BUNDLE'] = '/Users/user1/Documents/nbox_py_scripts/myCA.pem'
```

## Usage

To allow for easier reporting and rollback each VM is created or updated on a one-by-one basis so that all VM elements (VM attributes, interfaces and IP addresses) are created under the same loop iteration. For newly created VMs if any of the element creation fails ((VM attributes, interfaces or IPs) that VM creation is rollback by removing the VM.

```bash
python nbox_add_device.py input_file.yml
```

There are three possible outcomes from the attempt to create each object which are relayed back in stdout:\
✅ VM or device created or updated\
⚠️ VM or device already exists in the desired state\
❌ Object can’t be created or updated because of the returned error or the cluster/device-type is not defined

![run_example_video](https://user-images.githubusercontent.com/33333983/163674996-87ace222-a460-4d79-bcd5-b2a03a4b87c4.gif)
