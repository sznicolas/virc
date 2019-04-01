import time, json, os, glob
import collections

from flask import Flask, render_template, redirect, flash, url_for, request, jsonify, send_from_directory
from flask_bootstrap import Bootstrap
from flask_sse import sse

from forms import OrderBot, StopLossBot, CondBot

import utils
from guiutils import *

rds = utils.redis_connect()

# TODO: get this in redis
pairs = os.environ['pairs'].split()
graph_path = os.environ['GRAPHPATH']

app = Flask(__name__)
Bootstrap(app)
secret_key = os.environ.get('FLASK_SECRET_KEY') or '3a9b9c9e9f432478'
app.config['SECRET_KEY'] = secret_key
app.config['REDIS_URL'] = "redis://redis"
app.config['BOOTSTRAP_SERVE_LOCAL'] = True
app.config['CUSTOM_STATIC_PATH'] = graph_path 
app.register_blueprint(sse, url_prefix='/stream')

# send data to the ticker panel
panel_tickers = []  

# for ext. generated images
@app.route('/cstat/<path:filename>')
def custom_static(filename):
    return send_from_directory(app.config['CUSTOM_STATIC_PATH'], filename)

# --------- flash, streams, ... ---------
@app.context_processor
def inject_common_data():
    ''' sends ticker, and icons global var to all templates '''
    panel_tickers = []
    for k in sorted(rds.scan(match="cb:mkt:tick:*", count=100)[1]):
        pair = k.split(":")[-1]
        panel_tickers.append({'name': k, 'pair': pair, "price": rds.get(k)})
    return dict(panel_tickers=panel_tickers, icons=icons)

@app.before_request
def get_status():
    for m in  rds.scan_iter(match="gui:message:*"):
        jmsg = rds.get(m)
        if (jmsg is None):
            continue
        msg = json.loads(jmsg)
        rds.delete(m)
        flash(msg['data'], msg['type'])
        rds.publish("virc:pubsub", jmsg)

# --------- Main Pages ---------
@app.route("/")
def root():
    tickers={}
    for k in  rds.scan_iter(match="cb:mkt:tick:*"):
      pair = k.split(":")[3]
      tickers[pair] = rds.get(k)
    return render_template("index.html", tickers=tickers, graph_path=graph_path)

@app.route("/graphs/<pair>", methods=["GET"])
def graphs(pair):
    divs = ""
    scripts = ""
    for divfile in sorted(glob.glob("{}/{}*.div".format(graph_path, pair))):
        with open(divfile) as f:
            divs += f.read()
    for scriptfile in sorted(glob.glob("{}/{}*.script".format(graph_path, pair))):
        with open(scriptfile) as f:
            scripts += f.read()
    return render_template("graphs.html", pair=pair, divs=divs, scripts=scripts)

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

# --------- Bot Pages ---------
@app.route("/bots")
def bots():
    newbots = [] 
    bots = [] 
    histbots=[]
    for b in rds.lrange("trader:startbot", 0, -1):
        newbots.append(json.loads(b))
    for b in rds.lrange("trader:build", 0, -1):
        newbots.append(json.loads(b))
    for k in rds.scan_iter(match = "trader:rb:*"):
        bots.append(json.loads(rds.get(k)))
    for k in rds.scan_iter(match = "trader:hb:*"):
        histbots.append(json.loads(rds.get(k)))
    return render_template("bots/index.html", bots=bots, newbots=newbots, histbots=histbots)

@app.route("/bot/<uid>")
def bot2(uid):
    res = rds.get("trader:rb:" + uid)
    if res is None:
        res = rds.get("trader:hb:" + uid)
        if res is None:
            return render_template("404.html", title="<h1>Bot {} was not found</h1>".format(uid)), 404
    bot = json.loads(res)
    return render_template("bots/bot.html", bot=bot)

@app.route("/bot_stop/<uid>", methods=["GET"])
def bot_stop(uid):
    rds.rpush("trader:action", json.dumps({"type": "stop_bot", "uid": uid}))
    return redirect(url_for("bots"))

