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
if __name__ == "__main__":
    pass

