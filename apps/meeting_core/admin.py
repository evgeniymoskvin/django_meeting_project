from django.contrib import admin

from .models import *

# Register your models here.
admin.site.register(MeetingModel)
admin.site.register(MeetingProtocolModel)
admin.site.register(MeetingEmployeesModel)