@app.route("/bot_pause/<uid>", methods=["GET"])
def bot_pause(uid):
    rds.rpush("trader:action", json.dumps({"type": "pause_bot", "uid": uid}))
    return redirect(url_for("bots"))

@app.route("/bots_stopall", methods=["GET"])
def bots_stopall():
    rds.rpush("trader:action", json.dumps({"type": "stop_all_bots"}))
    return render_template("bots.html")

@app.route("/bot_dup/<uid>", methods=["GET", "POST"])
def bot_dup(uid):
    # get bot data
    bot = rds.get("trader:rb:" + uid)
    if bot is None:
        bot = rds.get("trader:hb:" + uid)
        if bot is None:
            return "Bot's uid '%s' found neither in trader:rb: nor trader:hb" % uid
    bot = json.loads(bot)
    # get bot type
    if (bot['type'] == "orderbot"):
        form = OrderBot()
        form.cambista.choices = []
        # TODO: Put pre-fill in Form constructor
        form.pair.choices = [(p,p) for p in pairs]
        form.cambista.choices = get_cambista_choices(rds)
        if form.validate_on_submit():
            create_orderbot(form)
            return redirect(url_for("bots"))
        form.bot_name.data = bot['name']
        form.pair.data = bot['instruction_book']['pair']
        form.instructions_loop.data = bot['instruction_book']['loop']
        form.cambista.data = bot['cambista_link']
        form.size.data = bot['instruction_book']["instructions"][0]["size"]
        if (bot['instruction_book']["instructions"][0]['side'] == "sell"): 
            form.sell_at.data = bot['instruction_book']["instructions"][0]['price'] 
            form.buy_at.data = bot['instruction_book']["instructions"][1]['price'] 
        else:
            form.buy_at.data = bot['instruction_book']["instructions"][0]['price'] 
            form.sell_at.data = bot['instruction_book']["instructions"][1]['price'] 
    else:
        return("Sorry, type {} not implemented yet.".format(bot['type'])) 
    return render_template("bots/new_orderbot.html", form=form)

@app.route("/bot_continue/<uid>", methods=["GET", "POST"])
def bot_continue(uid):
    try:
        bot = json.loads(rds.get("trader:hb:" + uid))
        rds.rename("trader:hb:" + uid, "archive:hb:" + uid)
    except:
        return "Bot " + uid + " not found"
    rds.lpush("trader:build", str(json.dumps(bot)))
    return redirect(request.referrer)

# ------ new bots 
@app.route("/bot/new_orderbot", methods=["GET", "POST"])
def new_orderbot():
    form = OrderBot()
    form.pair.choices = [(p,p) for p in pairs]
    form.cambista.choices = get_cambista_choices(rds)
    if form.validate_on_submit():
        create_orderbot(form)
        return redirect(url_for("bots"))
    if form.errors:
        flash(form.errors, "danger")
    return render_template("bots/new_orderbot.html", form=form)

