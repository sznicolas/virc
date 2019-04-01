from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, BooleanField, SelectField, DecimalField, RadioField, HiddenField
from wtforms.validators import DataRequired, NumberRange, InputRequired


class BotHeader(FlaskForm):
    bot_name = StringField('Bot name', validators=[InputRequired()])
    pair = SelectField('Pair')
    cambista = SelectField('Cambista')
    submit = SubmitField('Create and run')

class OrderBot(BotHeader):
    instructions_loop = BooleanField('Loop')
    #sim_mode = BooleanField('Simulation mode')
    begin_sell = BooleanField('Begin at sell step')
    buy_at = DecimalField('Buy at', id='f_buy_at', places=2, validators=[InputRequired()])
    sell_at = DecimalField('Sell at', id='f_sell_at', places=2, validators=[InputRequired(), NumberRange(min=0)])
    size = DecimalField("Size", places=8, id='f_size', validators=[InputRequired(), NumberRange(min=0)])

class StopLossBot(BotHeader):
    bypair = BooleanField('By Pair')
    bybot  = BooleanField('By Bot') 

class CondBot(BotHeader):
    instructions_loop = BooleanField('Loop')
    
    cond1_sel1     = SelectField("cond1_sel1")
    subcond1_sel1  = SelectField("subcond1_sel1")
    cond1_op1      = SelectField("cond1_op1")
    cond1_arg2type = RadioField('type', choices=[('select', 'select'), ('input', 'input')], default="select")
    cond1_sel2     = SelectField("cond1_sel2")
    subcond1_sel2  = SelectField("subcond1_sel2")
    cond1_input    = StringField("val")

    cond2_sel1     = SelectField("cond2_sel1")
    subcond2_sel1  = SelectField("subcond2_sel1")
    cond2_op1      = SelectField("cond2_op1")
    cond2_arg2type = RadioField('type', choices=[('select', 'select'), ('input', 'input')], default="select")
    cond2_sel2     = SelectField("cond2_sel2")
    subcond2_sel2  = SelectField("subcond2_sel2")
    cond2_input    = StringField("val")

    side1  = RadioField('Side', choices=[('buy','buy'),('sell','sell')])
    size1  = DecimalField("Size", places=6, id='f_size', validators=[InputRequired(), NumberRange(min=0)])
    price1 = DecimalField("Mkt price (+/- nn.nn)", places=6, id='f_price')


    cond3_sel1     = SelectField("cond3_sel1")
    subcond3_sel1  = SelectField("subcond3_sel1")
    cond3_op1      = SelectField("cond3_op1")
    cond3_arg2type = RadioField('type', choices=[('select', 'select'), ('input', 'input')], default="select")
    cond3_sel2     = SelectField("cond3_sel2")
    subcond3_sel2  = SelectField("subcond3_sel2")
    cond3_input    = StringField("val")

    cond4_sel1     = SelectField("cond4_sel1")
    subcond4_sel1  = SelectField("subcond4_sel1")
    cond4_op1      = SelectField("cond4_op1")
    cond4_arg2type = RadioField('type', choices=[('select', 'select'), ('input', 'input')], default="select")
    cond4_sel2     = SelectField("cond4_sel2")
    subcond4_sel2  = SelectField("subcond4_sel2")
    cond4_input    = StringField("val")

    side2  = RadioField('Side', choices=[('buy','buy'),('sell','sell')])
    size2  = DecimalField("Size", places=6, id='f_size', validators=[InputRequired(), NumberRange(min=0)])
    price2 = DecimalField("Mkt price (+/- nn.nn)", places=6, id='f_price')

