import os
import platform
import locale

from django import template
from datetime import datetime, timedelta
# from apps.legacy_models.models import *

# from page_calculator_app.functions import update_date

register = template.Library()



#
# @register.simple_tag()
# def get_name(user):
#     """Получение имени сотрудника"""
#     full_user = EmployeeModel.objects.get(user=user)
#     return full_user
#
#
# @register.simple_tag()
# def get_short_name(user):
#     """Получение имени и инициалов сотрудника"""
#     full_user = EmployeeModel.objects.get(user=user)
#     return f'{full_user.last_name} {full_user.first_name[:1]}.{full_user.middle_name[:1]}'
#

@register.simple_tag()
def get_file_name(contract_str_path):
    try:
        return os.path.basename(contract_str_path.file.name)
    except:
        return f'---'


@register.filter(name='del_comma')
def del_comma(value):
    try:
        x = '{0:,}'.format(value).replace(',', ' ')
        return f'{x} ₽'
    except Exception as e:
        return '-'

@register.filter(name='replace_dot')
def del_comma(value:str):
    return str(value).replace(',','.')