from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, BooleanField, SelectField, DecimalField
from wtforms.validators import DataRequired, NumberRange, InputRequired


class BotHeader(FlaskForm):
    bot_name = StringField('Bot name', validators=[InputRequired()])
    pair = SelectField('Pair')
    submit = SubmitField('Create and run')

class OrderBot(BotHeader):
    instructions_loop = BooleanField('Loop')
    #sim_mode = BooleanField('Simulation mode')
    cambista = SelectField('Cambista')
    begin_sell = BooleanField('Begin at sell step')
    buy_at = DecimalField('Buy at', id='f_buy_at', places=2, validators=[InputRequired()])
    sell_at = DecimalField('Sell at', id='f_sell_at', places=2, validators=[InputRequired(), NumberRange(min=0)])
    size = DecimalField("Size", places=8, id='f_size', validators=[InputRequired(), NumberRange(min=0)])

class StopLossBot(BotHeader):
    bypair = BooleanField('By Pair')
    bybot  = BooleanField('By Bot') 

class CondBot(OrderBot):
    cond1_sel1 = SelectField("cond1_sel1")
    cond1_sel2 = SelectField("cond1_sel2")
    cond1_op1  = SelectField("cond1_op1")
    cond1_sel3  = SelectField("cond1_sel3")
    cond1_sel4  = SelectField("cond1_sel4")
