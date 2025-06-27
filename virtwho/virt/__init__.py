# -*- coding: utf-8 -*-
from __future__ import print_function, absolute_import


from .virt import (
    Virt, VirtError, Guest, AbstractVirtReport, DomainListReport,
    HostGuestAssociationReport, ErrorReport, StatusReport,
    Hypervisor, DestinationThread, IntervalThread, info_to_destination_class
)

from .proxmox.proxmox import Proxmox, ProxmoxConfigSection

__all__ = [
    'Virt', 'VirtError', 'Guest', 'AbstractVirtReport',
    'DomainListReport', 'HostGuestAssociationReport',
    'StatusReport', 'ErrorReport', 'Hypervisor',
    'DestinationThread', 'IntervalThread',
    'info_to_destination_class'
]

VIRT_BACKENDS = {
    'proxmox': Proxmox,
}
VIRT_CONFIG_SECTIONS = {
    'proxmox': ProxmoxConfigSection,
}