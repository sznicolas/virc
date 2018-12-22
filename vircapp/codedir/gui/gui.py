import time, json, os

from flask import Flask, render_template, redirect, flash, url_for
from flask_bootstrap import Bootstrap
from flask_sse import sse

from forms import SimpleBot

import utils

rds = utils.redis_connect()

# TODO: get this in redis
pairs = os.environ['pairs'].split()

app = Flask(__name__)
Bootstrap(app)
secret_key = os.environ.get('FLASK_SECRET_KEY') or '3a9b9c9e9f432478'
app.config['SECRET_KEY'] = secret_key
app.config['REDIS_URL'] = "redis://redis"
app.register_blueprint(sse, url_prefix='/stream')


@app.before_request
def get_status():
    while ( rds.llen("gui:message") > 0 ):
        msg = json.loads(rds.lpop("gui:message"))
        flash(msg['data'], msg['type'])

@app.route("/")
def root():
    tickers={}
    for k in  rds.scan_iter(match="cb:mkt:tick:*"):
      pair = k.split(":")[3]
      tickers[pair] = rds.get(k)
    print tickers
    return render_template("index.html", tickers=tickers)

@app.route("/bots")
def bots():
    newbots = [] 
    bots = [] 
    for b in rds.lrange("trader:startbot", 0, -1):
        newbots.append(json.loads(b))
    for b in rds.lrange("trader:build", 0, -1):
        newbots.append(json.loads(b))
    for k, b in rds.hscan_iter("trader:rb"):
        bots.append(json.loads(b))
    return render_template("bots.html", bots=bots, newbots=newbots)

@app.route("/bot/<uid>")
def bot(uid):
    bot   = json.loads(rds.hget("trader:rb",  uid))
    ihist=[]
    for h in rds.lrange("trader:hist:" + uid, 0, -1):
        ihist.append(json.loads(h))
    return render_template("bot.html", bot=bot, instructions_history=ihist)

@app.route("/bot_stop/<uid>", methods=["GET"])
def bot_stop(uid):
    rds.rpush("trader:action", json.dumps({"type": "stop_bot", "uid": uid}))
    return redirect(url_for("bots"))

@app.route("/bots_stopall", methods=["GET"])
def bots_stopall():
    rds.rpush("trader:action", json.dumps({"type": "stop_all_bots"}))
    return render_template("bots.html")

@app.route("/bots_new_simple", methods=["GET", "POST"])
def bots_new_simple():
    form = SimpleBot()
    form.pair.choices = [(p,p) for p in pairs]
    if form.validate_on_submit():
        instruction1 = { 
                "side": "buy", "price": float(form.buy_val.data),
                "size": float(form.size.data), "type": "order" }
        instruction2 = { "side": "sell", "price" : float(form.sell_val.data),
                "size": float(form.size.data), "type": "order"}
        if (form.begin_sell.data):
            instructions = [ instruction2, instruction1]
        else:
            instructions = [ instruction1, instruction2 ]

        bot = {"type": "simple",
                "name": form.bot_name.data,
                "instructions_loop": form.instructions_loop.data,
                "pair": form.pair.data,
                "sim_mode": form.sim_mode.data,
                "instructions" : instructions
              }
        rds.lpush("trader:build", str(json.dumps(bot)))
        return redirect(url_for("bots"))
    return render_template("bots_new_simple.html", form=form)

@app.route("/trade_status")
def trade_status():
    return render_template("trades.html")

@app.route("/redis")
def redis_ls():
    # redis known keys
    changes = []
    tickers=[]
    traderrb = {}
    # redis unknown keys
    redisdata = []
    orderbook_sim=[]

    for k in rds.keys("*"):
        rdstype = rds.type(k)
        # Messages implemented in template
        if ( k.startswith("cb:mkt:change:")):
            changes.append({'name': k, 'pair': k.split(":")[-1], "value": json.loads(rds.get(k))})
        elif (k.startswith("cb:mkt:tick")):
            tickers.append({'name': k, 'pair': k.split(":")[-1], "price": rds.get(k)})
        elif k.startswith("trader:rb"):
            for k, v in rds.hscan_iter("trader:rb"):
                traderrb[k] = json.dumps(json.loads(v), sort_keys = True, indent = 4, separators = (',', ': '))
        elif (k == "cambisim:orderbook"):
            orderbook_sim = json.loads(rds.get(k))
        # Other messages
        else:
            if (rdstype == 'string'):
                redisdata.append({'name': k, 'value': rds.get(k), 'type':rdstype })
            elif (rdstype == 'hash'): 
                redisdata.append({'name': k, 'value' : rds.hgetall(k), 'type': rdstype})
            elif (rdstype == 'list'): 
                redisdata.append({'name': k, 'value' : rds.lrange(k, 0, -1), 'type': rdstype})

    return render_template("redis.html", redisdata=redisdata, changes=changes, tickers=tickers, traderrb=traderrb, orderbook_sim=orderbook_sim)

@app.route("/redis_del/<key>")
def redis_del(key):
    rds.delete(key)
    utils.flash("deleted '%s'" % key,'danger')
    return redirect(url_for("redis_ls"))

