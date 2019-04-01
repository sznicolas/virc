#from __future__ import print_function # In python 2.7
#import sys
import json
global icons 
icons = {
        "loop"     : "fas fa-redo",
        "oneshot"  : "fas fa-tasks",
        "stop"     : "fas fa-stop",
        "pause"    : "fas fa-pause",
        "close"    : "fas fa-window-close",
        "dup"      : "fas fa-edit",
        "continue" : "fas fa-play",
        "delete"   : "fas fa-trash-alt",
        "config"   : "fas fa-cog"
}

def get_cambista_choices(rds):
    res = []
    for k in sorted(rds.scan(match="virc:cambista:*", count=100)[1]):
        cambista_info = json.loads(rds.get(k))
        res.append((k, "{} ({})".format(cambista_info['name'], cambista_info['role'])))
    return res

def get_indicators(rds):
    res = {}
    for k in rds.scan(match="cb:mkt:change:*", count=100)[1]:
        pair = k.split(":")[3]
        res[pair] = json.loads(rds.get(k))
    return res

def get_indicator_choices(indicators, pair, sel1):
    ch = []
    subch = []
    if pair == "None":
        apair = indicators.keys()[0]
    else:
        apair = pair
    if sel1 == "None":
        akey = indicators[apair].keys()[0]
    else:
        akey = sel1
    for p in sorted(indicators[apair].keys()):
        if indicators[apair][p].get('title'):
            ptext = "{} {}".format(p, indicators[apair][p].get('title', p))
        else:
            ptext = p
        ch.append((p, ptext))
    for p in sorted(indicators[apair][akey].keys()):
        if ( p == 'title') :
            continue
        subch.append((p,p)) #[(p,p) for p in indicators[apair][akey].keys()]
    return ch, subch

if __name__ == "__main__":
    pass

