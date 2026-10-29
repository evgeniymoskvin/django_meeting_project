from django.urls import path
from . import views

app_name = "meeting_core"
urlpatterns = [

    path(
        "meeting/<uuid:pk>/access/grant/",
        views.MeetingAccessGrantView.as_view(),
        name="meeting_access_grant",
    ),
    path(
        "meeting/<uuid:pk>/access/<uuid:access_id>/revoke/",
        views.MeetingAccessRevokeView.as_view(),
        name="meeting_access_revoke",
    ),
    path(
        "meeting/<uuid:pk>/participants/add/",
        views.MeetingParticipantsAddView.as_view(),
        name="meeting_participants_add",
    ),
    path(
        "meeting/<uuid:pk>/rename/",
        views.MeetingRenameView.as_view(),
        name="meeting_rename",
    ),
]
