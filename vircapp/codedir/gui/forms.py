from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, BooleanField, SelectField, DecimalField
from wtforms.validators import DataRequired, NumberRange, InputRequired


class OrderBot(FlaskForm):
    bot_name = StringField('Bot name', validators=[InputRequired()])
    pair = SelectField('Pair')
    instructions_loop = BooleanField('Loop')
    #sim_mode = BooleanField('Simulation mode')
    cambista = SelectField('Cambista')
    begin_sell = BooleanField('Begin at sell step')
    buy_at = DecimalField('Buy at', id='f_buy_at', places=2, validators=[InputRequired()])
    sell_at = DecimalField('Sell at', id='f_sell_at', places=2, validators=[InputRequired(), NumberRange(min=0)])
    size = DecimalField("Size", places=8, id='f_size', validators=[InputRequired(), NumberRange(min=0)])
    submit = SubmitField('Create and run')

class StopLossBot(FlaskForm):
    bot_name = StringField('Bot name', validators=[InputRequired()])
    bypair = BooleanField('By Pair')
    pair   = SelectField('Pair')
    bybot  = BooleanField('By Bot') 
    submit = SubmitField('Create and run')