@app.route("/bot/new_condbot", methods=["GET", "POST"])
def new_condbot():
    form = CondBot()
    form.pair.choices = [(p,p) for p in pairs]
    indicators = get_indicators(rds)
    form.cambista.choices = get_cambista_choices(rds)

    choices, subchoices = get_indicator_choices(indicators, form.pair.data, form.cond1_sel1.data)
    form.cond1_sel1.choices = choices
    form.subcond1_sel1.choices = subchoices
    form.cond1_op1.choices = [("==", "=="), (">=", ">="), ("<=", "<=")]
    choices, subchoices = get_indicator_choices(indicators, form.pair.data, form.cond1_sel2.data)
    form.cond1_sel2.choices = choices
    form.subcond1_sel2.choices = subchoices
    choices, subchoices = get_indicator_choices(indicators, form.pair.data, form.cond2_sel1.data)
    form.cond2_sel1.choices = choices
    form.subcond2_sel1.choices = subchoices
    form.cond2_op1.choices = [("==", "=="), (">=", ">="), ("<=", "<=")]
    choices, subchoices = get_indicator_choices(indicators, form.pair.data, form.cond2_sel2.data)
    form.cond2_sel2.choices = choices
    form.subcond2_sel2.choices = subchoices

    choices, subchoices = get_indicator_choices(indicators, form.pair.data, form.cond3_sel1.data)
    form.cond3_sel1.choices = choices
    form.subcond3_sel1.choices = subchoices
    form.cond3_op1.choices = [("==", "=="), (">=", ">="), ("<=", "<=")]
    choices, subchoices = get_indicator_choices(indicators, form.pair.data, form.cond3_sel2.data)
    form.cond3_sel2.choices = choices
    form.subcond3_sel2.choices = subchoices
    choices, subchoices = get_indicator_choices(indicators, form.pair.data, form.cond4_sel1.data)
    form.cond4_sel1.choices = choices
    form.subcond4_sel1.choices = subchoices
    form.cond4_op1.choices = [("==", "=="), (">=", ">="), ("<=", "<=")]
    choices, subchoices = get_indicator_choices(indicators, form.pair.data, form.cond4_sel2.data)
    form.cond4_sel2.choices = choices
    form.subcond4_sel2.choices = subchoices

    if form.validate_on_submit():
        bot = {"type": "condbot",
                "name": form.bot_name.data,
                "cambista_link": form.cambista.data}
        #if (form.cond1_arg2type
        bot["instruction_book"] = {
                "loop": form.instructions_loop.data,
                "pair": form.pair.data,
                "instructions" : []
            }
        jsdata = collections.defaultdict(dict)
        jsdata[form.cond1_sel1.data][form.subcond1_sel1.data] = None
        jsdata[form.cond2_sel1.data][form.subcond2_sel1.data] = None
        if (form.cond1_arg2type.data == 'input'):
            cond1_data2 = form.cond1_input.data
        else:
            jsdata[form.cond1_sel2.data][form.subcond1_sel2.data] = None
            cond1_data2 ={'var': "{}.{}".format(form.cond1_sel2.data, form.subcond1_sel2.data)}
        if (form.cond2_arg2type.data == 'input'):
            cond2_data2 = form.cond2_input.data
        else:
            jsdata[form.cond2_sel2.data][form.subcond2_sel2.data] = None
            cond2_data2 ={'var': "{}.{}".format(form.cond2_sel2.data, form.subcond2_sel2.data)}
        rules = { "and" : 
            [ 
                { form.cond1_op1.data: 
                    [ {'var': "{}.{}".format(form.cond1_sel1.data, form.subcond1_sel1.data) }
                    , cond1_data2 ]
                },
                { form.cond2_op1.data: 
                    [ {'var': "{}.{}".format(form.cond2_sel1.data, form.subcond2_sel1.data) }
                    , cond2_data2 ]
                }
            ] 
            }
        bot["instruction_book"]['instructions'].append({'type': 'conditionnal', 'data': jsdata, 'rules': rules})

        instruction = { "side": form.side1.data, "price" : "mkt:" + '{0:+f}'.format(form.price1.data),
                "size": float(form.size1.data), "type": "order_var"}
        bot["instruction_book"]['instructions'].append(instruction)

        jsdata = collections.defaultdict(dict)
        jsdata[form.cond3_sel1.data][form.subcond3_sel1.data] = None
        jsdata[form.cond4_sel1.data][form.subcond4_sel1.data] = None
        if (form.cond3_arg2type.data == 'input'):
            cond3_data2 = form.cond3_input.data
        else:
            jsdata[form.cond3_sel2.data][form.subcond3_sel2.data] = None
            cond3_data2 ={'var': "{}.{}".format(form.cond3_sel2.data, form.subcond3_sel2.data)}
        if (form.cond4_arg2type.data == 'input'):
            cond4_data2 = form.cond4_input.data
        else:
            jsdata[form.cond4_sel2.data][form.subcond4_sel2.data] = None
            cond4_data2 ={'var': "{}.{}".format(form.cond4_sel2.data, form.subcond4_sel2.data)}
        rules = { "and" : 
            [ 
                { form.cond3_op1.data: 
                    [ {'var': "{}.{}".format(form.cond3_sel1.data, form.subcond3_sel1.data) }
                    , cond3_data2 ]
                },
                { form.cond4_op1.data: 
                    [ {'var': "{}.{}".format(form.cond4_sel1.data, form.subcond4_sel1.data) }
                    , cond4_data2 ]
                }
            ] 
          }
        bot["instruction_book"]['instructions'].append({'type': 'conditionnal', 'data': jsdata, 'rules': rules})

        instruction = { "side": form.side2.data, "price" : "mkt:" +  '{0:+f}'.format(form.price2.data),
                "size": float(form.size2.data), "type": "order_var"}
        bot["instruction_book"]['instructions'].append(instruction)
        
        rds.lpush("trader:build", str(json.dumps(bot)))
        return redirect(url_for("bots"))
    if form.errors:
        flash(form.errors, "danger")
    return render_template("bots/new_condbot.html", form=form, indicators=json.dumps(indicators, sort_keys=True)) 

