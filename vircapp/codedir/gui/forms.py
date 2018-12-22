from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, BooleanField, SelectField, DecimalField
from wtforms.validators import DataRequired, NumberRange, InputRequired


class SimpleBot(FlaskForm):
    bot_name = StringField('Bot name', validators=[InputRequired()])
    pair = SelectField('Pair')
    instructions_loop = BooleanField('Loop')
    sim_mode = BooleanField('Simulation mode')
    begin_sell = BooleanField('Begin at sell step')
    buy_val = DecimalField('Buy at', places=2, validators=[NumberRange(min=0)])
    sell_val = DecimalField('Sell at', places=2, validators=[InputRequired(), NumberRange(min=0)])
    size = DecimalField("Size", places=2, validators=[InputRequired(), NumberRange(min=0)])
    submit = SubmitField('Create and run')
