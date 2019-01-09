import time, json, os

from flask import Flask, render_template, redirect, flash, url_for
from flask_bootstrap import Bootstrap
from flask_sse import sse

from forms import SimpleBot, StopLossBot

import utils

rds = utils.redis_connect()

# TODO: get this in redis
pairs = os.environ['pairs'].split()

app = Flask(__name__)
Bootstrap(app)
secret_key = os.environ.get('FLASK_SECRET_KEY') or '3a9b9c9e9f432478'
app.config['SECRET_KEY'] = secret_key
app.config['REDIS_URL'] = "redis://redis"
app.config['BOOTSTRAP_SERVE_LOCAL'] = True
app.register_blueprint(sse, url_prefix='/stream')

# send data to the ticker panel
panel_tickers = []  

# --------- flash, streams, ... ---------
@app.context_processor
def inject_common_data():
    panel_tickers = []
    #tick_keys = rds.scan(match="cb:mkt:tick:*"):
    #for k in rds.scan_iter(match="cb:mkt:tick:*"):
    for k in sorted(rds.scan(match="cb:mkt:tick:*", count=100)[1]):
        pair = k.split(":")[3]
        panel_tickers.append({'name': k, 'pair': k.split(":")[-1], "price": rds.get(k)})
    return dict(panel_tickers=panel_tickers)

@app.before_request
def get_status():
    while ( rds.llen("gui:message") > 0 ):
        msg = json.loads(rds.lpop("gui:message"))
        flash(msg['data'], msg['type'])

# --------- Main Pages ---------
@app.route("/")
def root():
    tickers={}
    for k in  rds.scan_iter(match="cb:mkt:tick:*"):
      pair = k.split(":")[3]
      tickers[pair] = rds.get(k)
    print tickers
    return render_template("index.html", tickers=tickers)

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

# --------- Bot Pages ---------
@app.route("/bots")
def bots():
    newbots = [] 
    bots = [] 
    for b in rds.lrange("trader:startbot", 0, -1):
        newbots.append(json.loads(b))
    for b in rds.lrange("trader:build", 0, -1):
        newbots.append(json.loads(b))
    for k in rds.scan_iter(match = "trader:rb:*"):
        bots.append(json.loads(rds.get(k)))
    return render_template("bots.html", bots=bots, newbots=newbots)

@app.route("/bot/<uid>")
def bot(uid):
    res = rds.get("trader:rb:" + uid)
    if res is None:
        return render_template("404.html", title="<h1>Bot {} was not found</h1>".format(uid)), 404
    bot = json.loads(res)
    return render_template("bot.html", bot=bot)

@app.route("/bot_stop/<uid>", methods=["GET"])
def bot_stop(uid):
    rds.rpush("trader:action", json.dumps({"type": "stop_bot", "uid": uid}))
    return redirect(url_for("bots"))

@app.route("/bots_stopall", methods=["GET"])
def bots_stopall():
    rds.rpush("trader:action", json.dumps({"type": "stop_all_bots"}))
    return render_template("bots.html")

@app.route("/bot_new_simple", methods=["GET", "POST"])
def bot_new_simple():
    form = SimpleBot()
    form.pair.choices = [(p,p) for p in pairs]
    form.cambista.choices = []
    for k in sorted(rds.scan(match="virc:cambista:*", count=100)[1]):
        cambista_info = json.loads(rds.get(k))
        form.cambista.choices.append((k, "{} ({})".format(cambista_info['cambista_name'], cambista_info['role'])))
    if form.validate_on_submit():
        instruction1 = { 
                "side": "buy", "price": float(form.buy_at.data),
                "size": float(form.size.data), "type": "order" }
        instruction2 = { "side": "sell", "price" : float(form.sell_at.data),
                "size": float(form.size.data), "type": "order"}
        if (form.begin_sell.data):
            instructions = [ instruction2, instruction1]
        else:
            instructions = [ instruction1, instruction2 ]

        bot = {"type": "simple",
                "name": form.bot_name.data,
                "instructions_loop": form.instructions_loop.data,
                "pair": form.pair.data,
                "cambista_link": form.cambista.data,
                "cambista_title": dict(form.cambista.choices).get(form.cambista.data),
                "instructions" : instructions
              }
        rds.lpush("trader:build", str(json.dumps(bot)))
        return redirect(url_for("bots"))
    return render_template("bot_new_simple.html", form=form)

@app.route("/bot_new_stop_loss", methods=["GET", "POST"])
def bot_new_stop_loss():
    form = StopLossBot()
    form.pair.choices = [(p,p) for p in pairs]
    return render_template("bot_new_stop_loss.html", form=form)

# --------- Trade Pages ---------
@app.route("/trade_status")
def trade_status():
    return render_template("trades.html")

# --------- Conf Pages ---------
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
            bot = json.loads(rds.get(k))
            traderrb[bot['uid']] = json.dumps(bot, sort_keys = True, indent = 4, separators = (',', ': '))
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

