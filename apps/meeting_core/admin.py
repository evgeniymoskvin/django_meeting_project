from django.contrib import admin

from .models import *


class MeetingAdmin(admin.ModelAdmin):
    # list_display = ("author", "text_task")
    list_display = ('title', 'created_by', 'status', 'created_at')


class MeetingProtocolAdmin(admin.ModelAdmin):
    # list_display = ("author", "text_task")
    list_display = ('title', 'meeting', 'status', 'document_date')


class MeetingEmployeesAdmin(admin.ModelAdmin):
    # list_display = ("author", "text_task")
    list_display = ('meeting', 'employee', 'created_at')


class MeetingAccessAdmin(admin.ModelAdmin):
    # list_display = ("author", "text_task")
    list_display = (
    'employee', 'meeting', 'can_play_audio', 'can_download_audio', 'can_view_transcript', 'can_view_summary',
    'can_view_protocol', 'can_edit_protocol', 'can_manage_access', 'granted_by', 'created_at')


# Register your models here.
admin.site.register(MeetingModel, MeetingAdmin)
admin.site.register(MeetingProtocolModel, MeetingProtocolAdmin)
admin.site.register(MeetingEmployeesModel, MeetingEmployeesAdmin)
admin.site.register(MeetingAccessModel, MeetingAccessAdmin)
