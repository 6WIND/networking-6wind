#    Copyright 2015 6WIND S.A.
#    All Rights Reserved.
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

import os

from fp_vdev_remote import vdev_utils

from neutron.agent.common import utils as neutron_utils

from networking_6wind.common import constants
from oslo_config import cfg

cfg.CONF.import_group('ml2_fp', 'networking_6wind.common.config')

FP_VDEV_CMD = None


def get_socket_settings():
    global FP_VDEV_CMD
    if FP_VDEV_CMD is None:
        FP_VDEV_CMD = vdev_utils.get_vdev_cmd()
    path = neutron_utils.execute(cmd=[FP_VDEV_CMD, 'get', 'sockfolder'],
                                 run_as_root=True)
    mode = neutron_utils.execute(cmd=[FP_VDEV_CMD, 'get', 'sockmode'],
                                 run_as_root=True)
    return (path.strip(), mode.strip())


def get_socket_path(socket_dir, port_id):
    if cfg.CONF.ml2_fp.vhostuser_socket_use_devname:
        vhostuser_socket_name = (constants.VHOSTUSER_SOCKET_DEVNAME_PREFIX
                                 + port_id)[:14]
    else:
        vhostuser_socket_name = constants.VHOSTUSER_SOCKET_PREFIX + port_id

    return os.path.join(socket_dir, vhostuser_socket_name)
