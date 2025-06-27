# -*- coding: utf-8 -*-
"""
Module for communication with Proxmox, part of virt-who

Copyright (C) 2025 Jerry Riley <jeriley@redhat.com>

This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License
as published by the Free Software Foundation; either version 2
of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
"""

import requests
from virtwho.virt import Virt, Hypervisor, Guest, VirtError
from virtwho.config import VirtConfigSection

class ProxmoxConfigSection(VirtConfigSection):
    VIRT_TYPE = 'proxmox'
    HYPERVISOR_ID = ('uuid', 'hostname')

    def __init__(self, *args, **kwargs):
        super(ProxmoxConfigSection, self).__init__(*args, **kwargs)
        self.add_key('server', validation_method=self._validate_server, required=True)
        self.add_key('username', validation_method=self._validate_username, required=True)
        self.add_key('password', validation_method=self._validate_unencrypted_password, required=True)
        self.add_key('realm', validation_method=self._validate_non_empty_string, default='pam')

class Proxmox(Virt):
    CONFIG_TYPE = "proxmox"

    def __init__(self, logger, config, dest, terminate_event=None,
                 interval=None, oneshot=False, status=False):
        super(Proxmox, self).__init__(logger, config, dest,
                                      terminate_event=terminate_event,
                                      interval=interval,
                                      oneshot=oneshot,
                                      status=status)
        self.base_url = f"https://{self.config['server']}:8006/api2/json"
        self.username = self.config['username']
        self.password = self.config['password']
        self.realm = self.config.get('realm', 'pam')
        self.ticket = None
        self.csrf_token = None

    def authenticate(self):
        url = f"{self.base_url}/access/ticket"
        data = {
            'username': f"{self.username}@{self.realm}",
            'password': self.password
        }
        resp = requests.post(url, data=data, verify=False)
        if resp.status_code == 200:
            result = resp.json()['data']
            self.ticket = result['ticket']
            self.csrf_token = result['CSRFPreventionToken']
        else:
            raise VirtError(f"Proxmox authentication failed: {resp.text}")

    def _get_headers(self):
        if not self.ticket:
            self.authenticate()
        return {
            'Cookie': f"PVEAuthCookie={self.ticket}",
            'CSRFPreventionToken': self.csrf_token
        }

    def getHostGuestMapping(self):
        headers = self._get_headers()
        resp = requests.get(f"{self.base_url}/nodes", headers=headers, verify=False)
        if resp.status_code != 200:
            raise VirtError(f"Failed to get nodes: {resp.text}")
        nodes = resp.json()['data']

        mapping = {'hypervisors': []}
        for node in nodes:
            node_name = node['node']
            guests = []
            # KVM/QEMU VMs
            vm_resp = requests.get(f"{self.base_url}/nodes/{node_name}/qemu", headers=headers, verify=False)
            if vm_resp.status_code == 200:
                for vm in vm_resp.json()['data']:
                    guests.append(Guest(str(vm['vmid']), self.CONFIG_TYPE, Guest.STATE_RUNNING))
            # LXC containers
            lxc_resp = requests.get(f"{self.base_url}/nodes/{node_name}/lxc", headers=headers, verify=False)
            if lxc_resp.status_code == 200:
                for lxc in lxc_resp.json()['data']:
                    guests.append(Guest(str(lxc['vmid']), self.CONFIG_TYPE, Guest.STATE_RUNNING))
            # Host facts (expand as needed)
            facts = {
                Hypervisor.HYPERVISOR_TYPE_FACT: "proxmox",
                Hypervisor.SYSTEM_UUID_FACT: node.get('nodeid', node_name),
            }
            mapping['hypervisors'].append(Hypervisor(
                hypervisorId=node_name,
                guestIds=guests,
                name=node_name,
                facts=facts
            ))
        return mapping

    def statusConfirmConnection(self):
        self.authenticate()