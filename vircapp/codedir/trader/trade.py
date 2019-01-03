#!/usr/bin/env python

import sys, time, json, logging
import os, subprocess, signal
import redis
import uuid
import utils

logging.basicConfig(format='%(asctime)s %(message)s', filename='/logs/trader.log', level=logging.NOTSET)

waittime = 1 # in seconds.

def check_bots():
    """ check if all bots are still running """
    # get all bots defined in trader:rb
    rb = {}
    for uid, bot in rds.hscan_iter("trader:rb"):
        rb[uid] = json.loads(bot)

    for uid, proc in running_bots.items():
        # check if they are running or move them in trader:hb
        if uid in rb.keys():
            try:
                os.kill(proc.pid, 0)
            except OSError:
                rds.hdel("trader:rb", uid)
                rb[uid]['status'] = "dead"
                print "%s not running. Move %s" % (proc.pid, uid)
                rds.hset("trader:hb", uid, json.dumps(rb[uid]))
        else:
            print "'%s' is not in 'trader:rb' !?" % uid
            logging.error("'%s' is not in 'trader:rb' !?" % uid) 
            running_bots.pop(uid)

    # move old bots
    for uid in rb.keys():
        if uid not in running_bots.keys():
            rds.hdel("trader:rb", uid)
            rb[uid]['status'] = "dead"
            print "Not in 'running_bots',move '%s' to trader:hb" % uid
            rds.hset("trader:hb", uid, json.dumps(rb[uid]))
    
def stop_bot(uid):
    proc = running_bots[uid]    
    utils.flash("Stopping bot '%s'" % uid, "danger")
    logging.warning("os.kill(" + str(proc.pid) + ", signal.SIGTERM)")
    os.kill(proc.pid, signal.SIGTERM)
    proc.wait()
    running_bots.pop(uid)
    
def stop_all_bots():
    for k in running_bots.keys():
        stop_bot(k)
# -----------------------------------------------
# -- init --

logging.info("Starting trader...")
running_bots = {} # {uid: proc} proc is from subprocess.Popen

rds = utils.redis_connect()

print("{} : Ready").format(str(time.ctime(int(time.time()))))
while True:
    check_bots()

    recmsg = rds.brpop("trader:build", waittime)
    if (recmsg):
        try :
            recv = json.loads(recmsg[1])
        except:
            logging.error("Message '%s' is not well formatted" % recmsg)
        else:
            new_bot_uid = str(uuid.uuid4())
            recv['uid'] = new_bot_uid
            rds.set("trader:startbot:" + new_bot_uid, json.dumps(recv))
            res = subprocess.Popen(["./simplebot.py", new_bot_uid])
            running_bots[new_bot_uid] = res
            utils.flash("Spawning %s ..." % new_bot_uid, "success")

    recmsg = rds.brpop("trader:action", waittime)
    if (recmsg):
        try :
            recv = json.loads(recmsg[1])
        except:
            print("Message is not well formatted")
        else:
            if (recv['type'] == "stop_all_bots"):
                stop_all_bots()
            elif (recv['type'] == "stop_bot"):
                stop_bot(recv['uid'])
