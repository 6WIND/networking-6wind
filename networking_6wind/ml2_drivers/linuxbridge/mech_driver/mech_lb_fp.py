#    Copyright 2015 6WIND S.A.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
from neutron_lib.api.definitions import portbindings
from neutron_lib import constants as n_constants
from neutron_lib.plugins.ml2 import api
from oslo_config import cfg
from oslo_log import log

from networking_6wind.common import constants
from networking_6wind.common.utils import get_socket_path
from neutron.plugins.ml2.drivers.linuxbridge.mech_driver import (
    mech_linuxbridge)

LOG = log.getLogger(__name__)

cfg.CONF.import_group('ml2_fp', 'networking_6wind.common.config')


class LBFPMechanismDriver(mech_linuxbridge.LinuxbridgeMechanismDriver):
    """Attach to networks using neutron-fastpath-agent L2 agent.

    The LBFPMechanismDriver integrates Ml2Plugin class with
    neutron-fastpath-agent and neutron-linuxbridge-agent.
    Port binding with this driver requires neutron-fastpath-agent and
    neutron-linuxbridge-agent to be run
    on the port's host, and these agent should have connectivity
    to at least one segment of the port's network.
    """

    def __init__(self):
        super(LBFPMechanismDriver, self).__init__()
        self.conf = cfg.CONF.ml2_fp
        self.agent_type = constants.FP_AGENT_TYPE
        self.fp_info = None

    def _get_lb_agent(self, context):
        for agent in context.host_agents(n_constants.AGENT_TYPE_LINUXBRIDGE):
            if agent.get('alive'):
                return agent
        return None

    def _need_to_bind(self, context):
        accelerated = self.conf.accelerated
        profile = context.current.get(portbindings.PROFILE)
        if profile:
            accelerated = profile.get('accelerated', self.conf.accelerated)
        if accelerated in ['True', 'true', '1', True, 1]:
            return True
        LOG.info("Refusing to bind non-accelerated port %s" %
                 context.current['id'])
        return False

    def _check_segment_for_agent(self, segment, lb_agent):
        # workaround to call check_segment_for_agent, see:
        # https://opendev.org/openstack/neutron/commit/e12580f602f81
        self.agent_type = n_constants.AGENT_TYPE_LINUXBRIDGE
        ret = self.check_segment_for_agent(segment, lb_agent)
        # restore correct value for agent_type
        self.agent_type = constants.FP_AGENT_TYPE
        return ret

    def try_to_bind_segment_for_agent(self, context, segment, agent):
        if not self._need_to_bind(context):
            return False
        lb_agent = self._get_lb_agent(context)
        if lb_agent is None:
            LOG.error("Refusing to bind port %s due to "
                      "dead neutron-linuxbridge-agent" % context.current['id'])
            return False
        # pass lb_agent, because it contains supported tunnel type in its
        # 'configurations' dict
        if not self._check_segment_for_agent(segment, lb_agent):
            return False
        LOG.debug("Trying to retrieve fp_info from %s..." % agent)
        self.fp_info = agent.get('configurations')
        if self.fp_info is None or not self.fp_info['active']:
            LOG.error("Can't retrieve fp_info")
            return False
        LOG.debug("Correctly retrieved fp_info: %s" % self.fp_info)
        if portbindings.VIF_TYPE_BRIDGE not in self.fp_info['supported_plugs']:
            LOG.error("vif_type %s is not supported in ovs-lb ML2 mechanism "
                      " driver" % portbindings.VIF_TYPE_BRIDGE)
        context.set_binding(segment[api.ID], portbindings.VIF_TYPE_VHOST_USER,
                            self.get_vif_details(context, agent, segment))
        return True

    def get_vif_details(self, context, agent, segment):
        socket_dir = self.fp_info['vhostuser_socket_dir']
        socket = get_socket_path(socket_dir, context.current['id'])
        brg = constants.BRIDGE_PREFIX + context.network.current['id']

        if self.fp_info['vhostuser_socket_mode'] == 'client':
            qemu_mode = portbindings.VHOST_USER_MODE_SERVER
        else:
            qemu_mode = portbindings.VHOST_USER_MODE_CLIENT

        details_copy = self.vif_details.copy()
        details_copy[portbindings.VHOST_USER_SOCKET] = socket
        details_copy[portbindings.VHOST_USER_MODE] = qemu_mode
        details_copy[constants.VIF_DETAILS_VHOSTUSER_FP_PLUG] = True

        # Workaroud to notify nova of bridge name to be used during
        # plug. This should not be necessary because Nova can detect
        # this bridge name, but some code is missing for the
        # VHOSTUSER_FP_PLUG case (in nova/network/neutronv2/api.py)
        details_copy[portbindings.VIF_DETAILS_BRIDGE_NAME] = brg
        return details_copy
