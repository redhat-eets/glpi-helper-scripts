# glpi-helper-scripts
A repository that holds resources in support of deployments of GLPI for lab management, mainly in the form of scripting. This aims to create lightweight tooling which can be deployed to import machine information, filter reservations and machines, as well as create reservations. This tooling is higher touch but much lighter weight than a dedicated agent running on each machine. In a lab where machines are often reprovisioned/reallocated this tooling allows for tracking of equipment and the current reservation status of said equipment, allowing one to better share resources and report on usage.

> ❗ _Red Hat does not provide commercial support for the content of this repo.
Any assistance is purely on a best-effort basis, as resources permit._

```
#############################################################################
DISCLAIMER: THE CONTENT OF THIS REPO IS EXPERIMENTAL AND PROVIDED **"AS-IS"**

THE CONTENT IS PROVIDED AS REFERENCE WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
#############################################################################
```

## What is GLPI?
[GLPI](https://github.com/glpi-project/glpi) is open source asset management software that, for our needs, can be used to track inventory and reservations of computers and various sub-components. Additionally, it provides features such as ticketing systems, asset reservation, etc. 

## What does this work aim to accomplish?
This work does not exist in a vacuum, and the authors are aware of both first and third party agents, inventory gathering tools, and plugins that integrate with GLPI. However, in our lab configurations change often, machines are reallocated, and there may be restrictions on third-party software being installed. For these reasons, we chose to implement this scripting to fit our needs. For this reason the reader should also consult prior work before choosing to use this tooling.

## Prerequisites
A current version of Python is recommended to run the scripts. As of writing the minimum version to avoid warnings would be 3.7. However, the scripting has been successfully run up to version 3.11. The same is true of pip, which should be a current version (23.0 as of writing, but this should be upgraded in the following steps).

Running the script from a python3 virtual environment is recommended (note that the Python version of your venv can differ from the default Python path, if desired). Install the required python modules as follows, demonstrated for Python 3.11:

```
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Importing machine(s) into GLPI
The `population/create...`  scripts handle creating a computer and updating fields in a GLPI deployment. For more specific usage information use the help message provided by the scripts.

### RHEL, CentOS, and Fedora workflow (Directly on Target CLI):
![alt text](/docs/images/GLPI-Direct-REST.png)

NOTE: This approach must have direct CLI access to the target server, the ability to host this code on the target, and may need sudo on the target
1. Copy the repository to the server to be imported.
2. Ensure you have the following Python requirements installed:
    - Python3
    - pip3
    - All packages listed in `requirements.txt` (you can install them by running `pip3 install -r requirements.txt` in your terminal)
3. Ensure you have the following operating system requirements installed:
    - lshw
    - hostnamectl
    - dmidecode
    - lscpu
    - uname
    - ifconfig
    - parted
4. Run the script either with sudo or as a root user. Pass in the GLPI API token, general configuration, as well as the IP address of the GLPI instance.
    - The API token is available from the Administration/Users, in the "Remote access keys" section of a specific user.
    - An example of the general configuration YAML specifying a mapping of processing accelerator device ID to the name field of Processing Accelerators is as follows:
```
ACCELERATOR_IDS:
  '0d5c': 
    'ACC100' 
  '0d8f': 
    'N3000'
```
    - Optionally, pass in a switch configuration in the following format:
```
LAB:                     # lab name
  switches:
    IP:                  # IP address
      name: switch_name  # switch name
      location: location # location
      username: username # username
      password: password # password
      type: type         # type of switch (currently supports dell or cumulus)

      # Will result in {'lab': {'switches': {'ip': {'name: 'switch_name', 'location': 'location', 'username': 'username', 'password': 'password', type: 'type'}, {'ip_2':...}}}

```
    - For additional usage options see the help option of the script.
6. If the script was run successfully, go to the GLPI URL and ensure that fields were correctly populated.
    - The script by default will not overwrite any unique names given to the target. Pass in the "-o" flag to overwrite with the default hostname.
7. If desired, manually set the location, technician, group, status, and any other desired fields for this machine, as these fields may help with identification or reporting later.
8. If there was previously information populated, check fields are remove redundant information if present(for example, in the 'Components' section one may need "Unspecified" memory if previously populated). This has been specifically noticed as a remnant of running the Redfish based script, and one work around is currently to simply remove the machine if populating it a second time.

### OS Agnostic, IPMI and Redfish based workflow (Remote):
![alt text](/docs/images/GLPI-Remote-REST.png)

NOTE: Useful for importing many machines sequentially, and those that do not have direct CLI access/an OS installed or do not wish to have the code/to install dependencies on the target machine.
1. Create a list of machines to populate in the following format (see `population/redfish_list_example` in this repository for a further example):
    IPMI_IP,IPMI_USERNAME,IPMI_PASSWORD,PUBLIC_IP,LAB
2. Ensure you have the following Python requirements installed:
    - Python3
    - pip3
    - All packages listed in `requirements.txt` (you can install them by running `pip3 install -r requirements.txt` in your terminal)
3. Call the `population/create_computer_redfish.py` script, passing in the GLPI API token to `-t`, the URL of your GLPI instance to `-i`, and the list from step 1. to `-m`. If you would like to use a custom name for a machine instead of relying on DNS, pass in your custom name to `-n`. If you would like to use the service tag / SKU for Dell Machines rather than the serial number, use `-s`. NOTE: You can also add a machine's details via the `--ipmi_ip`, `--ipmi_user`, `--ipmi_pass`, `--public_ip`, and `--lab` flags. This machine will be imported along with any machines you've passed in via `-m`. For other options see the script's help message.
4. Continue from step 6. of the RHEL, CentOS, Fedora workflow section above.

### CoreOS Workflow (Directly on Target CLI):
![alt text](/docs/images/GLPI-Remote-SSH-REST.png)

NOTE: All OpenShift nodes must be accessible via SSH using a key. 
1. Copy the repository to the jump host which can access the OpenShift nodes.
2. Ensure you have the following Python requirements installed:
    - Python3
    - pip3
    - All packages listed in `requirements.txt` (you can install them by running `pip3 install -r requirements.txt` in your terminal)
3. Run the script with sudo. Pass in the GLPI IP, GLPI API token, username of the user to SSH into, and IP address of the server. Optionally, pass in the SSH key and switch configuration, if necessary/desired. For further usage see the script's help message.
4. Continue from step 6. of the "RHEL, CentOS, Fedora Workflow" section above.

### Additional options for lab managers:
1. Authorize reservations for the machine, if desired and applicable.
2. From the reservations menu, reserve the machine for the applicable user, start date, duration, and add the work item identifier (e.g. Jira epic number) in the comments field (e.g. JIRA_PROJECT-0000). See also Managing Reservations below.

## Updating Switch Ports (Cumulus or Dell):
A script, `population/update_switch_ports.py`, is provided to query the MAC address tables on switches and populate these ports in GLPI. This script requires passing in the GLPI IP address, the GLPI API token, and the switch config YAML (see examples above).

### Recommended workflow:
1. Populate the switches into GLPI by hand, if not present. Fill in fields such as the name (critical for switch mapping using the switch config YAML), serial number, etc.
2. Call the `population/update_switch_ports.py` script, passing in the GLPI IP address, the GLPI API token, and the switch config.
3. If the script was run successfully, go to the GLPI URL and ensure that fields were correctly populated.

## Managing Reservations:
There are scripts included which will help query reservations of machines from, and add reservations to, GLPI.

Before using them, ensure that you have installed all packages listed in `requirements.txt`, by running `pip3 install -r requirements.txt` in your terminal.

### check_glpi_reservation.py
The `filtering/check_glpi_reservation.py` script queries the GLPI deployment for reservations and prints a digest including the reservation id, user id, username, computer id, computer name, beginning time, end time, and comment (which would be the work item identifier per the best practice above, or whatever was populated in the comment field). For usage information see the help message provided by the script.

### check_glpi_computers.py
The `filtering/check_glpi_reservation.py` script queries the GLPI deployment for computers and prints a digest of computer fields. For usage information see the help message provided by the script.

### create_reservation_wrapper.py
This is the recommended workflow for creating reservations using the REST API. One has the ability to manually manage reservations via the GUI (fine for an individual machine or to view the calendar), but for convenience there is an included wrapper around `reservation/create_glpi_reservation.py` which can take in a YAML file defining reservations of machines. The wrapper takes in the API token as well as the reservation YAML file. Required for proper function are the username for which to reserve the machine, start and end time in "YYYY-MM-DD HH:MM:SS" format, and servers by identifier. You can optionally include a Jira Epic, which will be included as a comment if specified. The global comment field will be added to the comment field below the Jira Epic tag if specified (omitted if set to None). If a server contains None (~) then it will use the global fields, otherwise they will be overwritten for that specific machine. Below is an explanation of the required YAML structure (also see `reservation/reservation_example.yaml`):
<pre>
username:example_user
start:"2021-09-30 23:59:59"
end:"2021-10-30 23:59:59"
epic: "JIRA-0000"                  # (optional)
comment:~                          # (optional)
servers:
  identifier-1:                    # identifier in GLPI (i.e. serial number, service tag, or hostname)
    ~
  identifier-2:                    # identifier in GLPI (i.e. serial number, service tag, or hostname)
    username:overwritten_username  # (optional) override user
    start:"2021-10-01 23:59:59"    # (optional) override start
    end:"2021-10-31 23:59:59"      # (optional) override end
    epic: "JIRA-0001"              # (optional) override Jira Epic, if defined above
    comment:"a comment"            # (optional) override comment, if defined above
</pre>
For usage information see the help message provided by the script.

### create_glpi_reservation.py
The `reservation/create_glpi_reservation.py` script attempts to create a reservation in the GLPI deployment for a given username, computer name, beginning time, end time, Jira epic number and optional comment. For usage information see the help message provided by the script.

### filter_computers.py
The `filtering/filter_computers.py` script will filter computers in a GLPI instance based on resource requirements, and whether they are currently reservable and/or reserved. For usage information see the help message provided by the script. Note that `filtering/requirements_example.yaml` is an example YAML file for filtering, demonstrating the fields available:
```
0:
  cpu: 1                     # cpus
  cores: 4                   # cores
  ram: 200000                # MB
  disks:
    - disk_type: nvme        # type
      storage: 500           # MB
    - disk_type: nvme        # type: scsi, nvme
      storage: 10            # MB
  start: 2021-10-01 00:00:00 # YYYY-MM-DD HH-MM-SS
  end: 2021-10-04 00:00:00   # YYYY-MM-DD HH-MM-SS
1:
  cpu: 1                     # cpus
  cores: 4                   # cores
  ram: 16000                 # MB
  gpu: 'ASPEED'              # GPU name
  nic: 'XL710'               # NIC name
  disks:                     # Total disks
    - storage: 500000        # MB
      disk_type: 'scsi'      # type: scsi, nvme
  start: 2022-09-01 17:00:00 # YYYY-MM-DD HH-MM-SS
  end: 2022-10-04 00:00:00   # YYYY-MM-DD HH-MM-SS
2:
  cpu: 2                     # cpus
  cores: 16                  # cores
  ram: 128000                # MB
  disks:
    - storage: 500           # MB
  start: 2021-10-01 00:00:00 # YYYY-MM-DD HH-MM-SS
  end: 2021-10-04 00:00:00   # YYYY-MM-DD HH-MM-SS
3:
  cpu: 2                     # cpus
  cores: 36                  # cores
  ram: 128000                # MB
  disks:
    - storage: 500           # MB
  start: 2021-10-01 00:00:00 # YYYY-MM-DD HH-MM-SS
  end: 2021-10-04 00:00:00   # YYYY-MM-DD HH-MM-SS
```

### filter_reservations_by_project.py
The `filtering/filter_reservations_by_project.py` will filter the reservations in GLPI by project (JIRA tag in the comment field), returning all projects with the corresponding tag. For usage information use the help message provided by the script.

## Integrations

### integrations/sunbird/compare_sunbird_with_glpi.py
The `integrations/sunbird/compare_sunbird_with_glpi.py` script compares all machines in GLPI with all machines in Sunbird located in the labs specified by a user-provided YAML file. It returns a list of machines that are in GLPI, but not Sunbird, and vice versa.

Example script usage: 

`python3 compare_sunbird_with_glpi.py -i <GLPI URL> -t <GLPI API TOKEN> -v -g <path to YAML file> -u <Sunbird USERNAME> -p <Sunbird PASSWORD> -s <Sunbird URL>`

You can also email the output of this script to someone via optional flags:

`python3 compare_sunbird_with_glpi.py -i <GLPI URL> -t <GLPI API TOKEN> -v -g <path to YAML file> -u <Sunbird USERNAME> -p <Sunbird PASSWORD> -s <Sunbird URL> -r <RECIPIENT EMAIL> -S <SENDER EMAIL> -e <EMAIL SERVER>`

### integrations/ldap/compare_ldap_with_glpi.py
The `integrations/ldap/compare_ldap_with_glpi.py` script compares the LDAP groups specified in a user-provided YAML file to the groups in GLPI. It then adds any missing users to the relevant GLPI group. There is an example YAML file in the `integrations/ldap` folder. The script assumes that you have the `ldapsearch` CLI tool installed. You can install it with `dnf install openldap-clients`

Example script usage:
`python3 compare_ldap_with_glpi.py -i <GLPI URL> -t <GLPI API TOKEN> -v -c <path to YAML file> -l <LDAP server> -b <Base DN>`

## Utilities

### utilities/tag_unreservable_machines.py
NOTE: This script requires the "[Tag Management](https://github.com/pluginsGLPI/tag)" plugin.

This script tags all unreservable machines with a specified tag.

Example script usage:
`python3 tag_unreservable_machines.py -i <GLPI URL> -t <GLPI API TOKEN> -v -n <TAG NAME>`