@app.route("/new_stop_loss", methods=["GET", "POST"])
def new_stop_loss():
    form = StopLossBot()
    form.pair.choices = [(p,p) for p in pairs]
    return render_template("bots/new_stop_loss.html", form=form)

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
    traderhb = {}
    # redis unknown keys
    redisdata = []
    orderbook_sim=[]

    for k in rds.keys("*"):
        rdstype = rds.type(k)
        # Messages implemented in template
        if ( k.startswith("cb:mkt:change:")):
            changes.append({'name': k, 'pair': k.split(":")[-1], "value": json.loads(rds.get(k))})
        elif (k.startswith("cb:mkt:tick")):
#        if (k.startswith("cb:mkt:tick")):
            tickers.append({'name': k, 'pair': k.split(":")[-1], "price": rds.get(k)})
        elif k.startswith("trader:rb"):
            bot = json.loads(rds.get(k))
            traderrb[bot['uid']] =  {
                    'name': bot['name'],
                    'data': json.dumps(bot, sort_keys = True, indent = 4, separators = (',', ': ')) }
        elif k.startswith("trader:hb"):
            bot = json.loads(rds.get(k))
            traderhb[bot['uid']] =  {
                    'name': bot['name'],
                    'data': json.dumps(bot, sort_keys = True, indent = 4, separators = (',', ': ')) }
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

    return render_template("redis.html", redisdata=redisdata, changes=changes, tickers=tickers, traderrb=traderrb, traderhb=traderhb, orderbook_sim=orderbook_sim)

@app.route("/redis_del/<key>")
def redis_del(key):
    rds.delete(key)
    utils.flash("deleted '%s'" % key,'danger')
    return redirect(request.referrer) #url_for("redis_ls"))


# ------------- functions --------
def create_orderbot(form):
    bot = {"type": "orderbot",
            "name": form.bot_name.data,
            "cambista_link": form.cambista.data}
    instruction1 = { 
            "side": "buy", "price": float(form.buy_at.data),
            "size": float(form.size.data), "type": "order" }
    instruction2 = { "side": "sell", "price" : float(form.sell_at.data),
            "size": float(form.size.data), "type": "order"}
    if (form.begin_sell.data):
        instructions = [ instruction2, instruction1]
    else:
        instructions = [ instruction1, instruction2 ]
    bot["instruction_book"] = {
            "loop": form.instructions_loop.data,
            "pair": form.pair.data,
            "instructions" : instructions
        }
    rds.lpush("trader:build", str(json.dumps(bot)))

# -- filters
@app.template_filter('pjsonlogic') 
def pjsonlogic(d,txt=""):
  for k,v in d.items():
    if type(v) is list:
        if type(v[0]) is dict:
            txt = pjsonlogic(v[0], txt)
        else:
            txt+=v[0]
        txt += " " + k + " "
        if type(v[1]) is dict:
            txt = pjsonlogic(v[1], txt)
        else:
            txt+=v[1]
    else:
        txt+=v
  return txt
