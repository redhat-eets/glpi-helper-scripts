# Use ubi9-minimal as base image
FROM redhat/ubi9-minimal

# Install dnf pkgs needed for ldap and nslookup
RUN microdnf -y install python3-pip openldap-clients bind-utils

# Set the working directory in the container
WORKDIR /usr/src/app

# Copy the requirements file into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the current directory contents into the container
COPY . .