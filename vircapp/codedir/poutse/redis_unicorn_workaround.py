#!/usr/bin/python3

import socket
import utils

# -- init --
rds = utils.redis_connect()

max_connect_time = 3 * 60 * 60
gui_hostname = 'vircapp_gui_1.vircapp_front'
for r  in rds.client_list("pubsub"):
    if (int(r['age']) > max_connect_time)  and (gui_hostname in socket.gethostbyaddr(r['addr'].split(":")[0])):
        print("Kill :'{}'".format(r))
        rds.client_kill(r['addr'])
