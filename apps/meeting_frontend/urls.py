from django.urls import path
from . import views


app_name = "meeting_frontend"
urlpatterns = [

    path('', views.NewRecordingView.as_view(), name='recording_page'),
    path('meeteng/<str:pk>', views.MeetingDetailView.as_view(), name='meeting_detail'),
]
